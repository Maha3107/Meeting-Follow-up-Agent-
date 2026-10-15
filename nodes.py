"""
Each function here is one LangGraph node. Every node takes the full MeetingState
and returns a dict of the fields it wants to update - LangGraph merges it in.
"""
import os
from rapidfuzz import process, fuzz

from state import MeetingState
from llm_clients import call_llm, call_llm_json
from actions import send_email, create_notion_task
import storage

SUMMARIZE_MODEL = os.getenv("SUMMARIZE_MODEL", "gemini")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "groq")
CLASSIFY_MODEL = os.getenv("CLASSIFY_MODEL", "groq")


# ---------------------------------------------------------------------------
def summarize_node(state: MeetingState) -> dict:
    prompt = f"""Summarize this meeting transcript in 3-6 concise bullet points.
Focus on decisions made and topics discussed. Ignore filler words and noise.

Transcript:
{state['transcript']}
"""
    summary = call_llm(prompt, provider=SUMMARIZE_MODEL)
    return {"summary": summary}


# ---------------------------------------------------------------------------
def extract_action_items_node(state: MeetingState) -> dict:
    prompt = f"""Extract every action item from this meeting transcript.
Return ONLY valid JSON matching this exact shape:
{{
  "action_items": [
    {{
      "task": "string - what needs to be done",
      "mentioned_owner": "string - the name mentioned as responsible, or 'unassigned'",
      "due_date": "string or null - date/day mentioned, or null if none given"
    }}
  ]
}}
If there are no action items, return {{"action_items": []}}.

Transcript:
{state['transcript']}
"""
    result = call_llm_json(prompt, provider=EXTRACT_MODEL)
    raw_items = result.get("action_items", [])

    action_items = [
        {
            "task": item["task"],
            "mentioned_owner": item.get("mentioned_owner", "unassigned"),
            "resolved_owner_email": None,
            "resolved_owner_name": None,
            "resolved_owner_role": None,
            "due_date": item.get("due_date"),
            "action_type": "task",       # default, refined in classify_and_assign_node
            "status": "pending",
        }
        for item in raw_items
    ]
    return {"action_items": action_items}


# ---------------------------------------------------------------------------
def classify_and_assign_node(state: MeetingState) -> dict:
    participants = state["participants"]
    participant_names = [p["name"] for p in participants]

    updated_items = []
    for item in state["action_items"]:
        # Resolve fuzzy-matched owner name against the real participant list
        match = process.extractOne(
            item["mentioned_owner"], participant_names, scorer=fuzz.WRatio
        )
        if match and match[1] > 70:
            matched_name = match[0]
            person = next(p for p in participants if p["name"] == matched_name)
            item["resolved_owner_email"] = person.get("email")
            item["resolved_owner_name"] = person.get("name")
            item["resolved_owner_role"] = person.get("role")

        # Classify action type with a lightweight prompt
        classify_prompt = f"""Classify this action item into exactly one category:
"task" (should be tracked in a task manager), "reminder" (a quick nudge is enough),
or "info_only" (no action needed, just informational).

Task: {item['task']}
Owner: {item['mentioned_owner']}

Respond with ONLY the category word."""
        category = call_llm(classify_prompt, provider=CLASSIFY_MODEL).strip().lower()
        item["action_type"] = category if category in ("task", "reminder", "info_only") else "task"

        updated_items.append(item)

    return {"action_items": updated_items}


def _greeting_name(item: dict) -> str:
    """Prefers the matched participant's real name + role (e.g. 'Priya (HR)')
    over the raw name as it happened to appear in the transcript."""
    name = item.get("resolved_owner_name") or item["mentioned_owner"]
    role = item.get("resolved_owner_role")
    return f"{name} ({role})" if role else name


# ---------------------------------------------------------------------------
def execute_actions_node(state: MeetingState) -> dict:
    """
    Loops over every action item and routes it to the RIGHT person only:
      - "task"     -> creates a Notion task AND emails just that person
      - "reminder" -> emails just that person (no Slack anymore)
      - "info_only"-> no action, just logged
      - unresolved owner -> flagged, nothing sent (avoids messaging the wrong person)
    """
    actions_taken = []
    errors = []
    updated_items = []

    for item in state["action_items"]:
        try:
            if item["action_type"] == "info_only":
                item["status"] = "skipped"

            elif not item["resolved_owner_email"]:
                # Nobody could be confidently matched - don't guess who to email
                item["status"] = "unresolved_owner"

            elif item["action_type"] == "reminder":
                due_str = f" (due {item['due_date']})" if item["due_date"] else ""
                greeting = _greeting_name(item)
                result = send_email(
                    item["resolved_owner_email"],
                    f"Reminder: {item['task']}",
                    f"Hi {greeting},\n\nQuick reminder from the meeting:\n{item['task']}{due_str}",
                )
                actions_taken.append(result)
                item["status"] = "sent"

            elif item["action_type"] == "task":
                notion_result = create_notion_task(item["task"], item["mentioned_owner"], item["due_date"])
                due_str = f" (due {item['due_date']})" if item["due_date"] else ""
                greeting = _greeting_name(item)
                email_result = send_email(
                    item["resolved_owner_email"],
                    f"Task assigned: {item['task']}",
                    f"Hi {greeting},\n\nFrom today's meeting, you're assigned:\n{item['task']}{due_str}",
                )
                actions_taken.append(notion_result)
                actions_taken.append(email_result)
                item["status"] = "sent"

        except Exception as e:
            errors.append(f"{item['task']}: {str(e)}")
            item["status"] = "failed"

        updated_items.append(item)

    return {"action_items": updated_items, "actions_taken": actions_taken, "errors": errors}


# ---------------------------------------------------------------------------
def send_summary_email_node(state: MeetingState) -> dict:
    """
    Sends ONLY the overall meeting recap to every participant - no per-item
    task/reminder detail here, since those already went to the specific
    assigned person individually in execute_actions_node.
    """
    actions_taken = []
    errors = []
    recap = f"Meeting: {state.get('meeting_title', 'Untitled')}\n\n{state['summary']}"

    for p in state["participants"]:
        if p.get("email"):
            try:
                role_suffix = f" ({p['role']})" if p.get("role") else ""
                body = f"Hi {p.get('name', 'there')}{role_suffix},\n\n{recap}"
                result = send_email(p["email"], "Meeting Summary", body)
                actions_taken.append(result)
            except Exception as e:
                errors.append(f"email to {p['email']}: {str(e)}")

    return {"actions_taken": actions_taken, "errors": errors}


# ---------------------------------------------------------------------------
def persist_state_node(state: MeetingState) -> dict:
    storage.save_final_result(
        meeting_id=state["meeting_id"],
        summary=state["summary"],
        action_items=state["action_items"],
        actions_taken=state["actions_taken"],
        errors=state["errors"],
    )
    return {}