"""Intent router."""

from __future__ import annotations

from typing import Any, Dict


def classify_intent(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = (payload.get("text") or payload.get("description") or "").lower()
    report_type = (payload.get("report_type") or "").upper()
    action = (payload.get("action") or "").lower()
    if action in ("claim", "verify") or "claim" in text:
        intent = "verify"
    elif action == "match" or "match" in text:
        intent = "match"
    elif report_type in ("LOST", "FOUND") or action == "intake":
        intent = "intake"
    elif "fraud" in text:
        intent = "fraud"
    else:
        intent = "unknown"
    return {
        "intent": intent,
        "report_type": report_type or None,
        "confidence": 0.9 if intent != "unknown" else 0.3,
    }
