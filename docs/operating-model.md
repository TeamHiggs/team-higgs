# Operating model — how the team works across repos

Authoritative record of how the platform operates across its repositories
(decided 2026-07-19). Changes are PRs with Tyler's merge.

## Two repos, two jobs, near-zero duplication

- **`team-higgs` = the team's brain.** Agent charters, operating rules,
  cross-product learnings, the authoritative stack/standards docs, `emctl`
  source, and the central Postgres **state store** live here. Loaded as
  *context* when working any product.
- **Products are separate sibling repos** (repo-per-product; the first is
  `plant-log`). Each holds its own product code and product-specific
  context/learnings, and is where its own branch / PR / review / merge loop
  happens. On GitHub that loop is intrinsically per-repo — which is why work
  happens *in* the product repo.
- **Operate across both:** run Claude Code with `team-higgs` as the primary
  context repo and the product repo added as an additional working directory.
  Agents read team knowledge here, edit product code there; team learnings
  commit here, product learnings commit there.
- **No vendored platform code.** `emctl` is a **tool**, not copied source —
  product repos install it (`uv tool install emctl`) and point it at the central
  `DATABASE_URL`, so all coordination state flows back to the one shared brain.

## Standards live once, referenced everywhere

Stack and conventions are authored **here** (`team-higgs/docs`) and *referenced*
by each product (a product PRD names product-specific choices and points at
these docs; it does not restate or fork them). This is what makes the
experience repeatable — every new product starts from the same settled stack.

## CI stays DRY

Product-repo CI (headless review on PRs, docs-on-merge) needs the reviewer/
workflow definitions, but a CI runner only has the product repo checked out. So:
publish `review.yml` / `on-merge.yml` from `team-higgs` as **reusable workflows**
(and/or a shared Claude Code plugin), pinned by SHA. Each product repo carries a
tiny *caller* workflow (`uses: theTylerDorland/team-higgs/.github/workflows/…@<sha>`),
not a copy. The definition lives once, here.

## Product-repo template

The `plant-log` repo's shape (service + SPA + Dockerfile + Terraform module +
caller CI + the append-only scaffolding) becomes the seed for a **product-repo
template**, so product #2 is generated from the template rather than hand-built.

## External skills governance

External capability skills are off by default and Tyler-approved per-skill,
per-scope (CLAUDE.md; EM charter, *External skills and tooling*). Approved to
date:

- **frontend-design skill** — approved 2026-07-19 for UI mockup + frontend build
  work. The mockup-artifact task and the implementer-frontend task invoke it.
