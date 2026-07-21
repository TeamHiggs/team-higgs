import { api } from "../api/client";
import { useApi } from "../api/hooks";
import { ErrorState, Loading, Pill, ReadOnlyChip, Sev } from "../components/atoms";
import type { PrOut } from "../api/types";

interface Props {
  onUnauthorized: () => void;
}

const STATUS_ORDER: Record<string, number> = { open: 0, merged: 1, closed: 2, rejected: 2 };

export function PrsView({ onUnauthorized }: Props) {
  const { data, error, loading, reload } = useApi(api.prs, onUnauthorized);

  const rows = data
    ? [...data].sort(
        (a, b) =>
          (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9) ||
          b.github_pr - a.github_pr,
      )
    : [];

  return (
    <section className="view" aria-label="Pull requests">
      <div className="view-head">
        <div className="view-head-row">
          <div>
            <h1>Pull requests</h1>
            <p className="sub">
              Every PR the EM has opened, with its synthesized risk and your
              recorded decision. Reviewing and approving happens at the line —
              this is the ledger.
            </p>
          </div>
          <span className="spacer" />
          <ReadOnlyChip />
        </div>
      </div>
      <div className="view-scroll">
        {loading && <Loading label="loading pull requests" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && rows.length === 0 && (
          <p className="sub">No pull requests recorded yet.</p>
        )}
        {data && rows.length > 0 && (
          <table className="tbl">
            <thead>
              <tr>
                <th>PR</th>
                <th>project</th>
                <th>implements</th>
                <th>status</th>
                <th>risk</th>
                <th>your decision</th>
                <th>EM summary</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((pr: PrOut) => (
                <tr key={pr.id}>
                  <td className="tnum">#{pr.github_pr}</td>
                  <td className="ref">project #{pr.project_id}</td>
                  <td className="ref">{pr.task_id != null ? `task ${pr.task_id}` : "—"}</td>
                  <td>
                    <Pill status={pr.status} />
                  </td>
                  <td>{pr.risk_level ? <Sev level={pr.risk_level} /> : "—"}</td>
                  <td className="ref">
                    {pr.tyler_decision ? (
                      <span className="strong">{pr.tyler_decision}</span>
                    ) : (
                      "— awaiting"
                    )}
                  </td>
                  <td className="strong">{pr.em_summary ?? "—"}</td>
                </tr>
              ))}
            </tbody>
            <caption>open PRs sort first · decided PRs shown for recent context</caption>
          </table>
        )}
      </div>
    </section>
  );
}
