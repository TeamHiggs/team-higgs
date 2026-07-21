# Command-center cutover runbook

Operational sequence to bring the gated command-center service to
`higgs.tylerdorland.com` and retire the `higgs-command` placeholder (closing
platform risk #3). This runbook is referenced by the infra PR for task #29.

Nothing here is applied by an agent. `terraform apply` runs only in the
merge-triggered workflow (docs/stack-devops.md); the Tyler-only steps are
console / registrar / Secret Manager actions Terraform cannot perform.

## Ordering principle

**Never expose the service to close a gap later.** The placeholder keeps serving
`higgs.tylerdorland.com` (public hello page, no data) until the *locked* fronting
is proven. The public `allUsers` binding is retired only at the very end, after
the IAP-fronted path is verified. There is no window in which the real service is
publicly invokable.

## State this PR leaves behind (before cutover)

- `command-center` Cloud Run service exists, ingress = `INTERNAL_LOAD_BALANCER`,
  **no `run.invoker` binding at all** → not reachable from the internet.
- Four secret containers exist; session secret has a real (TF-generated) value;
  the Google client secret, the GitHub merge token, and `DATABASE_URL` hold
  `SET-REAL-VALUE-OUT-OF-BAND` placeholders.
- `higgs-command` placeholder is untouched and still owns the domain mapping and
  its `allUsers` invoke binding.

## Prerequisites (must land before cutover completes)

1. **Platform state store on Cloud SQL (Phase 3).** The service reuses emctl's
   data layer and reads `DATABASE_URL`. The emctl Postgres is local today
   (docs/stack-devops.md: "local now, Cloud SQL at Phase 3"). Until it is a
   database on the `platform-pg` instance with a least-privilege user, DB-backed
   endpoints are not live (the service still boots; `/healthz` is static). This
   is out of scope for task #29 — tracked as a follow-up.
2. **IAP-fronted external HTTPS load balancer (the ingress fronting).** See
   "Fronting" below — proposed as a sequenced follow-up PR because it introduces
   two new GCP services (Cloud Load Balancing, IAP) and depends on an OAuth
   consent-screen brand that is a console step.

## Tyler-only steps (console / registrar / Secret Manager)

These cannot be Terraform'd (or must not be — no secret value in code):

1. **Create the command-center OAuth Web client** (Google Cloud console → APIs &
   Services → Credentials). Separate from plant-log's client. Authorized redirect
   URI: `https://higgs.tylerdorland.com/api/auth/callback`. Put the **client ID**
   (not secret) in `terraform.tfvars` as `cc_google_client_id`. Add the **client
   secret** to Secret Manager:
   ```sh
   printf '%s' 'REAL_CLIENT_SECRET' \
     | gcloud secrets versions add command-center-google-client-secret \
       --data-file=- --project=team-higgs-platform
   ```
2. **Create the least-privilege GitHub merge token** (decision #21). A
   **fine-grained PAT** scoped to **exactly the two repositories**
   (`TeamHiggs/team-higgs`, `TeamHiggs/plant-log`) with **Contents:
   Read and write** and **Pull requests: Read and write** — nothing else, no org
   admin, no workflow scope. Store it:
   ```sh
   printf '%s' 'github_pat_...' \
     | gcloud secrets versions add command-center-github-token \
       --data-file=- --project=team-higgs-platform
   ```
   Set a calendar reminder to rotate it (fine-grained PATs support an expiry —
   use one and re-add a new version before it lapses).
3. **DATABASE_URL** (after Phase 3): add the real connection string as a new
   version of `command-center-database-url` (unix-socket form against the
   platform DB, mirroring `plantlog-database-url`).
4. **DNS** (registrar / Squarespace): at cutover, replace the `higgs` CNAME
   (→ `ghs.googlehosted.com.`, which points at the placeholder's Cloud Run
   domain mapping) with an **A record to the load balancer's static IP**. The
   managed cert on the LB provisions once DNS resolves.
5. **Grant yourself IAP access**: `roles/iap.httpsResourceAccessor` to
   `user:tyler@tylerdorland.com` (or the Google identity you sign in with) on the
   IAP-protected backend — Tyler only.
6. **Required status check (branch protection)**: after the CI-gate workflow (the
   separate PR) is green on `main`, enable it as a **required status check** on
   `team-higgs` main in repo settings → Rulesets. This is a repo-settings step;
   agents do not set branch protection.

## Fronting: the ingress lock (proposed minimal option + tradeoff)

To remove `allUsers` **and** keep the app reachable from Tyler's browser, the
service must sit behind something that authenticates the user at the edge and
presents an authorized identity to Cloud Run. A browser cannot present a GCP IAM
token, so "ingress-locked + no allUsers" alone makes the service unreachable —
by design in this PR, pending the fronting.

**Recommended minimal option: Identity-Aware Proxy (IAP) behind an external
HTTPS load balancer** with a serverless NEG to the Cloud Run service:

- external static IP + global forwarding rule + target HTTPS proxy + managed
  cert for `higgs.tylerdorland.com` + URL map + backend service with **IAP
  enabled** + serverless NEG → `command-center`.
- IAP authenticates the user against Google and enforces
  `roles/iap.httpsResourceAccessor` (Tyler only). Cloud Run ingress stays
  `INTERNAL_LOAD_BALANCER`; invoke is granted narrowly to the LB/IAP path, never
  `allUsers`.
- In-app Google OIDC (already built) stays on as defence-in-depth — two
  independent gates on a service that can merge PRs.

**Tradeoffs (why this is a sequenced follow-up, not this PR):**

- **Two new GCP services** (Cloud Load Balancing, IAP) not yet in
  docs/stack-devops.md → warrants an explicit stack decision + its own security
  review, per "new GCP services require justification."
- **Cost:** an external HTTPS LB carries a standing ~$18–25/mo baseline
  (forwarding rule + IP) even at zero traffic — non-trivial for a single-user
  internal tool.
- **Console dependency:** IAP needs an OAuth consent-screen **brand**; brand
  creation via Terraform is constrained (org/internal caveats) and is realistically
  a console step, so it cannot be fully plan-validated here.
- **Double auth:** IAP + in-app OIDC is deliberate defence-in-depth, but is
  redundant sign-in UX; acceptable given the merge-token blast radius.

A lighter alternative (direct "IAP for Cloud Run" without an LB) may remove the
LB cost/complexity; its Terraform/GA maturity should be checked when the fronting
PR is authored.

## Cutover sequence (execute top to bottom; each step verified before the next)

1. Merge this infra PR → CI applies → `command-center` service + secrets + IAM
   exist (locked, unreachable). Verify: `gcloud run services describe
   command-center` shows ingress `INTERNAL_LOAD_BALANCER` and **no** `allUsers`
   in its IAM policy.
2. Complete prerequisites: Phase-3 DB + real DATABASE_URL; real OAuth client
   secret; real GitHub merge token. Deploy the real command-center image
   (`gcloud run deploy` / CI deploy follow-up). Verify `/healthz` = 200 on the
   service's internal URL.
3. Land the fronting PR (LB + IAP + serverless NEG). Grant Tyler
   `iap.httpsResourceAccessor`. Verify: reaching the LB IP without a session
   redirects to Google sign-in; a non-allowlisted account is refused.
4. **DNS cutover:** point `higgs.tylerdorland.com` A record at the LB IP; wait
   for the managed cert to go ACTIVE; verify `https://higgs.tylerdorland.com`
   serves the command center behind IAP + in-app OIDC.
5. **Retire the placeholder (closes risk #3):** remove `infra/higgs_command.tf`
   (service + `higgs_command_public_invoke` allUsers binding + domain mapping) in
   a small PR; CI apply deletes them. Verify the plan shows the placeholder
   service and its `allUsers` binding destroyed and **nothing else**. After apply,
   confirm `higgs-command` no longer exists and no `allUsers` invoke binding
   remains anywhere for the command center.

## Rollback

- Before step 4 (DNS): nothing user-facing changed; the placeholder still serves
  `higgs`. Abort by not cutting DNS.
- After step 4, if the fronting misbehaves: revert the `higgs` DNS record to the
  placeholder CNAME (`ghs.googlehosted.com.`); the placeholder (still present
  until step 5) resumes serving. Do **not** run step 5 until the fronting is
  stable.
