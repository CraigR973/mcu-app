# MCU App — Agent Instructions

> **This is the canonical instruction file for ALL coding agents on this repo
> (Claude Code, Codex, etc.).** `CLAUDE.md` is a symlink to this file. Codex reads
> `AGENTS.md` natively. Keep everything cross-tool here — never put a decision or a
> convention somewhere only one tool can see.

**Mark's Cinematic Universe (The Real MCU)** — a private, two-person film-collection
app for Craig and Mark. Catalogues ~140 physical discs (4K / Blu-ray / DVD), enriched
from TMDB, imported from a spreadsheet.

## Source of truth — read these first

| Doc | Holds |
|---|---|
| `STATUS.md` | Where we are *right now* + the next step + gotchas. **Read at the start of every session; update at the end.** |
| `DECISIONS.md` | Why things are the way they are. **Don't re-litigate a settled decision; append a new one that supersedes it if you change course.** |
| `docs/house-standard.md` | The cross-project engineering standard, extracted from `garmin-coach`, `the-coupon`, `wc_2026_predictor` and `app-starter`. Graded by what the code does, not what its docs claim. |
| `REVIEW_PLAN_2026-09-07.md` | The in-flight review of this app and its roadmap, and the decisions taken. |
| `ARCHITECTURE.md` | The April 2026 design spec — data model, API design, integrations, feature detail, frontend design system, security, ops, conventions, glossary, deployment strategy — split from `MCU_Architecture_v2.1_FINAL.md` in Batch 10. **Never read it whole** — grep for a `Phase X.Y` heading or `## N.` section and read a small window. `DECISIONS.md`/`STATUS.md` are the authority where it conflicts with them; §17 carries a reconciled status per decision. |
| `OWNER-ACTIONS.md` | **Everything blocked on Craig** — credentials, live runs, devices, choices that aren't an agent's to make. **Read it before picking work, and never work around an item on it.** |
| `docs/phase-batches.md` | **The single batch source of record** — what each batch is, its acceptance criteria, which batches run together, and **which model and effort each needs**. Read it to choose what to work on. |
| `docs/agent-commands/` | The real command procedures. `.claude/commands/` holds thin wrappers only. |

**Cross-tool rule:** the repo is the single source of truth. Claude Code has a private
memory store; treat it as a convenience cache only — every durable fact must also live
in these in-repo docs so Codex and future sessions can see it.

## Current state — read STATUS.md, but in one line

The app is mid-**re-scaffold** onto the in-house `app-starter` template (Decision #5).
The API is deployed and serving its commit SHA; the web app is built and hosted but does
not boot until Batch 3 restores auth. Do not build new features onto the old spine.

## Stack

FastAPI + SQLAlchemy + Postgres (Neon) + Alembic / React 18 + Vite + Tailwind +
shadcn/ui. Auth: display name + PIN + JWT, no public sign-up.
Hosting: Neon (Postgres) + Railway (API) + Vercel (web) — live since Batch 2.

## Bash discipline

- **Never `cd`.** This repo has **autoenv** installed: `cd apps/api` sources
  `apps/api/.env` and triggers an interactive allow/deny prompt that will hang or
  mislead an agent. Use absolute paths and `git -C` everywhere.
- **Python is 3.12.** The system python is 3.7 — always use `apps/api/.venv/bin/python3.12`.
- **Node 20 via nvm.** The system node is v14. Prefix with
  `PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"`.
- `DATABASE_URL` lives in `apps/api/.env.local` (gitignored) — the live Neon connection —
  **on the Mac.** In a cloud session it is the throwaway test database (next section).

## Cloud sessions (`DECISIONS.md` #236)

- **The startup hook readies the gate** (`.claude/hooks/session-start.sh`, cloud only): the
  API venv, the pnpm workspace, Postgres 16 on `localhost:5433` with `mcu_test` at head, and
  `DATABASE_URL` pointing at it for the session. The Mac's paths above do not apply there:
  Python 3.12 and Node 22 are on `PATH`.
- **No Postgres connection leaves a cloud container**; its proxy carries HTTPS only. Read the
  live database with `PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m
  src.scripts.live_sql "<one SELECT>"` (`--explain` for a plan, `--json` for rows), which
  uses the read-only role in `NEON_READONLY_URL`. Never print that variable. Writes to live
  data are not a cloud session's to make: they go through the app, or a Railway job, at
  Craig's word.
- **The read-only role, `mcu_readonly`, has no default privileges**, so a new table stays
  unreadable until its migration grants it, guarded so CI's database (which has no such
  role) still migrates: `DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname =
  'mcu_readonly') THEN GRANT SELECT ON <table> TO mcu_readonly; END IF; END $$`. Never grant
  a table or column that holds a credential. **Prove one is withheld from the catalogue**
  (`has_column_privilege`, `has_table_privilege`), never by selecting it.
- **Railway:** with `RAILWAY_TOKEN` set (or `RAILWAY_API_TOKEN`, after `railway link -p
  "$RAILWAY_PROJECT_ID" -e production`), `railway config plan` runs from the repo root.
  `config apply` still waits for Craig's word in the chat ("Still explicit", below). At rest
  the plan has read `0 to add, 1 to change, 0 to destroy` since 26 Sep: the API's restart policy.
- **A cron job's logs belong to the deployment that ran it.** Every merge to `main` redeploys
  each job, so `railway logs --service cron-scrape` often shows an empty deployment. Find the
  one live at the run's time with `railway deployment list --service <job>`, then
  `railway logs <deployment-id> --service <job> --lines 500`.
- Still Craig's, wherever the session runs: his phones, his word on hosting and data
  changes, and the environment's settings. The one-off setup is `docs/mac-cloud-setup.md`.

## Conventions

