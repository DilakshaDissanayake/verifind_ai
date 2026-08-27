import { useCallback, useEffect, useState } from "react";
import {
  blockUser, clearToken, decideMatch, decideReview, downloadExport, getOverview, getReview,
  getStoredToken, listAdminReports, listAdminUsers, listAuditLogs, listModeration,
  listReviews, listSuggestions, login, resolveModeration, resolveReport,
  revealContact, unblockUser,
  type AdminReport, type AdminUser, type AuditLog, type ModerationEvent,
  type Overview, type ReviewDetail, type ReviewItem, type Suggestion,
} from "./api";

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
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Ready");
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const [email, setEmail] = useState("admin@gmail.com");
  const [password, setPassword] = useState("");

  async function withLoad<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
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
        setNotice(decision === "PASS" ? "Claim approved — chat opened." : "Claim blocked.");
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
        setNotice(res.message);
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
      setNotice(active ? "User unblocked." : "User blocked.");
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
      setNotice(`Contact for ${res.email}: ${res.emergency_contact || "Not provided"}`);
      await load();
    });
  }

  async function onResolveReport(id: string, action: "approve" | "quarantine" | "remove") {
    await withLoad(`Updating report (${action})…`, async () => {
      const res = await resolveReport(id, action);
      setNotice(res.message);
      await load();
    });
  }

  async function onResolveModeration(id: string) {
    await withLoad("Marking safety event resolved…", async () => {
      await resolveModeration(id);
      setNotice("Moderation event marked resolved.");
      await load();
    });
  }

  async function onExport(kind: "lost" | "found" | "handovers" | "all") {
    await withLoad(`Exporting ${kind} CSV…`, async () => {
      await downloadExport(kind);
      setNotice(`Downloaded ${kind} export.`);
    });
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
          <span className="logo-mark">V</span>
          <div>
            VERIFIND
            <small>CONTROL ROOM</small>
          </div>
        </div>
        <div className="workspace">
          <span className={`status-dot${loading ? " pulse" : ""}`} />{" "}
          {loading ? "Syncing…" : "Live workspace"}
        </div>
        <nav>
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
                className={page === key ? "nav-item active" : "nav-item"}
                disabled={loading}
                onClick={() => {
                  setPage(key);
                  setDetail(null);
                }}
              >
                <b>{icon}</b>
                {label}
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
            className="signout"
            disabled={loading}
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
            <h1>{title(page)}</h1>
          </div>
          <div className="top-actions">
            <div className="sync-chip" title={lastSynced ? lastSynced.toLocaleString() : "Not synced yet"}>
              <span className={`sync-dot${loading ? " on" : ""}`} />
              {loading ? loadingLabel : lastSynced ? `Synced ${lastSynced.toLocaleTimeString()}` : "Awaiting sync"}
            </div>
            <button
              className="icon-button"
              disabled={loading}
              onClick={() => void load()}
              aria-label="Refresh"
            >
              {loading ? "…" : "↻"}
            </button>
            <div className="admin-avatar">A</div>
          </div>
        </header>
        {loading && (
          <div className="process-banner" role="status">
            <span className="spinner" />
            <div>
              <strong>Process running</strong>
              <p>{loadingLabel}</p>
            </div>
          </div>
        )}
        {error && (
          <div className="error-banner">
            {error}
            <button onClick={() => setError(null)}>×</button>
          </div>
        )}
        {notice && (
          <div className="notice-banner">
            {notice}
            <button onClick={() => setNotice(null)}>×</button>
          </div>
        )}
        {detail ? (
          <ReviewDetailView
            detail={detail}
            loading={loading}
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
            search={search}
            setSearch={setSearch}
            loading={loading}
            loadingLabel={loadingLabel}
            openReview={openReview}
            onDecideMatch={onDecideMatch}
            onBlockUser={onBlockUser}
            onRevealContact={onRevealContact}
            onResolveReport={onResolveReport}
            onResolveModeration={onResolveModeration}
            onExport={onExport}
            go={(p) => setPage(p)}
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
  return (
    <div className="login-screen">
      <div className="login-art">
        <span>V</span>
        <p>
          Trust, with
          <br />
          <strong>evidence.</strong>
        </p>
      </div>
      <form className="login-card" onSubmit={props.onLogin}>
        <div className="logo">
          <span className="logo-mark">V</span>
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
        {props.error && <div className="error-banner">{props.error}</div>}
        <label>
          Email
          <input
            type="email"
            value={props.email}
            onChange={(e) => props.setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={props.password}
            onChange={(e) => props.setPassword(e.target.value)}
            required
          />
        </label>
        <button className="primary-button" disabled={props.loading}>
          {props.loading ? "Signing in…" : "Enter control room →"}
        </button>
        {props.loading && (
          <p className="muted" style={{ marginTop: 14, fontSize: 11 }}>
            Verifying administrator credentials…
          </p>
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
  onExport: (kind: "lost" | "found" | "handovers" | "all") => void;
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
        ⌕
        <input
          placeholder={`Search ${p.page}…`}
          value={p.search}
          disabled={p.loading}
          onChange={(e) => p.setSearch(e.target.value)}
        />
      </div>
      <span className="result-count">
        {p.loading ? p.loadingLabel : "Updated just now"}
      </span>
    </div>
  );
  if (p.page === "reports") {
    return (
      <>
        <SectionIntro
          kicker="Community activity"
          heading="All reports"
          copy="Approve, quarantine, or remove flagged posts. Export lost, found, and successful handover CSVs anytime — including hidden closed posts."
        />
        {common}
        <div className="export-bar">
          <span className="eyebrow">Admin export</span>
          <div className="row-actions">
            <button className="mini-button" disabled={p.loading} onClick={() => p.onExport("lost")}>
              Export lost
            </button>
            <button className="mini-button" disabled={p.loading} onClick={() => p.onExport("found")}>
              Export found
            </button>
            <button className="mini-button ok" disabled={p.loading} onClick={() => p.onExport("handovers")}>
              Export handovers
            </button>
            <button className="mini-button" disabled={p.loading} onClick={() => p.onExport("all")}>
              Export all
            </button>
          </div>
        </div>
        {p.loading && !p.reports.length ? (
          <SkeletonBoard label={p.loadingLabel} />
        ) : (
          <ReportTable
            rows={p.reports}
            busy={p.loading}
            onResolve={p.onResolveReport}
            onReveal={p.onRevealContact}
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
  const cards = data
    ? [
        ["Reports", data.reports, "Across the network"],
        ["Needs review", data.pending_reviews, "Fraud claims"],
        ["Handovers", data.successful_handovers ?? 0, "PASS / success"],
        ["Hidden closed", data.closed_reports ?? 0, "After handover"],
      ]
    : [];
  return (
    <>
      <SectionIntro
        kicker="Good morning, admin"
        heading="The network at a glance"
        copy="Approve matches, resolve fraud reviews, hide completed handovers from public, and export full reports."
      />
      <div className="metric-grid">
        {cards.map(([label, value, hint]) => (
          <div className="metric-card" key={String(label)}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{hint}</small>
          </div>
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
          <button className="priority-row row-button" onClick={() => go("reviews")}>
            <div className="priority-icon amber">!</div>
            <div>
              <strong>{data?.pending_reviews ?? 0} claims need a decision</strong>
              <p>Compare vault vs public before opening chat.</p>
            </div>
            <span className="arrow">→</span>
          </button>
          <button className="priority-row row-button" onClick={() => go("suggestions")}>
            <div className="priority-icon amber">✦</div>
            <div>
              <strong>{data?.pending_match_approvals ?? 0} matches awaiting pass</strong>
              <p>Approve genuine pairs; reject noise.</p>
            </div>
            <span className="arrow">→</span>
          </button>
          <button className="priority-row row-button" onClick={() => go("reports")}>
            <div className="priority-icon amber">▤</div>
            <div>
              <strong>
                Export lost / found / {data?.successful_handovers ?? 0} handovers
              </strong>
              <p>CSV includes closed posts after successful handover.</p>
            </div>
            <span className="arrow">→</span>
          </button>
          <button className="priority-row row-button" onClick={() => go("moderation")}>
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
          <span className="eyebrow">Exports</span>
          <h2>Download control-room CSVs</h2>
          <p>
            After lost and found complete handover, posts leave the public feed. Admins still
            export every lost item, found item, and successful handover record.
          </p>
          <div className="export-stack">
            <button className="mini-button" onClick={() => onExport("lost")}>
              Lost items CSV
            </button>
            <button className="mini-button" onClick={() => onExport("found")}>
              Found items CSV
            </button>
            <button className="mini-button ok" onClick={() => onExport("handovers")}>
              Successful handovers CSV
            </button>
          </div>
          <div className="principle-line">
            <span>◈</span> Decisions stay reviewable
          </div>
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

function ReportTable({
  rows,
  busy,
  onResolve,
  onReveal,
}: {
  rows: AdminReport[];
  busy: boolean;
  onResolve: (id: string, action: "approve" | "quarantine" | "remove") => void;
  onReveal: (userId: string) => void;
}) {
  return (
    <div className={`surface-panel table-panel${busy ? " dimmed" : ""}`}>
      <TableHead labels={["Report", "Type", "Owner", "Status", "Actions"]} />
      {rows.map((r) => (
        <div className="data-row actions-row" key={r.report_id}>
          <div>
            <strong>{r.title || "Untitled report"}</strong>
            <small>{r.category || "No category"}</small>
          </div>
          <span className={`type type-${r.report_type.toLowerCase()}`}>{r.report_type}</span>
          <span>{r.user_email || r.user_id.slice(0, 8)}</span>
          <Status value={r.status} />
          <div className="row-actions">
            {r.status === "flagged" && (
              <button className="mini-button" disabled={busy} onClick={() => onResolve(r.report_id, "approve")}>
                Approve
              </button>
            )}
            <button className="mini-button warn" disabled={busy} onClick={() => onResolve(r.report_id, "quarantine")}>
              Flag
            </button>
            <button className="mini-button danger" disabled={busy} onClick={() => onResolve(r.report_id, "remove")}>
              Remove
            </button>
            <button className="mini-button" disabled={busy} onClick={() => onReveal(r.user_id)}>
              Contact
            </button>
          </div>
        </div>
      ))}
      {!rows.length && <Empty text="No reports found." />}
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
      <TableHead labels={["Person", "Strikes", "Trust", "State", "Actions"]} />
      {rows.map((u) => (
        <div className="data-row actions-row" key={u.user_id}>
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
      {!rows.length && <Empty text="No users found." />}
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
      <TableHead labels={["Pair", "Score", "Band", "Admin", "Actions"]} />
      {rows.map((s) => (
        <div className="data-row actions-row" key={s.match_id}>
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
      {!rows.length && <Empty text="No suggestions found." />}
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
      <TableHead labels={["Event", "User / contact", "Strike", "Snippet", "Actions"]} />
      {rows.map((e) => (
        <div className="data-row actions-row" key={e.event_id}>
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
      {!rows.length && <Empty text="No open safety events." />}
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
      <TableHead labels={["Risk", "Claimant", "Item", "Score", "Created"]} />
      {rows.map((r) => (
        <button
          className="data-row row-button"
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
      {!rows.length && <Empty text="The review queue is clear." />}
    </div>
  );
}

function AuditTable({ rows }: { rows: AuditLog[] }) {
  return (
    <div className="surface-panel table-panel">
      <TableHead labels={["Action", "Entity", "Actor", "Details", "Time"]} />
      {rows.map((r) => (
        <div className="data-row" key={r.audit_id}>
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

function TableHead({ labels }: { labels: string[] }) {
  return (
    <div className="table-head">
      {labels.map((label) => (
        <span key={label}>{label}</span>
      ))}
    </div>
  );
}

function Status({ value }: { value: string }) {
  return <span className={`status status-${value.toLowerCase()}`}>{value}</span>;
}

function Empty({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
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
      <button className="back-link" disabled={loading} onClick={onBack}>
        ← Back to review queue
      </button>
      <SectionIntro
        kicker="Evidence review"
        heading={detail.found_report_title || "Claim detail"}
        copy="Review vault vs public evidence. Contacts are shown for issue handling only."
      />
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
            {detail.questions.map((q, i) => (
              <li key={i}>
                <strong>{String(q.question || q.question_id || `Q${i + 1}`)}</strong>
                <span>Answer: {detail.answers[i] || "—"}</span>
                <span>
                  Score:{" "}
                  {detail.semantic_scores[i] == null
                    ? "—"
                    : detail.semantic_scores[i].toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="surface-panel decision-panel">
        <div>
          <span className="eyebrow">Decision</span>
          <h3>
            Overall {detail.overall_score?.toFixed(3) || "—"} · Risk{" "}
            {detail.fraud_risk?.toFixed(3) || "—"}
          </h3>
          <p className="muted">PASS opens anonymous chat. BLOCK applies a trust penalty.</p>
        </div>
        <div className="decision-actions">
          <button className="secondary-button" disabled={loading} onClick={() => onDecide("BLOCK")}>
            {loading ? "Working…" : "Block claim"}
          </button>
          <button className="primary-button" disabled={loading} onClick={() => onDecide("PASS")}>
            {loading ? "Working…" : "Approve and open chat →"}
          </button>
        </div>
      </div>
    </div>
  );
}
