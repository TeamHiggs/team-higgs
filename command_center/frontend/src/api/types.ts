// All API types are derived from the OpenAPI contract (command_center/openapi.json)
// via `pnpm gen:api` -> schema.d.ts. Never hand-declare a duplicate that can drift.
import type { components } from "./schema";

type S = components["schemas"];

export type ApprovalItem = S["ApprovalItem"];
export type ApprovalsOut = S["ApprovalsOut"];
export type ArtifactContentOut = S["ArtifactContentOut"];
export type BacklogOut = S["BacklogOut"];
export type TaskOut = S["TaskOut"];
export type CreateTaskRequest = S["CreateTaskRequest"];
export type BlockRequest = S["BlockRequest"];
export type ReorderRequest = S["ReorderRequest"];
export type DecisionRequest = S["DecisionRequest"];
export type AnswerRequest = S["AnswerRequest"];
export type MergeOut = S["MergeOut"];
export type MessageOut = S["MessageOut"];
export type PrOut = S["PrOut"];
export type PrDetailOut = S["PrDetailOut"];
export type ReviewOut = S["ReviewOut"];
export type Finding = S["Finding"];
export type RiskOut = S["RiskOut"];
export type QuestionOut = S["QuestionOut"];
export type RunOut = S["RunOut"];
export type NoteOut = S["NoteOut"];
export type NoteCreate = S["NoteCreate"];
export type ImprovementOut = S["ImprovementOut"];
export type RetroOut = S["RetroOut"];
export type LearningOut = S["LearningOut"];
export type DebtOut = S["DebtOut"];
export type UserOut = S["UserOut"];

export type ApprovalKind = ApprovalItem["kind"];
export type ModelTier = NonNullable<CreateTaskRequest["tier"]>;
