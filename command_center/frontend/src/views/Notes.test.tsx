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
  const api = { notes: vi.fn(), createNote: vi.fn() };
  return { api, ApiError };
});

vi.mock("../api/client", () => ({ api, ApiError }));

import { NotesView } from "./Notes";
import { ToastProvider } from "../components/ToastProvider";

function renderView() {
  return render(
    <ToastProvider>
      <NotesView onUnauthorized={vi.fn()} />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("NotesView", () => {
  it("renders note bodies as escaped text — no HTML injection (risk #4)", async () => {
    const injection = '<img src=x onerror="alert(1)"> keep it safe';
    api.notes.mockResolvedValue([
      { id: 1, body: injection, created_at: "2026-07-20T00:00:00Z", author: "tyler", context: null },
    ]);
    const { container } = renderView();

    const body = await screen.findByText(/keep it safe/);
    expect(body.textContent).toContain("<img");
    expect(container.querySelector("img")).toBeNull();
  });

  it("posts a new note and refreshes the list", async () => {
    const user = userEvent.setup();
    api.notes.mockResolvedValue([]);
    api.createNote.mockResolvedValue({
      id: 2,
      body: "a fresh thought",
      created_at: "2026-07-21T00:00:00Z",
      author: "tyler",
      context: null,
    });
    renderView();
    await screen.findByText(/No notes yet/);

    await user.type(screen.getByLabelText(/new note/), "a fresh thought");
    await user.click(screen.getByRole("button", { name: "Save note" }));

    expect(api.createNote).toHaveBeenCalledWith({ body: "a fresh thought" });
    // list re-fetched after the write
    expect(api.notes).toHaveBeenCalledTimes(2);
  });

  it("disables save on an empty note", async () => {
    api.notes.mockResolvedValue([]);
    renderView();
    await screen.findByText(/No notes yet/);
    expect(screen.getByRole("button", { name: "Save note" })).toBeDisabled();
  });
});
