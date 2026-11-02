"""SQLite storage for practice attempts.

Why SQLite and not session state: session state dies on browser refresh, so a
user can never see whether they improved between one sitting and the next -
which is the whole point of a coach.

Why also an export file: Streamlit Cloud rebuilds the container on redeploy and
after idle periods, which wipes the database. Export gives the user something
durable that survives that, and import brings it back.
"""

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("COACH_DB", "practice_history.db")

DIMENSIONS = ["specificity", "structure", "evidence", "relevance"]


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                profile     TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                mode        TEXT,
                question    TEXT NOT NULL,
                answer      TEXT NOT NULL,
                specificity INTEGER,
                structure   INTEGER,
                evidence    INTEGER,
                relevance   INTEGER,
                overall     REAL,
                strongest   TEXT,
                weakest     TEXT,
                rewrite     TEXT
            )
        """)
        # Looking up one profile's attempts is the only query that runs often.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_profile ON attempts(profile)")


def save_attempt(profile, question, answer, scores, mode="", extras=None):
    """Store one scored answer. `scores` maps each dimension to 1-5."""
    extras = extras or {}
    overall = round(sum(scores[d] for d in DIMENSIONS) / len(DIMENSIONS), 2)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO attempts
               (profile, created_at, mode, question, answer,
                specificity, structure, evidence, relevance, overall,
                strongest, weakest, rewrite)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                profile.strip(),
                datetime.now().isoformat(timespec="microseconds"),
                mode,
                question,
                answer,
                scores["specificity"], scores["structure"],
                scores["evidence"], scores["relevance"], overall,
                extras.get("strongest", ""), extras.get("weakest", ""),
                extras.get("rewrite", ""),
            ),
        )
    return overall


def load_attempts(profile):
    """All attempts for one profile, oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM attempts WHERE profile = ? ORDER BY id ASC",
            (profile.strip(),),
        ).fetchall()
    return [dict(r) for r in rows]


def list_profiles():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT profile, COUNT(*) AS n FROM attempts GROUP BY profile ORDER BY profile"
        ).fetchall()
    return [(r["profile"], r["n"]) for r in rows]


def delete_profile(profile):
    with _connect() as conn:
        conn.execute("DELETE FROM attempts WHERE profile = ?", (profile.strip(),))


def export_profile(profile):
    """JSON bytes the user can download and keep."""
    payload = {
        "profile": profile,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "attempts": load_attempts(profile),
    }
    return json.dumps(payload, indent=2).encode("utf-8")


def import_profile(raw_bytes, profile=None):
    """Restore from an exported file. Returns how many rows were added.

    Rows already present (same profile, timestamp and question) are skipped, so
    importing the same file twice does not duplicate the history.
    """
    data = json.loads(raw_bytes.decode("utf-8"))
    attempts = data.get("attempts", [])
    target = (profile or data.get("profile") or "").strip()
    if not target:
        raise ValueError("No profile name in the file, and none given.")

    added = 0
    with _connect() as conn:
        for a in attempts:
            exists = conn.execute(
                "SELECT 1 FROM attempts "
                "WHERE profile=? AND created_at=? AND question=? AND answer=?",
                (target, a.get("created_at"), a.get("question"), a.get("answer")),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO attempts
                   (profile, created_at, mode, question, answer,
                    specificity, structure, evidence, relevance, overall,
                    strongest, weakest, rewrite)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    target, a.get("created_at"), a.get("mode", ""),
                    a.get("question", ""), a.get("answer", ""),
                    a.get("specificity"), a.get("structure"),
                    a.get("evidence"), a.get("relevance"), a.get("overall"),
                    a.get("strongest", ""), a.get("weakest", ""), a.get("rewrite", ""),
                ),
            )
            added += 1
    return added
