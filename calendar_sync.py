"""
Talks to Google Calendar: reads your next meeting (attendees + join link),
and now also CREATES meetings - scheduling everyone (HR, TL, manager,
whoever) with one call from scheduler.py.

First-time setup:
  1. Go to console.cloud.google.com -> create a project (free)
  2. Enable "Google Calendar API" for that project
  3. Create OAuth credentials (Desktop App type) -> download as credentials.json
  4. Put credentials.json in this project folder
  5. First run will open a browser to authorize once; after that a token.json
     is saved and reused automatically - no repeated logins.

Note: the scope below was widened from read-only to read/write so this file
can create events. If you have an old token.json from before that only
granted read-only access, delete it once so the next run re-authorizes with
the new (write) scope.
"""
import os
import json
import uuid
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


def get_next_meeting() -> dict | None:
    """
    Returns the next upcoming calendar event that has a video call link, with
    its attendee list already extracted - no manual participant entry needed.
    Returns None if nothing is coming up soon.
    """
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    events_result = service.events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=5,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = events_result.get("items", [])

    for event in events:
        # Only care about events that actually have a video call attached
        meet_link = event.get("hangoutLink") or _extract_conference_link(event)
        if not meet_link:
            continue

        participants = [
            {"name": a.get("displayName", a["email"].split("@")[0]), "email": a["email"]}
            for a in event.get("attendees", [])
            if not a.get("resource")  # skip meeting rooms/resources
        ]

        return {
            "meeting_title": event.get("summary", "Untitled meeting"),
            "start_time": event["start"].get("dateTime", event["start"].get("date")),
            "join_link": meet_link,
            "participants": participants,
        }

    return None


def create_meeting(title: str, start_dt: datetime.datetime, duration_minutes: int,
                    participants: list) -> dict:
    """
    Creates a new Google Calendar event with a Google Meet link and invites
    everyone in `participants` - each a {"name", "email", "role"} dict, e.g.
    role="HR" / "TL" / "Manager". Google Calendar attendees don't have a
    native "role" field, so the role mapping is also stashed in the event's
    extendedProperties (belt-and-suspenders alongside the local DB copy
    scheduler.py saves, so either source can be read back later).

    Returns the created event's id, join link, and the same participant list
    passed in (so the caller can persist it alongside the meeting_id).
    """
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)

    end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)
    roles_by_email = {p["email"]: p.get("role", "") for p in participants}

    event = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
        "attendees": [
            {"email": p["email"], "displayName": p.get("name")} for p in participants
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": f"meet-{uuid.uuid4()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "extendedProperties": {
            "private": {"participant_roles": json.dumps(roles_by_email)}
        },
    }

    created = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all",  # emails the calendar invite to every attendee
    ).execute()

    join_link = created.get("hangoutLink") or _extract_conference_link(created)

    return {
        "event_id": created["id"],
        "meeting_title": title,
        "start_time": start_dt.isoformat(),
        "join_link": join_link,
        "participants": participants,
    }


def _extract_conference_link(event: dict) -> str | None:
    """Handles Zoom/Teams links that show up in conferenceData instead of hangoutLink."""
    conf = event.get("conferenceData", {})
    for entry_point in conf.get("entryPoints", []):
        if entry_point.get("entryPointType") == "video":
            return entry_point.get("uri")
    return None