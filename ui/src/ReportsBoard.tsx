import { useMemo, useState } from "react";
import type { AdminReport } from "./api";
import ReportsMap from "./ReportsMap";

const STATUSES = ["pending", "processing", "active", "matched", "flagged", "closed"];

function when(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

export default function ReportsBoard({
  rows,
  busy,
  onResolve,
  onReveal,
  onExport,
}: {
  rows: AdminReport[];
  busy: boolean;
  onResolve: (id: string, action: "approve" | "quarantine" | "remove") => void;
  onReveal: (userId: string) => void;
  onExport: (kind: "lost" | "found" | "handovers" | "all", ids?: string[]) => void;
}) {
  const [view, setView] = useState<"list" | "map">("list");
  const [typeFilter, setTypeFilter] = useState<"ALL" | "LOST" | "FOUND">("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) {
      const c = (r.category || "").trim();
      if (c) set.add(c);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [rows]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (typeFilter !== "ALL" && r.report_type !== typeFilter) return false;
      if (statusFilter !== "ALL" && r.status !== statusFilter) return false;
      if (categoryFilter !== "ALL") {
        const cat = (r.category || "").toLowerCase();
        if (!cat.includes(categoryFilter.toLowerCase())) return false;
      }
      return true;
    });
  }, [rows, typeFilter, statusFilter, categoryFilter]);

  const selected = filtered.find((r) => r.report_id === selectedId) || null;
  const lostN = filtered.filter((r) => r.report_type === "LOST").length;
  const foundN = filtered.filter((r) => r.report_type === "FOUND").length;
  const mappedN = filtered.filter((r) => r.latitude != null && r.longitude != null).length;
  const visibleIds = filtered.map((r) => r.report_id);
  const checkedVisible = visibleIds.filter((id) => checked.has(id));
  const allVisibleChecked =
    visibleIds.length > 0 && checkedVisible.length === visibleIds.length;

  function toggleChecked(id: string, on?: boolean) {
    setChecked((prev) => {
      const next = new Set(prev);
      const shouldOn = on ?? !next.has(id);
      if (shouldOn) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleSelectAllVisible() {
    setChecked((prev) => {
      const next = new Set(prev);
      if (allVisibleChecked) {
        for (const id of visibleIds) next.delete(id);
      } else {
        for (const id of visibleIds) next.add(id);
      }
      return next;
    });
  }

  function exportKind(kind: "lost" | "found" | "handovers" | "all") {
    if (checked.size === 0) {
      onExport(kind);
      return;
    }
    const picked = rows.filter((r) => checked.has(r.report_id));
    const ids =
      kind === "lost"
        ? picked.filter((r) => r.report_type === "LOST").map((r) => r.report_id)
        : kind === "found"
          ? picked.filter((r) => r.report_type === "FOUND").map((r) => r.report_id)
          : picked.map((r) => r.report_id);
    if (!ids.length) return;
    onExport(kind, ids);
  }

  const exportHint =
    checked.size === 0
      ? "Nothing checked — each button exports the full matching list."
      : `${checked.size} selected — export uses those rows (lost/found buttons keep only that type).`;

  return (
    <div className={`reports-board${busy ? " dimmed" : ""}`}>
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Type</span>
          {(["ALL", "LOST", "FOUND"] as const).map((v) => (
            <button
              key={v}
              type="button"
              className={`chip${typeFilter === v ? " on" : ""}`}
              onClick={() => setTypeFilter(v)}
            >
              {v === "ALL" ? "All" : v}
            </button>
          ))}
        </div>
        <div className="filter-group">
          <span className="filter-label">Status</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="ALL">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <span className="filter-label">Category</span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Filter by category"
          >
            <option value="ALL">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group view-toggle">
          <span className="filter-label">View</span>
          <button
            type="button"
            className={`chip${view === "list" ? " on" : ""}`}
            onClick={() => setView("list")}
          >
            List
          </button>
          <button
            type="button"
            className={`chip${view === "map" ? " on" : ""}`}
            onClick={() => setView("map")}
          >
            Map
          </button>
        </div>
      </div>

      <div className="export-bar">
        <div>
          <span className="eyebrow">Admin export</span>
          <p className="export-hint">{exportHint}</p>
        </div>
        <div className="row-actions">
          <button className="mini-button" disabled={busy} onClick={() => exportKind("lost")}>
            Export lost
          </button>
          <button className="mini-button" disabled={busy} onClick={() => exportKind("found")}>
            Export found
          </button>
          <button className="mini-button ok" disabled={busy} onClick={() => exportKind("handovers")}>
            Export handovers
          </button>
          <button className="mini-button" disabled={busy} onClick={() => exportKind("all")}>
            Export all
          </button>
        </div>
      </div>

      <div className="report-stats">
        <label className="select-all">
          <input
            type="checkbox"
            checked={allVisibleChecked}
            disabled={!visibleIds.length}
            onChange={toggleSelectAllVisible}
          />
          Select all shown
        </label>
        {checked.size > 0 && (
          <button type="button" className="clear-search" onClick={() => setChecked(new Set())}>
            Clear selection ({checked.size})
          </button>
        )}
        <span>{filtered.length} shown</span>
        <span>{lostN} lost</span>
        <span>{foundN} found</span>
        <span>{mappedN} on map</span>
      </div>

      {view === "map" ? (
        <ReportsMap
          rows={filtered}
          selectedId={selectedId}
          onSelect={(r) => setSelectedId(r.report_id)}
        />
      ) : (
        <div className="report-grid">
          {filtered.map((r) => (
            <div
              key={r.report_id}
              className={`report-card${selectedId === r.report_id ? " selected" : ""}${
                checked.has(r.report_id) ? " checked" : ""
              }`}
            >
              <label className="report-check">
                <input
                  type="checkbox"
                  checked={checked.has(r.report_id)}
                  onChange={(e) => toggleChecked(r.report_id, e.target.checked)}
                  aria-label={`Select ${r.title || "report"}`}
                />
              </label>
              <button
                type="button"
                className="report-card-hit"
                onClick={() => setSelectedId(r.report_id)}
              >
                <div className="report-thumb">
                  {r.public_image_urls?.[0] ? (
                    <img src={r.public_image_urls[0]} alt="" />
                  ) : (
                    <span>No public photo</span>
                  )}
                  <em className={`type type-${r.report_type.toLowerCase()}`}>{r.report_type}</em>
                </div>
                <div className="report-card-body">
                  <strong>{r.title || "Untitled report"}</strong>
                  <small>
                    {r.category || "Uncategorized"} · {r.user_email || r.user_id.slice(0, 8)}
                  </small>
                  <div className="report-card-meta">
                    <span className={`status status-${r.status.toLowerCase()}`}>{r.status}</span>
                    <span>{r.location_label || "Area not set"}</span>
                  </div>
                  <time>{when(r.created_at)}</time>
                </div>
              </button>
            </div>
          ))}
          {!filtered.length && (
            <div className="empty-state">
              <div className="empty-mark" aria-hidden>○</div>
              <strong>No reports match these filters.</strong>
              <p>Clear type, status, or category, or widen search.</p>
            </div>
          )}
        </div>
      )}

      {selected && (
        <ReportDetail
          row={selected}
          busy={busy}
          checked={checked.has(selected.report_id)}
          onToggleCheck={(on) => toggleChecked(selected.report_id, on)}
          onClose={() => setSelectedId(null)}
          onResolve={onResolve}
          onReveal={onReveal}
        />
      )}
    </div>
  );
}

function ReportDetail({
  row,
  busy,
  checked,
  onToggleCheck,
  onClose,
  onResolve,
  onReveal,
}: {
  row: AdminReport;
  busy: boolean;
  checked: boolean;
  onToggleCheck: (on: boolean) => void;
  onClose: () => void;
  onResolve: (id: string, action: "approve" | "quarantine" | "remove") => void;
  onReveal: (userId: string) => void;
}) {
  const photos = row.public_image_urls || [];
  return (
    <aside className="report-detail surface-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Sanitized public details</span>
          <h2>{row.title || "Untitled report"}</h2>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close details">
          ×
        </button>
      </div>
      <div className="report-detail-pills">
        <span className={`type type-${row.report_type.toLowerCase()}`}>{row.report_type}</span>
        <span className={`status status-${row.status.toLowerCase()}`}>{row.status}</span>
        {row.category ? <span className="role">{row.category}</span> : null}
      </div>
      {photos.length > 0 && (
        <div className="report-detail-photos">
          {photos.slice(0, 4).map((url) => (
            <img key={url} src={url} alt="Sanitized report" />
          ))}
        </div>
      )}
      <p className="report-desc">{row.description || "No description provided."}</p>
      <dl className="report-dl">
        <div>
          <dt>Owner</dt>
          <dd>{row.user_email || row.user_id.slice(0, 8)}</dd>
        </div>
        <div>
          <dt>Approximate area</dt>
          <dd>{row.location_label || "Not recorded"}</dd>
        </div>
        <div>
          <dt>Filed</dt>
          <dd>{when(row.created_at)}</dd>
        </div>
      </dl>
      <p className="muted">
        Map pins are privacy-fuzzed. Vault originals stay in the fraud review queue only.
      </p>
      <label className="select-all" style={{ marginBottom: 12 }}>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onToggleCheck(e.target.checked)}
        />
        Include this report in export
      </label>
      <div className="row-actions">
        {row.status === "flagged" && (
          <button className="mini-button" disabled={busy} onClick={() => onResolve(row.report_id, "approve")}>
            Approve
          </button>
        )}
        <button className="mini-button warn" disabled={busy} onClick={() => onResolve(row.report_id, "quarantine")}>
          Flag
        </button>
        <button className="mini-button danger" disabled={busy} onClick={() => onResolve(row.report_id, "remove")}>
          Remove
        </button>
        <button className="mini-button" disabled={busy} onClick={() => onReveal(row.user_id)}>
          Contact
        </button>
      </div>
    </aside>
  );
}
