"""
Wires every node from nodes.py into the compiled LangGraph pipeline.
This is the single source of truth for the workflow shape.
"""
from langgraph.graph import StateGraph, END
from state import MeetingState
from nodes import (
    summarize_node,
    extract_action_items_node,
    classify_and_assign_node,
    execute_actions_node,
    send_summary_email_node,
    persist_state_node,
)


def build_graph():
    graph = StateGraph(MeetingState)

    graph.add_node("summarize", summarize_node)
    graph.add_node("extract_actions", extract_action_items_node)
    graph.add_node("classify_assign", classify_and_assign_node)
    graph.add_node("execute_actions", execute_actions_node)
    graph.add_node("send_summary_email", send_summary_email_node)
    graph.add_node("persist", persist_state_node)

    graph.set_entry_point("summarize")
    graph.add_edge("summarize", "extract_actions")
    graph.add_edge("extract_actions", "classify_assign")
    graph.add_edge("classify_assign", "execute_actions")
    graph.add_edge("execute_actions", "send_summary_email")
    graph.add_edge("send_summary_email", "persist")
    graph.add_edge("persist", END)

    return graph.compile()


# Compiled app, ready to .invoke()
app = build_graph()
