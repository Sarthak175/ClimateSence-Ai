import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, Info, Loader2, RefreshCw, ServerCrash, ShieldAlert } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { fmtClock } from "../utils/format";

export function Card({ title, subtitle, icon: Icon, right, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && (
        <header className="card-head">
          <div className="card-title">
            {Icon && <Icon size={16} />}
            <div>
              <h3>{title}</h3>
              {subtitle && <p className="muted small">{subtitle}</p>}
            </div>
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, unit, sub, icon: Icon, accent = "teal", children }) {
  return (
    <div className={`stat accent-${accent}`}>
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        {Icon && <Icon size={16} className="stat-icon" />}
      </div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
      {children}
    </div>
  );
}

export function Skeleton({ height = 120 }) {
  return <div className="skeleton" style={{ height }} />;
}

export function Loading({ label = "Loading…", height = 160 }) {
  return (
    <div className="loading" style={{ minHeight: height }}>
      <Loader2 className="spin" size={20} /> <span>{label}</span>
    </div>
  );
}

const HINTS = {
  model_unavailable: "The backend you are running cannot find the trained model files. Check that backend/models/best_model.joblib exists in the folder the backend was started from (see the path in the message above), then restart the backend. Until then the site refuses to show any prediction instead of inventing one.",
  upstream_unavailable: "The upstream data provider did not answer. The previous cached result is used automatically when one exists; otherwise try again in a minute.",
  network: "Check that the backend is running and that VITE_API_BASE_URL points to it.",
};

export function ErrorBox({ error, onRetry, compact = false }) {
  if (!error) return null;
  const Icon = error.code === "model_unavailable" ? Info : error.status === 0 ? ServerCrash : AlertTriangle;
  return (
    <div className={`errorbox ${compact ? "compact" : ""} ${error.code === "model_unavailable" ? "info" : ""}`}>
      <Icon size={18} />
      <div>
        <strong>{error.code === "model_unavailable" ? "Model not available" : error.code === "network" ? "API unreachable" : `Request failed${error.status ? ` (${error.status})` : ""}`}</strong>
        <p>{error.message}</p>
        {!compact && HINTS[error.code] && <p className="muted small">{HINTS[error.code]}</p>}
        {onRetry && <button className="btn ghost sm" onClick={onRetry}><RefreshCw size={13} /> Try again</button>}
      </div>
    </div>
  );
}

export function HeatBadge({ risk }) {
  if (!risk) return <span className="badge muted-badge">–</span>;
  return (
    <span className="badge" style={{ background: `${risk.color}22`, color: risk.color, borderColor: `${risk.color}66` }}>
      <span className="dot" style={{ background: risk.color }} /> {risk.label}
    </span>
  );
}

export function SourceNote({ children, href, label }) {
  return (
    <p className="source-note">
      <Info size={13} /> <span>{children}</span>
      {href && (
        <a href={href} target="_blank" rel="noreferrer">
          {label || "source"} <ExternalLink size={11} />
        </a>
      )}
    </p>
  );
}

export function RefreshBar({ updatedAt, onRefresh, loading, note }) {
  return (
    <div className="refreshbar">
      <span className="muted small">{note} Last updated {fmtClock(updatedAt)}</span>
      <button className="btn ghost sm" onClick={onRefresh} disabled={loading}>
        <RefreshCw size={13} className={loading ? "spin" : ""} /> Refresh
      </button>
    </div>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      <div className="page-actions">{children}</div>
    </div>
  );
}


/** Live-data status: auto-refresh countdown + the exact public URLs the data comes from. */
export function LiveSourceBar({ updatedAt, intervalMs = 300000, attemptedAt, error, stale, sources = [], onRefresh, loading }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const base = attemptedAt || (updatedAt ? updatedAt.getTime() : null);
  const left = base ? Math.max(0, Math.round((base + intervalMs - now) / 1000)) : null;
  const mm = left === null ? "--" : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  const status = error ? "bad" : stale ? "warn" : updatedAt ? "ok" : "wait";
  const label = { ok: "LIVE", warn: "STALE", bad: "OFFLINE", wait: "CONNECTING" }[status];
  return (
    <div className="livebar">
      <div className="livebar-row">
        <span className={`livepill ${status}`}><span className="dot" /> {label}</span>
        <span className="small">Auto-refresh every {Math.round(intervalMs / 60000)} min · next refresh in <b>{loading ? "…" : mm}</b>
          {updatedAt && <> · last fetched {fmtClock(updatedAt)}</>}</span>
        {onRefresh && (
          <button className="btn ghost sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={13} className={loading ? "spin" : ""} /> Refresh now
          </button>
        )}
      </div>
      {error && updatedAt && <div className="small warn-text">Last refresh failed ({error.message}) - showing the previous data.</div>}
      <div className="livebar-src small">
        <span className="muted">Data source{sources.length > 1 ? "s" : ""}:</span>
        {sources.map((s) => (
          <a key={s.url} href={s.url} target="_blank" rel="noreferrer" title={s.url}>
            {s.label} <ExternalLink size={11} />
          </a>
        ))}
      </div>
    </div>
  );
}

/** Readiness verdict of the trained model, computed by the API from the real notebook metrics. */
export function QualityBanner({ compact = false }) {
  const q = useApi("/model-quality", {}, { interval: 0 });
  if (q.error || !q.data) return null;
  const { verdict, summary, checks } = q.data;
  const Icon = verdict === "ready" ? CheckCircle2 : verdict === "limited" ? Info : ShieldAlert;
  const title = { ready: "Model quality: READY", limited: "Model quality: LIMITED", not_ready: "Model quality: NOT READY" }[verdict];
  const failed = checks.filter((c) => !c.passed);
  return (
    <div className={`qbanner ${verdict}`}>
      <div className="qhead"><Icon size={17} /> <b>{title}</b> <span className="small">{summary}</span></div>
      {!compact && (
        <ul className="qchecks small">
          {checks.map((c) => (
            <li key={c.name} className={c.passed ? "pass" : c.severity === "required" ? "fail" : "adv"}>
              {c.passed ? "✔" : c.severity === "required" ? "✘" : "!"} <b>{c.name}</b>: {String(c.value ?? "n/a")} <span className="muted">({c.rule})</span>
            </li>
          ))}
        </ul>
      )}
      {compact && failed.length > 0 && <div className="small muted">Open Model Lab for the {failed.length} failed check(s).</div>}
    </div>
  );
}
