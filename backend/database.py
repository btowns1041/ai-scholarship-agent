"""SQLite persistence for scholarships and the user profile."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parent / "scholarships.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scholarships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    provider TEXT,
    award_amount TEXT,
    award_amount_value REAL DEFAULT 0,
    deadline TEXT,
    url TEXT,
    eligibility_summary TEXT,
    match_score INTEGER DEFAULT 0,
    ai_rationale TEXT,
    status TEXT DEFAULT 'Saved',
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_scholarships_url ON scholarships(url)
    WHERE url IS NOT NULL AND url != '';

CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

DEFAULT_PROFILE: dict[str, Any] = {
    "full_name": "Alex Rivera",
    "major": "Artificial Intelligence",
    "gpa": 3.8,
    "degree": "Undergraduate",
    "year": "Junior",
    "demographics": "First-generation",
    "interests": "AI, Cybersecurity",
    "citizenship": "US",
    "state": "NY",
    "financial_need": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute("SELECT id FROM profile WHERE id = 1").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO profile (id, payload, updated_at) VALUES (1, ?, ?)",
                (json.dumps(DEFAULT_PROFILE), utc_now()),
            )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def get_profile() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute("SELECT payload FROM profile WHERE id = 1").fetchone()
        if not row:
            return DEFAULT_PROFILE.copy()
        return json.loads(row["payload"])


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    merged = {**get_profile(), **profile}
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO profile (id, payload, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (json.dumps(merged), utc_now()),
        )
    return merged


def upsert_scholarship(item: dict[str, Any]) -> int:
    url = (item.get("url") or "").strip()
    with get_conn() as conn:
        existing = None
        if url:
            existing = conn.execute(
                "SELECT id, status FROM scholarships WHERE url = ?", (url,)
            ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE scholarships
                SET title = ?, provider = ?, award_amount = ?, award_amount_value = ?,
                    deadline = ?, eligibility_summary = ?, match_score = ?,
                    ai_rationale = ?
                WHERE id = ?
                """,
                (
                    item.get("title") or "Untitled scholarship",
                    item.get("provider"),
                    item.get("award_amount"),
                    item.get("award_amount_value") or 0,
                    item.get("deadline"),
                    item.get("eligibility_summary"),
                    int(item.get("match_score") or 0),
                    item.get("ai_rationale"),
                    existing["id"],
                ),
            )
            return int(existing["id"])
        cursor = conn.execute(
            """
            INSERT INTO scholarships (
                title, provider, award_amount, award_amount_value, deadline, url,
                eligibility_summary, match_score, ai_rationale, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.get("title") or "Untitled scholarship",
                item.get("provider"),
                item.get("award_amount"),
                item.get("award_amount_value") or 0,
                item.get("deadline"),
                url or None,
                item.get("eligibility_summary"),
                int(item.get("match_score") or 0),
                item.get("ai_rationale"),
                item.get("status") or "Saved",
                utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def list_scholarships(sort_by: str = "score", status: str | None = None) -> list[dict[str, Any]]:
    order = {
        "score": "match_score DESC, created_at DESC",
        "deadline": "CASE WHEN deadline IS NULL OR deadline = '' THEN 1 ELSE 0 END, deadline ASC",
        "status": "status ASC, match_score DESC",
        "amount": "award_amount_value DESC, match_score DESC",
        "newest": "created_at DESC",
    }.get(sort_by, "match_score DESC, created_at DESC")

    query = f"SELECT * FROM scholarships"
    params: tuple[Any, ...] = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += f" ORDER BY {order}"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_status(scholarship_id: int, status: str) -> dict[str, Any] | None:
    allowed = {"Saved", "In Progress", "Submitted", "Not Interested"}
    if status not in allowed:
        raise ValueError(f"Invalid status: {status}")
    with get_conn() as conn:
        conn.execute(
            "UPDATE scholarships SET status = ? WHERE id = ?",
            (status, scholarship_id),
        )
        row = conn.execute(
            "SELECT * FROM scholarships WHERE id = ?", (scholarship_id,)
        ).fetchone()
    return row_to_dict(row)


def get_metrics() -> dict[str, Any]:
    import pandas as pd

    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM scholarships", conn)

    if df.empty:
        return {
            "total_matches": 0,
            "pending_applications": 0,
            "submitted": 0,
            "total_award_potential": 0,
            "upcoming_deadlines": 0,
        }

    today = datetime.now(timezone.utc).date()
    deadlines = df["deadline"].map(parse_deadline)
    upcoming = int(
        deadlines.apply(
            lambda d: bool(d and 0 <= (d - today).days <= 14)
        ).sum()
    )
    award_potential = float(
        df.loc[df["status"] != "Not Interested", "award_amount_value"].fillna(0).sum()
    )

    return {
        "total_matches": int(len(df)),
        "pending_applications": int(df["status"].isin(["Saved", "In Progress"]).sum()),
        "submitted": int((df["status"] == "Submitted").sum()),
        "total_award_potential": round(award_potential, 2),
        "upcoming_deadlines": upcoming,
    }


def parse_deadline(value: str | None):
    if not value:
        return None
    from datetime import date

    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text if fmt.startswith("%Y") else str(value).strip(), fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
