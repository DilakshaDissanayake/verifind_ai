"""Pre-publication content safety checks for report text."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status

# Sexual, drugs, and weapons / illegal items — lost-and-found must not accept these.
_PROHIBITED = (
    r"\b(?:"
    # drugs
    r"cocaine|heroin|meth|methamphetamine|crack|fentanyl|ecstasy|mdma|"
    r"marijuana|cannabis|weed|drugs?|"
    # sexual (include sexy / common misspellings; \bsex\b alone misses \"sexy\")
    r"porn|pornography|sexya?|sexxy|sexual|sex|nude|naked|"
    r"escort|prostitut(?:e|ion)|child\s+sexual|rape|"
    # weapons / illegal arms
    r"weapons?|firearms?|guns?|handguns?|pistols?|rifles?|shotguns?|"
    r"ammunition|ammo|explosives?|bombs?|grenades?|molotov|"
    r"assault\s+rifle|machine\s+guns?"
    r")\b",
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
            status_code=422,
            detail=(
                "This report contains prohibited content. Lost and found reports "
                "cannot include sexual, drug, or weapon-related content."
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
                f"Your account is BLOCKED after {strike}/{limit} prohibited "
                "content attempts. Contact an administrator."
            ),
        )
    raise HTTPException(
        status_code=422,
        detail=(
            "Prohibited content detected (sexual, drugs, or weapons). "
            f"Report was NOT posted. Warning {strike}/{limit} — "
            "your account will be blocked after 3 attempts."
        ),
    )
