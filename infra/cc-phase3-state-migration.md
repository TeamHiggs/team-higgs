# Phase 3 — platform state store → Cloud SQL (task #39)

Ordered, copy-pasteable runbook for moving the emctl Postgres (the team's
`tasks`/`decisions`/`risks`/`runs`/`notes`/… — the whole platform memory) off the
local `platform-db` Docker container onto the shared `platform-pg` Cloud SQL
instance, and giving the deployed command-center service a least-privilege user
on it.

**Nothing here is applied by an agent, and `terraform apply` is not run by hand.**
The one Terraform change in this PR (the `platform` database) applies **only** on
merge, in the apply-on-merge workflow (docs/stack-devops.md). Every step below
runs **after** that apply and is executed by **Higgs** (infra admin, under
`tyler@tylerdorland.com` gcloud ADC), except the final Secret Manager value, which
is out-of-band. It moves LIVE state — run it top-to-bottom, verify each step
before the next, and keep the local container untouched until the row-count check
passes (it is the rollback).

## Ground facts

| Thing | Value |
|---|---|
| Project | `team-higgs-platform` |
| Region | `us-central1` |
| Instance | `platform-pg` (POSTGRES_16, RUNNABLE) |
| Instance connection name | `team-higgs-platform:us-central1:platform-pg` |
| New database (this PR) | `platform` |
| Superuser (owns the schema after migrate) | `postgres` (Cloud SQL cloudsqlsuperuser) |
| Least-priv app role (created below) | `command_center` (LOGIN) |
| Local source (unchanged during migration) | `postgresql://platform:localdev@localhost:5433/platform` |

`PGPW` below = the `postgres` user's password on `platform-pg` (a Tyler/Higgs-held
credential; not in this repo, not in Terraform state). Reset it if unknown:
`gcloud sql users set-password postgres --instance=platform-pg --project=team-higgs-platform --prompt-for-password`.

## Prerequisites

- The Cloud SQL Auth Proxy is the connection path for scripted `pg_dump`/`psql`
  (it authenticates via IAM — Higgs's ADC holds `cloudsql.client`/admin — and
  tunnels over TLS; the instance has no `authorized_networks`). Install:
  `gcloud components install cloud-sql-proxy` (or the standalone binary).
- The local `platform-db` container is running and holds current state.

Open the proxy in its own terminal for the whole runbook (leave it running):

```sh
cloud-sql-proxy team-higgs-platform:us-central1:platform-pg --port 5432
# → listening on 127.0.0.1:5432 for the `platform-pg` instance
```

After this, the Cloud SQL `platform` DB is reachable at
`postgresql://postgres:PGPW@127.0.0.1:5432/platform`.

---

## Step 1 — Create the `platform` database (merged Terraform apply)

