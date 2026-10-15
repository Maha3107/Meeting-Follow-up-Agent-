# 🤖 Meeting Follow-up Agent

An AI agent that **joins your meeting, listens, and does the follow-up work for you**: it writes the summary, finds the action items, creates tasks, and emails the right people.

## What it does (in simple words)
1. You schedule a meeting (Streamlit form) and add people with roles like HR, TL, Manager.
2. A Google Calendar invite is created and sent to everyone.
3. At meeting time, a free recording bot (Attendee) joins the call and gets a speaker-tagged transcript. You can also upload an audio file instead.
4. A LangGraph pipeline then runs: **summarize → extract action items → classify and assign → send task/reminder → email summary → save to database**.
5. Everyone gets the summary. Only the person assigned a task or reminder gets that specific email, and tasks are also created in Notion.
6. If it can't confidently match a name to a participant, it sends nothing and marks the item `unresolved_owner` rather than guessing.

## Tech Stack
Python · LangGraph · Groq (Llama 3.3 70B + Whisper-large-v3) · Google Gemini · Google Calendar API · Attendee meeting bot · Gmail SMTP · Notion API · SQLite · Streamlit · RapidFuzz

## What's here

| File | Role |
|---|---|
| `state.py` | Shared state schema that flows through the graph |
| `llm_clients.py` | Wrapper so any node can call Groq or Gemini interchangeably |
| `asr.py` | Speech-to-text via Groq's free Whisper-large-v3 endpoint (audio-file mode only) |
| `calendar_sync.py` | Reads your next Google Calendar meeting, and **creates** new ones |
| `streamlit_app.py` | Web form to schedule a meeting (point-and-click version of `scheduler.py`) |
| `scheduler.py` | Terminal CLI: schedule a meeting and invite people with roles (HR/TL/Manager/...) |
| `bot_client.py` | Talks to Attendee (free, self-hosted bot) — joins the call, records, hands back a transcript |
| `run_scheduled_meeting.py` | Sends the bot into a scheduled meeting, then runs the follow-up pipeline |
| `storage.py` | SQLite persistence (scheduled meetings, transcript checkpoint, final record) |
| `nodes.py` | All LangGraph node functions (summarize, extract, classify, execute, persist) |
| `graph.py` | Wires the nodes into the compiled pipeline |
| `actions.py` | Real API calls: Gmail SMTP, Notion |
| `main.py` | Audio-file entry point + `run_graph_pipeline()`, shared by both entry points |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
```

You'll need free accounts/keys for:
- **Groq** — console.groq.com (LLM + Whisper ASR, used only in audio-file mode)
- **Gemini** — aistudio.google.com (LLM, used for summarize_node)
- **Notion** — create an integration at notion.so/my-integrations, share your task database with it
- **Gmail** — generate an "App Password" at myaccount.google.com/apppasswords (requires 2FA enabled)
- **Google Calendar** — see `calendar_sync.py` docstring for the one-time OAuth setup (create a
  Google Cloud project, enable Calendar API, download `credentials.json` into this folder). This
  now needs write access (to create events), not just read.
- **Attendee** (free, self-hosted recording bot) — see `bot_client.py` docstring for the one-time
  self-hosting steps (Docker Compose), plus a free Deepgram key for transcription.

## Run it

### Option A — schedule a meeting, let the bot record it (the new flow)

Point-and-click, via Streamlit:
```bash
streamlit run streamlit_app.py
```
Fill in the meeting details, add each person (name, email, role), click
**Schedule meeting**. It creates the Google Calendar event and sends the
invites, and gives you the exact command to run at meeting time.

...or the same thing from the terminal:
```bash
python scheduler.py
```
Walks you through the same fields as the Streamlit form. Either way you'll
get back a `meeting_id`.

At meeting time:
```bash
python run_scheduled_meeting.py <meeting_id>
```
This sends the bot into the call, waits for the meeting to end, pulls the
transcript, and runs the full summarize → extract → classify → email/task
pipeline automatically — no audio file needed.

### Option B — you already have an audio file

```bash
python main.py path/to/meeting_recording.mp3
```
Participants are pulled **automatically** from your next Google Calendar
meeting. If no upcoming meeting is found, it falls back to a small hardcoded
test list in `main.py`.

## What's NOT included yet (your next build steps)

1. **Speaker diarization for audio-file mode** — `asr.py` returns plain text
   without speaker labels (the bot path already gets speaker-tagged
   transcripts from Attendee directly). Add `pyannote.audio` if you need
   "who said what" for audio-file uploads too.
2. **Human-in-the-loop approval** — nothing here pauses for your review
   before sending. Add a `human_approval_node` using LangGraph's
   `interrupt()` if you want to review before actions fire.
3. **Gmail OAuth** — currently uses SMTP + App Password for simplicity.
   Swap to the Gmail API + OAuth2 if you need higher send volume.
4. **Auto-triggering the bot at meeting time** — `run_scheduled_meeting.py`
   is run manually right now. Wire it to a cron job / scheduler that checks
   `scheduled_meetings` for anything starting soon if you want it hands-free.

## How a run flows

```
scheduler.py
  -> create_meeting()                (calendar_sync.py) - creates the event,
                                       invites HR/TL/Manager/etc with roles
  -> save_scheduled_meeting()        (storage.py)

run_scheduled_meeting.py  (run at/after meeting time)
  -> start_bot()                     (bot_client.py) - bot joins the call
  -> wait_for_meeting_to_end()       (bot_client.py)
  -> get_transcript_text()           (bot_client.py) - speaker-tagged transcript
  -> run_graph_pipeline()            (main.py)
       summarize_node
       -> extract_action_items_node
       -> classify_and_assign_node     (also resolves each owner's role)
       -> execute_actions_node         (Notion task + targeted email to the SPECIFIC
                                         assigned person, per action item)
       -> send_summary_email_node      (recap emailed to ALL participants, personalized
                                         with each person's name + role)
       -> persist_state_node           (writes final record to SQLite)
```

**Who gets what, now:**
- **Everyone** in the meeting gets one email: the overall summary, greeted with their name and role.
- **Only the person assigned a task** gets an email about that specific task (plus it lands in Notion).
- **Only the person assigned a reminder** gets an email about that specific reminder.
- If nobody could be confidently matched to an item, nothing is sent for it — it's marked `unresolved_owner` in the database instead of guessing.

## Screenshots
_Add screenshots of the Streamlit form and a sample summary email here._

## Author
Your Name — [GitHub](https://github.com/Maha3107)
