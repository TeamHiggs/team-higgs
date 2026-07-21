import { api } from "../api/client";
import { useApi } from "../api/hooks";
import { EmptyNote, ErrorState, Loading, ReadOnlyChip } from "../components/atoms";
import { relativeTime } from "../lib/format";
import type { ViewName, GotoOptions } from "../components/Shell";

interface Props {
  onUnauthorized: () => void;
  goto: (view: ViewName, opts?: GotoOptions) => void;
}

export function QuestionsView({ onUnauthorized, goto }: Props) {
  const { data, error, loading, reload } = useApi(api.questions, onUnauthorized);

  // Unanswered first, blocking above those; the full open set (answered shown
  // for context, matching the read-only ledger intent).
  const rows = data
    ? [...data].sort((a, b) => {
        const aOpen = a.answer == null ? 0 : 1;
        const bOpen = b.answer == null ? 0 : 1;
        if (aOpen !== bOpen) return aOpen - bOpen;
        return Number(b.blocking) - Number(a.blocking);
      })
    : [];

  return (
    <section className="view" aria-label="Open questions">
      <div className="view-head">
        <div className="view-head-row">
          <div>
            <h1>Open questions</h1>
            <p className="sub">
              Everything the team has stopped to ask you. Blocking questions also
              dock at the line; answer them there — this view is the full open
              set.
            </p>
          </div>
          <span className="spacer" />
          <ReadOnlyChip />
        </div>
      </div>
      <div className="view-scroll">
        {loading && <Loading label="loading questions" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && rows.length === 0 && (
          <EmptyNote title="No open questions" body="The team has nothing waiting on your word." />
        )}
        {rows.length > 0 && (
          <div className="stack">
            {rows.map((qn) => {
              const open = qn.answer == null;
              return (
                <div className={`qcard${qn.blocking && open ? " blocking" : ""}`} key={qn.id}>
                  <div className="qtop">
                    <span className="ref mono">
                      Q#{qn.id}
                      {qn.project_id != null ? ` · project #${qn.project_id}` : ""}
                    </span>
                    {qn.blocking && open && <span className="flag">blocking</span>}
                  </div>
                  <p className="qbody">{qn.body}</p>
                  <div className="qfoot">
                    <span>asked {relativeTime(qn.created_at)}</span>
                    {open && qn.blocking && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => goto("approvals")}
                      >
                        answer at the line ↗
                      </button>
                    )}
                  </div>
                  {qn.answer != null && (
                    <div className="qanswer">
                      <span className="lbl">your answer</span> {qn.answer}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
