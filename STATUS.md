# STATUS — MCU App

## Now

**Batch 3 — Auth (PIN + JWT) is shipped and live.** `main` is at `e89a9c6`, CI green on
all five jobs, production serving that SHA. **The deployed web app renders for the first
time** — the Supabase import that was white-screening it is gone.

Verified against production, not merely in CI:

```
/api/docs, /api/openapi.json      404   docs off in production
/api/v1/auth/signup               404   no public sign-up route exists
login as an unknown name          401   {"detail":"Invalid display name or PIN"}
login as Craig                    403   {"detail":"No PIN has been set for this profile yet."}
```

That last one was driven from a browser on `https://mcu-app-fawn.vercel.app`, so it also
proves the cross-origin path end to end: Vercel → CORS → Railway → Neon → back to a
rendered error. The whole stack works. Only the PIN is missing.

**The durable lockout is proved on Postgres in CI** — 9 tests in
`tests/test_auth_lockout.py`, all of which dispose the engine entirely between writes,
which is the closest thing to a restart available in-process. An in-memory limiter hands
back a fresh window there; that is the defect `app-starter` ships and the reason the
criterion is worded the way it is. The lock is durable in two independent places:
`profiles.failed_login_count` / `locked_until_utc`, and a Postgres-backed rate-limit
counter charged on a session of its own so an attempt counts even when the handler's
transaction rolls back.

## Next

**Set your PINs. Nobody can log in until you do** — both profiles are seeded with
`pin_hash = NULL`, which means *no credential*, not a blank one. From the repo root, with
the Neon URL in the environment:

```
DATABASE_URL='<neon url from apps/api/.env.local>' PYTHONPATH=apps/api \
  apps/api/.venv/bin/python3.12 -m src.scripts.set_pin Craig
```

It prompts twice, hidden, so the PIN never reaches `ps`, your shell history, or a log.
Repeat for `Mark`. Then sign in at `https://mcu-app-fawn.vercel.app/login`. After that,
either of you can change your own PIN in the app; this script is only needed for the
first one (`DECISIONS.md` #25).

**Then Batch 4 — Domain layer + re-import.** It is the 🔴 XL one, it re-lands 1.1 and
1.3–1.8, and it owns the location-columns defect in gotcha 0b. It also re-enables the 13
derived-field trigger tests, which must **resume, not skip**, once `movies` and
`collection_items` exist.

Two owner actions remain outstanding:
1. **Revoke the April PAT at GitHub.** Classic PAT, 40 chars, `ghp_3gLc…`, committed in
   full in `0bfb672` (2026-04-25, `CLAUDE.md`) and referenced truncated in `4768da8`.
   Dead (401) but never revoked at github.com/settings/tokens. History rewrite is **not**
   recommended — the repo is private and the token is already invalid.
2. **`VITE_API_URL` is set for Production only.** The Vercel CLI would not accept the
   Preview scope non-interactively; add it in the dashboard if preview deploys are wanted.

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

   **Batch 3 removed the wizard entirely** — its completion flag was a Supabase column
   that no longer exists, so porting it would have shipped a wizard that appears to work
   and saves nothing (`DECISIONS.md` #27). Batch 9 rebuilds it against the new schema and
   must add its own completion column. Two of the three dead steps are fixed by the
   re-scaffold's service worker and push stack; the third goes when Stage 10 is settled.

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

15. **There is no local Postgres and no Docker on this machine.** Migration changes and
    the DB-backed lockout tests cannot be run here at all — they skip locally and only
    execute in CI. Both of Batch 3's CI failures were migration defects invisible to a
    green local gate. **Treat a green local run as silent about anything touching SQL.**

## Log

- **2026-09-07** — **Batch 3 shipped — Craig and Mark can log in; nobody else can.**
  `main` `e89a9c6`, CI green, production serving that SHA and the deployed web app rendering
  for the first time. bcrypt PINs, HS256 access/refresh on separate secrets, rotated
  SHA-256-hashed refresh rows, durable Postgres lockout proved by 9 CI tests that dispose the
  engine between writes. Migration `002` seeds both profiles with `pin_hash = NULL`; the first
  PIN is set by `src/scripts/set_pin.py` from a hidden prompt (`DECISIONS.md` #25). Removed
  the sign-up page outright and the onboarding wizard with it (#27), and closed a hole where
  `VITE_SKIP_AUTH` was honoured in production builds (#26). Two CI failures on the way, both
  migration defects a green local gate could not see: the `user_role` enum created twice, then
  the seeded role sent as varchar to an enum column.
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
