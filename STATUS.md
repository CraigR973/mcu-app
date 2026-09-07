# STATUS — MCU App

## Now

**Batch 1 — New spine foundations shipped 2026-09-07. The app remains undeployed.**

The backend now runs on the new foundation: async SQLAlchemy + asyncpg with the house
pool settings, fail-closed non-development config, a `models/` package with UUID and
naive-UTC mixins, a shared async test harness, and health-only routing. Structlog
correlation IDs, security headers and Sentry PII scrubbing carry forward Phase 0.6.

The old sync route layer and per-request Supabase Auth implementation are gone. The
framework-independent TMDB client, matching engine, spreadsheet parser and import script
remain for Batch 4. `packages/shared` now runs its own Vitest suite and owns the health
response Zod schema. The frontend was deliberately unchanged in Batch 1 and still
contains the old feature UI; it will not have a matching API again until the auth/domain/
read surfaces re-land in Batches 3–5.

PR #1 passed both CI jobs after one location-dependent config-test failure was fixed in
`15ed148`. Implementation commits: `0910428`, `15ed148`.

## Next

**Owner checkpoint: provision the new Supabase, Railway and Vercel projects.** This is the
explicit gate before Batch 2 in `docs/phase-batches.md`. Once the projects and credentials
exist, run `/batch-start 2` — Deploy spine + CI gate.

Two other owner actions remain outstanding:
1. **Revoke the April PAT at GitHub.** Redacted from the working tree; still in history at commits `4768da8` and `0bfb672`. Whether to rewrite history is a separate call.
2. **Check for manual edits to the live Supabase data since April.** Batch 2 provisions a fresh project and Batch 4 re-imports from the spreadsheet; anything hand-edited since would not survive. If nothing was, the old project can be decommissioned once the new deployment verifies.

## Gotchas

0. **The collection is 1,866 items, not ~140.** The source spreadsheet has 1,867 rows and the roadmap states 1,866 in five places (`:19`, `:580`, `:903`, `:1412`, `:1676`). `import_review.csv` (137 rows) is a *review-queue* artifact from the April import, not the collection. This was mis-read during the 2026-09-07 review and briefed into every Part D cluster agent; affected verdicts are being re-run. Anything that scales with catalogue size — location tracking, shelf QR codes, smart collections, saved filters, export, natural-language search — must be judged at 1,866.

0b. **The location data is extracted at import and then discarded. This is the most consequential defect found in the review.** The chain, each link verified:
   - `MCU_Architecture_v2.1_FINAL.md` §3.4 (`:164-180`) **designs** `location`, `section` and `shelf` as first-class columns on `collection_items`.
   - `apps/api/src/spreadsheet/parser.py:194-198` **implements** the extraction — `parse_location()` yields `section` (Front | Back | Lounge | Garage | Digital) and `shelf` ("1st", "2nd", …).
   - The legacy `apps/api/migrations/versions/0003_create_collection_items.py` and
     pre-re-scaffold `apps/api/src/models.py:56-81` **omit all three columns**. Batch 1
     removed the flat model; the live legacy schema remains unchanged until Batch 4.
   - `apps/api/scripts/import_collection.py:324` therefore falls back to `notes = candidate.location_raw` — the **raw** string survives for all 1,866 rows, the parsed `section`/`shelf` structure is discarded. A knock-on: `notes` now holds location for imported rows and real notes for anything added via the Phase 3.1 form, with nothing distinguishing them.
   - `0015_derived_field_triggers.py:31-60` builds `search_vector` from `movies.title/original_title/tagline/overview` only — **zero** references to `notes`. So the "put it in notes" workaround recorded in the session log would not make location searchable even if the import did it.
   - `0012_create_gift_links_and_shelf_qr.py:75-92` creates `shelf_qr_codes` with `section`/`shelf` columns and a unique constraint on the pair — **an orphaned table with nothing to join against.**
   - §6.2 (`:917`) promises *"show me everything on the Front 2nd shelf"*; Phase 3.1's form bullet names a "location" field. Neither is implementable as built.

   **Net: 1,866 discs across five physical locations, and the app cannot answer "where is this disc?" — the one question a physical-media catalogue exists to answer.** Adding the three columns, backfilling from the parser's existing output, and exposing them as filters is small work and unowned by any phase. It should be the first item after the deploy spine.

