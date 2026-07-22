# Terraform CI — apply-on-merge (runbook)

`.github/workflows/terraform.yml` runs Terraform in GitHub Actions:

| Trigger | Job | Identity | What runs |
|---|---|---|---|
| `push` to `main` touching `infra/**` | `apply` | `github-ci` SA (write/admin, **main-ref only**) | `terraform apply -auto-approve` (re-plans, then applies) |

**The merge is the deploy decision.** There is no separate apply approval and no
manual environment gate (Tyler's call, task #23). Merging a PR that changed
`infra/` applies it. Local `terraform apply` ends here.

There is **no plan-on-PR job.** `terraform apply` re-plans immediately before
applying, so the plan is still computed and gated — on `main`, under the write
identity, at merge time. Read the plan in the merge run's Actions log; a plan
that would destroy a stateful resource errors out (see below).

## Why no plan-on-PR (and why one identity)

A plan-on-PR job needs an identity assumable from **PR refs**. But to compute a
real plan over this module that identity must READ remote state — the state
object holds the plant-log DB password and session secret in **plaintext** — and
read the three plant-log secrets to refresh the `google_secret_manager_secret_version`
resources. That is a PR-ref-impersonable identity with production-secret read.
**Same-repo agent PRs are this platform's threat model**, so plan-on-PR is
dropped entirely (security review 38 / task #23, Tyler's path A). It is deferred
to hardening **task #35**, which moves the TF-generated secrets out of state
first — after which a plan identity no longer needs state-read and plan-on-PR
can be reconsidered safely.

That leaves a single CI identity:

- **`github-ci`** — the APPLY identity. Its WIF binding is authoritative to
  `attribute.ref/refs/heads/main` (unchanged by this work). It holds the
  resource-management roles in `ci_iam.tf`. **Never assumable from a PR.**

## State and locking

Remote state is the versioned GCS bucket `team-higgs-platform-tfstate`
(`versions.tf` backend, `backend.hcl`). The GCS backend locks automatically:
`apply` acquires a lock object (github-ci has `storage.objectAdmin` on the
bucket). Concurrency in the workflow serializes runs per ref so main applies
never overlap.

## tfvars

CI variables live in committed **`infra/ci.auto.tfvars`** — NON-SECRET only
(project id, region, email allow-list, OAuth *client ID*, public URLs,
placeholder image). Terraform auto-loads `*.auto.tfvars`, so the apply job gets
its inputs with no workflow wiring. Chosen over workflow `env`/`TF_VAR_*`
because the values are then reviewed in the PR diff, versioned under the same
gate, and applied exactly as reviewed.

The OAuth client **secret** is NOT in CI — it stays in Secret Manager
(`plantlog-google-client-secret`), set out-of-band. `ci.auto.tfvars` is the
authoritative committed config and supersedes the local, gitignored
`terraform.tfvars` for its keys (`.auto.tfvars` overrides `terraform.tfvars`);
keep them consistent or remove the redundant local file.

## One-time setup (Tyler, once)

CI cannot apply the change that grants CI its own permissions — the same
bootstrap caveat as day zero / the WIF import (see `README.md`). Before CI can
run Terraform:

1. **Repo variable** `WIF_PROVIDER` = the full provider resource name:
   ```sh
   gh variable set WIF_PROVIDER --repo TeamHiggs/team-higgs \
     --body "$(cd infra && terraform output -raw wif_provider_name)"
   ```
   (The `github-ci` SA email is hard-coded in the workflow; only the provider
   path, which embeds the project number, is a variable.)

2. **Bootstrap apply** (local, Tyler's own gcloud ADC) of THIS PR after merge —
   it creates the `github-ci` management roles. Review the plan first:
   ```sh
   cd infra
   terraform init -backend-config=backend.hcl
   terraform plan -out plan.tfplan     # expect: creates only (roles + new SA)
   terraform apply plan.tfplan
   ```
   From the **next** infra PR onward, CI owns apply; this is the last local one.

## How apply-on-merge behaves

- Merge a PR that changed `infra/**` → the `apply` job runs on the push to
  `main` → `terraform apply -auto-approve`.
- A plan that would **destroy a stateful resource** (Cloud SQL instance, state
  bucket — `prevent_destroy`) makes `apply` **error out** instead of destroying.
  That is the guard working; fix the change, don't force it.
- Image changes are ignored (`lifecycle.ignore_changes` on Cloud Run images), so
  apply never reverts a shipped revision.

## Rollback

- **Bad Terraform change:** `git revert` the merge commit and merge the revert —
  CI applies it, returning infra to the prior declared state. This is the normal
  path; state is code.
- **Bad Cloud Run revision (image):** Terraform doesn't manage the running image
  (`ignore_changes`); roll back with
  `gcloud run services update-traffic <svc> --to-revisions <prev>=100`.
- **Failed apply (main and live diverged):** the run log shows what applied.
  Land a corrective PR. Do **not** hand-edit state or run `-target`; state
  surgery is off-limits without a task saying so. Object versioning on the state
  bucket is the last-resort recovery, Tyler-only.
- **Stuck lock** (killed run): `terraform force-unlock <LOCK_ID>` locally, Tyler,
  only after confirming no apply is in flight.

## Security surface (summary)

The full grant delta and its blast-radius ranking is in the PR "Surface"
section; `ci_iam.tf` documents each binding inline. Headline: `github-ci` gains
project-scoped `run.admin`, `cloudsql.admin`, `secretmanager.admin`,
`artifactregistry.admin`, `iam.serviceAccountAdmin`,
`iam.workloadIdentityPoolAdmin`, and — highest blast radius —
`resourcemanager.projectIamAdmin`, plus `storage.objectAdmin` on the state
bucket. This makes `github-ci` an effectively project-admin identity; it stays
main-ref-only. Proposed mitigations are in the PR Follow-ups.
