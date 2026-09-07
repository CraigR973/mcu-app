# STATUS — MCU App

## Now

**Batch 4 — Domain layer + re-import is built and green, but the import has NOT been run.
Nothing is merged and nothing is deployed.** Branch `feat/4-domain-layer-reimport`,
commits `e2ebc18` and `700847c`, CI green on all five jobs (run `34162647232`).

Two of the four acceptance criteria are demonstrably met; two cannot be met until a
matching-engine defect is settled. **Gotcha 1b is the blocker** — the engine picks the film
by TMDB popularity whenever candidates tie, and 652 of the 1,857 rows tie with no year to
separate them. Running the import today would write a confidently-wrong film for an
unknown fraction of those, along with its poster, cast, genres and search vector.

| # | Criterion | State |
|---|---|---|
| 1 | row count = 1,857 | **not met** — needs the live import |
| 2 | `section` non-trivial and in {Front, Back, Lounge, Garage, Digital} | **not met in the DB** — proved over the parser: 1,733 / 1,857, all five values present |
| 3 | `--dry-run` diffed against `matching_eval.csv` before the live run | **met** — and this is what found the blocker |
| 4 | the 13 derived-field trigger tests run in CI, not skipped | **met** — 14 ran, zero skips |

What did land, all of it proved rather than asserted:

- **Migration `003`** creates `movies`, `movie_credits` and `collection_items` per roadmap
  §3.2–3.4, with `location`/`section`/`shelf` as real columns — the gotcha 0b fix. It
  applies and reverses cleanly against Postgres 17; CI's `upgrade head → downgrade base`
  job is green.
- **The derived-field triggers are rewritten for the JSONB shapes** and keep 0015's
  behaviour: 14 tests exercise them against a real database inside rolled-back
  transactions.
- **The importer is rewritten** for §3.4 and moved under `src/` so mypy covers it. It
  writes location as columns and leaves `notes` alone, treats a combo pack as one row with
  a `formats` array, and **catalogues every owned item whether or not TMDB identifies it** —
  April inserted nothing at all for its 137 unmatched rows, so discs genuinely on the shelf
  were simply absent.
- **`parse_location` gained `E:\\Movies` → `Digital`**, without which all 413 digital rows
  landed unsectioned.
- **The collection is 1,857 items, not 1,866** (gotcha 0). Corrected across the roadmap and
  the batch ledger.

## Next

**Decide how the importer should handle an ambiguous match** (gotcha 1b). Three options,
in the order I would take them:

