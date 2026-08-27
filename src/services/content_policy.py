"""Pre-publication content safety checks for report text."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status

_PROHIBITED = (
    r"\b(cocaine|heroin|meth|methamphetamine|crack|fentanyl|ecstasy|mdma|"
    r"marijuana|cannabis|weed|drugs?|porn|pornography|sex|sexual|nude|naked|"
    r"escort|prostitut(?:e|ion)|child\s+sexual|rape)\b",
)
_PATTERN = re.compile("|".join(_PROHIBITED), re.IGNORECASE)


def find_prohibited_match(*values: str | None) -> str | None:
    content = " ".join(value.strip() for value in values if value)
    hit = _PATTERN.search(content)
    return hit.group(0) if hit else None


def validate_report_content(*values: str | None) -> None:
    """Legacy hard reject (no strike tracking). Prefer enforce_report_content."""
    if find_prohibited_match(*values):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "This report contains prohibited content. Lost and found reports "
                "cannot include sexual or drug-related content."
            ),
        )


def enforce_report_content(
    *,
    user_id: UUID,
    category: str | None,
    title: str | None,
    description: str | None,
) -> None:
    """
    Block posting when account inactive or prohibited content is detected.
    3 prohibited attempts → auto-block; report is never created.
    """
    from services.moderation_service import (
        CONTENT_STRIKE_LIMIT,
        assert_user_can_post,
        record_prohibited_attempt,
    )

    try:
        assert_user_can_post(user_id)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    hit = find_prohibited_match(category, title, description)
    if not hit:
        return

    snippet = " ".join(v.strip() for v in (category, title, description) if v)
    result = record_prohibited_attempt(
        user_id=user_id,
        source="report_create",
        snippet=f"matched={hit}; {snippet}",
    )
    strike = result["strike_number"]
    limit = result.get("limit", CONTENT_STRIKE_LIMIT)
    if result["blocked"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Account blocked after {strike} prohibited content attempts "
                f"(limit {limit}). An admin has been notified."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "This report contains prohibited content (sexual or drug-related). "
            f"It was not posted. Warning {strike}/{limit} — "
            "3 violations permanently block your account."
        ),
    )
