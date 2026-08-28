import { useCallback, useEffect, useRef, useState } from "react";
import {
  blockUser, clearToken, decideMatch, decideReview, downloadExport, getOverview, getReview,
  getStoredToken, listAdminReports, listAdminUsers, listAuditLogs, listModeration,
  listReviews, listSuggestions, login, resolveModeration, resolveReport,
  revealContact, unblockUser,
  type AdminReport, type AdminUser, type AuditLog, type ModerationEvent,
  type Overview, type ReviewDetail, type ReviewItem, type Suggestion,
} from "./api";
import ReportsBoard from "./ReportsBoard";

type Page =
  | "overview" | "reports" | "users" | "suggestions"
  | "reviews" | "moderation" | "records";

const nav: Array<[Page, string, string]> = [
  ["overview", "Overview", "⌂"],
  ["reviews", "Review queue", "!"],
  ["suggestions", "Matches", "✦"],
  ["moderation", "Safety", "⚠"],
  ["reports", "Reports", "▤"],
  ["users", "People", "◎"],
  ["records", "Records", "▥"],
];

const date = (value?: string | null) =>
  value ? new Date(value).toLocaleString() : "—";
const title = (page: Page) => nav.find(([key]) => key === page)?.[1] || "Overview";
const relativeTime = (value: Date | null) => {
  if (!value) return "Awaiting sync";
  const sec = Math.max(0, Math.round((Date.now() - value.getTime()) / 1000));
  if (sec < 8) return "Just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  return value.toLocaleTimeString();
};

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [loggedIn, setLoggedIn] = useState(Boolean(getStoredToken()));
  const [overview, setOverview] = useState<Overview | null>(null);
  const [reports, setReports] = useState<AdminReport[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [moderation, setModeration] = useState<ModerationEvent[]>([]);
  const [records, setRecords] = useState<AuditLog[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Ready");
  const [busyAction, setBusyAction] = useState(false);
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const [tick, setTick] = useState(0);
  const [email, setEmail] = useState("admin@gmail.com");
  const [password, setPassword] = useState("");
  const noticeTimer = useRef<number | null>(null);

  function flashNotice(msg: string) {
    setNotice(msg);
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(null), 4200);
  }

  async function withLoad<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    setBusyAction(true);
    setLoading(true);
    setLoadingLabel(label);
    setError(null);
    try {
      const result = await fn();
      setLastSynced(new Date());
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setBusyAction(false);
      setLoading(false);
      setLoadingLabel("Ready");
    }
  }

  const load = useCallback(async () => {
    setLoading(true);
    setLoadingLabel(
      page === "overview"
        ? "Refreshing network metrics…"
        : page === "reviews"
          ? "Loading fraud review queue…"
          : page === "suggestions"
            ? "Loading match approvals…"
            : page === "moderation"
              ? "Loading safety events…"
              : page === "reports"
                ? "Loading reports…"
                : page === "users"
                  ? "Loading people…"
                  : "Loading audit records…"
    );
    setError(null);
    try {
      const ov = await getOverview();
      setOverview(ov);
      if (page === "reports") setReports(await listAdminReports(search));
      if (page === "users") setUsers(await listAdminUsers(search));
      if (page === "suggestions") setSuggestions(await listSuggestions());
      if (page === "moderation") setModeration(await listModeration(true));
      if (page === "records") setRecords(await listAuditLogs());
      if (page === "reviews") setReviews(await listReviews());
      setLastSynced(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      setLoadingLabel("Ready");
    }
  }, [page, search]);

  useEffect(() => {
    if (loggedIn) void load();
  }, [loggedIn, load]);

  // Debounce search so typing does not hammer the API
  useEffect(() => {
    const t = window.setTimeout(() => setSearch(searchInput.trim()), 320);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    const t = window.setInterval(() => setTick((n) => n + 1), 15000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    if (!detail) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busyAction) setDetail(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [detail, busyAction]);

  // silence unused tick lint — drives relativeTime re-render
  void tick;

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    await withLoad("Signing in to control room…", async () => {
      await login(email, password);
      setLoggedIn(true);
    });
  }

  async function openReview(id: string) {
    await withLoad("Opening claim evidence (vault + public)…", async () => {
      setDetail(await getReview(id));
    });
  }

  async function decide(decision: "PASS" | "BLOCK") {
    if (!detail) return;
    if (decision === "BLOCK" && !window.confirm("Block this claim and apply a trust penalty?")) return;
    await withLoad(
      decision === "PASS"
        ? "Approving claim and provisioning chat…"
        : "Blocking claim and applying trust penalty…",
      async () => {
        await decideReview(detail.claim_attempt_id, decision, "Admin dashboard decision");
        setDetail(null);
        flashNotice(decision === "PASS" ? "Claim approved — chat opened." : "Claim blocked.");
        await load();
      }
    );
  }

  async function onDecideMatch(id: string, decision: "PASS" | "REJECT") {
    const note = window.prompt(
      decision === "PASS" ? "Optional note for approve:" : "Why reject this match?",
      decision === "PASS" ? "Approved" : "False positive"
    );
    if (note === null) return;
    await withLoad(
      decision === "PASS" ? "Approving match for users…" : "Rejecting match (hide from feeds)…",
      async () => {
        const res = await decideMatch(id, decision, note);
        flashNotice(res.message);
        await load();
      }
    );
  }

  async function onBlockUser(u: AdminUser, active: boolean) {
    const reason = window.prompt(
      active ? "Reason to unblock:" : "Reason to block this user:",
      active ? "Appeal accepted" : "Policy violation"
    );
    if (!reason) return;
    await withLoad(active ? "Unblocking account…" : "Blocking account…", async () => {
      if (active) await unblockUser(u.user_id, reason);
      else await blockUser(u.user_id, reason);
      flashNotice(active ? "User unblocked." : "User blocked.");
      await load();
    });
  }

  async function onRevealContact(userId: string) {
    const reason = window.prompt(
      "Safety reason required to view emergency contact (audited):",
      "Issue investigation"
    );
    if (!reason || reason.trim().length < 3) return;
    await withLoad("Revealing emergency contact (audited)…", async () => {
      const res = await revealContact(userId, reason.trim());
      flashNotice(`Contact for ${res.email}: ${res.emergency_contact || "Not provided"}`);
      await load();
    });
  }

  async function onResolveReport(id: string, action: "approve" | "quarantine" | "remove") {
    await withLoad(`Updating report (${action})…`, async () => {
      const res = await resolveReport(id, action);
      flashNotice(res.message);
      await load();
    });
  }

  async function onResolveModeration(id: string) {
    await withLoad("Marking safety event resolved…", async () => {
      await resolveModeration(id);
      flashNotice("Moderation event marked resolved.");
      await load();
    });
  }

  async function onExport(
    kind: "lost" | "found" | "handovers" | "all",
    ids?: string[]
  ) {
    const scoped = ids && ids.length > 0;
    await withLoad(
      scoped ? `Exporting ${ids.length} selected (${kind})…` : `Exporting ${kind} CSV…`,
      async () => {
        await downloadExport(kind, scoped ? ids : undefined);
        flashNotice(
          scoped
            ? `Downloaded ${kind} export (${ids.length} selected).`
            : `Downloaded full ${kind} export.`
        );
      }
    );
  }

  if (!loggedIn) {
    return (
      <Login
        email={email}
        setEmail={setEmail}
        password={password}
        setPassword={setPassword}
        loading={loading}
        error={error}
        onLogin={onLogin}
      />
    );
  }

  return (
    <div className={`admin-frame${loading ? " is-busy" : ""}`}>
      {loading && <div className="progress-rail" aria-hidden />}
      <aside className="sidebar">
        <div className="logo">
          <img className="logo-mark-img" src="/logo.png" alt="VERIFIND" width={34} height={34} />
          <div>
            VERIFIND
            <small>CONTROL ROOM</small>
          </div>
        </div>
        <div className="workspace">
          <span className={`status-dot${loading ? " pulse" : ""}`} />{" "}
          {loading ? "Syncing…" : "Live workspace"}
        </div>
        <nav aria-label="Control room">
          {nav.map(([key, label, icon]) => {
            const count =
              key === "reviews"
                ? overview?.pending_reviews
                : key === "suggestions"
                  ? overview?.pending_match_approvals
                  : key === "moderation"
                    ? overview?.open_moderation
                    : 0;
            return (
              <button
                key={key}
                type="button"
                className={page === key ? "nav-item active" : "nav-item"}
                aria-current={page === key ? "page" : undefined}
                onClick={() => {
                  setPage(key);
                  setDetail(null);
                  setSearchInput("");
                  setSearch("");
                }}
              >
                <b aria-hidden>{icon}</b>
                <span className="nav-label">{label}</span>
                {count ? <span className="nav-count">{count}</span> : null}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="privacy-note">
            ◈ Private moderation surface
            <br />
            <span>Contacts & vault access are audited</span>
          </div>
          <button
            type="button"
            className="signout"
            onClick={() => {
              clearToken();
              setLoggedIn(false);
            }}
          >
            Sign out ↗
          </button>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="eyebrow">Operations / {title(page)}</span>
            <h1>{detail ? "Claim evidence" : title(page)}</h1>
          </div>
          <div className="top-actions">
            <div className="sync-chip" title={lastSynced ? lastSynced.toLocaleString() : "Not synced yet"}>
              <span className={`sync-dot${loading ? " on" : ""}`} />
              {loading ? loadingLabel : relativeTime(lastSynced)}
            </div>
            <button
              type="button"
              className="icon-button"
              disabled={loading}
              onClick={() => void load()}
              aria-label="Refresh data"
              title="Refresh"
            >
              {loading ? "…" : "↻"}
            </button>
            <div className="admin-avatar" title="Administrator">A</div>
          </div>
        </header>
        {busyAction && (
          <div className="process-banner" role="status">
            <span className="spinner" />
            <div>
              <strong>Working on it</strong>
              <p>{loadingLabel}</p>
            </div>
          </div>
        )}
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button type="button" aria-label="Dismiss error" onClick={() => setError(null)}>×</button>
          </div>
        )}
        {notice && (
          <div className="notice-banner" role="status">
            <span>{notice}</span>
            <button type="button" aria-label="Dismiss notice" onClick={() => setNotice(null)}>×</button>
          </div>
        )}
        {detail ? (
          <ReviewDetailView
            detail={detail}
            loading={busyAction}
            loadingLabel={loadingLabel}
            onBack={() => setDetail(null)}
            onDecide={decide}
          />
        ) : (
          <PageView
            page={page}
            overview={overview}
            reports={reports}
            users={users}
            suggestions={suggestions}
            moderation={moderation}
            records={records}
            reviews={reviews}
            search={searchInput}
            setSearch={setSearchInput}
            loading={loading}
            loadingLabel={loadingLabel}
            openReview={openReview}
            onDecideMatch={onDecideMatch}
            onBlockUser={onBlockUser}
            onRevealContact={onRevealContact}
            onResolveReport={onResolveReport}
            onResolveModeration={onResolveModeration}
            onExport={onExport}
            go={(p) => {
              setPage(p);
              setSearchInput("");
              setSearch("");
            }}
          />
        )}
      </main>
    </div>
  );
}

function Login(props: {
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  loading: boolean;
  error: string | null;
  onLogin: (e: React.FormEvent) => void;
}) {
  const [showPw, setShowPw] = useState(false);
  return (
    <div className="login-screen">
      <div className="login-art">
        <img src="/logo.png" alt="VERIFIND" width={88} height={88} />
        <p>
          Trust, with
          <br />
          <strong>evidence.</strong>
        </p>
        <ul className="login-points">
          <li>Fraud review with vault vs public</li>
          <li>Match approvals before users see them</li>
          <li>Audited contact reveals</li>
        </ul>
      </div>
      <form className="login-card" onSubmit={props.onLogin}>
        <div className="logo">
          <img className="logo-mark-img" src="/logo.png" alt="VERIFIND" width={34} height={34} />
          <div>
            VERIFIND
            <small>CONTROL ROOM</small>
          </div>
        </div>
        <span className="eyebrow">Secure administrator access</span>
        <h1>Good to see you.</h1>
        <p className="muted">
          Approve matches, review claims, enforce content safety, and contact users only when an
          issue requires it.
        </p>
        {props.error && <div className="error-banner" role="alert">{props.error}</div>}
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={props.email}
            onChange={(e) => props.setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <div className="password-field">
            <input
              type={showPw ? "text" : "password"}
              autoComplete="current-password"
              value={props.password}
              onChange={(e) => props.setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              className="ghost-toggle"
              onClick={() => setShowPw((v) => !v)}
              aria-label={showPw ? "Hide password" : "Show password"}
            >
              {showPw ? "Hide" : "Show"}
            </button>
          </div>
        </label>
        <button className="primary-button" disabled={props.loading}>
          {props.loading ? "Signing in…" : "Enter control room →"}
        </button>
        {props.loading && (
          <p className="muted login-hint">Verifying administrator credentials…</p>
        )}
      </form>
    </div>
  );
}

type PageProps = {
  page: Page;
  overview: Overview | null;
  reports: AdminReport[];
  users: AdminUser[];
  suggestions: Suggestion[];
  moderation: ModerationEvent[];
  records: AuditLog[];
  reviews: ReviewItem[];
  search: string;
  setSearch: (v: string) => void;
  loading: boolean;
  loadingLabel: string;
  openReview: (id: string) => void;
  onDecideMatch: (id: string, d: "PASS" | "REJECT") => void;
  onBlockUser: (u: AdminUser, currentlyActive: boolean) => void;
  onRevealContact: (userId: string) => void;
  onResolveReport: (id: string, action: "approve" | "quarantine" | "remove") => void;
  onResolveModeration: (id: string) => void;
  onExport: (kind: "lost" | "found" | "handovers" | "all", ids?: string[]) => void;
  go: (p: Page) => void;
};

function PageView(p: PageProps) {
  if (p.page === "overview") {
    return p.loading && !p.overview ? (
      <SkeletonBoard label={p.loadingLabel} />
    ) : (
      <OverviewPage data={p.overview} go={p.go} onExport={p.onExport} />
    );
  }
  const common = (
    <div className="page-toolbar">
      <div className="search-box">
        <span aria-hidden>⌕</span>
        <input
          placeholder={`Search ${p.page}…`}
          value={p.search}
          disabled={p.loading}
          onChange={(e) => p.setSearch(e.target.value)}
          aria-label={`Search ${p.page}`}
        />
        {p.search ? (
          <button
            type="button"
            className="clear-search"
            aria-label="Clear search"
            onClick={() => p.setSearch("")}
          >
            ×
          </button>
        ) : null}
      </div>
      <span className="result-count">
        {p.loading
          ? p.loadingLabel
          : p.page === "reports"
            ? `${p.reports.length} report${p.reports.length === 1 ? "" : "s"}`
            : p.page === "users"
              ? `${p.users.length} people`
              : "Updated"}
      </span>
    </div>
  );
  if (p.page === "reports") {
    return (
      <>
        <SectionIntro
          kicker="Community activity"
          heading="Lost & found board"
          copy="Smart list or map of every report. Filter by type, status, and category. Photos are sanitized public images only — vault originals stay in the fraud queue."
        />
        {common}
        {p.loading && !p.reports.length ? (
          <SkeletonBoard label={p.loadingLabel} />
        ) : (
          <ReportsBoard
            rows={p.reports}
            busy={p.loading}
            onResolve={p.onResolveReport}
            onReveal={p.onRevealContact}
            onExport={p.onExport}
          />
        )}
      </>
    );
  }
  if (p.page === "users") {
    return (
      <>
        <SectionIntro
          kicker="Trust network"
          heading="People"
          copy="Block after policy abuse. Reveal emergency numbers only for active issues (audited)."
        />
        {common}
        {p.loading && !p.users.length ? (
          <SkeletonBoard label={p.loadingLabel} />
        ) : (
          <UserTable
            rows={p.users}
            busy={p.loading}
            onBlock={p.onBlockUser}
            onReveal={p.onRevealContact}
          />
        )}
      </>
    );
  }
  if (p.page === "suggestions") {
    return (
      <>
        <SectionIntro
          kicker="AI matching"
          heading="Match approvals"
          copy="Pass genuine pairs. Reject false positives so they never reach users."
        />
        {p.loading && !p.suggestions.length ? (
          <SkeletonBoard label={p.loadingLabel} />
        ) : (
          <SuggestionTable rows={p.suggestions} busy={p.loading} onDecide={p.onDecideMatch} />
        )}
      </>
    );
  }
  if (p.page === "moderation") {
    return (
      <>
        <SectionIntro
          kicker="Content safety"
          heading="Prohibited content & strikes"
          copy="Sexual or drug-related posts never publish. 3 strikes auto-block the account — review here."
        />
        {p.loading && !p.moderation.length ? (
          <SkeletonBoard label={p.loadingLabel} />
        ) : (
          <ModerationTable
            rows={p.moderation}
            busy={p.loading}
            onResolve={p.onResolveModeration}
            onReveal={p.onRevealContact}
          />
        )}
      </>
    );
  }
  if (p.page === "records") {
    return (
      <>
        <SectionIntro
          kicker="Accountability"
          heading="Moderation records"
          copy="A durable trail of decisions, contact reveals, and blocks."
        />
        {p.loading && !p.records.length ? (
          <SkeletonBoard label={p.loadingLabel} />
        ) : (
          <AuditTable rows={p.records} />
        )}
      </>
    );
  }
  return (
    <>
      <SectionIntro
        kicker="Safety desk"
        heading="Fraud review queue"
        copy="Medium-risk claims need a human PASS or BLOCK before chat opens."
      />
      {p.loading && !p.reviews.length ? (
        <SkeletonBoard label={p.loadingLabel} />
      ) : (
        <ReviewTable rows={p.reviews} busy={p.loading} openReview={p.openReview} />
      )}
    </>
  );
}

function SkeletonBoard({ label }: { label: string }) {
  return (
    <div className="surface-panel skeleton-board" aria-busy>
      <div className="skeleton-head">
        <span className="spinner" />
        <div>
          <strong>Loading details</strong>
          <p>{label}</p>
        </div>
      </div>
      {[0, 1, 2, 3].map((i) => (
        <div className="skeleton-row" key={i}>
          <i />
          <i />
          <i />
          <i />
        </div>
      ))}
    </div>
  );
}

function OverviewPage({
  data,
  go,
  onExport,
}: {
  data: Overview | null;
  go: (p: Page) => void;
  onExport: (kind: "lost" | "found" | "handovers" | "all") => void;
}) {
  const pending =
    (data?.pending_reviews ?? 0) +
    (data?.pending_match_approvals ?? 0) +
    (data?.open_moderation ?? 0);
  const attentionOk = pending === 0;

  const cards: Array<{
    label: string;
    value: number;
    hint: string;
    target: Page;
    tone?: "alert" | "danger";
  }> = data
    ? [
        { label: "Reports", value: data.reports, hint: "Live network", target: "reports" },
        {
          label: "Fraud queue",
          value: data.pending_reviews,
          hint: "Needs decision",
          target: "reviews",
          tone: data.pending_reviews > 0 ? "alert" : undefined,
        },
        {
          label: "Match pass",
          value: data.pending_match_approvals,
          hint: "Awaiting approve",
          target: "suggestions",
          tone: data.pending_match_approvals > 0 ? "alert" : undefined,
        },
        {
          label: "Safety",
          value: data.open_moderation,
          hint: "Open events",
          target: "moderation",
          tone: data.open_moderation > 0 ? "danger" : undefined,
        },
        {
          label: "Handovers",
          value: data.successful_handovers ?? 0,
          hint: "PASS / success",
          target: "reports",
        },
        {
          label: "Blocked",
          value: data.blocked_users,
          hint: "Accounts",
          target: "users",
          tone: data.blocked_users > 0 ? "danger" : undefined,
        },
      ]
    : [];

  return (
    <>
      <SectionIntro
        kicker="Operations desk"
        heading="Network control room"
        copy="Triage fraud reviews, approve AI matches, moderate safety strikes, and export handover records — without leaving this desk."
      />

      <div className={`attention-bar${attentionOk ? " ok" : ""}`}>
        <div>
          <strong>
            {attentionOk
              ? "All clear — no urgent queues"
              : `${pending} item${pending === 1 ? "" : "s"} need attention`}
          </strong>
          <p>
            {attentionOk
              ? "Fraud, matches, and safety queues are empty."
              : "Jump to the highest-priority queue below."}
          </p>
        </div>
        {!attentionOk && (
          <div className="attention-actions">
            {(data?.pending_reviews ?? 0) > 0 && (
              <button type="button" className="mini-button warn" onClick={() => go("reviews")}>
                Review claims
              </button>
            )}
            {(data?.pending_match_approvals ?? 0) > 0 && (
              <button type="button" className="mini-button warn" onClick={() => go("suggestions")}>
                Approve matches
              </button>
            )}
            {(data?.open_moderation ?? 0) > 0 && (
              <button type="button" className="mini-button danger" onClick={() => go("moderation")}>
                Safety events
              </button>
            )}
          </div>
        )}
      </div>

      <div className="metric-grid metric-grid-6">
        {cards.map((c) => (
          <button
            type="button"
            className={`metric-card metric-card-btn${c.tone ? ` ${c.tone}` : ""}`}
            key={c.label}
            onClick={() => go(c.target)}
          >
            <span>{c.label}</span>
            <strong>{c.value}</strong>
            <small>{c.hint}</small>
          </button>
        ))}
      </div>

      <div className="overview-grid">
        <div className="surface-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Priority lane</span>
              <h2>Keep the network clean</h2>
            </div>
            <span className="live-pill">
              <i /> LIVE
            </span>
          </div>
          <button type="button" className="priority-row row-button" onClick={() => go("reviews")}>
            <div className="priority-icon amber">!</div>
            <div>
              <strong>{data?.pending_reviews ?? 0} claims need a decision</strong>
              <p>Compare vault vs public before opening chat.</p>
            </div>
            <span className="arrow">→</span>
          </button>
          <button type="button" className="priority-row row-button" onClick={() => go("suggestions")}>
            <div className="priority-icon amber">✦</div>
            <div>
              <strong>{data?.pending_match_approvals ?? 0} matches awaiting pass</strong>
              <p>Approve genuine pairs; reject noise.</p>
            </div>
            <span className="arrow">→</span>
          </button>
          <button type="button" className="priority-row row-button" onClick={() => go("reports")}>
            <div className="priority-icon amber">▤</div>
            <div>
              <strong>
                Export lost / found / {data?.successful_handovers ?? 0} handovers
              </strong>
              <p>CSV includes closed posts after successful handover.</p>
            </div>
            <span className="arrow">→</span>
          </button>
          <button type="button" className="priority-row row-button" onClick={() => go("moderation")}>
            <div className="priority-icon red">⚠</div>
            <div>
              <strong>
                {data?.open_moderation ?? 0} safety events · {data?.blocked_users ?? 0} blocked
              </strong>
              <p>3 prohibited attempts → auto-block. Contact numbers for issues.</p>
            </div>
            <span className="arrow">→</span>
          </button>
        </div>
        <div className="surface-panel tone-panel">
          <span className="eyebrow">Exports & posture</span>
          <h2>Control-room toolkit</h2>
          <p>
            After handover, posts leave the public feed. Admins still export every lost item,
            found item, and successful handover — and keep an audit trail of decisions.
          </p>
          <div className="health-strip">
            <div className="health-pill">
              <span>Closed posts</span>
              <strong>{data?.closed_reports ?? 0}</strong>
            </div>
            <div className="health-pill">
              <span>Open queues</span>
              <strong>{pending}</strong>
            </div>
            <div className="health-pill">
              <span>People</span>
              <strong>{data?.users ?? 0}</strong>
            </div>
          </div>
          <div className="export-stack">
            <button type="button" className="mini-button" onClick={() => onExport("lost")}>
              Lost CSV
            </button>
            <button type="button" className="mini-button" onClick={() => onExport("found")}>
              Found CSV
            </button>
            <button type="button" className="mini-button ok" onClick={() => onExport("handovers")}>
              Handovers CSV
            </button>
            <button type="button" className="mini-button" onClick={() => onExport("all")}>
              Full export
            </button>
          </div>
          <div className="principle-line">◆ Decisions stay reviewable</div>
        </div>
      </div>
    </>
  );
}

function SectionIntro({
  kicker,
  heading,
  copy,
}: {
  kicker: string;
  heading: string;
  copy: string;
}) {
  return (
    <div className="section-intro">
      <span className="eyebrow">{kicker}</span>
      <h2>{heading}</h2>
      <p>{copy}</p>
    </div>
  );
}

function UserTable({
  rows,
  busy,
  onBlock,
  onReveal,
}: {
  rows: AdminUser[];
  busy: boolean;
  onBlock: (u: AdminUser, currentlyActive: boolean) => void;
  onReveal: (userId: string) => void;
}) {
  return (
    <div className={`surface-panel table-panel${busy ? " dimmed" : ""}`}>
      <TableHead labels={["Person", "Strikes", "Trust", "State", "Actions"]} cols="cols-actions" />
      {rows.map((u) => (
        <div className="data-row cols-actions" key={u.user_id}>
          <div>
            <strong>{u.display_name || "Unnamed member"}</strong>
            <small>{u.email}</small>
          </div>
          <span className="score">
            {u.content_strike_count}/3 · fails {u.fail_count}
          </span>
          <span className="trust">
            {u.trust_score == null ? "—" : `${Math.round(u.trust_score * 100)}%`}
          </span>
          <Status value={u.is_active ? "active" : "blocked"} />
          <div className="row-actions">
            <button className="mini-button" disabled={busy} onClick={() => onReveal(u.user_id)}>
              Contact
            </button>
            <button
              className={u.is_active ? "mini-button danger" : "mini-button"}
              disabled={busy}
              onClick={() => onBlock(u, u.is_active)}
            >
              {u.is_active ? "Block" : "Unblock"}
            </button>
          </div>
        </div>
      ))}
      {!rows.length && (
        <Empty text="No users found." hint="Registered members will appear here." />
      )}
    </div>
  );
}

function SuggestionTable({
  rows,
  busy,
  onDecide,
}: {
  rows: Suggestion[];
  busy: boolean;
  onDecide: (id: string, d: "PASS" | "REJECT") => void;
}) {
  return (
    <div className={`surface-panel table-panel${busy ? " dimmed" : ""}`}>
      <TableHead labels={["Pair", "Score", "Band", "Admin", "Actions"]} cols="cols-actions" />
      {rows.map((s) => (
        <div className="data-row cols-actions" key={s.match_id}>
          <div>
            <strong>{s.lost_title || "Lost item"}</strong>
            <small>↔ {s.found_title || "Found item"}</small>
          </div>
          <span className="score">{Math.round(s.score * 100)}%</span>
          <Status value={s.band.toLowerCase()} />
          <Status value={s.admin_status} />
          <div className="row-actions">
            {s.admin_status === "pending" ? (
              <>
                <button className="mini-button ok" disabled={busy} onClick={() => onDecide(s.match_id, "PASS")}>
                  Pass
                </button>
                <button className="mini-button danger" disabled={busy} onClick={() => onDecide(s.match_id, "REJECT")}>
                  Reject
                </button>
              </>
            ) : (
              <span className="muted">{s.notified ? "Notified" : "—"}</span>
            )}
          </div>
        </div>
      ))}
      {!rows.length && (
        <Empty text="No suggestions found." hint="New AI matches awaiting approval show up here." />
      )}
    </div>
  );
}

function ModerationTable({
  rows,
  busy,
  onResolve,
  onReveal,
}: {
  rows: ModerationEvent[];
  busy: boolean;
  onResolve: (id: string) => void;
  onReveal: (userId: string) => void;
}) {
  return (
    <div className={`surface-panel table-panel${busy ? " dimmed" : ""}`}>
      <TableHead labels={["Event", "User / contact", "Strike", "Snippet", "Actions"]} cols="cols-actions" />
      {rows.map((e) => (
        <div className="data-row cols-actions" key={e.event_id}>
          <div>
            <strong>{e.kind.replace(/_/g, " ")}</strong>
            <small>{date(e.created_at)}</small>
          </div>
          <div>
            <strong>{e.user_email || e.user_id.slice(0, 8)}</strong>
            <small>{e.emergency_contact || "Contact hidden — reveal if needed"}</small>
          </div>
          <span className="score">{e.strike_number == null ? "—" : `${e.strike_number}/3`}</span>
          <span className="muted truncate">{e.snippet || "—"}</span>
          <div className="row-actions">
            <button className="mini-button" disabled={busy} onClick={() => onReveal(e.user_id)}>
              Contact
            </button>
            {!e.resolved && (
              <button className="mini-button ok" disabled={busy} onClick={() => onResolve(e.event_id)}>
                Resolve
              </button>
            )}
          </div>
        </div>
      ))}
      {!rows.length && (
        <Empty text="No open safety events." hint="Prohibited content strikes will list here." />
      )}
    </div>
  );
}

function ReviewTable({
  rows,
  busy,
  openReview,
}: {
  rows: ReviewItem[];
  busy: boolean;
  openReview: (id: string) => void;
}) {
  return (
    <div className={`surface-panel table-panel${busy ? " dimmed" : ""}`}>
      <TableHead labels={["Risk", "Claimant", "Item", "Score", "Created"]} cols="cols-reviews" />
      {rows.map((r) => (
        <button
          type="button"
          className="data-row row-button cols-reviews"
          key={r.claim_attempt_id}
          disabled={busy}
          onClick={() => openReview(r.claim_attempt_id)}
        >
          <Status value="review" />
          <div>
            <strong>{r.claimant_email || r.claimant_id.slice(0, 8)}</strong>
            <small>{r.found_report_title || "Claim review"}</small>
          </div>
          <span>{r.found_report_title || "—"}</span>
          <span className="score">
            {r.overall_score == null ? "—" : `${Math.round(r.overall_score * 100)}%`}
          </span>
          <time>{date(r.created_at)}</time>
        </button>
      ))}
      {!rows.length && (
        <Empty text="The review queue is clear." hint="Medium-risk claims land here for a human PASS or BLOCK." />
      )}
    </div>
  );
}

function AuditTable({ rows }: { rows: AuditLog[] }) {
  return (
    <div className="surface-panel table-panel">
      <TableHead labels={["Action", "Entity", "Actor", "Details", "Time"]} cols="cols-default" />
      {rows.map((r) => (
        <div className="data-row cols-default" key={r.audit_id}>
          <strong>{r.action.replace(/_/g, " ")}</strong>
          <span>{r.entity_type || "—"}</span>
          <span>{r.actor_id?.slice(0, 8) || "system"}</span>
          <span className="muted">{Object.keys(r.meta || {}).length} metadata fields</span>
          <time>{date(r.created_at)}</time>
        </div>
      ))}
      {!rows.length && <Empty text="No moderation records yet." />}
    </div>
  );
}

function TableHead({ labels, cols = "cols-default" }: { labels: string[]; cols?: string }) {
  return (
    <div className={`table-head ${cols}`}>
      {labels.map((label) => (
        <span key={label}>{label}</span>
      ))}
    </div>
  );
}

function Status({ value }: { value: string }) {
  return <span className={`status status-${value.toLowerCase()}`}>{value}</span>;
}

function Empty({ text, hint }: { text: string; hint?: string }) {
  return (
    <div className="empty-state">
      <div className="empty-mark" aria-hidden>○</div>
      <strong>{text}</strong>
      {hint ? <p>{hint}</p> : null}
    </div>
  );
}

function ReviewDetailView({
  detail,
  loading,
  loadingLabel,
  onBack,
  onDecide,
}: {
  detail: ReviewDetail;
  loading: boolean;
  loadingLabel: string;
  onBack: () => void;
  onDecide: (d: "PASS" | "BLOCK") => void;
}) {
  const scorePct =
    detail.overall_score == null ? null : Math.round(detail.overall_score * 100);
  return (
    <div className={`detail-view${loading ? " is-busy" : ""}`}>
      {loading && (
        <div className="detail-loading" role="status">
          <span className="spinner" />
          <div>
            <strong>Processing decision</strong>
            <p>{loadingLabel}</p>
          </div>
        </div>
      )}
      <button type="button" className="back-link" disabled={loading} onClick={onBack}>
        ← Back to review queue
        <kbd className="kbd-hint">Esc</kbd>
      </button>
      <SectionIntro
        kicker="Evidence review"
        heading={detail.found_report_title || "Claim detail"}
        copy="Compare vault vs public. Contacts are shown for issue handling only."
      />
      <div className="score-strip">
        <div>
          <span className="eyebrow">Overall score</span>
          <strong>{scorePct == null ? "—" : `${scorePct}%`}</strong>
        </div>
        <div>
          <span className="eyebrow">Fraud risk</span>
          <strong>
            {detail.fraud_risk == null ? "—" : detail.fraud_risk.toFixed(2)}
          </strong>
        </div>
        <div>
          <span className="eyebrow">Status</span>
          <Status value={detail.status || "review"} />
        </div>
      </div>
      <div className="evidence-grid">
        <div className="evidence-card">
          <span>Public image</span>
          {detail.public_image_url ? (
            <img src={detail.public_image_url} alt="Sanitized report" />
          ) : (
            <Empty text="No public image" />
          )}
        </div>
        <div className="evidence-card vault-card">
          <span>Vault original · admin only</span>
          {detail.vault_image_url ? (
            <img src={detail.vault_image_url} alt="Original report" />
          ) : (
            <Empty text="No vault image" />
          )}
        </div>
      </div>
      <div className="surface-panel contact-panel">
        <div>
          <span className="eyebrow">Claimant contact</span>
          <h3>{detail.claimant_email || detail.claimant_id}</h3>
          <p className="muted">
            Emergency: {detail.claimant_emergency_contact || "Not provided"}
          </p>
        </div>
        <div>
          <span className="eyebrow">Report owner contact</span>
          <h3>{detail.owner_email || "—"}</h3>
          <p className="muted">
            Emergency: {detail.owner_emergency_contact || "Not provided"}
          </p>
        </div>
      </div>
      {(detail.questions?.length || 0) > 0 && (
        <div className="surface-panel qa-panel">
          <span className="eyebrow">Interrogation</span>
          <h3>Answers vs vault features</h3>
          <ul>
            {detail.questions.map((q, i) => {
              const s = detail.semantic_scores[i];
              const tone =
                s == null ? "" : s >= 0.6 ? "qa-good" : s >= 0.3 ? "qa-mid" : "qa-bad";
              return (
                <li key={i} className={tone}>
                  <strong>{String(q.question || q.question_id || `Q${i + 1}`)}</strong>
                  <span>Answer: {detail.answers[i] || "—"}</span>
                  <span className="qa-score">
                    Score: {s == null ? "—" : s.toFixed(2)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <div className="surface-panel decision-panel decision-sticky">
        <div>
          <span className="eyebrow">Decision</span>
          <h3>
            Overall {detail.overall_score?.toFixed(3) || "—"} · Risk{" "}
            {detail.fraud_risk?.toFixed(3) || "—"}
          </h3>
          <p className="muted">PASS opens anonymous chat. BLOCK applies a trust penalty.</p>
        </div>
        <div className="decision-actions">
          <button
            type="button"
            className="secondary-button"
            disabled={loading}
            onClick={() => onDecide("BLOCK")}
          >
            {loading ? "Working…" : "Block claim"}
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={loading}
            onClick={() => onDecide("PASS")}
          >
            {loading ? "Working…" : "Approve and open chat →"}
          </button>
        </div>
      </div>
    </div>
  );
}
