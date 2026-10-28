"""FastAPI server for the scholarship discovery agent."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import (
    get_metrics,
    get_profile,
    init_db,
    list_scholarships,
    save_profile,
    update_status,
    upsert_scholarship,
)
from evaluator import UserProfile, evaluate_many
from scraper import DEMO_SCHOLARSHIPS, scrape_urls

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Scholarship Discovery Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProfilePayload(BaseModel):
    full_name: str | None = None
    major: str = "Artificial Intelligence"
    gpa: float = Field(default=3.8, ge=0, le=4.0)
    degree: str = "Undergraduate"
    year: str | None = "Junior"
    demographics: str | None = "First-generation"
    interests: str | None = "AI, Cybersecurity"
    citizenship: str | None = "US"
    state: str | None = None
    financial_need: bool = True


class ScrapeRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    max_items: int = Field(default=20, ge=1, le=50)
    use_demo_fallback: bool = True


class StatusPayload(BaseModel):
    status: Literal["Saved", "In Progress", "Submitted", "Not Interested"]


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/profile")
def read_profile() -> dict[str, Any]:
    return get_profile()


@app.post("/api/profile")
def upsert_profile(payload: ProfilePayload) -> dict[str, Any]:
    return save_profile(payload.model_dump())


@app.post("/api/scrape-and-evaluate")
async def scrape_and_evaluate(payload: ScrapeRequest) -> dict[str, Any]:
    profile = UserProfile.model_validate(get_profile())
    scraped: list[dict[str, Any]] = []
    errors: list[str] = []

    if payload.urls:
        try:
            scraped = await scrape_urls(payload.urls, max_items=payload.max_items)
        except Exception as exc:
            logger.exception("Scrape failed")
            errors.append(str(exc))

    source = "live"
    if not scraped and payload.use_demo_fallback:
        scraped = DEMO_SCHOLARSHIPS[: payload.max_items]
        source = "demo"

    if not scraped:
        raise HTTPException(
            status_code=502,
            detail="No scholarships could be collected from the provided URLs.",
        )

    evaluations = evaluate_many(profile, scraped)
    stored = []
    for evaluation in evaluations:
        record = evaluation.model_dump()
        record_id = upsert_scholarship(record)
        record["id"] = record_id
        stored.append(record)

    stored.sort(key=lambda item: item.get("match_score") or 0, reverse=True)
    return {
        "count": len(stored),
        "source": source,
        "errors": errors,
        "scholarships": stored,
    }


@app.post("/api/rescore")
def rescore() -> dict[str, Any]:
    profile = UserProfile.model_validate(get_profile())
    existing = list_scholarships(sort_by="newest")
    if not existing:
        raise HTTPException(status_code=404, detail="No scholarships to rescore.")

    updated = []
    for row in existing:
        raw = {
            "title": row["title"],
            "provider": row["provider"],
            "award_amount": row["award_amount"],
            "deadline": row["deadline"],
            "url": row["url"],
            "raw_text": row.get("eligibility_summary") or "",
        }
        evaluation = evaluate_many(profile, [raw])[0].model_dump()
        evaluation["status"] = row["status"]
        record_id = upsert_scholarship(evaluation)
        evaluation["id"] = record_id
        updated.append(evaluation)
    updated.sort(key=lambda item: item.get("match_score") or 0, reverse=True)
    return {"count": len(updated), "scholarships": updated}


@app.get("/api/scholarships")
def get_scholarships(
    sort_by: str = Query(default="score", pattern="^(score|deadline|status|amount|newest)$"),
    status: str | None = None,
) -> dict[str, Any]:
    items = list_scholarships(sort_by=sort_by, status=status)
    return {"count": len(items), "scholarships": items}


@app.patch("/api/scholarships/{scholarship_id}/status")
def patch_status(scholarship_id: int, payload: StatusPayload) -> dict[str, Any]:
    try:
        updated = update_status(scholarship_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return updated


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    return get_metrics()