1. **A green CI run does not cover the derived-field triggers.** `test_derived_field_triggers.py` (13 tests) skips without `DATABASE_URL`, and `.github/workflows/ci.yml` has **zero** Postgres references. The Phase 1.8 triggers — the most complex component in the app — are verified by nothing automated. Set `DATABASE_URL` and run pytest locally before trusting any change near migration `0015`.

2. **The migration chain has never been proven to apply or reverse.** 17 revisions, 25 tables, no `alembic upgrade head` / `downgrade base` job in CI.

3. **`cd` is actively dangerous here.** autoenv sources `apps/api/.env` on entry and raises an interactive allow/deny prompt. Use absolute paths.

4. **~22 of the 25 tables are speculative** — created in April for roadmap stages 4–11 that were never built. Do not assume a table's existence means its feature exists. Part D decides which survive onto the new baseline.

5. **Three of the onboarding wizard's nine steps point at nothing.** All shipped in Phase 2.8 marked ✅.
   - `StepInstallPWA` (`OnboardingPage.tsx:125`) reads `window.__pwaInstallPrompt`; nothing sets it, and `beforeinstallprompt` cannot fire — there is no manifest and no service worker.
   - `StepNotifications` (`:185`) offers to enable push. The web app has **zero** occurrences of `vapid`, `pushManager` or `serviceWorker` — there is no push infrastructure at all.
   - `StepEmailConnect` (`:107`) connects a mailbox for Stage 10 purchase detection, which Part D recommends dropping (7 of its 8 phases).

   Two are fixed by the re-scaffold, which brings a real service worker and push stack. The third should be pruned from the wizard when Stage 10 is settled.

7. **`packages/shared` now validates the health response, but the old web app still imports
   no shared schemas.** That is expected during the bottom-up re-scaffold; Batch 5 ships
   shared schemas with every read endpoint and makes the web app `.parse()` each response.

8. **`pnpm -r test`, not `--filter @mcu/web test`** — the filtered form never runs `packages/shared`.

9. **mypy runs `strict = true` with `warn_unused_ignores`** — prefer `model_validate()` over `**spread` with a `type: ignore`.

10. **`ruff format` (not just `ruff check`) must pass** — a Phase 3.1 commit failed CI on formatting alone.

11. **A GitHub PAT was committed in April and remains in git history** (commits `4768da8`, `0bfb672`). It is dead (401) and now redacted from the working tree, but **it has not been revoked at GitHub and history has not been rewritten.** Both are outstanding owner decisions.

## Log

- **2026-09-07** — Batch 1 New spine foundations shipped via PR #1 (`0910428`, `15ed148`). Async SQLAlchemy/asyncpg, fail-closed config, `models/` mixins, health-only API, async pytest harness and the first shared Zod response schema are on `main`. CI green after fixing a test that assumed pytest always started at the repo root.
- **2026-09-07** — Cross-project review complete, Parts A–E. Merged to `main` as `9084ec6`, CI green (API + Web). 38 batches in 11 groups defined; owner reinstated all Part D drops except 9.6 (`DECISIONS.md` #16). Repo confirmed **private**, which lowers the urgency on the PAT still in history.
- **2026-05-05** — Phase 3.1 Add to Collection (manual). Commits `13d5f6b`, `fe7e895`. CI green. Close-out docs were written but never committed until today.
- **2026-04-30** — Phases 2.7, 2.8 (movie detail tabs; onboarding wizard).
- **2026-04-29** — Phases 2.2–2.6 (frontend shell, collection grid, view toggle, search, detail page).
- **2026-04-25 → 04-27** — Stage 1 (Alembic schema, TMDB client, spreadsheet parser, matching engine, bulk import, derived-field triggers). The real collection import landed 2026-04-27.
- **2026-04-20 → 04-24** — Stage 0 (scaffolding, backend, frontend, Supabase auth, CI, error tracking).
