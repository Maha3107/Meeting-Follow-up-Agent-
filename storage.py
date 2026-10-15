"""
SQLite persistence. Two writes per meeting:
  1. Right after ASR -> checkpoint the transcript (survives pipeline crashes)
  2. After the LangGraph pipeline finishes -> update with summary/actions
"""
import sqlite3
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DATABASE_PATH", "meetings.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            meeting_id TEXT PRIMARY KEY,
            participants TEXT,
            transcript TEXT,
            summary TEXT,
            action_items TEXT,
            actions_taken TEXT,
            errors TEXT,
            status TEXT DEFAULT 'transcribed',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    # Meetings created via scheduler.py: the calendar event + who's invited
    # (with their role) + which bot recorded it, tracked from "scheduled"
    # through "bot_joined" -> "transcribed" (at which point a row also shows
    # up in `meetings` above once the LangGraph pipeline runs on it).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_meetings (
            meeting_id TEXT PRIMARY KEY,
            event_id TEXT,
            title TEXT,
            start_time TEXT,
            join_link TEXT,
            participants TEXT,
            bot_id TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_scheduled_meeting(meeting_id: str, event_id: str, title: str, start_time: str,
                            join_link: str, participants: list):
    """Called right after scheduler.py creates the calendar event."""
    conn = sqlite3.connect(DB_PATH)
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO scheduled_meetings
            (meeting_id, event_id, title, start_time, join_link, participants,
             status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)
    """, (meeting_id, event_id, title, start_time, join_link, json.dumps(participants), now, now))
    conn.commit()
    conn.close()


def load_scheduled_meeting(meeting_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT event_id, title, start_time, join_link, participants, bot_id, status
        FROM scheduled_meetings WHERE meeting_id = ?
    """, (meeting_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "event_id": row[0], "title": row[1], "start_time": row[2], "join_link": row[3],
        "participants": json.loads(row[4]), "bot_id": row[5], "status": row[6],
    }


def update_scheduled_meeting_bot(meeting_id: str, bot_id: str, status: str):
    """Tracks bot progress: 'bot_joined' once sent in, 'transcribed' once the
    transcript is pulled back out."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE scheduled_meetings SET bot_id = ?, status = ?, updated_at = ? WHERE meeting_id = ?",
        (bot_id, status, datetime.utcnow().isoformat(), meeting_id),
    )
    conn.commit()
    conn.close()


def save_transcript_checkpoint(meeting_id: str, participants: list, transcript: str):
    """Called right after ASR finishes, before LangGraph even runs."""
    conn = sqlite3.connect(DB_PATH)
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO meetings (meeting_id, participants, transcript, status, created_at, updated_at)
        VALUES (?, ?, ?, 'transcribed', ?, ?)
        ON CONFLICT(meeting_id) DO UPDATE SET transcript=excluded.transcript, updated_at=excluded.updated_at
    """, (meeting_id, json.dumps(participants), transcript, now, now))
    conn.commit()
    conn.close()


def save_final_result(meeting_id: str, summary: str, action_items: list,
                       actions_taken: list, errors: list):
    """Called by persist_state_node at the end of the LangGraph pipeline."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE meetings
        SET summary = ?, action_items = ?, actions_taken = ?, errors = ?,
            status = 'completed', updated_at = ?
        WHERE meeting_id = ?
    """, (summary, json.dumps(action_items), json.dumps(actions_taken),
          json.dumps(errors), datetime.utcnow().isoformat(), meeting_id))
    conn.commit()
    conn.close()


def load_transcript(meeting_id: str) -> dict | None:
    """Useful for retrying the LangGraph pipeline without re-running ASR."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT participants, transcript FROM meetings WHERE meeting_id = ?", (meeting_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"participants": json.loads(row[0]), "transcript": row[1]}