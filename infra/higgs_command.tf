# -----------------------------------------------------------------------------
# team-higgs command center — day-zero address bridge.
#
# WHY: we want the command-center *address* (higgs.tylerdorland.com) live and
# TLS-provisioned before the real app exists, so front-end/OAuth/DNS wiring can
# proceed against a stable origin. This is the same bridge pattern plant-log
# used: stand up a minimal placeholder Cloud Run service now, map the subdomain,
# and let the real command-center image deploy into this same service later.
#
# The real command center is a separate future PROJECT with its own auth,
# database, and identity. This file is intentionally minimal — a public hello
# page and a hostname, nothing more. No Cloud SQL, no secrets, no runtime env.
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "higgs_command" {
  name     = "higgs-command"
  location = var.region

  # Stateless placeholder; nothing here is worth destroy-protecting. Mirrors
  # plant-log — auth (when the real app lands) is enforced in-app, not by
  # Cloud Run ingress.
  deletion_protection = false

  template {
    # No service_account: the placeholder needs no GCP identity (no Secret
    # Manager, no Cloud SQL). The real app will attach its own least-privilege SA.

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      # Public hello placeholder. It listens on the injected PORT, so the Cloud
      # Run v2 default container port suffices — no ports block needed.
      image = var.higgs_command_image
    }
  }

  # CI/`gcloud run deploy` owns the running image after the real app ships;
  # Terraform must not revert a shipped revision back to the placeholder.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

# Public invoke: allUsers may INVOKE (reach the service). This matches
# plant-log's public-invoke + in-app-auth model. The placeholder is
# INTENTIONALLY public and serves only the hello page. When the REAL command
# center ships (its own future project), it MUST gate access via in-app auth —
# this public binding does not substitute for application-level authorization.
resource "google_cloud_run_v2_service_iam_member" "higgs_command_public_invoke" {
  name     = google_cloud_run_v2_service.higgs_command.name
  location = google_cloud_run_v2_service.higgs_command.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Custom-domain mapping: binds higgs.tylerdorland.com to the higgs-command
# service (referenced by name via spec.route_name, which also gives Terraform an
# implicit dependency on the service). certificate_mode = AUTOMATIC has Cloud Run
# provision and renew a Google-managed TLS cert once DNS resolves — no cert
# resource needed. The parent domain is already Search-Console-verified for
# tyler@tylerdorland.com, so the mapping applies cleanly.
#
# ONLY the higgs subdomain is mapped. The apex (tylerdorland.com) and www are
# Tyler's Squarespace site and are deliberately left untouched.
#
# After apply, the mapping emits a CNAME (host `higgs` -> ghs.googlehosted.com.)
# that Tyler adds at Squarespace DNS; the cert then auto-provisions. See the PR
# go-live checklist.
resource "google_cloud_run_domain_mapping" "higgs_command" {
  location = var.region
  name     = "higgs.tylerdorland.com"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name       = google_cloud_run_v2_service.higgs_command.name
    certificate_mode = "AUTOMATIC"
  }
}
