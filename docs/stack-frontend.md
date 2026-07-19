# Frontend stack

Authoritative for frontend/UI work across products (decided 2026-07-19). Where
this doc and a charter disagree, the charter wins.

## Stack

- **React + TypeScript**, built with **Vite** — a client-rendered **SPA**, not
  SSR. Products are logged-in apps (no SEO/crawler need), so SSR/Next.js buys
  nothing and adds a server to run; if a future product is public and
  SEO-sensitive, revisit Next.js in that PRD specifically.
- **Tailwind CSS** for styling.
- **Vitest + Testing Library** for tests; typecheck must pass.
- **pnpm** as the package manager.
- The SPA builds against the backend's **OpenAPI contract** — the frontend owns
  no business logic that the API already computes (e.g. status/derived fields
  come from the API, not recomputed client-side).

## Serving

Default deploy is a **single Cloud Run service**: the FastAPI backend serves the
built static assets alongside its JSON API (one image, one deploy). Split
frontend hosting must argue against this specifically. See
`docs/stack-devops.md`.

## Design gate

UI is built to an **approved mockup artifact** (`docs/design/`), produced with
the **frontend-design skill** (Tyler-approved for UI work) and approved by Tyler
before the frontend is built. The mockup doubles as the build spec. See
`docs/operating-model.md` for the skill-approval governance.
