# DNS cutover runbook — delegate airportbar.app + tylerdorland.com to Cloud DNS

This runbook takes the two domains from hand-typed Squarespace records to
Terraform-managed Cloud DNS zones (`infra/dns.tf`) **without downtime**. It is a
procedure, not a script: the nameserver switch (step 5) is a **one-time manual
action Tyler performs at the registrar**. No agent and no CI job repoints
nameservers.

**Golden rule:** the zones and every record must exist and be verified to serve
*identical answers* **before** any nameserver is switched. Create → verify →
switch. Never switch first.

---

## 0. Live records captured (source of truth for replication)

Captured 2026-07-21 by `dig` against the **authoritative** nameservers (not a
cache). `infra/dns.tf` mirrors exactly this, TTLs included.

### airportbar.app — currently on Squarespace NS (`nse{1..4}.squarespacedns.com`)

| Name | Type | TTL | Value(s) |
|---|---|---|---|
| `airportbar.app.` | A | 14400 | 216.239.32.21, .34.21, .36.21, .38.21 |
| `airportbar.app.` | AAAA | 14400 | 2001:4860:4802:{32,34,36,38}::15 |
| `airportbar.app.` | TXT | 14400 | `google-site-verification=Xhx-dwQlBFmQ5rZ-x4dX5LwIod2ZNVs1fvc-nMAIsbg`; `v=spf1 -all` |
| `www.airportbar.app.` | CNAME | 14400 | ghs.googlehosted.com. |
| `_dmarc.airportbar.app.` | TXT | 14400 | `v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s` |

No MX (domain sends no mail). No CAA.

### tylerdorland.com — currently on Cloud DNS NS (`ns-cloud-c{1..4}.googledomains.com`)

| Name | Type | TTL | Value(s) |
|---|---|---|---|
| `tylerdorland.com.` | A | 14400 | 198.185.159.145 (Squarespace site) |
| `tylerdorland.com.` | TXT | 3600 | `google-site-verification=EU9g8d00Sv9XU4gVZCBg_0WjocS_w_frt5DpIwDT5WY`; `v=spf1 include:_spf.google.com ~all` |
| `tylerdorland.com.` | MX | 3600 | 1 aspmx.l.google.com.; 5 alt1; 5 alt2; 10 alt3; 10 alt4 (Google Workspace) |
| `www.tylerdorland.com.` | CNAME | 14400 | ext-sq.squarespace.com. |
| `higgs.tylerdorland.com.` | CNAME | 14400 | ghs.googlehosted.com. |

No CAA. No `_dmarc` today (a `p=none` DMARC record for the mail domain is a
sensible follow-up but is **not** in scope here — replication only).

**Discovery gap:** authoritative AXFR (zone transfer) was refused on both
domains, so this table is the set of records reachable by name query, not a
guaranteed-complete zone dump. Before switching NS, confirm the Squarespace DNS
panel (airportbar.app) and the existing Cloud DNS zone (tylerdorland.com) show
**no records beyond this table**. If they do, add them to `infra/dns.tf` first.

---

## 1. Pre-apply discovery (do this FIRST — tylerdorland.com is the trap)

`tylerdorland.com` is **already delegated to Cloud DNS** nameservers, which means
a managed zone for it **probably already exists** (a Google-Domains-era zone).
`airportbar.app`, by contrast, is on Squarespace NS and has **no** Cloud DNS zone
yet.

Run, authenticated as `tyler@tylerdorland.com`:

```sh
gcloud dns managed-zones list --project=team-higgs-platform
```

- **If a zone with `dnsName = tylerdorland.com.` already exists:** do **not** let
  Terraform create a duplicate. Import it into state so Terraform adopts it:

  ```sh
  cd infra
  terraform init -backend-config=backend.hcl
  terraform import google_dns_managed_zone.tylerdorland_com <EXISTING_ZONE_NAME>
  # then import each pre-existing record set it already serves, e.g.:
  terraform import google_dns_record_set.tylerdorland_apex_a \
    "<EXISTING_ZONE_NAME>/tylerdorland.com./A"
  # (repeat for TXT, MX, www CNAME, higgs CNAME)
  ```

  After import, the plan for tylerdorland.com should be **no-op or in-place
  only** — never a destroy/recreate. If the imported zone's nameservers already
  match what the registrar points at, **tylerdorland.com needs NO registrar NS
  change at all** — it is already delegated here; you are only bringing its
  records under Terraform.

- **If no such zone exists:** Terraform creates a fresh zone with a **new**
  `ns-cloud-XX` nameserver set, and tylerdorland.com **does** need the registrar
  NS switch in step 5.

