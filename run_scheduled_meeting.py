"""
Run this at (or after) the start time of a meeting created via scheduler.py.
It sends the Attendee bot into the call, waits for the meeting to end, pulls
the transcript, and runs it through the same summarize -> extract ->
classify -> email/task pipeline as main.py - except the transcript comes
from the bot instead of an uploaded audio file, so ASR is skipped entirely.

Usage:
    python run_scheduled_meeting.py <meeting_id>
"""
import sys

import storage
import bot_client
from main import run_graph_pipeline


def run(meeting_id: str) -> dict:
    storage.init_db()
    meeting = storage.load_scheduled_meeting(meeting_id)
    if not meeting:
        print(f"No scheduled meeting found with id {meeting_id}")
        sys.exit(1)

    if not meeting["join_link"]:
        print("This meeting has no video call link - nothing for the bot to join.")
        sys.exit(1)

    print(f"Sending the bot into: {meeting['title']}")
    bot_id = bot_client.start_bot(meeting["join_link"], bot_name=f"{meeting['title']} Notetaker")
    storage.update_scheduled_meeting_bot(meeting_id, bot_id, status="bot_joined")
    print(f"Bot joined (bot_id={bot_id}). Waiting for the meeting to end...")

    bot_client.wait_for_meeting_to_end(bot_id)
    print("Meeting ended. Fetching transcript...")
    transcript = bot_client.get_transcript_text(bot_id)

    if not transcript.strip():
        print("Warning: transcript came back empty - check the bot's Attendee dashboard.")

    storage.update_scheduled_meeting_bot(meeting_id, bot_id, status="transcribed")

    return run_graph_pipeline(
        meeting_id=meeting_id,
        participants=meeting["participants"],
        transcript=transcript,
        meeting_title=meeting["title"],
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_scheduled_meeting.py <meeting_id>")
        sys.exit(1)
    run(sys.argv[1])