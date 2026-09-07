# STATUS — MCU App

## Now

**Batch 2 — Deploy spine + CI gate is shipped. The MCU app is deployed for the first
time.** `main` is at `d4190ac`, pushed, CI green (run `34152808801`).

The production API is live at **`https://api-production-a8fe.up.railway.app`** and proves
the batch's acceptance criterion directly:

```
/api/v1/health        200  {"status":"ok","commitSha":"d4190ac22e576d1e63e156029bc2b27d0bb09059"}
/api/v1/health/ready  200  {"status":"ready","db":"ok"}
```

That SHA is `main` HEAD — production is provably serving the commit we think it is.
Migrate-on-boot applied Alembic `001` to Neon on first container start, and the
database-aware readiness probe confirms the Neon connection from inside Railway.

Railway (`mcu-app` / `production` / `api`, region `ams`) deploys `main` from
`CraigR973/mcu-app` through the root `Dockerfile`, with all five IaC variables applied and
both JWT secrets sealed for Batch 3. Vercel (`mcu-app`) is git-connected to the same repo
and its production build is live at **`https://mcu-app-fawn.vercel.app`**, serving the
bundle with `vercel.json`'s CSP and `X-Frame-Options` headers applied — the hosting
pipeline is proven on both halves.

**The deployed web app does not boot, by design** — `main.tsx` mounts `AuthProvider`,
which imports `lib/supabase.ts`, which throws without `VITE_SUPABASE_*`. Only
`VITE_API_URL` is set. Batch 2's remit is the API's SHA proof and the hosting pipeline;
Batch 3 replaces Supabase auth outright. See `DECISIONS.md` #22 — **a green Vercel build
is not evidence the app runs.**

## Next

**Batch 3 — Auth (PIN + JWT).** It now carries a hosting obligation as well as an
application one: its close-out must set the web auth env vars in Vercel and verify the
deployed app actually renders, not merely that the build went green.

Three owner actions remain outstanding:
1. **Revoke the April PAT at GitHub.** Redacted from the working tree; still in history at commits `4768da8` and `0bfb672`. Whether to rewrite history is a separate call.
2. **Check for manual edits to the live Supabase data since April.** Batch 4 re-imports from the spreadsheet; anything hand-edited since would not survive. The old Supabase project can be decommissioned once Batch 3 removes the web app's last dependency on it.
3. **`VITE_API_URL` is set for Production only.** The Vercel CLI would not accept the Preview scope non-interactively; add it in the dashboard if preview deploys are wanted.

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

1. **The 13 derived-field trigger tests intentionally remain skipped until Batch 4.** CI
   now provides Postgres 17 and a separate connectivity test, so a missing database can no
   longer pass silently. The trigger tests automatically resume once Batch 4 creates
   `movies` and `collection_items` and must then run, not skip.

2. **The new migration chain starts with an intentionally empty `001`.** It has been
   proven to apply and reverse against disposable Postgres, and CI repeats both commands.
   Batch 3 owns the auth schema and Batch 4 owns the domain schema; do not put future
   tables into the baseline.

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

12. **A Railway 502 does not mean the app is down.** The public domain must target
    Railway's injected `PORT` (8080), not the Dockerfile's `EXPOSE 8000`. Pointing it at
    8000 returned a public 502 while the container was healthy and its internal
    healthcheck returned 200 throughout. `DECISIONS.md` #20; `.railway/README.md`.

13. **Run the Railway CLI on Node 22+.** Its IaC engine uses Node's type-stripping flag,
    which Node 20 rejects, so `railway config plan` fails before touching infrastructure.
    The app's own build stays on Node 20.

14. **`mcu-app.vercel.app` is somebody else's app.** The bare name was taken, so Vercel
    assigned us `mcu-app-fawn.vercel.app`. `FRONTEND_ORIGIN` was initially set to the bare
    name, which pointed the API's CORS allowlist at a stranger's deployment while excluding
    our own front end. Corrected at close-out. **Read the alias list from
    `vercel inspect`; never assume the project name is the domain.** `DECISIONS.md` #23.

## Log

- **2026-09-07** — **Batch 2 shipped — the app is deployed for the first time.**
  `main` `d4190ac` pushed, CI green. Railway `api` live on the root Dockerfile; migrate-on-boot
  applied `001` to Neon; `/api/v1/health` returns the merged commit SHA and `/ready` reports
  `db: ok`. Public API `api-production-a8fe.up.railway.app`. Two failures on the way: the
  first deploy built `0419cb2` and failed on a missing Dockerfile because `main` had been
  merged locally but never pushed; the generated domain then returned 502 until repointed
  from port 8000 to Railway's injected 8080. Vercel git-connected; web ships without auth
  env vars and white-screens until Batch 3 — verified in a browser, the console throws the
  expected `Missing VITE_SUPABASE_URL` and nothing else. A third failure found during
  verification: `FRONTEND_ORIGIN` pointed at `mcu-app.vercel.app`, an unrelated third
  party's app, because Vercel had actually assigned `mcu-app-fawn.vercel.app`. CORS now
  allows the real origin and returns 400 to the stranger (`DECISIONS.md` #20–#23).
- **2026-09-07** — Batch 2 implementation prepared for review on
  `feat/2-deploy-spine-ci`: dedicated Neon Postgres connection verified; migrate-on-boot
  Dockerfile, Railway IaC, Vercel configuration, reversible `001`, commit/readiness health
  checks, Postgres-backed CI and hashed dependency gates added. Fresh-lock and disposable-
  Postgres verification green. No commit, project creation or deployment yet; those wait
  for explicit `/phase-closeout 2`.
- **2026-09-07** — Batch 1 New spine foundations shipped via PR #1 (`0910428`, `15ed148`). Async SQLAlchemy/asyncpg, fail-closed config, `models/` mixins, health-only API, async pytest harness and the first shared Zod response schema are on `main`. CI green after fixing a test that assumed pytest always started at the repo root.
- **2026-09-07** — Cross-project review complete, Parts A–E. Merged to `main` as `9084ec6`, CI green (API + Web). 38 batches in 11 groups defined; owner reinstated all Part D drops except 9.6 (`DECISIONS.md` #16). Repo confirmed **private**, which lowers the urgency on the PAT still in history.
- **2026-05-05** — Phase 3.1 Add to Collection (manual). Commits `13d5f6b`, `fe7e895`. CI green. Close-out docs were written but never committed until today.
- **2026-04-30** — Phases 2.7, 2.8 (movie detail tabs; onboarding wizard).
- **2026-04-29** — Phases 2.2–2.6 (frontend shell, collection grid, view toggle, search, detail page).
- **2026-04-25 → 04-27** — Stage 1 (Alembic schema, TMDB client, spreadsheet parser, matching engine, bulk import, derived-field triggers). The real collection import landed 2026-04-27.
- **2026-04-20 → 04-24** — Stage 0 (scaffolding, backend, frontend, Supabase auth, CI, error tracking).
