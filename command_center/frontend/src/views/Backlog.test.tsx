import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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
    backlog: vi.fn(),
    greenlight: vi.fn(),
    block: vi.fn(),
    unblock: vi.fn(),
    reorder: vi.fn(),
  };
  return { api, ApiError };
});

vi.mock("../api/client", () => ({ api, ApiError }));

import { BacklogView } from "./Backlog";
import { ToastProvider } from "../components/ToastProvider";

function task(over: Record<string, unknown>) {
  return {
    id: 1,
    project_id: 3,
    title: "A task",
    status: "backlog",
    blocked: false,
    blocked_reason: null,
    model_tier: "execute",
    role: "implementer-frontend",
    depends_on: [],
    branch: null,
    spec: null,
    prd_ref: null,
    groom_rank: null,
    created_at: "2026-07-20T00:00:00Z",
    updated_at: "2026-07-20T00:00:00Z",
    ...over,
  };
}

function renderView() {
  return render(
    <ToastProvider>
      <BacklogView onUnauthorized={vi.fn()} />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.backlog.mockResolvedValue({
    backlog: [
      task({ id: 26, title: "Build the SPA" }),
      task({ id: 27, title: "Read-only endpoints" }),
    ],
    planned: [task({ id: 20, title: "Deploy image", status: "planned" })],
    in_flight: [task({ id: 14, title: "Auth hardening", status: "in_progress" })],
  });
  api.greenlight.mockResolvedValue(task({ id: 26, status: "planned" }));
  api.block.mockResolvedValue(task({ id: 26, blocked: true, blocked_reason: "needs Q#4" }));
  api.reorder.mockResolvedValue([]);
});

describe("BacklogView", () => {
  it("greenlights a backlog task (backlog → planned state write)", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByText("Build the SPA");

    const rows = screen.getAllByRole("button", { name: "Greenlight → planned" });
    await user.click(rows[0]);
    expect(api.greenlight).toHaveBeenCalledWith(26);
  });

  it("blocking requires a reason before the block is written", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByText("Build the SPA");

    await user.click(screen.getAllByRole("button", { name: "Block" })[0]);
    const reason = screen.getByLabelText(/Block reason for task 26/);
    // Confirm is disabled until a reason is entered.
    expect(screen.getByRole("button", { name: "Confirm block" })).toBeDisabled();

    await user.type(reason, "waiting on Q#4");
    await user.click(screen.getByRole("button", { name: "Confirm block" }));
    expect(api.block).toHaveBeenCalledWith(26, "waiting on Q#4");
  });

  it("reorders via keyboard-accessible move controls", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByText("Build the SPA");

    await user.click(screen.getByRole("button", { name: "Move task 26 down" }));
    // ordered ids for the backlog set, with 26 and 27 swapped
    expect(api.reorder).toHaveBeenCalledWith([27, 26]);
  });

  it("does not offer grooming actions on in-flight tasks", async () => {
    renderView();
    await screen.findByText("Auth hardening");
    // Only the two backlog rows get grooming controls; the in-flight task is
    // context only (a status pill, no greenlight).
    expect(screen.getAllByRole("button", { name: "Greenlight → planned" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Block" })).toHaveLength(2);
  });
});
