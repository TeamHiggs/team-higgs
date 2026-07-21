# -----------------------------------------------------------------------------
# Cloud DNS — authoritative zones for airportbar.app and tylerdorland.com.
#
# WHY: today these domains' records are typed by hand at the Squarespace DNS
# panel. Hand-typed records were the root cause of the "Invalid IP" incident and
# the manually-added Cloud Run CNAMEs. This module makes DNS *code*: every record
# is declared here, reviewed as a plan, and applied by CI — the same governance
# path as the rest of the stack.
#
# WHAT A ZONE IS (for the backend engineer reading this): a
# `google_dns_managed_zone` is a container Cloud DNS serves as the authoritative
# source for one domain. Creating a public zone allocates Google four anycast
# nameservers (the `name_servers` output). DNS only starts flowing through this
# zone once the *registrar* delegates the domain to those nameservers — that NS
# switch is a ONE-TIME MANUAL step for Tyler at the registrar and is NOT done by
# this code or by CI. See infra/dns-cutover.md.
#
# ORDER OF OPERATIONS (critical, to avoid an outage — full detail in the runbook):
#   1. apply this module   -> zones + records exist in Cloud DNS, but nothing
#                             resolves through them yet (registrar still points
#                             elsewhere). Zero production impact.
#   2. verify replication   -> the new zone returns byte-identical answers to the
#                             current authoritative nameservers.
#   3. Tyler switches NS    -> registrar delegation flips to these nameservers.
#                             Only now does traffic move; because step 2 proved
#                             the answers match, resolvers see no change.
#
# The record sets below are a FAITHFUL MIRROR of what the live authoritative
# nameservers served on 2026-07-21 (captured with dig against the authoritative
# servers, not a cache). Values AND TTLs are replicated as-observed so the
# post-apply zone is answer-identical to today. Cloud DNS auto-manages the apex
# NS and SOA records, so they are deliberately NOT declared here.
#
# NOTE ON SCOPE: this module only *declares* the zones and records. The Cloud Run
# domain mappings that make the apex/www/higgs hostnames work already live in
# domain.tf and higgs_command.tf and are untouched by this change.
# -----------------------------------------------------------------------------

# =============================================================================
# Zone: airportbar.app  (plant-log — apex + www on Cloud Run, DMARC/SPF for mail)
# Currently delegated to Squarespace nameservers (nse{1..4}.squarespacedns.com);
# this zone replaces them once Tyler repoints NS at the registrar.
# =============================================================================
resource "google_dns_managed_zone" "airportbar_app" {
  name        = "airportbar-app"
  dns_name    = "airportbar.app."
  description = "airportbar.app (plant-log). Terraform-managed; see infra/dns-cutover.md."

  # Public authoritative zone. DNSSEC is intentionally left OFF: the live zone
  # is not signed today, and enabling it would change the delegation contract and
  # add a DS-record step to the cutover. Signing is a separate, deliberate task.
}

# Apex A -> Cloud Run's anycast frontend (the ghs A set the domain mapping emits).
resource "google_dns_record_set" "airportbar_apex_a" {
  managed_zone = google_dns_managed_zone.airportbar_app.name
  name         = google_dns_managed_zone.airportbar_app.dns_name
  type         = "A"
  ttl          = 14400
  rrdatas = [
    "216.239.32.21",
    "216.239.34.21",
    "216.239.36.21",
    "216.239.38.21",
  ]
}

# Apex AAAA -> Cloud Run's anycast frontend (IPv6). `.app` is HSTS-preloaded;
# the managed cert on the domain mapping covers HTTPS.
resource "google_dns_record_set" "airportbar_apex_aaaa" {
  managed_zone = google_dns_managed_zone.airportbar_app.name
  name         = google_dns_managed_zone.airportbar_app.dns_name
  type         = "AAAA"
  ttl          = 14400
  rrdatas = [
    "2001:4860:4802:32::15",
    "2001:4860:4802:34::15",
    "2001:4860:4802:36::15",
    "2001:4860:4802:38::15",
  ]
}

# Apex TXT: Google site verification + a strict SPF (this domain sends no mail:
# "v=spf1 -all"). Two independent TXT records at the same name.
resource "google_dns_record_set" "airportbar_apex_txt" {
  managed_zone = google_dns_managed_zone.airportbar_app.name
  name         = google_dns_managed_zone.airportbar_app.dns_name
  type         = "TXT"
  ttl          = 14400
  rrdatas = [
    "\"google-site-verification=Xhx-dwQlBFmQ5rZ-x4dX5LwIod2ZNVs1fvc-nMAIsbg\"",
    "\"v=spf1 -all\"",
  ]
}

