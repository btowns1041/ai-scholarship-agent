"""Claude-powered scholarship matching, scoring, and structured extraction."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")


class UserProfile(BaseModel):
    full_name: str | None = None
    major: str = "Undeclared"
    gpa: float = Field(default=0.0, ge=0, le=4.0)
    degree: str = "Undergraduate"
    year: str | None = None
    demographics: str | None = None
    interests: str | None = None
    citizenship: str | None = None
    state: str | None = None
    financial_need: bool = False


class ScholarshipEvaluation(BaseModel):
    title: str
    provider: str | None = None
    award_amount: str | None = None
    award_amount_value: float = 0
    deadline: str | None = None
    url: str | None = None
    eligibility_summary: str
    match_score: int = Field(ge=0, le=100)
    ai_rationale: str

    @field_validator("match_score", mode="before")
    @classmethod
    def clamp_score(cls, value: Any) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (TypeError, ValueError):
            return 0


SYSTEM_PROMPT = """You are an expert scholarship matching analyst.
Evaluate how well a scholarship fits a student profile.

Rules:
- Return ONLY valid JSON (no markdown fences).
- Parse messy listing text into clean fields.
- match_score is an integer 0-100 based on eligibility alignment:
  major/field fit, GPA, degree level, demographics, citizenship, interests, and deadline practicality.
- Penalize clear mismatches (wrong degree level, citizenship, gender-only awards the student cannot use).
- Reward strong alignment (first-gen, STEM/AI/cyber, GPA above minimums).
- eligibility_summary: 1-2 sentences of who can apply.
- ai_rationale: 2-3 sentences explaining the score, including any gaps.
- deadline: ISO date YYYY-MM-DD when possible, else original text.
- award_amount: human-readable (e.g. "$10,000").
- award_amount_value: numeric dollars, 0 if unknown.

JSON schema:
{
  "title": string,
  "provider": string|null,
  "award_amount": string|null,
  "award_amount_value": number,
  "deadline": string|null,
  "url": string|null,
  "eligibility_summary": string,
  "match_score": number,
  "ai_rationale": string
}
"""


def evaluate_scholarship(
    profile: dict[str, Any] | UserProfile,
    raw: dict[str, Any],
) -> ScholarshipEvaluation:
    profile_model = profile if isinstance(profile, UserProfile) else UserProfile.model_validate(profile)

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            return _evaluate_with_claude(profile_model, raw, api_key)
        except Exception as exc:
            logger.warning("Claude evaluation failed, using heuristic fallback: %s", exc)
    return _heuristic_evaluate(profile_model, raw)


def evaluate_many(
    profile: dict[str, Any] | UserProfile,
    items: list[dict[str, Any]],
) -> list[ScholarshipEvaluation]:
    return [evaluate_scholarship(profile, item) for item in items]


def _evaluate_with_claude(
    profile: UserProfile, raw: dict[str, Any], api_key: str
) -> ScholarshipEvaluation:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    user_payload = {
        "user_profile": profile.model_dump(),
        "scholarship": raw,
    }
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            }
        ],
    )
    text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    data = _extract_json(text)
    data.setdefault("url", raw.get("url"))
    data.setdefault("title", raw.get("title"))
    return ScholarshipEvaluation.model_validate(data)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _heuristic_evaluate(profile: UserProfile, raw: dict[str, Any]) -> ScholarshipEvaluation:
    blob = " ".join(
        str(raw.get(k) or "")
        for k in ("title", "provider", "raw_text", "award_amount", "deadline", "eligibility_summary")
    ).lower()
    title = (raw.get("title") or "Untitled scholarship").strip()
    score = 45
    reasons: list[str] = []

    major_tokens = _tokens(profile.major) | _tokens(profile.interests)
    hits = [tok for tok in major_tokens if tok in blob]
    if hits:
        score += min(30, 8 * len(set(hits)))
        reasons.append(f"Field overlap on {', '.join(sorted(set(hits))[:4])}.")
    elif any(word in blob for word in ("any major", "all majors", "unrestricted")):
        score += 10
        reasons.append("Open to any major.")
    else:
        score -= 8
        reasons.append("Major/interest alignment is limited.")

    if profile.gpa >= 3.7:
        score += 10
        reasons.append(f"GPA {profile.gpa} is competitive.")
    elif profile.gpa >= 3.3:
        score += 5
    if re.search(r"gpa\s*(of\s*)?(3\.[5-9]|4\.0)", blob) and profile.gpa < 3.5:
        score -= 15
        reasons.append("GPA may fall short of a listed minimum.")

    degree = (profile.degree or "").lower()
    if "undergraduate" in degree and "high school" in blob and "undergraduate" not in blob:
        score -= 25
        reasons.append("Looks targeted at high school seniors, not current undergraduates.")
    if "graduate" in blob and "undergraduate" in degree and "undergraduate" not in blob:
        score -= 10

    demo = (profile.demographics or "").lower()
    if demo and any(part in blob for part in _tokens(demo)):
        score += 12
        reasons.append("Demographic criteria appear to match.")
    if "first" in demo and "first-generation" in blob:
        score += 8

    if profile.financial_need and any(k in blob for k in ("need-based", "financial need", "pell")):
        score += 6
        reasons.append("Need-based criteria align.")

    if "u.s. citizen" in blob or "us citizenship" in blob:
        if (profile.citizenship or "").upper() in {"US", "USA", "UNITED STATES"}:
            score += 5
        else:
            score -= 20
            reasons.append("Citizenship requirement may be a blocker.")

    score = max(0, min(100, score))
    amount_text = raw.get("award_amount") or _money(blob)
    amount_value = _money_value(amount_text or blob)
    if not reasons:
        reasons.append("Scored with local heuristics because the Claude API key is not configured.")

    return ScholarshipEvaluation(
        title=title,
        provider=raw.get("provider"),
        award_amount=amount_text,
        award_amount_value=amount_value,
        deadline=raw.get("deadline"),
        url=raw.get("url"),
        eligibility_summary=(raw.get("raw_text") or title)[:420],
        match_score=score,
        ai_rationale=" ".join(reasons)[:600],
    )


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    parts = re.split(r"[,\s/&+]+", value.lower())
    stop = {"and", "or", "the", "of", "in", "a"}
    return {p for p in parts if len(p) > 2 and p not in stop}


def _money(text: str) -> str | None:
    match = re.search(r"\$\s?[\d,]+", text)
    return match.group(0) if match else None


def _money_value(text: str | None) -> float:
    if not text:
        return 0.0
    match = re.search(r"\$?\s?([\d,]+(?:\.\d{1,2})?)", str(text))
    if not match:
        return 0.0
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return 0.0


# Keep ValidationError imported for callers that want to catch parse issues.
_ = ValidationError