`airportbar.app` always needs the step-5 NS switch (it is moving off
Squarespace's nameservers).

---

## 2. Apply (creates zones + records; changes nothing that resolves yet)

Applying `infra/dns.tf` only populates Cloud DNS. Until the registrar delegates
to these nameservers, production traffic still flows through the old
authoritative servers — **apply is zero-impact**.

Apply happens on the standard path: **merge → CI apply via WIF** (pairs with the
Terraform-in-CI task #23). If that CI apply path is not yet live, this is a
supervised local `terraform apply` by Tyler under his own gcloud ADC (same
bootstrap caveat as the WIF import in `infra/README.md`). Agents do not apply.

Confirm the applied plan **creates** the zones + record sets and shows **no
destroys** and **no changes to any non-DNS resource** (no `plantlog-*`, no Cloud
Run, no SQL).

---

## 3. Read the new zone nameservers

```sh
cd infra && terraform output dns_zone_nameservers
```

Record both 4-nameserver sets. `airportbar.app`'s set is what you enter at the
registrar in step 5. `tylerdorland.com`'s set is only needed if step 1 said a new
zone was created.

---

## 4. Verify replication — the gate before any NS switch

Query the **new** Cloud DNS nameservers directly (bypassing delegation) and
confirm they answer identically to the **current** authoritative servers. Do this
per domain, per record. `NEW_NS` = one nameserver from step 3; `OLD_NS` =
`nse1.squarespacedns.com` for airportbar, `ns-cloud-c1.googledomains.com` for
tylerdorland.

```sh
for rr in "airportbar.app A" "airportbar.app AAAA" "airportbar.app TXT" \
          "www.airportbar.app CNAME" "_dmarc.airportbar.app TXT"; do
  set -- $rr
  echo "== $1 $2 =="
  diff <(dig +norecurse +noall +answer @OLD_NS "$1" "$2" | sort) \
       <(dig +norecurse +noall +answer @NEW_NS "$1" "$2" | sort) \
    && echo OK || echo "MISMATCH — STOP"
done
```

Repeat for tylerdorland.com (`A`, `TXT`, `MX` at apex; `www` and `higgs` CNAMEs).
Ignore TTL-column differences only if you deliberately changed a TTL; this module
did not, so answers should match on value **and** TTL. **Any MISMATCH halts the
cutover** — fix `infra/dns.tf`, re-apply, re-verify.

---

## 5. Switch nameservers at the registrar — ONE-TIME, MANUAL, TYLER ONLY

Only after step 4 is all-OK. Do the domains **one at a time**; verify the first
recovers before touching the second.

The domains are **registered at Squarespace** (post Google-Domains migration).
The nameserver setting is in the Squarespace **domain/registrar** panel, not the
per-record DNS editor.

**airportbar.app:**
1. Squarespace → Domains → `airportbar.app` → Nameservers → **Use custom
   nameservers**.
2. Replace the four `nse{1..4}.squarespacedns.com` entries with the four
   `airportbar.app` nameservers from step 3.
3. Save.

**tylerdorland.com:** only if step 1 created a NEW zone. Replace the current
`ns-cloud-c{1..4}.googledomains.com` entries with the new set from step 3. If step
1 imported an existing zone whose NS already match, **skip — no change needed**.

Registrar NS changes propagate on the parent TLD's delegation TTL (typically
minutes to a few hours; `.app` and `.com` are fast). Delegation is cached at the
parent, independent of the in-zone TTLs above.

---

## 6. Post-switch verification

```sh
dig +short NS airportbar.app        # -> the Cloud DNS set from step 3
dig +short A  airportbar.app        # -> 216.239.{32,34,36,38}.21
curl -sSI https://airportbar.app/   # -> 200 / healthy
dig +short NS tylerdorland.com      # -> Cloud DNS set
curl -sSI https://tylerdorland.com/ # -> Squarespace site still serving
dig +short MX tylerdorland.com      # -> Workspace MX intact (mail unbroken)
dig +short higgs.tylerdorland.com   # -> ghs.googlehosted.com. (bridge intact)
```

Mail (tylerdorland.com MX) is the highest-consequence record — confirm it
resolves before considering the cutover done.

---

## 7. Rollback

Because the switch is a registrar NS change, rollback is the reverse NS change —
fast and total. Restore the **old** nameservers at the registrar:

- **airportbar.app** → `nse1.squarespacedns.com`, `nse2.squarespacedns.com`,
  `nse3.squarespacedns.com`, `nse4.squarespacedns.com`.
- **tylerdorland.com** → `ns-cloud-c1.googledomains.com`,
  `ns-cloud-c2.googledomains.com`, `ns-cloud-c3.googledomains.com`,
  `ns-cloud-c4.googledomains.com`.

The old authoritative zones are untouched by this work and keep serving the same
records, so reverting NS restores the prior state. Do not delete the old
Squarespace records until the new zones have served correctly for a few days.

Do not `terraform destroy` the new zones as a rollback step during an incident —
reverting NS is enough and is instant; zone teardown is a later, deliberate
cleanup once the cutover is confirmed stable.