1. **Fix the 10 clear bugs, route the rest to review.** Prefer an exact `title` hit over an
   `original_title`-only one, then send every remaining ambiguous tie to `import_review.csv`
   instead of guessing. Import the ~1,205 unambiguous rows plus the reviewed ones. Safe,
   and it matches how the roadmap already treats the barcode phase ("confirmation UI is
   mandatory, not optional"). Costs a review pass over ~650 rows.
2. **Import everything now, correct later.** Accept popularity's pick, get all 1,857 rows in
   with their location data, and treat wrong films as a known backlog. Fastest to a browsable
   catalogue; leaves an unknown number of wrong posters and casts in front of Mark.
3. **Add a disambiguation heuristic** — e.g. prefer the candidate with the most TMDB votes,
   or the oldest, rather than the most popular. Cheap to try, but it is still a guess and
   would need its own eval before it could be trusted.

This is a genuine judgement call about the collection, not a technical one, which is why it
is stopping here rather than being decided in code.

Then: **set your PINs. Nobody can log in until you do** — both profiles are seeded with
`pin_hash = NULL`, which means *no credential*, not a blank one:

```
DATABASE_URL='<neon url from apps/api/.env.local>' PYTHONPATH=apps/api \
  apps/api/.venv/bin/python3.12 -m src.scripts.set_pin Craig
```

It prompts twice, hidden, so the PIN never reaches `ps`, your shell history, or a log.
Repeat for `Mark`, then sign in at `https://mcu-app-fawn.vercel.app/login` (`DECISIONS.md` #25).

Two owner actions remain outstanding:
1. **Revoke the April PAT at GitHub.** Classic PAT, 40 chars, `ghp_3gLc…`, committed in
   full in `0bfb672` (2026-04-25, `CLAUDE.md`) and referenced truncated in `4768da8`.
   Dead (401) but never revoked at github.com/settings/tokens. History rewrite is **not**
   recommended — the repo is private and the token is already invalid.
2. **`VITE_API_URL` is set for Production only.** The Vercel CLI would not accept the
   Preview scope non-interactively; add it in the dashboard if preview deploys are wanted.

## Gotchas

0. **The collection is 1,857 items, not ~140 and not 1,866.** Measured by running the
   real parser over the real spreadsheet on 2026-09-07. The sheet has 1,867 rows = 1
   header + 1,866 data rows, but **9 of those data rows are entirely blank** (all nine
   columns `None`, at sheet-rows 1857–1863, 1865, 1866). The parser correctly drops them
   and returns 1,857 candidates → 1,847 distinct titles, 10 of them repeated.

   **1,866 was a trailing-blank-row artifact and was wrong everywhere it appeared** — the
   roadmap's mentions, this gotcha, and Batch 4's own acceptance criterion. Phase 1.5's
   acceptance ("parser produces 1,866 structured entries with no data loss") was therefore
   unsatisfiable as written and always had been; there is no data loss, the count was just
   wrong. Corrected in `MCU_Architecture_v2.1_FINAL.md` and `docs/phase-batches.md`
   (`DECISIONS.md` #29). **`docs/part-b-audit.md` and `docs/part-d-roadmap.md` still say
   1,866** — they are dated analysis records and are left as written per `DECISIONS.md` #16.

   `import_review.csv` (137 rows) is a *review-queue* artifact from the April import, not
   the collection. Anything that scales with catalogue size — location tracking, shelf QR
   codes, smart collections, saved filters, export, natural-language search — must be
   judged at 1,857.

0b. **FIXED IN BATCH 4 (schema half). The location data was extracted at import and then
   discarded** — the most consequential defect the 2026-09-07 review found. Kept here
   because the *data* is not fixed until the import is re-run, which is still outstanding.

   What was wrong, each link verified in April and re-verified 2026-09-07:
   - `MCU_Architecture_v2.1_FINAL.md` §3.4 **designs** `location`, `section` and `shelf`
     as first-class columns on `collection_items`.
   - `apps/api/src/spreadsheet/parser.py` **implements** the extraction — `parse_location()`
     yields `section` and `shelf`.
   - The legacy `0003_create_collection_items.py` and the pre-re-scaffold flat
     `models.py` **omitted all three columns**.
   - The importer therefore fell back to `notes = candidate.location_raw` — the **raw**
     string survived, the parsed structure was thrown away, and `notes` then held location
     for imported rows and real notes for hand-added ones with nothing to tell them apart.
   - `0015`'s `search_vector` never referenced `notes`, so the "put it in notes" workaround
     would not have made location searchable even if it had been deliberate.
   - §6.2 promises *"show me everything on the Front 2nd shelf"*. Not implementable as built.

   **What Batch 4 changed.** Migration `003` creates `location`, `section` and `shelf` as
   real columns with a CHECK constraint pinning `section` to the five §3.4 values, and a
   partial composite index on `(section, shelf) WHERE deleted_at IS NULL` — the index
   Batch 6's "Front 2nd shelf" query needs. The importer writes all three and leaves
   `notes` alone. `parse_location` also gained `E:\\Movies` → `Digital`: the digital
   library is only ever recorded as its filesystem path, so without it all 413 digital rows
   landed with `section IS NULL` and the vocabulary never produced the value §3.4 names.

   **Coverage over the real sheet: 1,733 of 1,857 rows get a section** (Front 550, Back 575,
   Digital 413, Lounge 160, Garage 35). The remaining 124 are cabinets — "Top Big Cabinet",
   "Left Hand Side Small Cabinet Fish Room", "Black Box next to cabinet" — which have no
   §3.4 section. They keep their exact text in `location`, so nothing is lost; only the
   normalised columns are null. Whether the section vocabulary should grow to cover them is
   a Batch 6 question.

1. **RESOLVED. The derived-field trigger tests now run in CI — 14 of them, zero skips.**
   Proved on run `34162647232`: `tests/test_derived_field_triggers.py ..............`
   against the Postgres 17 service, no `s` characters in that line.

   They were **re-authored, not resumed.** They could not be resumed: every one of them was
   written against the April schema — `movies.id` as an INTEGER TMDB id, a scalar `format`
   column, scalar `hdr_format` and `audio_formats[]` — and all three are gone under §3.4.
   All 13 original behaviours are preserved one-for-one; the 14th covers a combo pack whose
   single row holds several formats, which the old scalar column could not express.
   This was an owner decision taken at the start of Batch 4 (`DECISIONS.md` #28) precisely
   because rewriting a test to match new code is otherwise forbidden as a route to green.

1b. **BLOCKER FOR THE BATCH 4 IMPORT. The matching engine picks the film by TMDB
   popularity whenever candidates tie, and 652 of the 1,857 rows tie with no year to
   separate them.** Found by Batch 4's own `--dry-run`-against-`matching_eval.csv`
   criterion, which is exactly what that criterion exists for. Nothing has been written to
   the database.

   The mechanism, both links verified:
   - `apps/api/src/matching/engine.py:113-114` scores `original_title` as well as `title`
     and takes the **max**, so a film whose *original* title matches scores identically to
     one whose displayed title matches.
   - `apps/api/src/matching/engine.py:181` sorts by
     `(confidence, popularity)` — so when several candidates tie on confidence, **current
     TMDB popularity decides**, and that ordering is not stable over time.

   Measured over all 1,857 titles on 2026-09-07 (full scan, 0 errors):

   | | rows |
   |---|---|
   | matched at ≥0.85 | 1,721 |
   | unmatched | 136 |
   | **matched rows with ≥2 candidates tied at the top confidence** | **687 (39.9%)** |
   | of those, tied at a perfect 1.000 | 635 |
   | ambiguous ties **with no year in the source title** | **652 — 35.1% of the collection** |

   Popularity is often a *good* tiebreak — it correctly picks `Batman` (1989),
   `Ben-Hur` (1959), `Sleepy Hollow` (1999). It fails whenever a recent release shares the
   title, and 2025/2026 releases now dominate popularity:
   `Frankenstein` → **2025**, not the 1931 Karloff · `Lolita` → **1997**, not Kubrick's
   1962 · `Sinners` → **2025** · `Amistad` → **`Friendship` (2023)**, whose original title
   is "Amistad".

   **Only 10 rows are fixable by code with confidence** — the class where the winner is not
   an exact title match but a tied candidate is (Amistad, Home Alone, Joan of Arc, The
   Train …). Preferring an exact `title` hit over an `original_title`-only hit repairs
   those outright. The other 652 are genuinely undecidable from the spreadsheet: it gives a
   bare title and no year, so nothing in the data says which *Frankenstein* is on the shelf.

   **This is out of Batch 4's scope** — the batch says port `matching/` *unchanged*, and
   changing the ranking is Phase 1.6's work with its own acceptance criterion. Awaiting an
   owner decision on approach; see the end of the Log entry below.

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

- **2026-09-07** — **Batch 4 built and green; the import is held on an owner decision.**
  `feat/4-domain-layer-reimport` at `700847c`, CI green on all five jobs. Migration `003`
  lands the §3.4 domain schema with `location`/`section`/`shelf` — the gotcha 0b fix — and
  the derived-field triggers rewritten for JSONB. **The 14 trigger tests run in CI with zero
  skips**, the criterion Batches 2 and 3 could only defer. Two decisions were taken with the
  owner before any code: §3.4's schema over the April one, which forced the trigger tests to
  be re-authored rather than resumed (#28); and the collection is **1,857 items, not 1,866**
  — nine trailing spreadsheet rows are entirely blank, so the number was wrong everywhere it
  appeared, Phase 1.5's acceptance included (#29).
  The importer was rewritten and now catalogues every owned item whether or not TMDB
  identifies it; April silently dropped its 137 unmatched rows.
  **Then criterion 3 did its job and stopped the batch.** Diffing a fresh matching run
  against `matching_eval.csv` surfaced `Amistad` → `Friendship (2023)` at full confidence; a
  full scan of all 1,857 titles showed the cause is structural — `engine.py:181` breaks
  confidence ties by TMDB popularity, and **652 rows (35.1%) tie with no year to separate
  them**. Popularity now favours 2025/2026 releases, so `Frankenstein` resolves to 2025 and
  `Lolita` to 1997. Only 10 rows are fixable by code with confidence. Fixing the ranking is
  Phase 1.6's work and outside this batch's "port `matching/` unchanged" scope, so nothing
  was written to the database and nothing was merged. Gotcha 1b holds the evidence; the
  three options are in **Next**.
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
