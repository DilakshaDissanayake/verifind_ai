"""API schemas — Sprint 1–6."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class HealthResponse(BaseModel):
    status: str
    service: str = "VERIFIND AI"
    version: str = "0.6.0-sprint6"
    uptime_seconds: float
    components: dict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=120)
    emergency_contact: Optional[str] = Field(default=None, min_length=7, max_length=30)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str = "user"
    mode: Literal["supabase", "dev_bypass"] = "dev_bypass"


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    access_token: Optional[str] = None
    token_type: str = "bearer"
    role: str = "user"
    mode: Literal["supabase", "dev_bypass"] = "supabase"
    message: str = "Account created"
    requires_email_confirmation: bool = False


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ResendVerificationResponse(BaseModel):
    message: str = "Verification email sent"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str = "If that email is registered, a password reset link was sent"


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class ChangePasswordResponse(BaseModel):
    message: str = "Password updated"


class MeResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    lost_count: int = 0
    found_count: int = 0
    active_chats: int = 0


class LocationPingRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationPingResponse(BaseModel):
    ok: bool = True


class ReportCreateRequest(BaseModel):
    report_type: Literal["LOST", "FOUND"]
    category: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    location_label: Optional[str] = None
    # Client may already fuzz; server still re-fuzzes unless False (tests)
    client_fuzzed: bool = False
    # Finder selected an existing LOST post — score against it after AI
    matched_to_report_id: Optional[UUID] = None


class ReportCreateResponse(BaseModel):
    report_id: UUID
    status: str = "pending"
    message: str = "Accepted for AI processing"
    job_enqueued: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    matched_to_report_id: Optional[UUID] = None


class ReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[
        Literal["pending", "processing", "active", "matched", "closed", "flagged"]
    ] = None


class ReportCloseRequest(BaseModel):
    """Owner takes a listing off public feeds. Never hard-deletes (audit / fraud)."""

    reason: Literal["self_found", "withdrawn"] = "self_found"


class ReportCloseResponse(BaseModel):
    report_id: UUID
    status: str
    reason: str
    already_closed: bool = False
    chats_closed: int = 0
    message: str = ""


class ReportOut(BaseModel):
    report_id: UUID
    report_type: Literal["LOST", "FOUND"]
    category: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_label: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReportListResponse(BaseModel):
    items: list[ReportOut]
    count: int


class NearbyHitOut(BaseModel):
    report_id: UUID
    report_type: Literal["LOST", "FOUND"]
    category: Optional[str] = None
    title: Optional[str] = None
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_m: float
    location_label: Optional[str] = None
    # Sanitized public URLs only — never vault paths
    image_urls: list[str] = []
    # When viewer already claimed / is in PASS chat for this report
    claim_status: Optional[str] = None
    verification_decision: Optional[str] = None
    chat_room_id: Optional[UUID] = None


class NearbyResponse(BaseModel):
    items: list[NearbyHitOut]
    count: int
    radius_m: int
    query_lat: float
    query_lon: float


class ReportImageOut(BaseModel):
    image_id: UUID
    report_id: UUID
    public_path: Optional[str] = None
    content_type: Optional[str] = None
    is_primary: bool = False
    # Sanitized EXIF only — never GPS / serials / vault paths
    exif: Optional[dict[str, Any]] = None
    has_vault: bool = True
    message: str = "Original stored in private vault; public blur in Sprint 4"


class AITagsOut(BaseModel):
    tag_id: Optional[UUID] = None
    brand: Optional[str] = None
    colors: list[str] = []
    category: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None
    mask_boxes: Optional[list[dict[str, Any]]] = None
    model: Optional[str] = None
    created_at: Optional[datetime] = None


class AIStatusResponse(BaseModel):
    report_id: UUID
    status: str
    has_embedding: bool = False
    tags: Optional[AITagsOut] = None
    sprint: str = "6"


# ---------------------------------------------------------------------------
# Sprint 4 — Matches + Notifications
# ---------------------------------------------------------------------------

class MatchOut(BaseModel):
    match_id: UUID
    report_a_id: UUID
    report_b_id: UUID
    score: float
    band: Literal["HIGH", "MEDIUM", "LOW"]
    vision_score: float = 0.0
    text_score: float = 0.0
    geo_score: float = 0.0
    category_score: float = 0.0
    distance_m: Optional[float] = None
    notified: bool = False
    created_at: Optional[datetime] = None
    # Claim / admin outcome — when PASS, client shows Open Chat (no re-claim)
    claim_status: Optional[str] = None
    verification_decision: Optional[str] = None
    chat_room_id: Optional[UUID] = None


class MatchesResponse(BaseModel):
    items: list[MatchOut]
    count: int
    report_id: UUID


class NotificationOut(BaseModel):
    notification_id: UUID
    type: str = "match_found"
    match_id: Optional[UUID] = None
    report_id: Optional[UUID] = None
    matched_report_id: Optional[UUID] = None
    band: Optional[str] = None
    score: Optional[float] = None
    distance_m: Optional[float] = None
    chat_room_id: Optional[UUID] = None
    preview: Optional[str] = None
    is_read: bool = False
    created_at: Optional[datetime] = None


class NotificationsResponse(BaseModel):
    items: list[NotificationOut]
    count: int
    unread_count: int


# ---------------------------------------------------------------------------
# Sprint 5 — Claims + Verification + Chat
# ---------------------------------------------------------------------------

class ClaimStartRequest(BaseModel):
    match_id: UUID
    found_report_id: UUID


class VerificationQuestion(BaseModel):
    question_id: str
    question: str


class ClaimStartResponse(BaseModel):
    allowed: bool
    reason: str = "OK"
    claim_attempt_id: Optional[UUID] = None
    verification_session_id: Optional[UUID] = None
    questions: list[VerificationQuestion] = []


class AnswerSubmitRequest(BaseModel):
    claim_attempt_id: UUID
    answers: list[str] = Field(min_length=1, max_length=10)


class VerificationResultResponse(BaseModel):
    decision: Literal["PASS", "REVIEW", "BLOCK"]
    overall_score: float
    semantic_scores: list[float] = []
    chat_room_id: Optional[UUID] = None
    claim_attempt_id: UUID
    verification_session_id: UUID
    message: str = ""


class ClaimStatusOut(BaseModel):
    claim_attempt_id: UUID
    match_id: UUID
    status: str
    decision: Optional[str] = None
    risk_score: Optional[float] = None
    fraud_risk: Optional[float] = None
    chat_room_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


# Chat

class ChatRoomOut(BaseModel):
    room_id: UUID
    match_id: UUID
    owner_id: UUID
    finder_id: UUID
    is_active: bool = True
    created_at: Optional[datetime] = None
    # Claim-named room + match context for UI
    title: Optional[str] = None
    lost_title: Optional[str] = None
    found_title: Optional[str] = None
    match_score: Optional[float] = None
    match_band: Optional[str] = None
    viewer_id: Optional[UUID] = None


class ChatRoomListResponse(BaseModel):
    items: list[ChatRoomOut]
    count: int


class HandoverCompleteResponse(BaseModel):
    room_id: UUID
    match_id: UUID
    already_complete: bool = False
    message: str = ""


class ChatMessageOut(BaseModel):
    message_id: UUID
    room_id: UUID
    sender_id: UUID
    body: str
    created_at: Optional[datetime] = None
    message_type: Literal["text", "image", "voice", "system"] = "text"
    media_url: Optional[str] = None
    is_mine: bool = False


class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ChatHistoryResponse(BaseModel):
    room_id: UUID
    messages: list[ChatMessageOut]
    count: int
    viewer_id: Optional[UUID] = None
    title: Optional[str] = None


# ---------------------------------------------------------------------------
# Sprint 6 — Admin REVIEW queue
# ---------------------------------------------------------------------------

class AdminReviewItemOut(BaseModel):
    claim_attempt_id: UUID
    verification_session_id: Optional[UUID] = None
    match_id: UUID
    claimant_id: UUID
    claimant_email: Optional[str] = None
    status: str
    risk_score: Optional[float] = None
    fraud_risk: Optional[float] = None
    overall_score: Optional[float] = None
    decision: Optional[str] = None
    found_report_title: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminReviewListResponse(BaseModel):
    items: list[AdminReviewItemOut]
    count: int


class AdminReviewDetailOut(BaseModel):
    claim_attempt_id: UUID
    verification_session_id: Optional[UUID] = None
    match_id: UUID
    claimant_id: UUID
    claimant_email: Optional[str] = None
    claimant_emergency_contact: Optional[str] = None
    status: str
    risk_score: Optional[float] = None
    fraud_risk: Optional[float] = None
    overall_score: Optional[float] = None
    decision: Optional[str] = None
    questions: list[dict[str, Any]] = []
    answers: list[str] = []
    semantic_scores: list[float] = []
    # Admin-only — never on public claim APIs
    vault_features: Optional[dict[str, Any]] = None
    public_image_url: Optional[str] = None
    vault_image_url: Optional[str] = None
    found_report_id: Optional[UUID] = None
    lost_report_id: Optional[UUID] = None
    found_report_title: Optional[str] = None
    owner_email: Optional[str] = None
    owner_emergency_contact: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AdminDecideRequest(BaseModel):
    decision: Literal["PASS", "BLOCK"]
    note: Optional[str] = Field(default=None, max_length=1000)


class AdminDecideResponse(BaseModel):
    claim_attempt_id: UUID
    decision: Literal["PASS", "BLOCK"]
    status: str
    chat_room_id: Optional[UUID] = None
    message: str = ""


class AdminOverviewOut(BaseModel):
    reports: int = 0
    users: int = 0
    pending_reviews: int = 0
    open_suggestions: int = 0
    flagged_reports: int = 0
    blocked_users: int = 0
    pending_match_approvals: int = 0
    open_moderation: int = 0
    successful_handovers: int = 0
    closed_reports: int = 0


class AdminReportOut(BaseModel):
    report_id: UUID
    report_type: str
    title: Optional[str] = None
    category: Optional[str] = None
    status: str
    user_id: UUID
    user_email: Optional[str] = None
    emergency_contact: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    description: Optional[str] = None
    location_label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    public_image_urls: list[str] = []


class AdminReportListResponse(BaseModel):
    items: list[AdminReportOut]
    count: int


class AdminReportResolveRequest(BaseModel):
    action: Literal["approve", "quarantine", "remove"]
    note: Optional[str] = Field(default=None, max_length=500)


class AdminReportResolveResponse(BaseModel):
    report_id: UUID
    status: str
    message: str = ""


class AdminUserOut(BaseModel):
    user_id: UUID
    email: str
    display_name: Optional[str] = None
    emergency_contact: Optional[str] = None
    role: str
    is_active: bool
    trust_score: Optional[float] = None
    fail_count: int = 0
    content_strike_count: int = 0
    reports_count: int = 0
    created_at: Optional[datetime] = None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserOut]
    count: int


class AdminUserBlockRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class AdminUserBlockResponse(BaseModel):
    user_id: UUID
    is_active: bool
    message: str = ""


class AdminContactRevealRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class AdminContactRevealResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: Optional[str] = None
    emergency_contact: Optional[str] = None
    is_active: bool
    message: str = "Contact revealed — action audited."


class AdminSuggestionOut(BaseModel):
    match_id: UUID
    report_a_id: UUID
    report_b_id: UUID
    lost_title: Optional[str] = None
    found_title: Optional[str] = None
    score: float
    band: str
    notified: bool = False
    admin_status: str = "pending"
    created_at: Optional[datetime] = None


class AdminSuggestionListResponse(BaseModel):
    items: list[AdminSuggestionOut]
    count: int


class AdminMatchDecideRequest(BaseModel):
    decision: Literal["PASS", "REJECT"]
    note: Optional[str] = Field(default=None, max_length=500)


class AdminMatchDecideResponse(BaseModel):
    match_id: UUID
    admin_status: str
    decision: Literal["PASS", "REJECT"]
    message: str = ""


class AdminModerationEventOut(BaseModel):
    event_id: UUID
    user_id: UUID
    user_email: Optional[str] = None
    emergency_contact: Optional[str] = None
    kind: str
    source: Optional[str] = None
    snippet: Optional[str] = None
    strike_number: Optional[int] = None
    report_id: Optional[UUID] = None
    match_id: Optional[UUID] = None
    resolved: bool = False
    meta: dict[str, Any] = {}
    created_at: Optional[datetime] = None


class AdminModerationListResponse(BaseModel):
    items: list[AdminModerationEventOut]
    count: int


class AdminAuditLogOut(BaseModel):
    audit_id: UUID
    actor_id: Optional[UUID] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    meta: dict[str, Any] = {}
    created_at: Optional[datetime] = None


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogOut]
    count: int
