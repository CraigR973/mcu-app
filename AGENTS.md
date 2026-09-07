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
| `MCU_Architecture_v2.1_FINAL.md` | The 2,639-line master plan. **Never read it whole** — grep for a `Phase X.Y` heading and read a small window. Being restructured; see STATUS. |
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
- `DATABASE_URL` lives in `apps/api/.env.local` (gitignored) — the live Neon connection.

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
PYTHONPATH=apps/api apps/api/.venv/bin/mypy apps/api/src
```
Frontend / shared (Node 20):
```
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm -r test
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

`test_derived_field_triggers.py` (13 tests) skips when `DATABASE_URL` is unset, and CI
provides no Postgres service. **Those tests have never run in CI.** A green CI run does
not cover the derived-field triggers. Run pytest with `DATABASE_URL` set before trusting
any change near migration `0015`. Fixing this is tracked in STATUS.

## Close-out protocol — **explicit on this project**

Close-out is triggered by `/phase-closeout <ids>`. **Do not auto-run it — wait for the
slash command so the work can be reviewed first.** This follows the global default in
`~/.claude/CLAUDE.md` rather than overriding it, unlike `the-coupon` and `garmin-coach`.

*Why:* automatic close-out is bought by a gate worth trusting, and this repo does not yet
have one — no deploy pipeline, no migration check in CI, and the DB-backed tests never
run there. **Revisit once the re-scaffold has landed a real gate.**

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
