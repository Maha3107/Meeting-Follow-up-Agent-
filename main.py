"""
End-to-end run:
  calendar -> find next meeting (attendees + join link) automatically
  audio file -> transcribe -> checkpoint to DB -> run LangGraph pipeline

Usage:
    python main.py path/to/meeting_audio.mp3
    (participants are now pulled from your Google Calendar automatically -
     no more hardcoded list. Falls back to a manual list if no meeting is found,
     useful for testing with a synthetic audio file.)

For meetings scheduled with scheduler.py, where a bot joins and records the
call automatically, use run_scheduled_meeting.py instead - it skips ASR
entirely and calls run_graph_pipeline() below directly with the bot's
transcript.
"""
import sys
import uuid

from asr import transcribe_audio, clean_transcript
import storage
from graph import app
from calendar_sync import get_next_meeting


def run_graph_pipeline(meeting_id: str, participants: list, transcript: str,
                        meeting_title: str = "Untitled meeting") -> dict:
    """
    Shared by every entry point (audio-file mode here, and the bot-recorded
    mode in run_scheduled_meeting.py): checkpoints the transcript, then runs
    the summarize -> extract -> classify -> execute -> email -> persist
    LangGraph pipeline.
    """
    storage.save_transcript_checkpoint(meeting_id, participants, transcript)

    print(f"[{meeting_id}] Running LangGraph pipeline...")
    initial_state = {
        "meeting_id": meeting_id,
        "meeting_title": meeting_title,
        "participants": participants,
        "transcript": transcript,
        "summary": "",
        "action_items": [],
        "actions_taken": [],
        "errors": [],
    }
    result = app.invoke(initial_state)

    print(f"[{meeting_id}] Done.")
    print("Summary:\n", result["summary"])
    print("Action items:", result["action_items"])
    print("Actions taken:", result["actions_taken"])
    if result["errors"]:
        print("Errors:", result["errors"])

    return result


def run_pipeline(audio_path: str, participants: list, meeting_title: str = "Untitled meeting"):
    storage.init_db()

    meeting_id = str(uuid.uuid4())
    print(f"[{meeting_id}] Transcribing audio...")
    raw_text = transcribe_audio(audio_path)
    transcript = clean_transcript(raw_text)

    return run_graph_pipeline(meeting_id, participants, transcript, meeting_title)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py path/to/audio_file.mp3")
        sys.exit(1)

    # Try to auto-pull participants + meeting info from your calendar
    meeting_info = get_next_meeting()

    if meeting_info:
        print(f"Found upcoming meeting: {meeting_info['meeting_title']}")
        participants = meeting_info["participants"]
        title = meeting_info["meeting_title"]
    else:
        # No calendar event found (or calendar_sync.py not set up yet) -
        # fall back to a manual list, mainly useful for testing with a
        # synthetic audio file before your calendar integration is wired up.
        print("No upcoming calendar meeting found - using fallback test participants.")
        participants = [
            {"name": "Alice", "email": "your_real_email@gmail.com"},
            {"name": "Bob", "email": "your_real_email@gmail.com"},
        ]
        title = "Test meeting"

    run_pipeline(sys.argv[1], participants, title)
