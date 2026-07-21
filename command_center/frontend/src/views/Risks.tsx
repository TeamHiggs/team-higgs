import { api } from "../api/client";
import { useApi } from "../api/hooks";
import { EmptyNote, ErrorState, Loading, Pill, ReadOnlyChip, Sev } from "../components/atoms";
import { severityRank } from "../lib/format";

interface Props {
  onUnauthorized: () => void;
}

export function RisksView({ onUnauthorized }: Props) {
  const { data, error, loading, reload } = useApi(api.risks, onUnauthorized);

  const rows = data
    ? [...data].sort((a, b) => severityRank(a.severity) - severityRank(b.severity))
    : [];

  return (
    <section className="view" aria-label="Risk register">
      <div className="view-head">
        <div className="view-head-row">
          <div>
            <h1>Risk register</h1>
            <p className="sub">
              The EM-curated register — acknowledged risks, their severity, and
              how each is being held. Curated via the CLI; surfaced here for
              awareness.
            </p>
          </div>
          <span className="spacer" />
          <ReadOnlyChip />
        </div>
      </div>
      <div className="view-scroll">
        {loading && <Loading label="loading risks" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && rows.length === 0 && (
          <EmptyNote title="No risks on the register" body="Nothing has been acknowledged yet." />
        )}
        {rows.length > 0 && (
          <div className="stack">
            {rows.map((r) => (
              <div className="rcard" key={r.id}>
                <div className="rtop">
                  <span className="rtitle">{r.title}</span>
                  <span className="cat">{r.category}</span>
                  <Sev level={r.severity} />
                  <Pill status={r.status} />
                </div>
                {r.body && <div className="rbody">{r.body}</div>}
                {r.mitigation && (
                  <div className="mit">
                    <span className="lbl">mitigation</span>
                    {r.mitigation}
                  </div>
                )}
                {(r.pr_id != null || r.decision_id != null) && (
                  <div className="links">
                    {r.pr_id != null && <span className="ref">↳ pr #{r.pr_id}</span>}
                    {r.decision_id != null && (
                      <span className="ref">↳ decision #{r.decision_id}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