# www -> Cloud Run domain-mapping CNAME target.
resource "google_dns_record_set" "airportbar_www_cname" {
  managed_zone = google_dns_managed_zone.airportbar_app.name
  name         = "www.${google_dns_managed_zone.airportbar_app.dns_name}"
  type         = "CNAME"
  ttl          = 14400
  rrdatas      = ["ghs.googlehosted.com."]
}

# _dmarc: reject policy (this domain sends no mail; strict alignment).
resource "google_dns_record_set" "airportbar_dmarc_txt" {
  managed_zone = google_dns_managed_zone.airportbar_app.name
  name         = "_dmarc.${google_dns_managed_zone.airportbar_app.dns_name}"
  type         = "TXT"
  ttl          = 14400
  rrdatas      = ["\"v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s\""]
}

# =============================================================================
# Zone: tylerdorland.com  (Squarespace consulting site + Google Workspace mail
# + higgs command-center bridge)
#
# IMPORTANT DISCOVERY: unlike airportbar.app, tylerdorland.com is ALREADY
# delegated to Cloud DNS nameservers (ns-cloud-c{1..4}.googledomains.com), not to
# Squarespace's. That means a Cloud DNS zone for this domain very likely ALREADY
# EXISTS (a legacy Google-Domains-era zone). This resource declares the zone we
# want to own going forward; whoever runs the apply MUST first check for a
# pre-existing zone and IMPORT it rather than let Terraform create a duplicate —
# see infra/dns-cutover.md ("Pre-apply discovery"). I could not verify this from
# the agent sandbox (no live GCP access); flagged as an open item.
#
# This apex is Tyler's future consulting site and serves live TODAY. Every record
# below (Squarespace A, www CNAME, Google Workspace MX, SPF/verification TXT,
# higgs bridge CNAME) is replicated so the site and mail keep working across the
# cutover.
# =============================================================================
resource "google_dns_managed_zone" "tylerdorland_com" {
  name        = "tylerdorland-com"
  dns_name    = "tylerdorland.com."
  description = "tylerdorland.com (Squarespace site + Workspace mail + higgs bridge). Terraform-managed; see infra/dns-cutover.md."

  # DNSSEC intentionally OFF (see airportbar zone note).
}

# Apex A -> Squarespace site frontend. MUST keep serving.
resource "google_dns_record_set" "tylerdorland_apex_a" {
  managed_zone = google_dns_managed_zone.tylerdorland_com.name
  name         = google_dns_managed_zone.tylerdorland_com.dns_name
  type         = "A"
  ttl          = 14400
  rrdatas      = ["198.185.159.145"]
}

# Apex TXT: Google site verification + Workspace SPF (softfail). Two records.
resource "google_dns_record_set" "tylerdorland_apex_txt" {
  managed_zone = google_dns_managed_zone.tylerdorland_com.name
  name         = google_dns_managed_zone.tylerdorland_com.dns_name
  type         = "TXT"
  ttl          = 3600
  rrdatas = [
    "\"google-site-verification=EU9g8d00Sv9XU4gVZCBg_0WjocS_w_frt5DpIwDT5WY\"",
    "\"v=spf1 include:_spf.google.com ~all\"",
  ]
}

# Apex MX -> Google Workspace. Mail delivery depends on these; replicate exactly.
resource "google_dns_record_set" "tylerdorland_apex_mx" {
  managed_zone = google_dns_managed_zone.tylerdorland_com.name
  name         = google_dns_managed_zone.tylerdorland_com.dns_name
  type         = "MX"
  ttl          = 3600
  rrdatas = [
    "1 aspmx.l.google.com.",
    "5 alt1.aspmx.l.google.com.",
    "5 alt2.aspmx.l.google.com.",
    "10 alt3.aspmx.l.google.com.",
    "10 alt4.aspmx.l.google.com.",
  ]
}

# www -> Squarespace external site host.
resource "google_dns_record_set" "tylerdorland_www_cname" {
  managed_zone = google_dns_managed_zone.tylerdorland_com.name
  name         = "www.${google_dns_managed_zone.tylerdorland_com.dns_name}"
  type         = "CNAME"
  ttl          = 14400
  rrdatas      = ["ext-sq.squarespace.com."]
}

# higgs -> Cloud Run domain mapping for the command-center address bridge
# (higgs_command.tf). This is the record that was hand-added at Squarespace and
# is now brought under Terraform.
resource "google_dns_record_set" "tylerdorland_higgs_cname" {
  managed_zone = google_dns_managed_zone.tylerdorland_com.name
  name         = "higgs.${google_dns_managed_zone.tylerdorland_com.dns_name}"
  type         = "CNAME"
  ttl          = 14400
  rrdatas      = ["ghs.googlehosted.com."]
}
