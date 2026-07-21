import { api } from "../api/client";
import { useApi } from "../api/hooks";
import { EmptyNote, ErrorState, Loading, ReadOnlyChip } from "../components/atoms";
import { fmtCost, fmtInt } from "../lib/format";
import type { RunOut } from "../api/types";

interface Props {
  onUnauthorized: () => void;
}

// Typed token mix (schema v2.1 / migration 0004): real spend is cache-dominated,
// so we break the bar out by type when the columns are present.
function TokenMix({ run }: { run: RunOut }) {
  const inTok = run.input_tokens ?? 0;
  const outTok = run.output_tokens ?? 0;
  const crTok = run.cache_read_tokens ?? 0;
  const cwTok = run.cache_write_tokens ?? 0;
  const total = inTok + outTok + crTok + cwTok;
  if (total === 0) return <span className="ref">—</span>;
  const pct = (n: number) => `${(n / total) * 100}%`;
  return (
    <span className="tokbar" title="input · output · cache read · cache write">
      <i className="in" style={{ width: pct(inTok) }} />
      <i className="out" style={{ width: pct(outTok) }} />
      <i className="cr" style={{ width: pct(crTok) }} />
      <i className="cw" style={{ width: pct(cwTok) }} />
    </span>
  );
}

function totalTokens(run: RunOut): number | null {
  const typed =
    (run.input_tokens ?? 0) +
    (run.output_tokens ?? 0) +
    (run.cache_read_tokens ?? 0) +
    (run.cache_write_tokens ?? 0);
  if (typed > 0) return typed;
  return run.token_cost ?? null;
}

export function RunsView({ onUnauthorized }: Props) {
  const { data, error, loading, reload } = useApi(() => api.runs(50), onUnauthorized);

  return (
    <section className="view" aria-label="Recent run costs">
      <div className="view-head">
        <div className="view-head-row">
          <div>
            <h1>Recent run costs</h1>
            <p className="sub">
              The latest runs and what they cost. Token usage is broken out by
              type (schema v2.1 / migration 0004) because real API spend is
              cache-dominated.
            </p>
          </div>
          <span className="spacer" />
          <ReadOnlyChip />
        </div>
      </div>
      <div className="view-scroll">
        {loading && <Loading label="loading run costs" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && data.length === 0 && (
          <EmptyNote title="No runs recorded" body="Nothing has run against the platform yet." />
        )}
        {data && data.length > 0 && (
          <>
            <table className="tbl">
              <thead>
                <tr>
                  <th>run</th>
                  <th>task</th>
                  <th>role</th>
                  <th>model</th>
                  <th>mode</th>
                  <th>outcome</th>
                  <th>tokens</th>
                  <th>mix</th>
                  <th>cost</th>
                </tr>
              </thead>
              <tbody>
                {data.map((run) => (
                  <tr key={run.id}>
                    <td className="tnum">#{run.id}</td>
                    <td className="ref">{run.task_id != null ? `task ${run.task_id}` : "—"}</td>
                    <td>{run.role}</td>
                    <td className="ref">{run.model}</td>
                    <td className="ref">{run.mode}</td>
                    <td className="ref">{run.outcome ?? "running"}</td>
                    <td className="tnum">{fmtInt(totalTokens(run))}</td>
                    <td>
                      <TokenMix run={run} />
                    </td>
                    <td className="tnum">{fmtCost(run.cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
              <caption>latest {data.length} runs · newest first</caption>
            </table>
            <div className="tokleg" aria-hidden="true">
              <span className="k">
                <i className="sw in" />
                input
              </span>
              <span className="k">
                <i className="sw out" />
                output
              </span>
              <span className="k">
                <i className="sw cr" />
                cache read
              </span>
              <span className="k">
                <i className="sw cw" />
                cache write
              </span>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
