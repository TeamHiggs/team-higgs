import { useMemo, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { useToast } from "../components/ToastProvider";
import { Pill } from "../components/atoms";
import type { CreateTaskRequest, ModelTier } from "../api/types";

export type CreatePrefill = "improve";

interface Props {
  prefill?: CreatePrefill;
  onUnauthorized: () => void;
}

// Project + role option sets mirror the approved mockup. There is no projects
// endpoint in the contract, so the id/label map lives here (public, non-secret);
// a projects list endpoint is a proposed backend follow-up.
const PROJECTS: { value: number; label: string }[] = [
  { value: 3, label: "command-center · #3" },
  { value: 1, label: "platform · #1" },
  { value: 2, label: "plant-log · #2" },
];

const ROLES = [
  "implementer-frontend",
  "implementer-backend",
  "implementer-devops",
  "implementer-ml",
  "reviewer-security",
  "tech-writer",
  "codebase-health",
  "em",
];

const TIERS: { tier: ModelTier; label: string; sub: string }[] = [
  { tier: "plan", label: "plan", sub: "deliberation" },
  { tier: "execute", label: "execute", sub: "default" },
  { tier: "local", label: "local", sub: "cheap / offline" },
];

function shellQuote(s: string): string {
  return /[^A-Za-z0-9_./#-]/.test(s) ? `"${s.replace(/"/g, '\\"')}"` : s;
}

function parseDeps(raw: string): number[] {
  return raw
    .split(/[,\s]+/)
    .map((d) => d.replace(/[^0-9]/g, ""))
    .filter(Boolean)
    .map(Number);
}

const IMPROVE_SPEC =
  "Scope the improvement: which retro finding, learning, or debt-ledger item this addresses, and what 'resolved' looks like.";

export function CreateTaskView({ prefill, onUnauthorized }: Props) {
  const { notify } = useToast();
  const improve = prefill === "improve";

  const [title, setTitle] = useState(improve ? "Improvement: health pass / debt paydown — " : "");
  const [project, setProject] = useState<number>(improve ? 1 : 3);
  const [role, setRole] = useState<string>(improve ? "codebase-health" : "implementer-frontend");
  const [tier, setTier] = useState<ModelTier>("execute");
  const [spec, setSpec] = useState(improve ? IMPROVE_SPEC : "");
  const [prdRef, setPrdRef] = useState("");
  const [deps, setDeps] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [titleError, setTitleError] = useState(false);

  const commandPreview = useMemo(() => {
    const parts = ["emctl task create"];
    parts.push(`--title ${title.trim() ? shellQuote(title.trim()) : "…"}`);
    parts.push(`--project ${project}`);
    if (role) parts.push(`--role ${role}`);
    parts.push(`--tier ${tier}`);
    const s = spec.trim();
    if (s) parts.push(`--spec ${shellQuote(s.length > 28 ? s.slice(0, 28) + "…" : s)}`);
    if (prdRef.trim()) parts.push(`--prd-ref ${shellQuote(prdRef.trim())}`);
    parseDeps(deps).forEach((d) => parts.push(`--depends-on ${d}`));
    return parts.join(" ");
  }, [title, project, role, tier, spec, prdRef, deps]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) {
      setTitleError(true);
      notify("Title is required to create a task.");
      return;
    }
    setSubmitting(true);
    const payload: CreateTaskRequest = {
      title: trimmed,
      project,
      role,
      tier,
      spec: spec.trim() || null,
      prd_ref: prdRef.trim() || null,
      depends_on: parseDeps(deps),
    };
    try {
      const task = await api.createTask(payload);
      notify(`Created task #${task.id} in backlog.`);
      setTitle("");
      setSpec("");
      setPrdRef("");
      setDeps("");
      setTier("execute");
      setTitleError(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return onUnauthorized();
      notify(err instanceof Error ? err.message : "Could not create the task.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="view" aria-label="Create a task">
      <div className="view-head">
        <h1>New task</h1>
        <p className="sub">
          Author a backlog item. It lands as <code className="mono">backlog</code>{" "}
          and waits for your greenlight before anything can pick it up.
        </p>
      </div>
      <div className="view-scroll">
        <form className="form" onSubmit={submit} noValidate>
          <div className="frow">
            <label htmlFor="f-title">
              Title <span className="req">required</span>
            </label>
            <input
              className="inp"
              id="f-title"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (titleError) setTitleError(false);
              }}
              aria-invalid={titleError}
              required
              placeholder="e.g. Build the emctl command-center SPA from mockup v1"
            />
          </div>

          <div className="frow-2">
            <div className="frow">
              <label htmlFor="f-project">
                Project <span className="req">required</span>
              </label>
              <select
                className="sel"
                id="f-project"
                value={project}
                onChange={(e) => setProject(Number(e.target.value))}
              >
                {PROJECTS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="frow">
              <label htmlFor="f-role">Role</label>
              <select
                className="sel"
                id="f-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="frow">
            <label id="tier-label">Model tier</label>
            <div className="seg" role="radiogroup" aria-labelledby="tier-label">
              {TIERS.map((t) => (
                <button
                  key={t.tier}
                  type="button"
                  className={tier === t.tier ? "on" : undefined}
                  role="radio"
                  aria-checked={tier === t.tier}
                  onClick={() => setTier(t.tier)}
                >
                  {t.label}
                  <span className="sub">{t.sub}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="frow">
            <label htmlFor="f-spec">Spec</label>
            <textarea
              className="ta"
              id="f-spec"
              value={spec}
              onChange={(e) => setSpec(e.target.value)}
              placeholder="What done looks like: scope, the governing artifact/contract, and the boundaries. This becomes the implementer's brief."
            />
            <span className="hint">
              Plain text. Reference the PRD section and the approved artifact
              rather than restating them.
            </span>
          </div>

          <div className="frow-2">
            <div className="frow">
              <label htmlFor="f-prd">PRD ref</label>
              <input
                className="inp"
                id="f-prd"
                value={prdRef}
                onChange={(e) => setPrdRef(e.target.value)}
                placeholder="docs/prd/emctl.md#4"
              />
            </div>
            <div className="frow">
              <label htmlFor="f-deps">Depends on</label>
              <input
                className="inp"
                id="f-deps"
                value={deps}
                onChange={(e) => setDeps(e.target.value)}
                placeholder="task ids, comma-separated — e.g. 25"
              />
              <span className="hint">Blockers that must reach done first.</span>
            </div>
          </div>

          <div className="form-foot">
            <span className="status-target">
              opens as
              <Pill status="backlog" />
            </span>
            <span className="spacer" />
            <button type="submit" className="btn btn-gate" disabled={submitting}>
              {submitting ? "Creating…" : "Create in backlog"}
            </button>
          </div>

          <div className="frow">
            <label>equivalent CLI</label>
            <div className="doc-render" aria-label="Equivalent emctl command" style={{ maxHeight: "none" }}>
              $ {commandPreview}
            </div>
          </div>
        </form>
      </div>
    </section>
  );
}
