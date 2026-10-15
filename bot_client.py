"""
Wraps Attendee (https://github.com/attendee-labs/attendee) - a free, open
source meeting bot API. A bot joins the Zoom/Google Meet/Teams call, records
it, and hands back a speaker-tagged transcript. Self-hosting it is free
(just your own server); that's the route this assumes, so there's no
per-meeting cost beyond hosting.

One-time setup:
  1. Self-host Attendee (free):
       git clone https://github.com/attendee-labs/attendee
       cd attendee
       docker compose up   # see the repo's README for the exact current command
     (Attendee also runs a hosted version at app.attendee.dev if you'd rather
     not self-host, but that's metered/paid past its trial credit - self
     hosting is the free path.)
  2. In the Attendee UI, add your Zoom OAuth credentials and a Deepgram API
     key (Deepgram gives ~400 free transcription hours, no card required) -
     that's what Attendee uses to transcribe.
  3. Create an API key in Attendee and put it in .env as ATTENDEE_API_KEY.
     Set ATTENDEE_BASE_URL to wherever you're hosting it (defaults to
     http://localhost:8000).

Field names in get_transcript_text() below match Attendee's documented
response shape at the time this was written - double check against your
running version's API docs if it comes back empty, since bot APIs evolve.
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("ATTENDEE_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("ATTENDEE_API_KEY")
DEFAULT_POLL_SECONDS = int(os.getenv("ATTENDEE_POLL_SECONDS", "30"))


def _headers() -> dict:
    return {"Authorization": f"Token {API_KEY}", "Content-Type": "application/json"}


def start_bot(meeting_url: str, bot_name: str = "Meeting Notetaker") -> str:
    """Sends the bot to join the meeting. Returns the bot_id."""
    resp = requests.post(
        f"{BASE_URL}/api/v1/bots",
        headers=_headers(),
        json={"meeting_url": meeting_url, "bot_name": bot_name},
        timeout=15,
    )
    if not resp.ok:
        raise RuntimeError(f"Attendee API error {resp.status_code}: {resp.text}")
    return resp.json()["id"]


def get_bot_status(bot_id: str) -> dict:
    """Returns the bot's current state, e.g. {"state": "joining"/"in_meeting"/"ended", ...}."""
    resp = requests.get(f"{BASE_URL}/api/v1/bots/{bot_id}", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def wait_for_meeting_to_end(bot_id: str, poll_seconds: int = None) -> None:
    """
    Blocks, polling Attendee, until the bot reports the meeting has ended.
    Safe to interrupt (Ctrl+C) and re-run later - it just polls the same
    bot_id again, it doesn't re-join.
    """
    poll_seconds = poll_seconds or DEFAULT_POLL_SECONDS
    while True:
        status = get_bot_status(bot_id)
        state = status.get("state")
        print(f"  bot state: {state} (transcription: {status.get('transcription_state')})")
        if state == "ended":
            return
        if state in ("fatal_error", "could_not_join"):
            raise RuntimeError(f"Bot failed to record the meeting: {status}")
        time.sleep(poll_seconds)


def get_transcript_text(bot_id: str) -> str:
    """
    Fetches the finished transcript and flattens it into the speaker-tagged
    plain-text format the rest of the pipeline (asr.py's output shape)
    expects, e.g.:
        Alice: Let's ship the v2 API by Friday.
        Bob: I'll own that.
    """
    resp = requests.get(
        f"{BASE_URL}/api/v1/bots/{bot_id}/transcript", headers=_headers(), timeout=30
    )
    resp.raise_for_status()
    entries = resp.json()

    lines = []
    for entry in entries:
        speaker = entry.get("speaker_name") or entry.get("speaker") or "Unknown"
        text = (entry.get("transcription") or {}).get("transcript") or entry.get("text", "")
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)