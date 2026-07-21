// Typed fetch wrapper around the command-center JSON API.
//
// The backend attaches a signed, httpOnly session cookie (command_center/security.py),
// so requests carry `credentials: "same-origin"` and we never touch a token in JS
// (nothing environment-specific or secret lives in the client). Every non-2xx
// becomes an ApiError carrying the backend's `{ detail }` message; a 401 means the
// session is gone, which the app turns into a login redirect.
import type {
  AnswerRequest,
  ApprovalsOut,
  ArtifactContentOut,
  BacklogOut,
  CreateTaskRequest,
  DecisionRequest,
  ImprovementOut,
  MergeOut,
  MessageOut,
  NoteCreate,
  NoteOut,
  PrDetailOut,
  PrOut,
  QuestionOut,
  RiskOut,
  RunOut,
  TaskOut,
  UserOut,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // auth / identity
  me: () => request<UserOut>("GET", "/api/me"),
  logout: () => request<MessageOut>("POST", "/api/auth/logout"),

  // approvals — the line
  approvals: () => request<ApprovalsOut>("GET", "/api/approvals"),
  prDetail: (prId: number) => request<PrDetailOut>("GET", `/api/approvals/pr/${prId}`),
  artifactContent: (artifactId: number) =>
    request<ArtifactContentOut>(
      "GET",
      `/api/approvals/artifact/${artifactId}/content`,
    ),
  decide: (payload: DecisionRequest) =>
    request<MessageOut>("POST", "/api/approvals/decision", payload),
  mergePr: (prId: number) =>
    request<MergeOut>("POST", `/api/approvals/pr/${prId}/merge`),
  answerQuestion: (questionId: number, payload: AnswerRequest) =>
    request<MessageOut>(
      "POST",
      `/api/approvals/question/${questionId}/answer`,
      payload,
    ),

  // backlog grooming
  backlog: () => request<BacklogOut>("GET", "/api/backlog"),
  greenlight: (taskId: number) =>
    request<TaskOut>("POST", `/api/tasks/${taskId}/greenlight`),
  block: (taskId: number, reason: string) =>
    request<TaskOut>("POST", `/api/tasks/${taskId}/block`, { reason }),
  unblock: (taskId: number) =>
    request<TaskOut>("POST", `/api/tasks/${taskId}/unblock`),
  reorder: (orderedIds: number[]) =>
    request<TaskOut[]>("POST", "/api/backlog/reorder", { ordered_ids: orderedIds }),

  // create task
  createTask: (payload: CreateTaskRequest) =>
    request<TaskOut>("POST", "/api/tasks", payload),

  // read-only state
  prs: () => request<PrOut[]>("GET", "/api/prs"),
  risks: () => request<RiskOut[]>("GET", "/api/risks"),
  questions: () => request<QuestionOut[]>("GET", "/api/questions"),
  runs: (limit = 50) => request<RunOut[]>("GET", `/api/runs?limit=${limit}`),

  // reflect
  improvement: () => request<ImprovementOut>("GET", "/api/improvement"),
  notes: () => request<NoteOut[]>("GET", "/api/notes"),
  createNote: (payload: NoteCreate) =>
    request<NoteOut>("POST", "/api/notes", payload),
};

export type Api = typeof api;
