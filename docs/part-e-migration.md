# Part E — Migration plan

**Date:** 2026-09-07 · Inputs: `docs/house-standard.md`, `docs/part-b-audit.md`,
`docs/part-d-roadmap.md`, `DECISIONS.md` #10–#15. Operational ledger: `docs/phase-batches.md`.

## The sequencing insight

Part D recommended a new Phase 3.1b to add structured location columns and backfill them.
**That phase should not exist as separate work.** Three facts, each verified:

- `spreadsheet/parser.py:75-93` — `parse_location()` already returns `(section, shelf)` in full. It needs a destination, not an implementation.
- `scripts/import_collection.py` — the importer takes `--dry-run`, uses `ON CONFLICT (id) DO NOTHING` and a per-item duplicate check. It is **idempotent and re-runnable**.
- `DECISIONS.md` #10 already records that the collection is re-runnable from the spreadsheet, and made that the reversal condition for the whole re-scaffold.

So: **the re-scaffold's re-import fixes the location defect at zero marginal cost.** Build
the new baseline with `location`/`section`/`shelf` on `collection_items`, then re-run the
existing importer. The parser writes what it has always computed. No backfill script, no
migration of legacy rows, no separate phase.

That is the single best argument that re-scaffolding was the right call: the app's central
defect is repaired as a side effect of the thing we were doing anyway.

## Database strategy — a fresh Neon project

Provision a **new** Neon project rather than migrating the existing shared Supabase
database. Neon provides Postgres only for this app; Batch 3 retains the custom PIN + JWT
auth decision rather than enabling Neon Auth.

*Why:* the shared Supabase project was already at 457,026,707 bytes (91.4% of its
500,000,000-byte free database limit), almost all of it Garmin Coach timeseries data. The
old MCU schema also carries a 17-revision chain and 25 tables, ~22 of them speculative,
with `profiles` sitting outside Alembic in raw SQL. A fresh project means **the old one
stays intact as a fallback** until the new deployment is verified and gives each app its
own database capacity.

The new `001` revision is an empty re-scaffold marker. Authentication tables land with
Batch 3, the domain schema and derived-field triggers land with Batch 4, and future tables
land with their owning feature batches. This keeps the migration chain reversible without
recreating unused roadmap tables.

The old data is not migrated. It is re-derived from
`Film Catalogue - 4k Blu Ray DVD v 1.0 bit 02.02.26.xlsx`, which is the actual source of truth.

## Ordering principle

**Deploy before features.** The deploy spine interlocks — Dockerfile → `alembic upgrade
head` on boot → healthcheck exposing the commit SHA → fail-closed config → CI proving the
migration chain reverses. It cannot be added a piece at a time later, and it is the one
thing this app has never had.

Everything after B2 lands on a running, publicly reachable app. Mark can see progress from
batch 5 onward instead of at the end.

## What lands where

| Concern | Batch | Why there |
|---|---|---|
| app-starter's known defects fixed on the way in | B1 | Never inherit the broken lockout or the two `vercel.json` header bugs |
| First deployment | **B2** | Earliest point it can possibly work |
| The location defect | **B4** | Free, via the re-import |
| PWA + offline (13.8, pulled forward from Stage 13) | B8 | "Standing at a shelf with no signal" is this app's most apt feature |
| Usage caps (9.7) | with 9.1, never after | There must be no window where the assistant spends uncapped |

## Corrections applied on the way in

From `docs/house-standard.md` Tier 3 and Part D, all verified:

1. **Durable account lockout** from the-coupon — app-starter defines `MAX_FAILED_ATTEMPTS` and never enforces it, while `rate_limit.py` cites that non-existent guard to justify its own weakness.
2. **`vercel.json:27`** — `Permissions-Policy: camera=()` silently disables `getUserMedia` in production. Fix before any camera feature.
3. **`vercel.json:22`** — CSP `connect-src` allows only `'self'` and Sentry, blocking signed-URL uploads to Supabase Storage. Fix before photo uploads.
4. **Strip leaked identity** — `@coach/web`, `coach_test`/`coach_migration` CI databases, `daily-loop` query keys in `queryClient.ts`, "Batch 62.1"/"Batch 52" comments, `sss_theme` storage key.
5. **Remove dangling references** — `docs/runbooks/` (empty, yet `closeout.md` step 1 reads a runbook from it) and the Playwright config pointing at a non-existent `e2e/`.
6. **Keep mcu_app's own `soft_delete()` BEFORE DELETE trigger** — it is better than app-starter's column-only pattern; port it forward rather than downgrading.

## Deferred deliberately

**The 2,639-line architecture doc split.** Part C deferred it pending Part D, and Part D
has now largely superseded it for planning: verdicts live in `part-d-roadmap.md`, sequence
in `phase-batches.md`. What remains valuable is the doc's *reference* half — data model,
API design, feature detail. Splitting it is mechanical work that deserves its own batch
rather than being half-done here. Filed as B10.

## Risks

| Risk | Mitigation |
|---|---|
| Re-import produces different TMDB matches than April | The matching engine is unchanged and has 44 tests. Run `--dry-run` first and diff against `matching_eval.csv` before committing |
| A fresh Neon project loses manual edits made since April | Check whether any exist before decommissioning the old Supabase schema. If they do, they are the one thing worth migrating by hand |
| Batch 2 exposes the app publicly before auth lands in B3 | B2 deploys with no routes except `/api/v1/health`. Nothing to reach |
| Scope creep back into dropped phases | The ledger is the record. Adding a dropped phase back is a `DECISIONS.md` entry, not a quiet edit |
