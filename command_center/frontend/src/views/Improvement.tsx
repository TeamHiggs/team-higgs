import { api } from "../api/client";
import { useApi } from "../api/hooks";
import { EmptyNote, ErrorState, Loading, Pill, Sev } from "../components/atoms";
import { relativeTime } from "../lib/format";
import type { ViewName, GotoOptions } from "../components/Shell";
import type { LearningOut } from "../api/types";

interface Props {
  onUnauthorized: () => void;
  goto: (view: ViewName, opts?: GotoOptions) => void;
}

const LEARNING_TAGS: Record<string, string> = {
  start: "start",
  stop: "stop",
  keep: "keep",
  question: "question",
};

function learningTagClass(category: string): string {
  return LEARNING_TAGS[category.toLowerCase()] ?? "keep";
}

export function ImprovementView({ onUnauthorized, goto }: Props) {
  const { data, error, loading, reload } = useApi(api.improvement, onUnauthorized);

  return (
    <section className="view" aria-label="Continuous improvement">
      <div className="view-head">
        <div className="view-head-row">
          <div>
            <h1>Continuous improvement</h1>
            <p className="sub">
              Retros, learnings, and the debt ledger — the team's reflective
              record. Scheduling an improvement is just authoring a task;{" "}
              <span className="never">nothing here runs a retro or an agent</span>.
            </p>
          </div>
          <span className="spacer" />
          <button
            className="btn btn-gate"
            onClick={() => goto("create", { prefill: "improve" })}
          >
            Schedule improvement task
          </button>
        </div>
      </div>
      <div className="view-scroll">
        {loading && <Loading label="loading improvement record" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && (
          <>
            <div className="groom-note">
              <span aria-hidden="true">ℹ️</span>
              <span>
                <b>“Schedule an improvement” creates a backlog task</b> (a state
                write) — e.g. a health pass or a debt paydown — that you then
                greenlight in{" "}
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => goto("backlog")}
                >
                  Backlog
                </button>
                . Retros themselves are run by the EM in-session, never from this
                page.
              </span>
            </div>

            <div className="board-sec">
              <span className="lbl">retros</span>
              {data.retros.length === 0 ? (
                <EmptyNote title="No retros" body="No retrospectives opened yet." />
              ) : (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>retro</th>
                      <th>trigger</th>
                      <th>doc</th>
                      <th>opened</th>
                      <th>status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.retros.map((retro) => (
                      <tr key={retro.id}>
                        <td className="tnum">#{retro.id}</td>
                        <td className="strong">{retro.trigger}</td>
                        <td className="ref">{retro.doc_path ?? "—"}</td>
                        <td className="ref">{relativeTime(retro.opened_at)}</td>
                        <td>
                          <Pill status={retro.closed_at ? "done" : "open"} label={retro.closed_at ? "closed" : "open"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="board-sec">
              <span className="lbl">learnings · start / stop / keep / question</span>
              {data.learnings.length === 0 ? (
                <EmptyNote title="No learnings" body="Nothing has been filed yet." />
              ) : (
                <div className="stack">
                  {data.learnings.map((l: LearningOut) => (
                    <div className="rcard" key={l.id}>
                      <div className="rtop">
                        <span className={`ltag ${learningTagClass(l.category)}`}>
                          {l.category}
                        </span>
                        <span className="rtitle">{l.observation}</span>
                        <Pill status={l.status} />
                      </div>
                      {(l.evidence || l.filed_by || l.retro_id != null) && (
                        <div className="links">
                          {l.evidence && <span className="ref">evidence: {l.evidence}</span>}
                          {l.filed_by && <span className="ref">filed by {l.filed_by}</span>}
                          {l.retro_id != null && <span className="ref">retro #{l.retro_id}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="board-sec">
              <span className="lbl">debt ledger</span>
              {data.debt.length === 0 ? (
                <EmptyNote title="No debt recorded" body="The ledger is clean." />
              ) : (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>id</th>
                      <th>location</th>
                      <th>kind</th>
                      <th>severity</th>
                      <th>recur</th>
                      <th>passes</th>
                      <th>status</th>
                      <th>evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.debt.map((d) => (
                      <tr key={d.id}>
                        <td className="tnum">#{d.id}</td>
                        <td className="ref">{d.location}</td>
                        <td className="ref">{d.kind}</td>
                        <td>
                          <Sev level={d.severity} />
                        </td>
                        <td className="tnum">{d.recurrence}</td>
                        <td className="tnum">{d.passes_survived}</td>
                        <td>
                          <Pill status={d.status} />
                        </td>
                        <td>{d.evidence}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
