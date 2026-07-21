import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AsyncState } from "../api/hooks";
import type { ApprovalsOut } from "../api/types";

const { api, ApiError } = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      public status: number,
      public detail: string,
    ) {
      super(detail);
    }
  }
  const api = {
    approvals: vi.fn(),
    prDetail: vi.fn(),
    artifactContent: vi.fn(),
    decide: vi.fn(),
    mergePr: vi.fn(),
    answerQuestion: vi.fn(),
  };
  return { api, ApiError };
});

vi.mock("../api/client", () => ({ api, ApiError }));

import { ApprovalsView } from "./Approvals";
import { ToastProvider } from "../components/ToastProvider";

function state(items: ApprovalsOut["items"], reload = vi.fn()): AsyncState<ApprovalsOut> {
  return { data: { items }, error: null, loading: false, reload };
}

function renderView(s: AsyncState<ApprovalsOut>) {
  return render(
    <ToastProvider>
      <ApprovalsView state={s} onUnauthorized={vi.fn()} />
    </ToastProvider>,
  );
}

const prItem = {
  kind: "pr" as const,
  id: 6,
  title: "Backend auth hardening",
  badge: "pr",
  project_id: 2,
  risk_level: "medium",
  github_pr: 6,
};

const artifactItem = {
  kind: "artifact" as const,
  id: 9,
  title: "docs/design/mockup.html",
  badge: "mockup",
  project_id: 1,
  artifact_type: "mockup",
};

beforeEach(() => {
  vi.clearAllMocks();
  api.prDetail.mockResolvedValue({
    pr: {
      id: 6,
      project_id: 2,
      github_pr: 6,
      status: "open",
      risk_level: "medium",
      em_summary: "Two reviewers, no blocks.",
      tyler_decision: null,
      task_id: 14,
    },
    reviews: [
      {
        id: 1,
        pr_id: 6,
        role: "reviewer-security",
        verdict: "approve",
        strongest_objection: "The /history 401 path is untested.",
        model: "opus-4.8",
        findings: [],
        created_at: "2026-07-20T00:00:00Z",
      },
    ],
  });
  api.decide.mockResolvedValue({ detail: "ok" });
  api.mergePr.mockResolvedValue({ merged: true, detail: "merged", sha: "abc123" });
});

describe("ApprovalsView", () => {
  it("shows the count and the empty state when the line is clear", () => {
    renderView(state([]));
    expect(screen.getByText("The line is clear")).toBeInTheDocument();
  });

  it("approve records a PR decision then surfaces a separate merge step (Q#4 → C)", async () => {
    const user = userEvent.setup();
    renderView(state([prItem]));

    await user.click(screen.getByRole("button", { name: /Backend auth hardening/ }));
    // review panel loads from the PR detail endpoint
    expect(await screen.findByText(/The \/history 401 path is untested\./)).toBeInTheDocument();
    expect(screen.getByText("Two reviewers, no blocks.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(api.decide).toHaveBeenCalledWith({
      kind: "pr",
      id: 6,
      verdict: "approve",
      note: null,
    });

    // Approving does NOT merge; a deliberate merge action appears.
    const mergeBtn = await screen.findByRole("button", { name: "Merge pull request" });
    expect(api.mergePr).not.toHaveBeenCalled();
    await user.click(mergeBtn);
    expect(api.mergePr).toHaveBeenCalledWith(6);
  });

  it("request changes rejects with the note attached", async () => {
    const user = userEvent.setup();
    const reload = vi.fn();
    renderView(state([prItem], reload));

    await user.click(screen.getByRole("button", { name: /Backend auth hardening/ }));
    await screen.findByText(/untested/);
    await user.type(screen.getByLabelText(/note/i), "Add the 401 test first.");
    await user.click(screen.getByRole("button", { name: "Request changes" }));

    expect(api.decide).toHaveBeenCalledWith({
      kind: "pr",
      id: 6,
      verdict: "reject",
      note: "Add the 401 test first.",
    });
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  it("renders untrusted artifact free-text ESCAPED — no HTML injection (risk #4)", async () => {
    const user = userEvent.setup();
    const payload = '<img src=x onerror="alert(1)"> <script>steal()</script> plain body';
    api.artifactContent.mockResolvedValue({
      path: "docs/design/mockup.html",
      content: payload,
      truncated: false,
    });
    const { container } = renderView(state([artifactItem]));

    await user.click(screen.getByRole("button", { name: /docs\/design\/mockup\.html/ }));

    // The raw text is present verbatim...
    const pre = await screen.findByText(/plain body/);
    expect(pre.textContent).toContain("<img");
    expect(pre.textContent).toContain("<script>");
    // ...but no element was injected into the DOM.
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });
});
