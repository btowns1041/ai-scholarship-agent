"""Asynchronous Playwright crawler for scholarship listing pages."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SELECTORS = {
    "cards": [
        "article",
        ".scholarship",
        ".scholarship-card",
        ".scholarship-item",
        "[class*='scholarship']",
        ".listing-item",
        ".result-item",
        "li.card",
        ".card",
    ],
    "title": ["h1", "h2", "h3", ".title", ".scholarship-title", "a"],
    "deadline": [".deadline", "[class*='deadline']", "time", "[datetime]"],
    "amount": [".amount", "[class*='award']", "[class*='amount']"],
    "provider": [".provider", ".organization", "[class*='sponsor']", "[class*='org']"],
}


MONEY_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")
DEADLINE_RE = re.compile(
    r"(?:deadline|due|apply by)[:\s]*([A-Z][a-z]+ \d{1,2},? \d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.I,
)


async def scrape_urls(urls: list[str], max_items: int = 25) -> list[dict[str, Any]]:
    if not urls:
        return []

    results: list[dict[str, Any]] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1400, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()
        try:
            for url in urls:
                try:
                    items = await _scrape_page(page, url, max_items=max_items)
                    results.extend(items)
                    await asyncio.sleep(random.uniform(1.2, 2.4))
                except Exception as exc:
                    logger.warning("Failed to scrape %s: %s", url, exc)
        finally:
            await context.close()
            await browser.close()

    deduped: dict[str, dict[str, Any]] = {}
    for item in results:
        key = (item.get("url") or item.get("title") or "").strip().lower()
        if key and key not in deduped:
            deduped[key] = item
    return list(deduped.values())[:max_items]


async def _scrape_page(page, url: str, max_items: int) -> list[dict[str, Any]]:
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(1200)
    await _auto_scroll(page)

    items = await _extract_cards(page, url)
    if len(items) < 3:
        items.extend(await _extract_link_fallback(page, url))

    cleaned = []
    for item in items:
        title = (item.get("title") or "").strip()
        if len(title) < 8:
            continue
        if not _looks_like_scholarship(title, item.get("raw_text") or ""):
            continue
        item["source_url"] = url
        cleaned.append(item)
        if len(cleaned) >= max_items:
            break
    return cleaned


async def _auto_scroll(page) -> None:
    previous_height = 0
    for _ in range(8):
        height = await page.evaluate("() => document.body.scrollHeight")
        if height <= previous_height:
            break
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(random.randint(400, 900))
        previous_height = height
    await page.evaluate("() => window.scrollTo(0, 0)")


async def _extract_cards(page, base_url: str) -> list[dict[str, Any]]:
    locator_css = ", ".join(SELECTORS["cards"])
    cards = page.locator(locator_css)
    count = min(await cards.count(), 40)
    items: list[dict[str, Any]] = []
    for i in range(count):
        card = cards.nth(i)
        try:
            text = (await card.inner_text(timeout=1500)).strip()
        except PlaywrightTimeout:
            continue
        if len(text) < 20:
            continue

        href = await _first_href(card, base_url)
        title = await _first_text(card, SELECTORS["title"]) or text.split("\n")[0][:180]
        provider = await _first_text(card, SELECTORS["provider"]) or _guess_provider(text, base_url)
        deadline = await _first_text(card, SELECTORS["deadline"]) or _find_deadline(text)
        amount = await _first_text(card, SELECTORS["amount"]) or _find_amount(text)

        items.append(
            {
                "title": title[:200],
                "provider": provider[:160] if provider else _host(base_url),
                "deadline": deadline,
                "award_amount": amount,
                "url": href or base_url,
                "raw_text": text[:4000],
            }
        )
    return items


async def _extract_link_fallback(page, base_url: str) -> list[dict[str, Any]]:
    links = page.locator("a")
    count = min(await links.count(), 80)
    items: list[dict[str, Any]] = []
    for i in range(count):
        link = links.nth(i)
        try:
            label = (await link.inner_text(timeout=800)).strip()
            href = await link.get_attribute("href")
        except PlaywrightTimeout:
            continue
        if not href or len(label) < 12:
            continue
        if not re.search(r"scholarship|fellowship|grant|award", f"{label} {href}", re.I):
            continue
        items.append(
            {
                "title": label[:200],
                "provider": _host(base_url),
                "deadline": None,
                "award_amount": None,
                "url": urljoin(base_url, href),
                "raw_text": label,
            }
        )
    return items


async def _first_text(locator, selectors: list[str]) -> str | None:
    for sel in selectors:
        node = locator.locator(sel).first
        try:
            if await node.count() == 0:
                continue
            text = (await node.inner_text(timeout=400)).strip()
            if text:
                return text.split("\n")[0][:200]
        except Exception:
            continue
    return None


async def _first_href(locator, base_url: str) -> str | None:
    try:
        href = await locator.locator("a").first.get_attribute("href", timeout=400)
        if href:
            return urljoin(base_url, href)
    except Exception:
        return None
    return None


def _looks_like_scholarship(title: str, text: str) -> bool:
    blob = f"{title} {text}".lower()
    keywords = ("scholarship", "fellowship", "grant", "award", "tuition", "stipend")
    return any(word in blob for word in keywords) or len(text) > 80


def _find_amount(text: str) -> str | None:
    match = MONEY_RE.search(text)
    return match.group(0) if match else None


def _find_deadline(text: str) -> str | None:
    match = DEADLINE_RE.search(text)
    return match.group(1) if match else None


def _guess_provider(text: str, url: str) -> str:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) > 1 and len(lines[1]) < 80:
        return lines[1]
    return _host(url)


def _host(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "")
    return host or "Unknown"


DEMO_SCHOLARSHIPS: list[dict[str, Any]] = [
    {
        "title": "Google Lime Scholarship",
        "provider": "Google / Lime Connect",
        "award_amount": "$10,000",
        "deadline": "2026-12-06",
        "url": "https://www.limeconnect.com/programs/page/google-lime-scholarship",
        "raw_text": (
            "For undergraduate and graduate students with disabilities pursuing computer "
            "science, computer engineering, or a closely related technical field. Award "
            "includes $10,000 and an invitation to the Google Scholars' Retreat."
        ),
    },
    {
        "title": "NSF Computer and Information Science and Engineering Scholarship",
        "provider": "National Science Foundation",
        "award_amount": "$8,000",
        "deadline": "2026-11-15",
        "url": "https://www.nsf.gov/funding/",
        "raw_text": (
            "Need-based and merit scholarships supporting undergraduate students in "
            "computer science, AI, cybersecurity, and related STEM majors. US citizenship "
            "or permanent residency typically required. GPA 3.0+ preferred."
        ),
    },
    {
        "title": "Generation Google Scholarship",
        "provider": "Google",
        "award_amount": "$10,000",
        "deadline": "2026-05-01",
        "url": "https://buildyourfuture.withgoogle.com/scholarships/generation-google-scholarship",
        "raw_text": (
            "Supports students who are pursuing computer science or a closely related field "
            "and demonstrate a commitment to diversity, equity, and inclusion. Open to "
            "undergraduates and graduate students."
        ),
    },
    {
        "title": "Palantir Women in Technology Scholarship",
        "provider": "Palantir",
        "award_amount": "$7,000",
        "deadline": "2026-04-03",
        "url": "https://www.palantir.com/careers/students/scholarship/wit-north-america/",
        "raw_text": (
            "For undergraduate women studying computer science, software engineering, or "
            "a closely related technical field. Includes mentorship and potential internship "
            "consideration."
        ),
    },
    {
        "title": "CyberCorps Scholarship for Service",
        "provider": "U.S. Office of Personnel Management",
        "award_amount": "$32,000",
        "deadline": "2026-02-15",
        "url": "https://www.sfs.opm.gov/",
        "raw_text": (
            "Full scholarship plus stipend for students in cybersecurity-related degree "
            "programs. Recipients complete a federal service commitment after graduation. "
            "U.S. citizenship required. Strong fit for AI + cybersecurity interests."
        ),
    },
    {
        "title": "Coca-Cola Scholars Program",
        "provider": "Coca-Cola Scholars Foundation",
        "award_amount": "$20,000",
        "deadline": "2026-10-31",
        "url": "https://www.coca-colascholarsfoundation.org/apply/",
        "raw_text": (
            "Merit-based scholarship for graduating high school seniors with leadership, "
            "service, and academic excellence. Less relevant for current undergraduates "
            "unless still in high school."
        ),
    },
    {
        "title": "AI for Good Undergraduate Research Award",
        "provider": "Association for the Advancement of Artificial Intelligence",
        "award_amount": "$5,000",
        "deadline": "2026-03-20",
        "url": "https://aaai.org/",
        "raw_text": (
            "Supports undergraduates conducting research in artificial intelligence, machine "
            "learning, or responsible AI. Essay and faculty recommendation required. GPA 3.5+."
        ),
    },
    {
        "title": "First-Generation College Student Scholarship",
        "provider": "Center for First-generation Student Success",
        "award_amount": "$2,500",
        "deadline": "2026-06-30",
        "url": "https://firstgen.naspa.org/",
        "raw_text": (
            "Need-based award for first-generation undergraduate students in any major. "
            "Requires a short personal statement about being first-generation."
        ),
    },
]
