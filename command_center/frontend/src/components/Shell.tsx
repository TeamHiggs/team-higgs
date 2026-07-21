import { useCallback, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { useApi } from "../api/hooks";
import { goToLogin } from "../lib/nav";
import type { UserOut } from "../api/types";
import { ApprovalsView } from "../views/Approvals";
import { BacklogView } from "../views/Backlog";
import { CreateTaskView, type CreatePrefill } from "../views/CreateTask";
import { PrsView } from "../views/Prs";
import { RisksView } from "../views/Risks";
import { QuestionsView } from "../views/Questions";
import { RunsView } from "../views/Runs";
import { ImprovementView } from "../views/Improvement";
import { NotesView } from "../views/Notes";

export type ViewName =
  | "approvals"
  | "backlog"
  | "create"
  | "prs"
  | "risks"
  | "questions"
  | "runs"
  | "improve"
  | "notes";

export interface GotoOptions {
  prefill?: CreatePrefill;
}

const SEG: Record<ViewName, [string, string]> = {
  approvals: ["approvals", "the line"],
  backlog: ["backlog", "grooming"],
  create: ["new task", "author"],
  prs: ["pull requests", "the ledger"],
  risks: ["risks", "register"],
  questions: ["questions", "open set"],
  runs: ["run costs", "spend"],
  improve: ["improvement", "reflect"],
  notes: ["notes", "yours"],
};

interface NavDef {
  view: ViewName;
  label: string;
  icon: ReactNode;
  gate?: boolean;
}

const NAV_GROUPS: { label: string; items: NavDef[] }[] = [
  {
    label: "the line",
    items: [
      {
        view: "approvals",
        label: "Approvals",
        gate: true,
        icon: <path d="M4 10h9M10 6l4 4-4 4" />,
      },
    ],
  },
  {
    label: "groom",
    items: [
      {
        view: "backlog",
        label: "Backlog",
        icon: (
          <>
            <rect x="4" y="4" width="12" height="3" rx="1" />
            <rect x="4" y="9" width="12" height="3" rx="1" />
            <rect x="4" y="14" width="8" height="3" rx="1" />
          </>
        ),
      },
      { view: "create", label: "New task", icon: <path d="M10 4v12M4 10h12" /> },
    ],
  },
  {
    label: "state · read-only",
    items: [
      {
        view: "prs",
        label: "Pull requests",
        icon: (
          <>
            <circle cx="6" cy="6" r="2" />
            <circle cx="6" cy="15" r="2" />
            <circle cx="14" cy="6" r="2" />
            <path d="M6 8v5M14 8v2a3 3 0 0 1-3 3H8" />
          </>
        ),
      },
      {
        view: "risks",
        label: "Risks",
        icon: (
          <>
            <path d="M10 3l7 13H3z" />
            <path d="M10 8v4M10 14v.5" />
          </>
        ),
      },
      {
        view: "questions",
        label: "Questions",
        icon: (
          <>
            <circle cx="10" cy="10" r="7" />
            <path d="M8 8a2 2 0 1 1 3 1.7c-.6.4-1 .8-1 1.6M10 14v.3" />
          </>
        ),
      },
      { view: "runs", label: "Run costs", icon: <path d="M4 16V9M9 16V5M14 16v-4" /> },
    ],
  },
  {
    label: "reflect",
    items: [
      {
        view: "improve",
        label: "Improvement",
        icon: (
          <>
            <path d="M4 10a6 6 0 0 1 10-4.5M16 5v3h-3" />
            <path d="M16 10a6 6 0 0 1-10 4.5M4 15v-3h3" />
          </>
        ),
      },
      { view: "notes", label: "Notes", icon: <path d="M5 4h10v12l-5-3-5 3z" /> },
    ],
  },
];

export function Shell({ user }: { user: UserOut }) {
  const [view, setView] = useState<ViewName>("approvals");
  const [prefill, setPrefill] = useState<CreatePrefill | undefined>();

  // The approvals query lives here so the amber "held at the line" nav badge and
  // the Approvals view share one fetch (the load-bearing count in this surface).
  const approvals = useApi(api.approvals, goToLogin);
  const approvalCount = approvals.data?.items.length ?? null;

  const goto = useCallback((next: ViewName, opts?: GotoOptions) => {
    setPrefill(opts?.prefill);
    setView(next);
  }, []);

  const initials = useMemo(() => {
    const source = user.name || user.email;
    const parts = source.split(/[\s@._-]+/).filter(Boolean);
    const letters = (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "");
    return (letters || source.slice(0, 2)).toUpperCase();
  }, [user]);

  const [seg, sub] = SEG[view];

  return (
    <div className="app">
      <header className="topbar">
        <div className="mark">
          emctl<span className="chev">▸</span>
          <span className="seg">{seg}</span>
          <small>{sub}</small>
        </div>
        <div className="spacer" />
        <div className="legend" aria-hidden="true">
          <span className="k">
            <i className="swatch machine" />
            machine work
          </span>
          <span className="k">
            <i className="swatch human" />
            your call
          </span>
        </div>
        <div className="who">
          <span>{user.name} · architect</span>
          <span className="av" aria-hidden="true">
            {initials}
          </span>
          <button
            className="signout"
            title="Single-user surface — Tyler only"
            onClick={() => {
              api.logout().finally(goToLogin);
            }}
          >
            sign out
          </button>
        </div>
      </header>

      <div className="shell">
        <nav className="rail" aria-label="Command center sections">
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.label}>
              <span className="lbl">{group.label}</span>
              {group.items.map((item) => {
                const active = view === item.view;
                const count = item.view === "approvals" ? approvalCount : null;
                return (
                  <button
                    key={item.view}
                    className={`nav-item${item.gate ? " gate" : ""}${active ? " active" : ""}`}
                    aria-current={active ? "page" : undefined}
                    onClick={() => goto(item.view)}
                  >
                    <svg viewBox="0 0 20 20">{item.icon}</svg>
                    <span className="txt">{item.label}</span>
                    {count != null && <span className="num tnum">{count}</span>}
                  </button>
                );
              })}
            </div>
          ))}
          <div className="rail-foot">
            <b>emctl</b> is the source of truth. This surface reads and writes the
            same Postgres state the CLI does — and <b>never launches agents</b>.
          </div>
        </nav>

        <div className="views">
          {view === "approvals" && (
            <ApprovalsView state={approvals} onUnauthorized={goToLogin} />
          )}
          {view === "backlog" && <BacklogView onUnauthorized={goToLogin} />}
          {view === "create" && (
            <CreateTaskView prefill={prefill} onUnauthorized={goToLogin} />
          )}
          {view === "prs" && <PrsView onUnauthorized={goToLogin} />}
          {view === "risks" && <RisksView onUnauthorized={goToLogin} />}
          {view === "questions" && (
            <QuestionsView onUnauthorized={goToLogin} goto={goto} />
          )}
          {view === "runs" && <RunsView onUnauthorized={goToLogin} />}
          {view === "improve" && (
            <ImprovementView onUnauthorized={goToLogin} goto={goto} />
          )}
          {view === "notes" && <NotesView onUnauthorized={goToLogin} />}
        </div>
      </div>
    </div>
  );
}
