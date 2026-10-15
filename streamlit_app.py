"""
Streamlit front end for scheduling a meeting - the point-and-click
replacement for scheduler.py. Creates the Google Calendar event (with a
Meet link) and invites everyone you add, each tagged with a role
(HR / TL / Manager / ...) that later personalizes the follow-up emails.

Run it:
    streamlit run streamlit_app.py

After scheduling, run the bot at meeting time from the terminal:
    python run_scheduled_meeting.py <meeting_id>
"""
import uuid
import datetime

import streamlit as st

import storage
from calendar_sync import create_meeting

ROLE_OPTIONS = ["HR", "TL", "Manager", "Team Member", "Other"]

st.set_page_config(page_title="Schedule a Meeting", page_icon="📅", layout="centered")
storage.init_db()

if "participants" not in st.session_state:
    st.session_state.participants = []  # list of {"name", "email", "role"}
if "last_scheduled" not in st.session_state:
    st.session_state.last_scheduled = None

st.title("📅 Schedule a Meeting")
st.caption("Invite HR, TL, Manager, or anyone else - the bot will join, record, "
           "and follow up automatically once the meeting happens.")

# --- Meeting details -------------------------------------------------------
st.subheader("Meeting details")
title = st.text_input("Meeting title", placeholder="e.g. Sprint Planning")

col1, col2, col3 = st.columns(3)
with col1:
    meeting_date = st.date_input("Date", value=datetime.date.today())
with col2:
    meeting_time = st.time_input("Time", value=datetime.time(10, 0))
with col3:
    duration = st.number_input("Duration (min)", min_value=5, max_value=480, value=30, step=5)

# --- Add participants --------------------------------------------------
st.subheader("Participants")

with st.form("add_participant_form", clear_on_submit=True):
    p_col1, p_col2, p_col3, p_col4 = st.columns([2, 3, 2, 1])
    with p_col1:
        p_name = st.text_input("Name")
    with p_col2:
        p_email = st.text_input("Email")
    with p_col3:
        p_role = st.selectbox("Role", ROLE_OPTIONS)
        if p_role == "Other":
            p_role = st.text_input("Custom role") or "Team Member"
    with p_col4:
        st.write("")
        st.write("")
        add_clicked = st.form_submit_button("Add")

    if add_clicked:
        if not p_name or not p_email:
            st.warning("Name and email are both required.")
        else:
            st.session_state.participants.append(
                {"name": p_name, "email": p_email, "role": p_role}
            )

if st.session_state.participants:
    st.write("**Invited so far:**")
    for i, p in enumerate(st.session_state.participants):
        row = st.columns([2, 3, 2, 1])
        row[0].write(p["name"])
        row[1].write(p["email"])
        row[2].write(p["role"])
        if row[3].button("✕", key=f"remove_{i}"):
            st.session_state.participants.pop(i)
            st.rerun()
else:
    st.info("No participants added yet.")

# --- Schedule ---------------------------------------------------------
st.divider()
if st.button("Schedule meeting", type="primary", disabled=not st.session_state.participants):
    if not title.strip():
        st.error("Give the meeting a title first.")
    else:
        start_dt = datetime.datetime.combine(meeting_date, meeting_time)
        with st.spinner("Creating calendar event and sending invites..."):
            try:
                meeting = create_meeting(title, start_dt, int(duration), st.session_state.participants)
                meeting_id = str(uuid.uuid4())
                storage.save_scheduled_meeting(
                    meeting_id=meeting_id,
                    event_id=meeting["event_id"],
                    title=title,
                    start_time=meeting["start_time"],
                    join_link=meeting["join_link"],
                    participants=st.session_state.participants,
                )
                st.session_state.last_scheduled = {
                    "meeting_id": meeting_id,
                    "title": title,
                    "start_time": meeting["start_time"],
                    "join_link": meeting["join_link"],
                    "participants": list(st.session_state.participants),
                }
                st.session_state.participants = []
            except Exception as e:
                st.error(f"Couldn't schedule the meeting: {e}")

if st.session_state.last_scheduled:
    m = st.session_state.last_scheduled
    st.success(f"Scheduled **{m['title']}** for {m['start_time']}")
    st.write(f"Join link: {m['join_link']}")
    st.write("Invited: " + ", ".join(f"{p['name']} ({p['role']})" for p in m["participants"]))
    st.code(f"python run_scheduled_meeting.py {m['meeting_id']}", language="bash")
    st.caption("Run that command at meeting time to send the bot in and get the follow-up emails/tasks sent automatically.")
