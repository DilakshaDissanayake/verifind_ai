"""LangGraph orchestrator stub — no hard LLM dependency at import time."""

from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from agents.router import classify_intent
from agents.state import AgentState


class AgentOrchestrator:
    def __init__(self) -> None:
        self.llm_router = None
        self.llm_vision = None
        self.llm_verify = None

    def attach_llms(self) -> None:
        try:
            from infrastructure.llm.llm_provider import (
                get_router_llm,
                get_verify_llm,
                get_vision_llm,
            )

            self.llm_router = get_router_llm()
            self.llm_vision = get_vision_llm()
            self.llm_verify = get_verify_llm()
            logger.info("LLM clients attached")
        except Exception as exc:
            logger.warning("LLM init deferred: {}", exc)

    def route(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return classify_intent(payload)

    def run(self, state: AgentState) -> AgentState:
        decision = self.route(state.get("payload") or {})
        state["route_decision"] = decision
        state["intent"] = decision.get("intent")
        state["final_answer"] = f"Routed to '{decision.get('intent')}'"
        return state


def build_agent() -> AgentOrchestrator:
    logger.info("Building AgentOrchestrator (Sprint 1)")
    agent = AgentOrchestrator()
    # Soft-attach — missing keys must not block /health
    agent.attach_llms()
    return agent
