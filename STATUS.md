# STATUS — MCU App

## Now

**Batch 6 — Location + facets + watch log is shipped.** The app answers "where is this
disc?" — §6.2's promise, written in April and unimplementable until now. Production serves
the merged SHA `1067a725295beee2314b7848e3651f7d526cfd37` with `db: ok`, at migration
**007**.

| # | Criterion | Result |
|---|---|---|
| 1 | "show me everything on the Front 2nd shelf" works end to end | **the API answers in 20 ms** against live Neon with network included — 0.4 ms execution, planned onto `ix_collection_items_section_shelf_live`, the index Batch 4 built for this and nothing had used. 119 films. Proved in CI against Postgres 17. **The production UI half is unverified — see the gap below** |
| 2 | `section`/`shelf` filter params and UI | shipped, and the pickers are built from `GET /collection/facets` rather than a hard-coded list, so they cannot offer a shelf that holds nothing or miss one a new disc creates |
| 3 | decade range | shipped. The old year `<select>` ran 1970→now, so **517 of the 1,085 dated films (47.6%) could not be selected at all** |
| 4 | watched status | shipped — and it needed `watch_log`, which **no phase in the roadmap ever created** (`DECISIONS.md` #35) |
| 5 | rating | shipped as a minimum-TMDB-rating filter. An unrated film is excluded rather than treated as zero |

In the database now: **1,857 collection items · 1,843 movies · 45,144 credits**, unchanged
by this batch. **1,855 of 1,857 items now carry a section, up from 1,733.** Back 575,
Front 550, Digital 413, Lounge 160, Top Big Cabinet 38, Top Small Cabinet 38, Garage 35,
Fish Room Cabinet 26, Black Box 20 — and 2 unsectioned, which is correct for both of them.

**The 124 unsectioned rows are settled** (`DECISIONS.md` #34). 122 were four named
cabinets; migration `007` widened the CHECK constraint and backfilled them from
`location`, which is never modified. The two that remain are `(In with The Killing)`,
which names another disc rather than a place, and one row with no location at all.

**A parser bug was found and fixed on the way.** `_ORDINAL_RE` matched any bare digit, so
`Top small cabinet (Arrow 4 Film Noir Classics Vol 2)` parsed to shelf **"4th"** — four
live discs that this batch's own shelf filter would have wrongly returned. The same trap
sits inside `Back 6th Shelf (Arrow 4 Film Noir Classics Vol 1)`, which produced the right
answer only because `re.search` returns the leftmost match. Both fixed; the four rows are
corrected in the database (`DECISIONS.md` #36).

**One gap, and it is the same shape as Batch 5's.** The browse UI is proved by 296 CI
tests against real Postgres, by direct measurement against the production database, and by
booting the built bundle with zero console errors — **but not by driving the production
UI**, because doing so needs a PIN and an agent must not type one. Craig's PIN is set;
**Mark's is still `NULL`**. Signing in and filtering to Front 2nd shelf is a one-minute
owner check that would close it.

## Next

**Verify Batch 6 in the browser, and set Mark's PIN.** Sign in at
`https://mcu-app-fawn.vercel.app/login`, choose Front → 2nd shelf, and confirm 119 films
render with "Front 2nd" on the cards. Then:

```
DATABASE_URL='<neon url from apps/api/.env.local>' PYTHONPATH=apps/api \
  apps/api/.venv/bin/python3.12 -m src.scripts.set_pin Mark
```

**Then Batch 7 — Write surface** (🟡). Add / edit / soft-delete collection items,
duplicate detection, condition tracking, with `admin_actions` audit writes. Its acceptance
is that changes persist, deleted items appear in trash, and the audit log records actor,
action and target and survives deletion of the target row (`DECISIONS.md` #5).

**Batch 7 also unblocks Phase 3.6 properly.** Batch 6 shipped location *filtering*; 3.6's
actual acceptance is a shelf *suggestion* — "adding a Kubrick film suggests the shelf where
other Kubrick films live" — which needs the Add form Batch 7 builds. The roadmap heading is
annotated rather than ticked, so this is not lost.

**Batch 37 is no longer blocked on a missing table.** `watch_log` exists and has its
endpoints; on-this-day and rewatch memories now wait only on real history accumulating.

Two owner actions remain outstanding, unchanged:
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

0b. **FIXED AND VERIFIED IN BATCH 4, COMPLETED IN BATCH 6. The location data was
   extracted at import and then discarded** — the most consequential defect the 2026-09-07
   review found. **1,855 of the 1,857 items now carry a structured `section`, and all 1,857
   carry their `location` text**, in the live database. Batch 4 got 1,733 of them; Batch 6
   added the four cabinets to the vocabulary and backfilled the remaining 122
   (`DECISIONS.md` #34). Only 2 are unsectioned, and correctly so. **Batch 6 also made the
   data reachable** — until then the columns and the composite index existed and no
   endpoint queried them. Kept here as the record of what was wrong and how it was proved
   fixed.

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

   **Coverage after Batch 4 was 1,733 of 1,857** (Front 550, Back 575, Digital 413,
   Lounge 160, Garage 35), with 124 cabinets unsectioned. **Batch 6 settled that question
   by growing the vocabulary**: Top Big Cabinet 38, Top Small Cabinet 38, Fish Room
   Cabinet 26, Black Box 20 — 122 rows, leaving 2. `location` was never modified, so the
   backfill is derived and reversible.

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

1b. **RESOLVED. The matching engine used to let TMDB popularity decide which film was on
   the shelf.** Found by Batch 4's own `--dry-run`-against-`matching_eval.csv` criterion,
   which is exactly what that criterion exists for.

   The mechanism, both links verified: `engine.py` scored `original_title` as well as
   `title` and took the **max**, so a film whose *original* title matched scored
   identically to one whose displayed title did; then it sorted by
   `(confidence, popularity)`, so ties were broken by a ranking that is not stable over
   time and now favours 2025/2026 releases.

   Measured over all 1,857 titles before the fix: **687 matched rows (39.9%) had ≥2
   candidates tied at the top confidence, 652 of them with no year in the source title —
   35.1% of the collection.** `Frankenstein` → 2025 rather than the 1931 Karloff,
   `Lolita` → 1997 rather than Kubrick's 1962, `Amistad` → `Friendship (2023)`.

   **The fix** (`DECISIONS.md` #31): `title_is_exact` promotes a displayed-title match
   over an `original_title`-only one — a tiebreak that never moves a confidence — and
   `is_ambiguous` marks a leader tied with films that are not plausibly the same one.
   Ambiguous rows are **catalogued with their location** and only their identification is
   deferred to review. After the fix: 1,093 settled, 628 ambiguous, 136 unmatched.

   **The ranking is still imperfect, but Batch 5 gave it a route out.**
   `title_similarity` floors a substring match at 0.9, and a near-miss that appends a
   numeral can beat it: "french connection" scores 0.919 against "French Connection II"
   and only 0.900 against the correct "The French Connection", because a leading article
   costs more than an appended "II". **11 of the 1,093 settled rows are in this class and
   about four look wrong:**

   | sheet row | as written | chose |
   |---|---|---|
   | 550 | French Connection | French Connection **II** (1975) |
   | 1789 | X-Men 2 | X-MEN 2 - **Wolverine's story** |
   | 1831 | 11.22.63 | 11-22-63: **The Day the Nation Cried** |
   | 1254 | Planet Earth II | Planet Earth II: **A World of Wonder** |

   **These are now corrected in the app, not in the engine.** The identify picker, opened
   from an already-identified film, replaces any of them in a click (`DECISIONS.md` #33).
   A third change to the matching ranking would have cost its own measurement pass over
   all 1,857 titles and risked regressing matches that are currently right.

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

7. **RESOLVED IN BATCH 5. The web app now parses every API response through
   `packages/shared`.** It previously imported no shared schemas at all — expected during
   the bottom-up re-scaffold, but only true because there were no read endpoints yet.
   Batch 5 shipped the schemas with their endpoints, as `DECISIONS.md` #6 requires: 7
   `.parse()` call sites and **zero `as Promise<T>` casts** on an API response. The rule
   that made this hold is that a schema ships *with* its endpoint — one added later never
   gets added.

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

16. **The first real write against real data is its own test stage.** Batch 4's gate was
    green, its `--dry-run` was clean, and the live import still hit three separate
    defects: the importer could not connect to any hosted database (its tests mock the
    connection), a 300-character `character_name` overflowed `VARCHAR(255)` and rolled
    back a whole item, and an idempotency key on the item's contents collapsed two
    distinct discs into one. **No test could have caught any of them** — mocks do not
    enforce column widths or unique constraints, and a dry run never writes. Budget for a
    real write, and read the import summary's error count rather than trusting its
    success lines (`DECISIONS.md` #32).

17. **A bare digit in a location string is not a shelf.** `parse_location`'s ordinal
    regex used to match any `\d+` anywhere, so `Top small cabinet (Arrow 4 Film Noir
    Classics Vol 2)` became shelf **"4th"** for four live discs. `Back 6th Shelf (Arrow 4
    Film Noir Classics Vol 1)` was right only because `re.search` returns the leftmost
    match — a correct answer for the wrong reason, which is the harder kind to notice.
    Fixed in Batch 6: a shelf needs its ordinal suffix, or the word "shelf" after the
    digit. **The general lesson is that the box-set titles in these cells are full of
    numerals**, so any future parse of `location` must anchor on structure rather than on
    finding a digit (`DECISIONS.md` #36).

18. **CI's migration job runs against an empty schema, so it cannot prove a backfill.**
    `upgrade head` → `downgrade base` proves a data migration *applies and reverses*; it
    says nothing about whether its `WHERE` clauses select the right rows, because there are
    no rows. Batch 6's `007` was checked by running its own predicates as read-only
    `SELECT`s against live Neon first — 122 sectioned, 4 shelves cleared, 2 left — and the
    post-deploy counts matched exactly. Do that for any future migration that writes data,
    and see gotcha 16 for why.

## Log

- **2026-09-08** — **Batch 6 shipped — the app finally answers "where is this disc?"**
  §6.2's promise has been in the architecture doc since April and unimplementable until
  Batch 4 added the columns; this batch is the first thing to query them. `section`,
  `shelf`, `decadeFrom`, `decadeTo`, `minRating` and `watched` on `GET /movies`, a
  facet endpoint serving the vocabularies from the data, and location on all three
  collection views. **Front 2nd shelf answers in 20 ms** including network — 0.4 ms
  execution on `ix_collection_items_section_shelf_live`, the index Batch 4 created for
  exactly this query and which nothing had used until today.

  **Two premises in the batch definition did not survive checking, and both were settled
  with the owner before any code was written.** "Watched status" was listed as a facet
  beside decade and rating as though the three cost the same. They did not: §3.7 designs
  `watch_log` and §6.5 lists its endpoints, but **no phase in §16 creates it** — checked
  against all 96 phase headings — while Batch 37 sat defined as "inert until `watch_log`
  has ~a year of history", waiting on a table nothing brought into existence. Built here
  (#35), which moved the batch 🟢 → 🟡 and unblocked Batch 37 as a side effect. And the
  124 unsectioned rows, which `STATUS.md` had flagged as this batch's open question,
  turned out to be four named cabinets covering 122 of them — now in the vocabulary and
  backfilled (#34), taking sectioned coverage from 1,733 to **1,855 of 1,857**.

  **Two real defects found on the way, neither of them in this batch's own code.** The
  shelf parser matched any bare digit, so `Top small cabinet (Arrow 4 Film Noir Classics
  Vol 2)` had been stored as shelf "4th" for four live discs — rows this batch's own
  shelf filter would have wrongly returned. `Back 6th Shelf (Arrow 4 Film Noir Classics
  Vol 1)` escaped only because `re.search` returns the leftmost match (#36, gotcha 17).
  And the year filter in `FilterBar` was generated from 1970 forward, so **517 of the
  1,085 dated films — 47.6% — could not be selected at all**; the decade range replaces
  it with bounds taken from the data.

  **The gate was green on the first CI run**, 296 API tests against Postgres 17 with zero
  skips, all five jobs passing. Because migration `007` writes to 126 live rows, close-out
  stopped for owner sign-off rather than deploying itself, per the protocol. Before asking,
  `007`'s own `WHERE` clauses were run as read-only `SELECT`s against live Neon and matched
  the parser exactly; the post-deploy counts then matched that prediction row for row —
  38 + 38 + 26 + 20 sectioned, 4 shelves cleared, 2 correctly left alone, 1,857 items and
  1,843 films unchanged. **CI cannot prove a backfill, because its migration job runs on an
  empty schema** (gotcha 18).

  **One acceptance criterion is proved indirectly, exactly as in Batch 5, and for a
  narrower reason.** The browse UI is covered by CI contract tests, by direct measurement
  against the production database, and by booting the built bundle with zero console
  errors — but **not by driving the production UI**, because that needs a PIN and an agent
  must not type one. Craig's PIN is now set, so this is a one-minute owner check; Mark's is
  still `NULL`.

- **2026-09-08** — **Batch 5 shipped — the collection is browsable, searchable, and every
  unidentified film can be settled from its own page.** List, detail, copies and tsvector
  search ship with camelCase DTOs and shared zod schemas the web app genuinely `.parse()`s
  — zero `as Promise<T>` casts. Migration `005` completes the search document that `003`
  deliberately left half-built, adding credited names and genres and re-firing when credits
  change, so a film identified in the app becomes searchable immediately.

  **The identify flow replaces the review CSV** (#33). `GET /movies/{id}/candidates` runs
  the existing `MatchingEngine` live against the stored spreadsheet title and returns the
  top five with posters, years and overviews; `POST /movies/{id}/identify` fills the §3.2
  columns and the credits. It needed no schema change — the unidentified set is exactly the
  757 movies with `tmdb_id IS NULL`, and all 757 still carry the title to search on. Either
  user can identify a film, and the same picker corrects the four wrong-sibling matches, so
  the matching ranking was left alone.

  **Measured against production, not asserted.** Search median **20 ms** and a 60-item list
  page **23 ms** against live Neon with network included — the <150 ms budget was never
  close. Zero of 1,843 movies are missing a `search_vector`. The metadata-only criterion was
  proved with **"Kubrick": 8 films returned, and the word appears in no title in the
  collection**, so the hit can only come from fetched credits; genres index too. Production
  serves the merged SHA with `db: ok` at migration 005.

  **Two failures on the way.** CI went red on run `34227781888` — the `search_vector`
  trigger could not expand `genres` when SQLAlchemy had serialised Python `None` as the
  JSON scalar `null`, which is not SQL NULL and cannot be treated as an array; `005` now
  guards on `jsonb_typeof(...) = 'array'`. Run `34228015029` was then green with 269 API
  tests and no skips, including the 16 derived-trigger tests. During close-out the local
  verification script also failed twice on its own errors — a `release_date` column that
  does not exist (it is `year`) and psycopg2 reading `%` in an `ILIKE` pattern as a
  parameter placeholder. Neither touched the app.

  **One acceptance criterion is proved indirectly, and it is worth naming.** Both profiles
  still have `pin_hash = NULL`, so nobody can log in and every read route requires
  `CurrentUser`. The deployed app boots and renders its login page with no console errors,
  but the browse grid, detail page and picker were verified by CI integration tests and by
  direct database measurement — **not** by driving the production UI. The 60fps figure in
  particular rests on all three views being virtualised with `@tanstack/react-virtual`,
  not on a frame-rate measurement. Setting the PINs closes it.

- **2026-09-08** — **Batch 4 shipped — 1,857 discs are in the database, with structured
  location, for the first time.** Migration `003` lands the §3.4 domain schema and `004`
  two fixes the live import forced. All four acceptance criteria proved against the live
  database: 1,857 `collection_items` with 1,857 distinct `import_source_row` and zero
  errors; 1,733 sectioned with zero values outside the §3.4 vocabulary; the dry run
  diffed against `matching_eval.csv`; and **14 derived-field trigger tests running in CI
  with zero skips** — the criterion Batches 2 and 3 could only defer. 1,843 movies and
  45,144 credits alongside, with `search_vector` and `best_format_owned` populated by
  trigger over real rows. 764 rows are catalogued but not yet identified and sit in a
  review queue that lists every tied candidate.

  Three decisions were taken with the owner before or during the work: §3.4's schema over
  the April one, which forced the trigger tests to be re-authored rather than resumed
  (#28); the collection is **1,857 items, not 1,866** — nine trailing spreadsheet rows are
  blank, so the number was wrong everywhere it appeared, Phase 1.5's acceptance included
  (#29); and an ambiguous match is catalogued but not enriched, which meant changing the
  matching engine against this batch's own "port `matching/` unchanged" instruction (#31).

  **Four defects, three of them invisible to a green gate.** Criterion 3 stopped the batch
  for a day when a fresh matching run against `matching_eval.csv` showed `Amistad`
  resolving to `Friendship (2023)`; a full scan found 652 rows (35%) whose film was chosen
  by TMDB popularity alone. Then the live write found three more that no test could have
  caught: the importer could not connect to any hosted database, a 300-character
  `character_name` overflowed its column and rolled back a whole item, and an idempotency
  key on item contents collapsed "French Connection" and "French Connection 2" into one
  disc. Gotcha 16 records the general lesson; #32 records the fixes.

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
