import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { AsyncState } from "../api/hooks";
import { useApi } from "../api/hooks";
import { useToast } from "../components/ToastProvider";
import { ErrorState, Loading, Sev } from "../components/atoms";
import { riskDotClass } from "../lib/format";
import type { ApprovalItem, ApprovalsOut, DecisionRequest } from "../api/types";

interface Props {
  state: AsyncState<ApprovalsOut>;
  onUnauthorized: () => void;
}

const keyOf = (it: ApprovalItem) => `${it.kind}:${it.id}`;

export function ApprovalsView({ state, onUnauthorized }: Props) {
  const { data, error, loading, reload } = state;
  const [selected, setSelected] = useState<string | null>(null);

  const items = data?.items ?? [];
  const selectedItem = items.find((it) => keyOf(it) === selected) ?? null;

  function clearAndReload() {
    setSelected(null);
    reload();
  }

  const oldestNote = items.length > 0 ? `${items.length} waiting` : "clear";

  return (
    <section className="view" aria-label="Approval queue">
      <div className="body">
        <nav className="gate" aria-label="Approval queue rail">
          <div className="gate-head">
            <div className="gate-count">
              <span className={`n${items.length === 0 ? " clearing" : ""}`} aria-live="polite">
                {loading && !data ? "…" : items.length}
              </span>
              <span className="cap">
                <b>held at the line</b>
                <span>work that stopped for you</span>
              </span>
            </div>
            <div className="gate-sub">
              <span>{oldestNote}</span>
            </div>
          </div>
          {error && <ErrorState error={error} onRetry={reload} />}
          <ol className="queue" aria-label="Items awaiting your decision">
            {items.map((it) => {
              const active = keyOf(it) === selected;
              return (
                <li key={keyOf(it)} style={{ listStyle: "none" }}>
                  <button
                    className={`card${active ? " sel" : ""}`}
                    aria-pressed={active}
                    onClick={() => setSelected(keyOf(it))}
                  >
                    <div className="card-top">
                      <span className={`badge ${it.badge}`}>{it.badge}</span>
                      <span className="proj">
                        {it.project_id != null ? `project #${it.project_id}` : it.kind}
                      </span>
                    </div>
                    <p className="card-title">{it.title}</p>
                    <div className="card-meta">
                      <span className="m">{it.kind}</span>
                      {it.risk_level && (
                        <span className="m">
                          <span className={`dot ${riskDotClass(it.risk_level)}`} />
                          {it.risk_level} risk
                        </span>
                      )}
                      {it.blocking && <span className="flag">blocking</span>}
                    </div>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <main className="detail" aria-label="Item review">
          {selectedItem ? (
            <ApprovalDetail
              key={selected}
              item={selectedItem}
              onDecided={clearAndReload}
              onUnauthorized={onUnauthorized}
            />
          ) : items.length === 0 && !loading && !error ? (
            <div className="empty">
              <div className="line-mark" aria-hidden="true" />
              <h2>The line is clear</h2>
              <p>
                Nothing is waiting on you. The team keeps working; new items dock
                here when they need your call.
              </p>
            </div>
          ) : (
            <div className="pick-prompt">
              <span className="lbl">nothing open</span>
              <p>
                Pick an item from the line to review its artifact here, then
                approve or send it back without leaving the page.
              </p>
            </div>
          )}
        </main>
      </div>
    </section>
  );
}

// ── detail pane — remounts per selection (keyed) so its fetches are scoped ──

interface DetailProps {
  item: ApprovalItem;
  onDecided: () => void;
  onUnauthorized: () => void;
}

function ApprovalDetail({ item, onDecided, onUnauthorized }: DetailProps) {
  const { notify } = useToast();
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // For a PR, approving records the decision but does not merge (backend §7 /
  // Q#4 answer C). Once approved we move to the merge phase in place.
  const [phase, setPhase] = useState<"decide" | "merge">("decide");

  async function decide(verdict: DecisionRequest["verdict"]) {
    if (item.kind === "question") return;
    setSubmitting(true);
    try {
      await api.decide({
        kind: item.kind as DecisionRequest["kind"],
        id: item.id,
        verdict,
        note: note.trim() || null,
      });
      if (item.kind === "pr" && verdict === "approve") {
        notify(`PR #${item.github_pr ?? item.id} approved — ready to merge.`);
        setPhase("merge");
      } else {
        notify(`${item.kind} ${item.id} ${verdict === "approve" ? "approved" : "sent back"}.`);
        onDecided();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return onUnauthorized();
      notify(err instanceof Error ? err.message : "Decision failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function merge() {
    setSubmitting(true);
    try {
      const result = await api.mergePr(item.id);
      notify(result.merged ? `Merged — ${result.detail}` : result.detail);
      onDecided();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return onUnauthorized();
      notify(err instanceof Error ? err.message : "Merge failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function answer() {
    const text = note.trim();
    if (!text) return;
    setSubmitting(true);
    try {
      await api.answerQuestion(item.id, { answer: text });
      notify(`Question ${item.id} answered.`);
      onDecided();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return onUnauthorized();
      notify(err instanceof Error ? err.message : "Could not send the answer.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="detail-scroll">
        <div className="dhead">
          <div className="dhead-top">
            <span className={`badge ${item.badge}`}>{item.badge}</span>
            <span className="proj mono" style={{ color: "var(--faint)", fontSize: "12px" }}>
              {item.project_id != null ? `project #${item.project_id}` : item.kind}
            </span>
          </div>
          <h1 className="dtitle">{item.title}</h1>
          <div className="dmeta">
            <div className="field">
              <span className="lbl">kind</span>
              <span className="v role">{item.kind}</span>
            </div>
            {item.risk_level && (
              <div className="field">
                <span className="lbl">risk</span>
                <span className="v">
                  <Sev level={item.risk_level} />
                </span>
              </div>
            )}
            {item.github_pr != null && (
              <div className="field">
                <span className="lbl">github pr</span>
                <span className="v">#{item.github_pr}</span>
              </div>
            )}
          </div>
        </div>

        {item.kind === "pr" && <PrPreview prId={item.id} onUnauthorized={onUnauthorized} />}
        {item.kind === "artifact" && (
          <ArtifactPreview artifactId={item.id} onUnauthorized={onUnauthorized} />
        )}
        {item.kind === "decision" && (
          <section className="section">
            <span className="lbl">decision record</span>
            <p className="q-body" style={{ fontSize: "14px", color: "var(--mute)" }}>
              The full decision context is curated in emctl. Accept records your
              acceptance; sending it back marks it reversed.
            </p>
          </section>
        )}
        {item.kind === "question" && (
          <section className="section">
            <span className="lbl">decision needed</span>
            <p className="q-body">{item.title}</p>
          </section>
        )}
      </div>

      <div className="decision-bar">
        {item.kind === "question" ? (
          <>
            <div className="note-row">
              <label className="lbl" htmlFor="answer">
                your answer
              </label>
              <textarea
                id="answer"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Answer the team — recorded against the question."
              />
            </div>
            <div className="act-row">
              <span className="spacer" />
              <button
                className="btn-approve"
                disabled={submitting || !note.trim()}
                onClick={answer}
              >
                Send answer
              </button>
            </div>
          </>
        ) : phase === "merge" ? (
          <div className="act-row">
            <span className="cmd-hint mono">
              Decision recorded. Merging calls the GitHub merge API — external
              state, no agent.
            </span>
            <span className="spacer" />
            <button className="btn-secondary" disabled={submitting} onClick={onDecided}>
              Later
            </button>
            <button className="btn-approve" disabled={submitting} onClick={merge}>
              {submitting ? "Merging…" : "Merge pull request"}
            </button>
          </div>
        ) : (
          <>
            <div className="note-row">
              <label className="lbl" htmlFor="note">
                note (optional)
              </label>
              <textarea
                id="note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="A line of reasoning for the record — attached to your decision."
              />
            </div>
            <div className="act-row">
              <span className="spacer" />
              <button
                className="btn-secondary"
                disabled={submitting}
                onClick={() => decide("reject")}
              >
                {item.kind === "decision" ? "Send back" : "Request changes"}
              </button>
              <button
                className="btn-approve"
                disabled={submitting}
                onClick={() => decide("approve")}
              >
                {submitting
                  ? "Recording…"
                  : item.kind === "decision"
                    ? "Accept decision"
                    : item.kind === "artifact"
                      ? "Approve as build spec"
                      : "Approve"}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function PrPreview({ prId, onUnauthorized }: { prId: number; onUnauthorized: () => void }) {
  const { data, error, loading, reload } = useApi(() => api.prDetail(prId), onUnauthorized);

  return (
    <>
      <section className="section">
        <span className="lbl">review panel · strongest objection surfaced</span>
        {loading && <Loading label="loading review panel" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && data.reviews.length === 0 && (
          <p className="sub">No reviews recorded for this PR.</p>
        )}
        {data && data.reviews.length > 0 && (
          <div className="panel-strip">
            {data.reviews.map((rev) => {
              const vd = rev.verdict.replace(/[^a-z_]/gi, "_");
              return (
                <div className="rev" key={rev.id}>
                  <span className={`vd ${vd}`}>{rev.verdict}</span>
                  <div className="rbody">
                    <div className="rrole">
                      {rev.role}
                      {rev.model && <span className="model">{rev.model}</span>}
                    </div>
                    <div className="robj">{rev.strongest_objection}</div>
                    {(rev.findings ?? []).length > 0 && (
                      <ul className="findings">
                        {(rev.findings ?? []).map((f, i) => (
                          <li key={i}>
                            {[f.severity, f.where, f.claim || f.why]
                              .filter(Boolean)
                              .join(" · ")}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {data?.pr.em_summary && (
          <div className="em-summary" style={{ marginTop: "14px" }}>
            {data.pr.em_summary}
          </div>
        )}
      </section>
      <section className="section">
        <span className="lbl">the diff</span>
        <p className="sub">
          The full diff lives on GitHub (the contract exposes the synthesized
          review, not the patch). Approving records your decision; a separate
          merge step calls the GitHub merge API.
        </p>
      </section>
    </>
  );
}

function ArtifactPreview({
  artifactId,
  onUnauthorized,
}: {
  artifactId: number;
  onUnauthorized: () => void;
}) {
  const { data, error, loading, reload } = useApi(
    () => api.artifactContent(artifactId),
    onUnauthorized,
  );

  return (
    <section className="section">
      <span className="lbl">artifact preview</span>
      {loading && <Loading label="loading artifact" />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && (
        <>
          <div style={{ marginBottom: "10px" }} className="ref mono">
            {data.path}
          </div>
          {/* Untrusted free-text (risk #4): rendered as an escaped text child in a
              <pre>. Never dangerouslySetInnerHTML — no HTML-injection path even
              when the artifact itself is an HTML mockup. */}
          <pre className="doc-render">{data.content}</pre>
          {data.truncated && (
            <div className="trunc-note">
              Preview truncated — open the full artifact from the repo.
            </div>
          )}
        </>
      )}
    </section>
  );
}
