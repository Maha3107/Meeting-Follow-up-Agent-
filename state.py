"""
Shared state definition that flows through every LangGraph node.
Every node reads from this and returns partial updates that get merged back in.
"""
from typing import TypedDict, List, Optional
import operator
from typing import Annotated


class ActionItem(TypedDict):
    task: str
    mentioned_owner: str          # name as it appeared in the transcript
    resolved_owner_email: Optional[str]   # filled in after matching participant list
    resolved_owner_name: Optional[str]    # matched participant's real name (for the email greeting)
    resolved_owner_role: Optional[str]    # matched participant's role, e.g. "HR" / "TL" / "Manager"
    due_date: Optional[str]
    action_type: str              # "task" | "reminder" | "info_only"
    status: str                   # "pending" | "sent" | "failed" | "unresolved_owner"


class MeetingState(TypedDict):
    meeting_id: str
    meeting_title: str
    participants: List[dict]      # [{"name": "Alice", "email": "...", "role": "HR"}] - from calendar/scheduler
    transcript: str                # cleaned, speaker-tagged transcript text
    summary: str
    action_items: List[ActionItem]
    # accumulate log messages across nodes instead of overwriting
    actions_taken: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]