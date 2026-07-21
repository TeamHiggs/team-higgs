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
  const api = { createTask: vi.fn() };
  return { api, ApiError };
});

vi.mock("../api/client", () => ({ api, ApiError }));

import { CreateTaskView } from "./CreateTask";
import { ToastProvider } from "../components/ToastProvider";

function renderView(prefill?: "improve") {
  return render(
    <ToastProvider>
      <CreateTaskView prefill={prefill} onUnauthorized={vi.fn()} />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.createTask.mockResolvedValue({
    id: 42,
    project_id: 3,
    title: "New task",
    status: "backlog",
    blocked: false,
    blocked_reason: null,
    model_tier: "execute",
    depends_on: [],
    created_at: "2026-07-20T00:00:00Z",
    updated_at: "2026-07-20T00:00:00Z",
  });
});

describe("CreateTaskView", () => {
  it("blocks submission and does not call the API when the title is empty", async () => {
    const user = userEvent.setup();
    renderView();
    await user.click(screen.getByRole("button", { name: "Create in backlog" }));
    expect(api.createTask).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/Title/)).toHaveAttribute("aria-invalid", "true");
  });

  it("submits a typed CreateTaskRequest with parsed dependencies", async () => {
    const user = userEvent.setup();
    renderView();

    await user.type(screen.getByLabelText(/Title/), "Wire the dashboard");
    await user.click(screen.getByRole("radio", { name: /plan/ }));
    await user.type(screen.getByLabelText(/Depends on/), "25, 27");
    await user.click(screen.getByRole("button", { name: "Create in backlog" }));

    expect(api.createTask).toHaveBeenCalledWith({
      title: "Wire the dashboard",
      project: 3,
      role: "implementer-frontend",
      tier: "plan",
      spec: null,
      prd_ref: null,
      depends_on: [25, 27],
    });
  });

  it("prefills the improvement variant without spawning anything", () => {
    renderView("improve");
    expect((screen.getByLabelText(/Title/) as HTMLInputElement).value).toMatch(
      /Improvement:/,
    );
  });
});
