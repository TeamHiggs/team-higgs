import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useApi } from "../api/hooks";
import { useToast } from "../components/ToastProvider";
import { EmptyNote, ErrorState, Loading, Pill, Tier } from "../components/atoms";
import type { TaskOut } from "../api/types";

interface Props {
  onUnauthorized: () => void;
}

export function BacklogView({ onUnauthorized }: Props) {
  const { data, error, loading, reload } = useApi(api.backlog, onUnauthorized);
  const { notify } = useToast();
  const [busy, setBusy] = useState<number | null>(null);
  const [blockingId, setBlockingId] = useState<number | null>(null);
  const [reason, setReason] = useState("");

  async function run(taskId: number, fn: () => Promise<unknown>, message: string) {
    setBusy(taskId);
    try {
      await fn();
      notify(message);
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return onUnauthorized();
      notify(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  async function confirmBlock(taskId: number) {
    const text = reason.trim();
    if (!text) return;
    setBlockingId(null);
    setReason("");
    await run(taskId, () => api.block(taskId, text), `Blocked #${taskId}.`);
  }

  async function moveWithin(list: TaskOut[], index: number, dir: -1 | 1) {
    const target = index + dir;
    if (target < 0 || target >= list.length) return;
    const ids = list.map((t) => t.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    await run(
      list[index].id,
      () => api.reorder(ids),
      `Reordered #${list[index].id}.`,
    );
  }

  function backlogRow(task: TaskOut, index: number, list: TaskOut[]) {
    const isBlocking = blockingId === task.id;
    return (
      <div className={`trow${task.blocked ? "" : ""}`} key={task.id}>
        <span className="reorder" role="group" aria-label={`Reorder task ${task.id}`}>
          <button
            aria-label={`Move task ${task.id} up`}
            disabled={index === 0 || busy != null}
            onClick={() => moveWithin(list, index, -1)}
          >
            ▲
          </button>
          <button
            aria-label={`Move task ${task.id} down`}
            disabled={index === list.length - 1 || busy != null}
            onClick={() => moveWithin(list, index, 1)}
          >
            ▼
          </button>
        </span>
        <div className="tmain">
          <div className="ttop">
            <span className="tid">#{task.id}</span>
            <span className="ttitle">{task.title}</span>
          </div>
          <div className="tmeta">
            <span className="m">project #{task.project_id}</span>
            {task.role && (
              <span className="m">
                <b>{task.role}</b>
              </span>
            )}
            <span className="m">
              <Tier tier={task.model_tier} />
            </span>
            {task.depends_on.length > 0 && (
              <span className="m dep">
                depends on {task.depends_on.map((d) => `#${d}`).join(", ")}
              </span>
            )}
            {task.blocked && (
              <span className="blk" title={task.blocked_reason ?? "blocked"}>
                blocked
              </span>
            )}
          </div>
        </div>
        <div className="tacts">
          {isBlocking ? (
            <>
              <input
                className="inp"
                style={{ width: "220px" }}
                autoFocus
                value={reason}
                placeholder="reason (required)"
                aria-label={`Block reason for task ${task.id}`}
                onChange={(e) => setReason(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void confirmBlock(task.id);
                  if (e.key === "Escape") {
                    setBlockingId(null);
                    setReason("");
                  }
                }}
              />
              <button
                className="btn btn-hold btn-sm"
                disabled={!reason.trim()}
                onClick={() => confirmBlock(task.id)}
              >
                Confirm block
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setBlockingId(null);
                  setReason("");
                }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                className="btn btn-hold btn-sm"
                disabled={busy != null}
                onClick={() =>
                  task.blocked
                    ? run(task.id, () => api.unblock(task.id), `Unblocked #${task.id}.`)
                    : (setBlockingId(task.id), setReason(""))
                }
              >
                {task.blocked ? "Unblock" : "Block"}
              </button>
              <button
                className="btn btn-gate btn-sm"
                disabled={busy != null}
                onClick={() =>
                  run(
                    task.id,
                    () => api.greenlight(task.id),
                    `Greenlit #${task.id} → planned.`,
                  )
                }
              >
                Greenlight → planned
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  function contextRow(task: TaskOut) {
    return (
      <div className="trow ctx" key={task.id}>
        <span className="grip" aria-hidden="true">
          ⠿
        </span>
        <div className="tmain">
          <div className="ttop">
            <span className="tid">#{task.id}</span>
            <span className="ttitle">{task.title}</span>
          </div>
          <div className="tmeta">
            <span className="m">project #{task.project_id}</span>
            {task.role && (
              <span className="m">
                <b>{task.role}</b>
              </span>
            )}
            <span className="m">
              <Tier tier={task.model_tier} />
            </span>
          </div>
        </div>
        <div className="tacts">
          <Pill status={task.status} />
        </div>
      </div>
    );
  }

  const dist = data
    ? {
        backlog: data.backlog.length,
        planned: data.planned.length,
        in_progress: data.in_flight.filter((t) => t.status === "in_progress").length,
        in_review: data.in_flight.filter((t) => t.status === "in_review").length,
      }
    : null;

  return (
    <section className="view" aria-label="Backlog grooming">
      <div className="view-head">
        <div className="view-head-row">
          <div>
            <h1>Backlog grooming</h1>
            <p className="sub">
              Greenlight, prioritize, and block — the state changes that shape
              what the team picks up next.{" "}
              <span className="never">writes state · never launches agents</span>
            </p>
          </div>
          <span className="spacer" />
          {dist && (
            <div className="dist" aria-label="Task counts by status">
              <span className="d hot">
                <b>{dist.backlog}</b> backlog
              </span>
              <span className="d">
                <b>{dist.planned}</b> planned
              </span>
              <span className="d">
                <b>{dist.in_progress}</b> in&nbsp;progress
              </span>
              <span className="d">
                <b>{dist.in_review}</b> in&nbsp;review
              </span>
            </div>
          )}
        </div>
      </div>
      <div className="view-scroll">
        {loading && <Loading label="loading backlog" />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && (
          <>
            <div className="groom-note">
              <span aria-hidden="true">ℹ️</span>
              <span>
                <b>
                  Greenlighting sets a task <code>backlog → planned</code>
                </b>{" "}
                — it marks the task ready to dispatch. Dispatch itself happens
                elsewhere (the EM's dispatch layer picks up <code>planned</code>{" "}
                tasks). Nothing on this page spawns an agent.
              </span>
            </div>

            <div className="board-sec">
              <span className="lbl">backlog · needs your greenlight</span>
              {data.backlog.length === 0 ? (
                <EmptyNote title="Backlog is empty" body="Nothing is waiting for a greenlight." />
              ) : (
                data.backlog.map((task, i) => backlogRow(task, i, data.backlog))
              )}
            </div>

            <div className="board-sec">
              <span className="lbl">planned · ready to dispatch (greenlit)</span>
              {data.planned.length === 0 ? (
                <p className="sub">Nothing greenlit yet.</p>
              ) : (
                data.planned.map((task) => contextRow(task))
              )}
            </div>

            <div className="board-sec">
              <span className="lbl">in flight · context only, no grooming actions</span>
              {data.in_flight.length === 0 ? (
                <p className="sub">Nothing in flight.</p>
              ) : (
                data.in_flight.map((task) => contextRow(task))
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
