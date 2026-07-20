# -----------------------------------------------------------------------------
# Workload Identity Federation — the CI -> GCP identity plane.
#
# GitHub Actions authenticates to GCP with short-lived OIDC tokens (no
# long-lived service-account keys, per docs/stack-devops.md). A GitHub OIDC
# token is exchanged, via this WIF *pool + provider*, for a short-lived
# credential that then *impersonates* the `github-ci` service account. That SA
# holds the deploy permissions.
#
# These resources were created out-of-band on day zero (see infra/README.md
# "Day-zero preconditions" #4) and had no code representation. This file brings
# them under Terraform and encodes two changes:
#
#   1. Named-repo trust under the TeamHiggs org. The org moved theTylerDorland
#      -> TeamHiggs, which broke CI auth because the provider still trusted the
#      old owner. The provider attribute_condition now trusts an explicit
#      allowlist of TeamHiggs repos (team-higgs + plant-log) — deliberate
#      least-privilege; new org repos are NOT auto-trusted.
#   2. main-ref hardening (task #14 / security review on PR #8). Impersonation
#      of github-ci is restricted to workflows running on refs/heads/main, and
#      is authoritative so no other principal can be added out of band. This is
#      a precondition for github-ci receiving any deploy roles (granted below).
#
# The `github-ci` SA itself is a day-zero precondition (like the project, the
# state bucket, and API enablement — none of which this module manages). It is
# referenced read-only via a data source; only its *bindings* are codified here.
# Codifying the SA as a managed resource is a possible follow-up (see PR).
# -----------------------------------------------------------------------------

# --- WIF pool + provider (imported; see infra/README.md "Importing WIF") ------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  # Explicit named-repo allowlist under the TeamHiggs org (deliberate
  # least-privilege — new org repos are NOT auto-trusted; add TeamHiggs/<repo>
  # here to grant access). BOTH repos are required: plant-log's deploy workflow
  # runs from TeamHiggs/plant-log, and team-higgs infra applies from
  # TeamHiggs/team-higgs. (Was: the two theTylerDorland repos, pre-rename.)
  # Ref-level scoping is layered on top by the SA binding below via attribute.ref.
  attribute_condition = "assertion.repository_owner=='TeamHiggs' && (assertion.repository=='TeamHiggs/team-higgs' || assertion.repository=='TeamHiggs/plant-log')"

  # google.subject + repository + repository_owner existed on day zero; the new
  # attribute.ref mapping is what lets the SA binding key on the git ref.
  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.ref"              = "assertion.ref"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# --- The CI service account (day-zero precondition, referenced read-only) -----

data "google_service_account" "github_ci" {
  account_id = "github-ci@team-higgs-platform.iam.gserviceaccount.com"
}

# --- Who may impersonate github-ci (authoritative for this role) --------------
#
# AUTHORITATIVE binding (not _member): applying this sets the complete member
# list for roles/iam.workloadIdentityUser on github-ci to exactly the one
# principalSet below, REMOVING the two old theTylerDorland per-repo bindings.
# Authoritative is deliberate here — it guarantees nothing else can be granted
# impersonation out of band, which is the whole point of the hardening.
#
# principalSet keys on attribute.ref/refs/heads/main. Combined with the
# provider's named-repo condition, the net trust is:
#   only refs/heads/main workflows from the allowlisted TeamHiggs repos.
resource "google_service_account_iam_binding" "github_ci_wif" {
  service_account_id = data.google_service_account.github_ci.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.ref/refs/heads/main",
  ]
}

# --- github-ci deploy roles (PR #8 precondition: least-privilege, scoped) -----
#
# Non-authoritative _member grants: github-ci is ADDED to each role on the named
# resource without disturbing any other members. All three are new (the SA had
# no roles before this) so they appear as creates in the plan, not imports.

# Push plant-log images — scoped to the plant-log repo, not project-wide.
resource "google_artifact_registry_repository_iam_member" "github_ci_ar_writer" {
  project    = google_artifact_registry_repository.plant_log.project
  location   = google_artifact_registry_repository.plant_log.location
  repository = google_artifact_registry_repository.plant_log.name
  role       = "roles/artifactregistry.writer"
  member     = data.google_service_account.github_ci.member
}

# Deploy new revisions — scoped to the plant-log service, not project-wide.
resource "google_cloud_run_v2_service_iam_member" "github_ci_run_developer" {
  project  = google_cloud_run_v2_service.plant_log.project
  location = google_cloud_run_v2_service.plant_log.location
  name     = google_cloud_run_v2_service.plant_log.name
  role     = "roles/run.developer"
  member   = data.google_service_account.github_ci.member
}

# actAs the runtime SA when deploying a revision that runs as plantlog-run.
# Scoped to that one SA, not project-wide serviceAccountUser.
resource "google_service_account_iam_member" "github_ci_actas_runtime" {
  service_account_id = google_service_account.plantlog_run.name
  role               = "roles/iam.serviceAccountUser"
  member             = data.google_service_account.github_ci.member
}
