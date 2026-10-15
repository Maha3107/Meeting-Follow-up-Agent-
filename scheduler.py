"""
Interactive CLI to schedule a meeting on Google Calendar and invite everyone
who needs to be there - HR, TL (team lead), manager, or anyone else - each
tagged with a role so later emails can be personalized ("Hi Priya (HR)...").

Usage:
    python scheduler.py

Once it's done you'll get back a meeting_id. Run the bot for that meeting
(at/after meeting time) with:
    python run_scheduled_meeting.py <meeting_id>
"""
import datetime
import uuid

import storage
from calendar_sync import create_meeting

ROLE_SUGGESTIONS = ["HR", "TL", "Manager", "Team Member"]


def _prompt_datetime() -> datetime.datetime:
    while True:
        date_str = input("Meeting date (YYYY-MM-DD): ").strip()
        time_str = input("Meeting time, 24hr (HH:MM): ").strip()
        try:
            return datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            print("  Couldn't parse that - use YYYY-MM-DD and HH:MM, try again.")


def _prompt_participants() -> list:
    participants = []
    print("\nAdd everyone who needs to be in this meeting.")
    print(f"Suggested roles: {', '.join(ROLE_SUGGESTIONS)} (or type your own)")
    while True:
        name = input("\nParticipant name (leave blank when done adding people): ").strip()
        if not name:
            break
        email = input(f"  {name}'s email: ").strip()
        role = input(f"  {name}'s role (e.g. HR / TL / Manager): ").strip() or "Team Member"
        participants.append({"name": name, "email": email, "role": role})
    return participants


def main():
    storage.init_db()

    title = input("Meeting title: ").strip() or "Untitled meeting"
    start_dt = _prompt_datetime()
    duration_str = input("Duration in minutes [30]: ").strip()
    duration = int(duration_str) if duration_str else 30
    participants = _prompt_participants()

    if not participants:
        print("\nNo participants added - nothing scheduled.")
        return

    print("\nCreating calendar event and sending invites...")
    meeting = create_meeting(title, start_dt, duration, participants)

    meeting_id = str(uuid.uuid4())
    storage.save_scheduled_meeting(
        meeting_id=meeting_id,
        event_id=meeting["event_id"],
        title=title,
        start_time=meeting["start_time"],
        join_link=meeting["join_link"],
        participants=participants,
    )

    invited = ", ".join(f"{p['name']} ({p['role']})" for p in participants)
    print(f"\nScheduled: {title}")
    print(f"  When: {meeting['start_time']}")
    print(f"  Join link: {meeting['join_link']}")
    print(f"  Invited: {invited}")
    print(f"\nMeeting ID (save this): {meeting_id}")
    print(f"At meeting time, run:  python run_scheduled_meeting.py {meeting_id}")


if __name__ == "__main__":
    main()