Merging this PR runs the apply-on-merge workflow, which creates
`google_sql_database.platform_state` (name `platform`) on `platform-pg`. Nothing
else in the plan (see the PR's plan-walk). Verify:

```sh
gcloud sql databases list --instance=platform-pg --project=team-higgs-platform
# expect: postgres, plantlog, platform
```

The database is empty at this point (no tables, no `command_center` user yet).

## Step 2 — Create the least-privilege `command_center` login role (out-of-band)

The role is **deliberately not** a Terraform resource: creating it in Terraform
would put its password in the versioned GCS state bucket (see the PR's
"password/secret handling"). Higgs creates it out-of-band with a locally
generated URL-safe password:

```sh
# Generate a 32-byte URL-safe password (chars: A–Z a–z 0–9 - _ — no URL-encoding
# needed in the connection string). Keep CC_PW in this shell for step 6.
CC_PW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

gcloud sql users create command_center \
  --instance=platform-pg --project=team-higgs-platform \
  --password="$CC_PW"
```

Do **not** write `CC_PW` to a file or commit it. It is used once more, in step 6,
to build the `command-center-database-url` secret value.

## Step 3 — Create the schema with `emctl migrate` (as `postgres`)

Run alembic (`upgrade head`) against the Cloud SQL `platform` DB. This creates all
tables + indexes AND the cluster-global `emctl_report_ro` NOLOGIN role (migration
`0002`) with its per-database grants. Tables are owned by `postgres` (the
migrating role), which is what makes the `command_center` grants in step 4 a real
privilege boundary — the app role is not the owner and cannot alter the schema.

```sh
DATABASE_URL="postgresql://postgres:PGPW@127.0.0.1:5432/platform" emctl migrate
```

Verify the schema landed at head:

```sh
psql "postgresql://postgres:PGPW@127.0.0.1:5432/platform" \
  -c "\dt" \
  -c "select version_num from alembic_version;"
# expect the 13 app tables + alembic_version, version_num = 0007
```

## Step 4 — Least-privilege GRANTs for `command_center` (as `postgres`)

Run against the Cloud SQL `platform` DB. Grants are SQL (not Terraform), matching
`sql.tf`'s note that per-table least privilege is enforced with SQL GRANTs.

```sh
psql "postgresql://postgres:PGPW@127.0.0.1:5432/platform" -v ON_ERROR_STOP=1 <<'SQL'
-- CONNECT + schema visibility.
GRANT CONNECT ON DATABASE platform TO command_center;
GRANT USAGE  ON SCHEMA public      TO command_center;

-- DML the command center actually performs: it READS every emctl table and
-- WRITES approvals (in-place status/note UPDATEs on prs/tasks/artifacts/decisions),
-- grooming (UPDATE tasks.groom_rank), and notes (INSERT). No DELETE, no TRUNCATE,
-- no DDL — domain state is append-only (edits are new rows or in-place UPDATEs),
-- and the schema is owned by `postgres`/`emctl migrate`, never the app role.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES    IN SCHEMA public TO command_center;
GRANT USAGE,  SELECT         ON ALL SEQUENCES IN SCHEMA public TO command_center;

-- Cover future tables/sequences created by the migrating role (postgres) so a
-- later `emctl migrate` does not silently drop the app role's access.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE ON TABLES    TO command_center;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE,  SELECT         ON SEQUENCES TO command_center;

-- Defence in depth: the app role must never create objects in public.
REVOKE CREATE ON SCHEMA public FROM command_center;
SQL
```

> If `emctl migrate` is ever run as a role other than `postgres`, re-run the two
> `ALTER DEFAULT PRIVILEGES` lines `FOR ROLE <that role>` — default privileges are
> keyed by the object-creating role.

Verify the boundary (expect `SELECT,INSERT,UPDATE`, and no privilege on a
representative table for anything the role should not have):

```sh
psql "postgresql://postgres:PGPW@127.0.0.1:5432/platform" -c \
  "select privilege_type from information_schema.role_table_grants
   where grantee='command_center' and table_name='tasks' order by 1;"
# expect exactly: INSERT, SELECT, UPDATE  (no DELETE / TRUNCATE / REFERENCES / TRIGGER)
```

## Step 5 — Load existing state (data-only) and verify row counts

Schema is already in place (step 3), so copy **data only** from the local
container into Cloud SQL. `--data-only` emits `COPY` in FK-dependency order and
`setval()` for every sequence, so PKs continue where the local DB left off.
`alembic_version` is excluded (the target already carries `0007` from step 3).

```sh
# 5a. Dump data from the local container.
pg_dump "postgresql://platform:localdev@localhost:5433/platform" \
  --data-only --no-owner --no-privileges \
  --exclude-table-data=alembic_version \
  -f /tmp/platform-data.sql

# 5b. Load into Cloud SQL (ON_ERROR_STOP aborts on the first problem — no partial load).
psql "postgresql://postgres:PGPW@127.0.0.1:5432/platform" \
  -v ON_ERROR_STOP=1 -f /tmp/platform-data.sql
```

Verify row counts match table-by-table (the acceptance gate for the migration):

```sh
LOCAL="postgresql://platform:localdev@localhost:5433/platform"
CLOUD="postgresql://postgres:PGPW@127.0.0.1:5432/platform"
for t in projects tasks runs prs reviews questions decisions \
         artifacts learnings debt metrics retros notes; do
  l=$(psql "$LOCAL" -tAc "select count(*) from $t")
  c=$(psql "$CLOUD" -tAc "select count(*) from $t")
  printf '%-12s local=%-5s cloud=%-5s %s\n' "$t" "$l" "$c" \
    "$([ "$l" = "$c" ] && echo OK || echo MISMATCH)"
done
```

**Expected: every row `OK`; `tasks` = 39** (and `decisions`, `risks*`, `runs`
non-zero and equal). Do not proceed on any `MISMATCH`.

> \*The current schema has no `risks` table (state v1 = projects, tasks, runs,
> prs, reviews, questions, decisions, artifacts, learnings, debt, metrics, retros,
> notes). "risks" in the task brief maps to the platform-risk records tracked
> elsewhere; the row-count gate covers the 13 tables that exist. If a `risks`
> table has been added by a later migration before this runs, add it to the loop.

## Step 6 — Cut emctl over to Cloud SQL (Higgs's daily target)

From now on emctl (local, on the subscription) reads/writes Cloud SQL, not the
container. Point `DATABASE_URL` at the proxy. emctl connects as `postgres`
(owner) because it runs migrations and full DML — the least-priv `command_center`
role is for the deployed service only.

```sh
# In Higgs's emctl environment (e.g. the shell profile / .env that sets DATABASE_URL):
export DATABASE_URL="postgresql://postgres:PGPW@127.0.0.1:5432/platform"
# Requires the Cloud SQL Auth Proxy on 127.0.0.1:5432 (see Prerequisites) to be
# running whenever emctl is used. Smoke test:
emctl task list   # should show the migrated tasks, including #39
```

The local `platform-db` container is now the **backup / rollback** — leave it in
place (do not delete) until the Cloud SQL cutover has been stable for a few days.

## Step 7 — Set the real `command-center-database-url` secret (out-of-band)

This is the value the deployed command-center service reads at runtime. It uses
the **unix-socket** form (Cloud Run mounts the Cloud SQL socket at `/cloudsql`,
per `command_center.tf`), the SQLAlchemy+psycopg driver prefix (the command
center is a SQLAlchemy app, mirroring `plantlog-database-url`), and the
least-priv `command_center` role with the `CC_PW` from step 2:

```
postgresql+psycopg://command_center:CC_PW@/platform?host=/cloudsql/team-higgs-platform:us-central1:platform-pg
```

Add it as a new version (no secret value in this repo or in Terraform state; the
service reads `version = "latest"`):

```sh
printf '%s' \
  "postgresql+psycopg://command_center:${CC_PW}@/platform?host=/cloudsql/team-higgs-platform:us-central1:platform-pg" \
  | gcloud secrets versions add command-center-database-url \
      --data-file=- --project=team-higgs-platform
```

> The `command-center-database-url` secret container exists only when
> `enable_command_center = true` (command_center.tf, gated). Set this value as
> part of standing the service up (reachability epic #33 / cutover step 2 in
> `infra/command-center-cutover.md`), not before the container exists.

## Rollback

- **Before step 6:** nothing has changed for emctl or the service — the local
  container still serves all state. Abort by simply not cutting `DATABASE_URL`
  over. The empty/partly-loaded Cloud SQL `platform` DB is inert.
- **Redo the data load** (e.g. after a `MISMATCH`): as `postgres`, clear and
  reload — the schema and grants stay:
  ```sh
  psql "$CLOUD" -v ON_ERROR_STOP=1 -c \
    "TRUNCATE projects, tasks, runs, prs, reviews, questions, decisions,
              artifacts, learnings, debt, metrics, retros, notes
     RESTART IDENTITY CASCADE;"
  # then re-run step 5b + the row-count check.
  ```
- **After step 6, if Cloud SQL misbehaves:** point emctl's `DATABASE_URL` back at
  `postgresql://platform:localdev@localhost:5433/platform` (the container is still
  present) and investigate. Note that state written to Cloud SQL after the cutover
  would not be in the container — reconcile before re-cutting.

`prevent_destroy` on `google_sql_database.platform_state` means Terraform will
never drop this database; a deliberate operator DROP (as `postgres`, via psql) is
the only way to remove it, and is out of scope here.