- **`/api/v1/` prefix** on every router, declared on the `APIRouter`, not inline in paths.
- **camelCase JSON, snake_case DB.** Write camelCase field names directly in the Pydantic
  response models — no `alias_generator`. (Decision #6.)
- **No `{data, meta, errors}` envelope.** Return the model or list directly. Batch
  endpoints with genuine partial-success semantics get their own shape. (Decision #6.)
- **The web app parses every API response through a zod schema in `packages/shared`.**
  Fetch as `unknown`, then `.parse()`. Schemas ship with the endpoint — a schema added
  later never gets added. (Decision #6.)
- **UTC everywhere.** Naive-UTC columns, `DateTime(timezone=False)`, `_utcnow()` =
  `datetime.now(UTC).replace(tzinfo=None)`, and the `*_utc` suffix on domain timestamp
  columns. Correct at the wire with a `UtcDatetime` annotation, not at each call site.
- **UUID primary keys**, `deleted_at` soft deletes, `admin_actions` for audit.
- Branches `feat/`/`fix/`/`chore/`; Conventional Commits; small commits (`git log` is a handoff).
- **Tests ship with every change.**

## Commands

Backend (absolute paths — never `cd`):
```
apps/api/.venv/bin/python3.12 -m pytest apps/api/tests
apps/api/.venv/bin/ruff check apps/api && apps/api/.venv/bin/ruff format --check apps/api
PYTHONPATH=apps/api apps/api/.venv/bin/mypy --config-file apps/api/pyproject.toml apps/api/src
```
Frontend / shared (Node 20):
```
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm -r test
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/shared typecheck
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/shared build
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web lint
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web typecheck
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web build
```
Alembic:
```
PYTHONPATH=apps/api apps/api/.venv/bin/alembic --config apps/api/alembic.ini <cmd>
```

**`pnpm -r test`, not `--filter @mcu/web test`** — the filtered form skips
`packages/shared` entirely, so a shared-schema regression passes locally by never running.

### What a green run currently proves — and does not

Batch 2 replaced the old gate, and on 4 Oct a sixth job joined it (`DECISIONS.md` #248). CI
is six jobs: API lint/typecheck, API pytest **against a real Postgres 17 service**, `upgrade
head` → `downgrade base` migration reversal, **the image Railway deploys** (built from the
Dockerfile, every cron job's module imported in it, then booted as production runs it,
migrating first, until `/api/v1/health/ready` says `db: ok`), web lint/typecheck/test/build,
and a Python + pnpm dependency audit. A green run proves the API migrates, reverses cleanly
and boots from its real image, and that a database was genuinely reachable while the tests
ran. `test_derived_field_triggers.py` runs in that job with no skips (16 tests on 4 Oct); a
green run that skips them is a failure being hidden.

**It still does not prove three things.** (1) The image boots with CI's throwaway values,
not production's variables, so a variable missing on Railway still surfaces only at deploy
(STATUS's "Anything that lives only in a Railway variable has no test"). (2) The cron jobs
are imported, not run. (3) CI builds the web bundle but never runs it in a browser; Batch 38
is the batch that would. **A green web job is not evidence the app runs.**

## Close-out protocol — **automatic after a green gate**

**This project overrides the global default in `~/.claude/CLAUDE.md`**, as `the-coupon` and
`garmin-coach` do. Since 2026-09-07 (`DECISIONS.md` #24, superseding #13) a batch closes
out automatically once the gate is green — no slash command needed. `/phase-closeout <ids>`
still works and runs the same procedure.

**Because pushing `main` is what deploys, an automatic close-out deploys to production
without a second confirmation.** That is intended.

Fire only when **all** of these hold; if any fails, stop and report rather than close out:

1. Every `batch-verify.md` command green locally, from a clean tree.
2. Every acceptance criterion for the batch demonstrably met, criterion by criterion.
3. The working tree holds nothing beyond this batch.
4. `main` was green before the batch began. A pre-existing red is fixed on its own `fix/`
   branch and closed out first — never folded into the batch.
5. **After the merge**, production `/api/v1/health` reports the **merged commit SHA** and
   `/api/v1/health/ready` reports `db: ok`.

**Still explicit — never auto-run:**

- **Hosting or credential changes.** Railway variables and domains, Vercel env and domains,
  Neon, anything that would land in `.railway/railway.ts`.
- **Destructive data or history operations.** History rewrite, force push, dropping or
  rewriting columns and tables holding real rows, or re-running the collection import over
  live data.

*Why those two stay manual:* the gate proves the code, not the infrastructure around it. It
cannot catch a wrong `FRONTEND_ORIGIN`, a domain on the wrong port, or an import that
overwrites 1,866 rows — the first two are real events from Batch 2's own close-out.

## CI

```
gh run list --limit 1
gh run view <run-id> --log-failed
```
Use `gh`. **Never put a token in a tracked file** — a PAT was committed here in April
2026 and had to be revoked.

## Guardrails

- Never weaken the gate to reach green. Deleting a test, loosening an assertion, changing
  an expected value to match what the code now emits, adding `type: ignore` or an
  eslint-disable to silence rather than solve — all forbidden *as a route to green*. If
  green genuinely requires changing a test's expectations, that is a decision to report,
  not to take.
- A pre-existing red on `main` is fixed on its own `fix/` branch and closed out first,
  never folded into the batch.
- Never force-push, never amend a pushed commit, never bypass hooks.
- Stage files explicitly — never `git add .` or `git add -A`.
- Don't touch hosting configuration unless the work explicitly requires it.

## Session handoff

At the **end** of a session: (1) update `STATUS.md` — overwrite the "Now" block and
prepend a dated line to the "Log"; (2) append any durable decision to `DECISIONS.md`
(what + why); (3) commit. The next agent — Claude or Codex — starts from a known state.
