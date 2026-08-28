/** Thin admin API client — vault URLs / contacts only via admin endpoints. */

const TOKEN_KEY = "verifind_admin_token";

export type ReviewItem = {
  claim_attempt_id: string;
  verification_session_id?: string | null;
  match_id: string;
  claimant_id: string;
  claimant_email?: string | null;
  status: string;
  risk_score?: number | null;
  fraud_risk?: number | null;
  overall_score?: number | null;
  decision?: string | null;
  found_report_title?: string | null;
  created_at?: string | null;
};

export type ReviewDetail = ReviewItem & {
  claimant_emergency_contact?: string | null;
  questions: Array<Record<string, unknown>>;
  answers: string[];
  semantic_scores: number[];
  vault_features?: Record<string, unknown> | null;
  public_image_url?: string | null;
  vault_image_url?: string | null;
  found_report_id?: string | null;
  lost_report_id?: string | null;
  owner_email?: string | null;
  owner_emergency_contact?: string | null;
  completed_at?: string | null;
};

export type Overview = {
  reports: number;
  users: number;
  pending_reviews: number;
  open_suggestions: number;
  flagged_reports: number;
  blocked_users: number;
  pending_match_approvals: number;
  open_moderation: number;
  successful_handovers: number;
  closed_reports: number;
};

export type AdminReport = {
  report_id: string;
  report_type: string;
  title?: string | null;
  category?: string | null;
  status: string;
  user_id: string;
  user_email?: string | null;
  emergency_contact?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  description?: string | null;
  location_label?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  public_image_urls?: string[];
};

export type ReportListQuery = {
  search?: string;
  status?: string;
  reportType?: string;
  category?: string;
};

export type AdminUser = {
  user_id: string;
  email: string;
  display_name?: string | null;
  emergency_contact?: string | null;
  role: string;
  is_active: boolean;
  trust_score?: number | null;
  fail_count: number;
  content_strike_count: number;
  reports_count: number;
  created_at?: string | null;
};

export type Suggestion = {
  match_id: string;
  report_a_id: string;
  report_b_id: string;
  lost_title?: string | null;
  found_title?: string | null;
  score: number;
  band: string;
  notified: boolean;
  admin_status: string;
  created_at?: string | null;
};

export type ModerationEvent = {
  event_id: string;
  user_id: string;
  user_email?: string | null;
  emergency_contact?: string | null;
  kind: string;
  source?: string | null;
  snippet?: string | null;
  strike_number?: number | null;
  report_id?: string | null;
  match_id?: string | null;
  resolved: boolean;
  meta: Record<string, unknown>;
  created_at?: string | null;
};

export type AuditLog = {
  audit_id: string;
  actor_id?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  meta: Record<string, unknown>;
  created_at?: string | null;
};

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY) || "dev";
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = await parse<{ access_token: string; role: string }>(res);
  localStorage.setItem(TOKEN_KEY, body.access_token);
  return body.access_token;
}

async function get<T>(path: string): Promise<T> {
  return parse<T>(await fetch(path, { headers: authHeaders() }));
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  return parse<T>(
    await fetch(path, {
      method: "POST",
      headers: authHeaders(),
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  );
}

export async function listReviews(): Promise<ReviewItem[]> {
  const body = await get<{ items: ReviewItem[] }>("/api/v1/admin/reviews");
  return body.items;
}

export async function getReview(id: string): Promise<ReviewDetail> {
  return get<ReviewDetail>(`/api/v1/admin/reviews/${id}`);
}

export async function decideReview(
  id: string,
  decision: "PASS" | "BLOCK",
  note?: string
): Promise<{ decision: string; status: string; chat_room_id?: string | null; message: string }> {
  return post(`/api/v1/admin/reviews/${id}/decide`, { decision, note: note || null });
}

export async function getOverview(): Promise<Overview> {
  return get<Overview>("/api/v1/admin/overview");
}

export async function listAdminReports(query: string | ReportListQuery = ""): Promise<AdminReport[]> {
  const q: ReportListQuery = typeof query === "string" ? { search: query } : query;
  const params = new URLSearchParams({ limit: "200" });
  if (q.search) params.set("search", q.search);
  if (q.status) params.set("status", q.status);
  if (q.reportType) params.set("report_type", q.reportType);
  if (q.category) params.set("category", q.category);
  const body = await get<{ items: AdminReport[] }>(`/api/v1/admin/reports?${params}`);
  return body.items;
}

export async function resolveReport(
  reportId: string,
  action: "approve" | "quarantine" | "remove",
  note?: string
): Promise<{ status: string; message: string }> {
  return post(`/api/v1/admin/reports/${reportId}/resolve`, { action, note: note || null });
}

export async function listAdminUsers(search = ""): Promise<AdminUser[]> {
  const body = await get<{ items: AdminUser[] }>(
    `/api/v1/admin/users?limit=100&search=${encodeURIComponent(search)}`
  );
  return body.items;
}

export async function blockUser(userId: string, reason: string): Promise<void> {
  await post(`/api/v1/admin/users/${userId}/block`, { reason });
}

export async function unblockUser(userId: string, reason: string): Promise<void> {
  await post(`/api/v1/admin/users/${userId}/unblock`, { reason });
}

export async function revealContact(
  userId: string,
  reason: string
): Promise<{ emergency_contact?: string | null; email: string }> {
  return post(`/api/v1/admin/users/${userId}/reveal-contact`, { reason });
}

export async function listSuggestions(): Promise<Suggestion[]> {
  const body = await get<{ items: Suggestion[] }>("/api/v1/admin/suggestions?limit=100");
  return body.items;
}

export async function decideMatch(
  matchId: string,
  decision: "PASS" | "REJECT",
  note?: string
): Promise<{ admin_status: string; message: string }> {
  return post(`/api/v1/admin/suggestions/${matchId}/decide`, { decision, note: note || null });
}

export async function listModeration(openOnly = true): Promise<ModerationEvent[]> {
  const body = await get<{ items: ModerationEvent[] }>(
    `/api/v1/admin/moderation?open_only=${openOnly}&limit=100`
  );
  return body.items;
}

export async function resolveModeration(eventId: string): Promise<void> {
  await post(`/api/v1/admin/moderation/${eventId}/resolve`);
}

export async function listAuditLogs(): Promise<AuditLog[]> {
  const body = await get<{ items: AuditLog[] }>("/api/v1/admin/audit-logs?limit=100");
  return body.items;
}

export async function downloadExport(
  kind: "lost" | "found" | "handovers" | "all",
  ids?: string[]
): Promise<void> {
  const params = new URLSearchParams({ kind });
  if (ids && ids.length > 0) {
    params.set("ids", ids.join(","));
  }
  const res = await fetch(`/api/v1/admin/export?${params}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^"]+)"?/i.exec(cd);
  const filename = match?.[1] || `verifind_${kind}.csv`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
