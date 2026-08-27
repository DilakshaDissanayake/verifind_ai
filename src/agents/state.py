"""Agent state — Sprint 1 TypedDict (LangGraph reducers wired in later sprints)."""

from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: list
    user_id: str
    session_id: str
    intent: Optional[str]
    report_id: Optional[str]
    report_type: Optional[str]
    payload: dict[str, Any]
    route_decision: Optional[dict]
    final_answer: Optional[str]
