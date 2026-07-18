# PRD — Plant Watering Log (first product)

**Status:** proposed · **Owner:** EM (Higgs) · **Author tier:** plan

The platform's **first real product** — and its deploy tracer bullet. A simple
personal web app to log plant waterings and see what's due, chosen because it
is genuinely useful, exercises the full stack (auth · API · DB · SPA · deploy),
and makes **no runtime Claude calls** (zero product-side API cost).

---

## 1. Purpose & users

Tyler waters plants across four zones and wants a pleasing web page he logs
into that tracks what he's done and shows what's due. **Single user** (Tyler),
gated by Google sign-in restricted to his account.

## 2. Scope

**MVP (this PRD):**
- Google sign-in (his account only).
- Four seeded zones; log a watering (one tap); edit/delete a log entry.
- Dashboard: per-zone last-watered + due status; history view.

**Explicitly later (not MVP):** alerts, emails, reminders, weather, scheduling,
multi-user/sharing, native mobile.

## 3. Domain

**Zones** (seeded, editable later):

| name | location | cadence |
|---|---|---|
| Frontyard | outside | daily |
| Backyard | outside | daily |
| First floor | inside | weekly |
| Second floor | inside | weekly |

**Waterings** (the log): `id`, `zone_id`, `watered_at` (defaults to now,
editable), `note` (optional), `created_at`.

**Due status** (computed, not stored): for a zone, take its most recent
`watered_at`. Outside is **overdue** if that is older than 1 day; inside if
older than 7 days; **due today** at the boundary; **ok** otherwise; **never**
(→ due) if no waterings. This is the day-to-day useful bit — it is *not*
alerts (those are later), just an at-a-glance view.

## 4. Stack (sets the product template + `stack-backend.md` service section + new `stack-frontend.md`)

- **Backend:** Python 3.12+, **FastAPI + Pydantic v2 + SQLAlchemy + Alembic +
  Postgres**, Docker (per the charter). A typed JSON API; OpenAPI is the
  contract the frontend builds against.
- **Frontend:** **React + Vite + TypeScript + Tailwind** (SPA), talking to the
  API. Built to an approved UI mockup artifact (see §7).
- **Auth:** **Google OAuth / OIDC**, allow-listed to Tyler's Google account;
  server-set **httpOnly session cookie**; OAuth client secret in Secret
  Manager (local: env). No password storage.
- **Data:** a dedicated **`plantlog`** database on the platform Cloud SQL
  instance (per stack-devops); local Postgres for dev. Its own Alembic
  history, separate from the platform state DB.
- **Serving/deploy:** **one Cloud Run service** — FastAPI serves the JSON API
  *and* the built React static assets (single image, single deploy). Public
  URL; all app routes behind the Google-auth gate.

## 5. API surface (sketch — typed Pydantic models, no bare dict/Any)

- `GET  /api/auth/login` → Google OAuth redirect; `GET /api/auth/callback` →
  set session, allow-list check; `POST /api/auth/logout`; `GET /api/me`.
- `GET  /api/zones` → zones with computed `last_watered_at` + `due_status`.
- `POST /api/waterings` `{zone_id, watered_at?, note?}` → create.
- `GET  /api/waterings?zone_id=&limit=` → history.
- `PATCH /api/waterings/{id}` / `DELETE /api/waterings/{id}` → edit/delete.

All app endpoints require a valid session; unauthenticated → 401.

## 6. UI (pleasing + functional)

- **Login** — a single "Sign in with Google" screen.
- **Dashboard** — a card per zone: name, location, last-watered ("2 days ago"),
  a due badge (overdue/due/ok), and a prominent **Log watering** button (logs
  *now*; optimistic update). Outside and inside grouped.
- **History** — chronological list, filter by zone, inline edit of
  `watered_at`/`note`, delete with confirm.
- Responsive, clean, quietly polished — built to the approved mockup.

## 7. Pipeline & artifacts (the tracer-bullet payoff)

This build **finalizes the product stacks and produces the repeatable template**:
1. **UI mockup artifact** (`docs/design/`, via the frontend-design skill) —
   the dashboard + history, approved by Tyler before frontend build (the
   charter's UI gate; the surest path to "pleasing").
2. **`stack-frontend.md`** (new) + **`stack-backend.md`** service section —
   the stack, written down as authoritative.
3. **Repeatable product template** — the scaffold (service + SPA + Dockerfile
   + Terraform module + CI shape) extracted so product #2 is create-from-template.
4. **Prove locally in Docker** (`docker compose`: API + Postgres + built SPA) —
   full end-to-end on the subscription, no cloud.
5. **Deploy** — GCP day-zero + Terraform base + Cloud Run + Cloud SQL
   (BOOTSTRAP Phase 3), as the deliberate final step.

## 8. Decisions to confirm (EM calls, flagged for Tyler)

- **Repo location:** build in the platform repo under **`products/plant-log/`**
  for this first product, then *extract* the repeatable template afterward —
  rather than standing up a separate product repo now. Fewer moving parts for
  the tracer bullet; the dedicated-repo-from-template model comes with product #2.
- **One Cloud Run service** serving both API and SPA static assets (vs. split
  frontend hosting). Simplest single deploy.

## 9. Decomposition (after PRD approval — not dispatched yet)

Multi-domain; sequenced with the mockup gate first:
1. Mockup artifact + stack docs (frontend-design + EM).
2. Backend service: models, `plantlog` Alembic migration, Google auth, the API
   + due-status logic, tests (implementer-backend).
3. React SPA to the approved mockup, wired to the API (implementer-frontend).
4. Local docker-compose integration proven end-to-end.
5. GCP deploy — day-zero (Tyler-supervised) + Terraform + Cloud Run + Cloud SQL
   (implementer-devops).

## 10. Definition of done

Signed-in-as-Tyler, on a live Cloud Run URL: log a watering in each zone, see
correct due status and history, edit/delete an entry — end to end, deployed,
with the reusable template + stack docs left behind. Backend `ruff`/`mypy`/
`pytest` green; frontend builds and typechecks; OpenAPI reflects the API.
