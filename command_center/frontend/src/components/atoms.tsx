// Small presentational atoms shared across views. All text is rendered as JSX
// children, so React escapes it — no raw-HTML path anywhere (risk #4).

export function Pill({ status, label }: { status: string; label?: string }) {
  const cls = status.replace(/[^a-z_]/gi, "_");
  return <span className={`pill ${cls}`}>{label ?? status.replace(/_/g, " ")}</span>;
}

export function Sev({ level }: { level: string }) {
  const cls = ["high", "medium", "low"].includes(level) ? level : "low";
  return <span className={`sev ${cls}`}>{level}</span>;
}

export function Tier({ tier }: { tier: string }) {
  return <span className="tier">{tier}</span>;
}

export function ReadOnlyChip() {
  return (
    <span className="ro">
      <i className="lock" aria-hidden="true" />
      read-only
    </span>
  );
}

// Loading / error / empty are first-class states for every consumed endpoint.
export function Loading({ label = "loading" }: { label?: string }) {
  return (
    <div className="state-note" role="status" aria-live="polite">
      <span className="spin" aria-hidden="true" />
      <span className="lbl">{label}</span>
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry?: () => void;
}) {
  return (
    <div className="state-note err" role="alert">
      <span className="lbl">something went wrong</span>
      <h2>Could not load this view</h2>
      {/* error.message is the backend's { detail } — rendered as escaped text */}
      <p>{error.message}</p>
      {onRetry && (
        <button className="btn btn-ghost btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyNote({ title, body }: { title: string; body: string }) {
  return (
    <div className="state-note">
      <span className="lbl">nothing here</span>
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  );
}
