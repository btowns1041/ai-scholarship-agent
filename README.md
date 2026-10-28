# AI Scholarship Discovery Agent

End-to-end scholarship finder: Playwright crawls listing pages, Claude scores each award against a student profile, and a React dashboard tracks fit, deadlines, and application status.

## Architecture

- `backend/scraper.py` — asynchronous Playwright crawler with auto-scroll, delays, and selector fallbacks
- `backend/evaluator.py` — Anthropic / Claude matching engine with a heuristic fallback when no API key is set
- `backend/database.py` — SQLite persistence (`backend/scholarships.db`)
- `backend/app.py` — FastAPI REST API for the dashboard
- `frontend/` — Vite + React + Tailwind dashboard

## Prerequisites

- Python 3.11+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com/) (optional; local heuristic scoring is used without it)

## Backend setup

```bash
cd scholarship-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
playwright install chromium
cp backend/.env.example backend/.env
```

Edit `.env` and set `ANTHROPIC_API_KEY` if you want Claude scoring.

Start the API:

```bash
source .venv/bin/activate
cd backend
uvicorn app:app --reload --port 8000
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to the FastAPI server.

## Typical workflow

1. Open the dashboard and edit the student profile (GPA, major, degree, demographics, interests).
2. Optionally paste scholarship listing URLs (one per line).
3. Click **Scrape and evaluate**. If live pages yield no listings (common with bot-protected portals), the API loads a curated demo set so you can still exercise scoring and status tracking.
4. Sort by score, deadline, amount, or status. Update application status from the table. Expand a row for the AI rationale.

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/profile` | Save / update the student profile |
| `GET` | `/api/profile` | Read the current profile |
| `POST` | `/api/scrape-and-evaluate` | Crawl URLs, score with Claude, store results |
| `POST` | `/api/rescore` | Re-score stored scholarships after a profile change |
| `GET` | `/api/scholarships` | List scholarships (`sort_by=score\|deadline\|status\|amount\|newest`) |
| `PATCH` | `/api/scholarships/{id}/status` | Update status (`Saved`, `In Progress`, `Submitted`, `Not Interested`) |
| `GET` | `/api/metrics` | Totals, pending count, award potential, 14-day deadlines |

Example scrape payload:

```json
{
  "urls": ["https://example.edu/scholarships"],
  "max_items": 20,
  "use_demo_fallback": true
}
```

## Notes

- Many commercial scholarship portals block headless browsers. The crawler is built for public listing pages and uses polite delays plus fallback selectors.
- Without `ANTHROPIC_MODEL` override, evaluations use `claude-3-5-sonnet-latest`.
- SQLite lives at `backend/scholarships.db` after the first API start.
