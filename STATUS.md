# STATUS — MCU App

## Now

**29 of 37 batches shipped, 8 remain.** Production serves the merged `main`, reporting
`db: ok`, `push: configured` and `ai: configured`.

**The 2026-09-09/10 overnight run is finished. All eight batches are built and deployed** —
11, 20, 30, 31, 32, 35, 25 and 23 — in the order the dependency chain required, plus a
doc-recovery commit that turned out to be necessary. **Groups F and J are complete**, and
Stage 9 is done apart from 9.6, which #16 dropped.

**Every gate was green before every merge**, and three batches needed a second push to get
there. Nothing was weakened to reach green: the three CI failures were a partial unique
index that cannot be an `ON CONFLICT` arbiter without its predicate, a `default=` that
SQLAlchemy applies when *it* builds the INSERT (so a hand-built one sent a NULL primary
key), and two assertions that read the whole table when migration `002`'s seeded profiles
mean a reminder correctly writes more rows than the fixture makes. All three are gotcha 15:
**a green local run is silent about anything touching SQL.**

**Batch 23 is complete: §3.7 was run on 2026-09-10 and it found the scraper broken.** The
owner accepted #110's risk and asked for the run (`#121`). All ten pages fetched — and
**nothing was extracted from any of them**. The parser looked for `<strong>`-labelled rows;
Blu-ray.com serves `<span class="subheading">` sections with bare `Label: value` lines. The
suite had been green throughout because `test_specs.py`'s fixture was *invented to match the
parser* — eleven tests passing against markup the site has never served (`#122`).

Then the fix's own re-run stored **one** audio track for Blade Runner 2049 where the page
lists **six**, because that page wraps its tracks in a `<span>` and Fight Club's does not.
**One real page is a sample of one.** Both are fixtures now, captured verbatim, and a test
asserts they stay captured.

§3.7 is met on the third attempt: **10 rows of 1,857, 10 distinct release URLs**, no halt,
no currency symbol in any derived field, Blade Runner 2049 reading 2160p/HEVC/HDR10 with all
six tracks. #110's bounds held throughout all three runs — sequential, five seconds apart,
honest user agent, no redirect following, and never a `403`.

**Nothing was lost while it was broken.** `apply_specs` checks `is_empty` before touching a
row, so a parser that stops matching the site writes nothing rather than blanking 1,857 rows.
That is the whole reason the failure cost ten wasted requests and no data.

**Nothing this run wrote to production data.** 1,857 `collection_items` untouched, 8
`price_checks`, and every new table empty — `ai_usage_log` included, so no model call has
been made on the owner's key. **The one exception is §3.7's own acceptance**: ten
`collection_items` now carry specs derived from Blu-ray.com, each with its source URL, and
`DELETE /api/v1/specs` reverses it.

### ⛔ What is waiting for you

`OWNER-ACTIONS.md` has four things this run created or unblocked, and they are mostly
minutes:

1. **Two Railway crons in one visit** — the nightly scrape and the reminder pass. **Each is
   now a command**, `python -m src.scripts.daily_scrape` and `python -m src.scripts.run_reminders`.
   Until 2026-09-10 both items said "point a cron at this endpoint" and **that could not be
   done**: both endpoints are admin-authed and an access token lives 24 hours, so no
   scheduler could ever have called them (`DECISIONS.md` #119).
2. **Push on for two devices** — closes 5.6 and 6.2 between them.
3. **One question to the assistant**, and **one spoken** — closes 9.1 and 9.5.
4. ~~**Ten Blu-ray.com URLs** — 3.7.~~ **Done 2026-09-10** — and it found the scraper
   broken. See above and `#122`.

**Six acceptance criteria still need a person**, none of them implied met: 6.2 (two
devices) · 5.6 (a price-drop push received) · 5.5 (first overnight run, needs the cron) ·
9.1 (one live model call) · 9.5 (a spoken query) · 8.4's push to a device. ~~3.7~~ **closed
2026-09-10.**

### What the live database holds

**1,857 `collection_items`**, untouched all run. **11 `wanted_list` rows, 8 live and
active.** 8 `price_checks`, 40 `completion_sets`, 32 `release_calendar`, 10 `retailers`.
The database measured **36 MB** on 2026-09-10, which is why Batch 25 resizes photos.

Empty and waiting for a person: `push_subscriptions`, `notification_preferences`,
`notifications`, `price_history_daily`, `scrape_runs`, `ai_usage_log`, `ai_settings`,
`ai_conversations`, `ai_messages`, `ai_tool_calls`, `movie_night_*`, `item_photos`.
**10 of the 1,857 `collection_items` now carry Blu-ray.com specs** (`specs_integration_state`
reads `fetch_count: 30` — ten wasted on the broken parser, ten more on the partial fix, ten
that worked).


## Next

**The overnight run of 2026-09-09 — eight batches, in this order.** The order is
dependency-derived and must not be rearranged: 20 needs 11's push, 31 needs 30, 32 needs 31.

| # | Batch | Closes fully? |
|---|---|---|
| ~~1~~ | ~~**11** Notifications + push (6.1, 6.2, 5.11)~~ | **shipped 2026-09-10** — 6.2 deferred, needs two real devices |
| ~~2~~ | ~~**20** Price scraping + drop alerts (5.5, 5.6, 5.8)~~ | **shipped 2026-09-10** — cron is hosting; 5.6 needs a device |
| ~~3~~ | ~~**30** AI assistant — client + caps (9.1, 9.7)~~ | **shipped 2026-09-10** — ⚠️ 9.1's live call is an owner action |
| ~~4~~ | ~~**31** AI assistant — tools + chat (9.2, 9.3, 9.4)~~ | **shipped 2026-09-10** |
| ~~5~~ | ~~**32** Voice input (9.5)~~ | **shipped 2026-09-10** — ❌ 9.5 still needs a human speaking |
| ~~6~~ | ~~**35** Movie night (8.3, 8.4)~~ | **shipped 2026-09-10** — ⚠️ 8.4's push to a device is an owner action |
| ~~7~~ | ~~**25** Photo uploads (3.10)~~ | **shipped 2026-09-10** |
| ~~8~~ | ~~**23** Specs — scraper + display (3.7, 3.8, 3.9)~~ | **built 2026-09-10** — ❌ 3.7's live run is an owner action |

**Every batch's criteria are in `docs/phase-batches.md`** under "Criteria recovered for the
2026-09-09 overnight run", each with what the April spec no longer knows. Read that section
rather than re-deriving from §16.

*This sentence was wrong when it was written and is now true.* It claimed all eight were
there; **only six were** — Batch 20's and Batch 35's were missing, and were recovered from
`d94a6b8~1` on 2026-09-10 before either batch was built, as `DECISIONS.md` #54 requires.

**Three hosting steps stop and wait for the owner**, per the close-out protocol:

1. ~~`VITE_VAPID_PUBLIC_KEY` on Vercel~~ — **no longer needed.** Batch 11 serves the public
   key from the API, derived from the private half (`DECISIONS.md` #114). What Batch 11 *does*
   need is a daily cron calling `POST /api/v1/notifications/run-reminders`.
2. **Two** Railway crons, in one visit — the nightly scrape and the reminder pass. `#60`
   explains why an in-process scheduler is worse than nothing for either. **The endpoints
   named here were not callable by a cron**; each job is now also a command, which is what
   a Railway cron runs (`#119`). `OWNER-ACTIONS.md` carries the exact lines.
3. ~~Nothing for Batch 35~~ — **correct, and now proved.** `LISTEN`/`NOTIFY` + SSE needed
   no new service, credential or hosting step (`#113`). Batch 35 shipped without one.

**Four acceptance criteria an agent cannot meet.** Say so plainly in each close-out; never let
a green gate imply otherwise. 6.2 (two devices) · 5.6 (a price-drop push received) · 9.5 (a
spoken query) · 8.4's "notification to both", depending on how the match is signalled.

**Settled inputs, so no batch has to ask again:** the AI daily cap is **50 messages per person**
(`#112`'s neighbour, recorded in the ledger); photos are capped at **~300 KB** after
server-side resize and stored in Postgres, not an object store — **confirmed by the owner
2026-09-10, `#120`**; Batch 23 gathers its ten
Blu-ray.com URLs from browse pages under `#110`'s bounds and extracts no prices.

### Verify against the live system, not only the suite

Three times on 2026-09-09 a green gate coexisted with a broken feature: CI was green while
production had no TMDB token; the scraper "test" button showed results while saving nothing;
and phase 5.5 carried a criterion no correctly working system could satisfy. For each batch,
run the gate **and then exercise the real thing** — live API, real database, the browser where
it renders — and report what was observed rather than what passed.

### Four things the next agent should know

1. **Planned batches whose criteria have not yet been recovered need them written into the
   ledger before implementation.** Batch 10 removed §16. Recover them verbatim from
   `git show d94a6b8~1:MCU_Architecture_v2.1_FINAL.md`, grep for `**Phase X.Y:`, and write
   them into the batch's ledger section **before** writing code (`DECISIONS.md` #54).
2. **Adding a Python dependency means regenerating both locks.** CI installs with
   `pip install --require-hashes -r requirements-dev.lock`; `pyproject.toml` alone is not
   enough. The command is in each lock file's own header.
3. **The Postgres-backed tests cannot run on this machine** — no local server, no Docker — so
   254 of them skip locally and run only in CI. Do **not** point them at production Neon to
   get local coverage. A test fixture bug on 2026-09-09 used an unresolvable host and was
   caught only because CI ran it against real Postgres; against Neon it would have passed and
   shipped hidden behind a green local run.
4. **Anything that lives only in a Railway variable has no test.** The TMDB token was missing
   for an unknown length of time behind a fully green gate. `AGENTS.md` already says the gate
   proves the code and not the infrastructure around it — the TMDB outage is what that
   sentence looks like in practice.


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

5. **RESOLVED IN BATCH 9 — and there were four dead steps, not three.** The wizard is
   rebuilt against a real completion column (migration `010`), and every remaining step is
   backed by something that exists.

   - `StepInstallPWA` read `window.__pwaInstallPrompt`, which nothing set and nothing
     could have — there was no manifest and no service worker for `beforeinstallprompt` to
     fire against. **Batch 8 supplied both**; `usePwaInstall` now captures the event, and
     falls back to instructions on iOS, which never fires it.
   - `StepNotifications` offered to enable push against **zero** infrastructure, and still
     does: no VAPID key, no subscription, no endpoint, no `push_subscription` column.
     **Dropped, not fixed** (`DECISIONS.md` #50) — the batch definition's claim that it
     "now has real infrastructure behind it" was wrong. **Batch 11 owns bringing it back.**
   - `StepEmailConnect` was doubly dead: Stage 10 is dropped *and* this app has no email
     addresses at all, since sign-in is a display name and a PIN.
   - **The fourth, which this gotcha never listed:** the catalogue step read
     `d?.meta?.total` — the `{data, meta, errors}` envelope `DECISIONS.md` #6 removed — so
     it rendered a loading skeleton for ever. A dead read can hide behind a plausible
     loading state indefinitely.

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

19. **A green build, green types and green tests can all coexist with a page that lies.**
    TanStack Query **pauses** a retry when it believes the app is offline: the query sits
    at `status: 'pending'`, `fetchStatus: 'paused'`, `isError: false`, with no data, and
    stays there. The usual `isLoading → isError → items.length === 0` ladder therefore
    falls through to the **empty state** — so `/trash` rendered "Nothing has been removed."
    while its request had never come back, indefinitely and confidently.

    Found by opening the page in a browser during Batch 7, with nothing failing anywhere
    else. `listState()` in `apps/web/src/lib/query-state.ts` names the fourth state so a
    list can say "waiting for the network" instead (`DECISIONS.md` #41). **Any new list
    must use it**, and Batch 8's offline banner should build on it rather than around it.

20. **A pydantic `field_validator` does not run for a field the request omits.** Batch 7's
    create body used one on `tmdbId` to enforce "exactly one of `movieId`/`tmdbId`", which
    correctly rejected a body naming *both* and silently accepted one naming **neither** —
    a 500 where a 422 belonged. Use `model_validator(mode="after")` for any rule that spans
    fields or must hold when a field is absent.

21. **`mypy` is unpinned (`>=1.11.2`), so local and CI disagree about unused ignores.**
    A `# type: ignore[arg-type]` that this machine's mypy 2.3.1 considered *necessary* was
    reported as *unused* by CI's, and `warn_unused_ignores` made that a red gate. The fix
    is to write code that needs no ignore — narrow in a loop rather than assert in a
    comprehension. **Pinning mypy is an open suggestion, not a decision taken.**

22. **A green build, green types and green tests prove nothing about behaviour with the
    network away.** Batch 8's four defects were all found by driving the built app against
    a stub API that could be switched off, with everything else passing. The most
    important: **React Query pauses queries and mutations when it thinks you are offline**
    (`networkMode` defaults to `'online'`), which silently disables both halves of an
    offline story — the mutation never runs `mutationFn`, so an offline write queue inside
    it is unreachable, and the query never issues the fetch a service worker exists to
    answer. `apps/web/src/lib/query-client.ts` sets `'always'`, and
    `query-client.test.ts` hangs if that is reverted. **Any new QueryClient must keep it.**

23. **`fetch` resolves for a 5xx, so "the server answered" and "the write was applied" are
    different questions.** A 503 comes from a gateway, a proxy, a captive portal or a
    container that is still booting as readily as from the application. Treating one as a
    refusal discards the write; treating it as certain failure and retrying duplicates it.
    It is the *unknown* case — see `DECISIONS.md` #43 — and the same reasoning is why
    only a 401 or 403 may end a session (#48).

24. **`NOW()` in Postgres is the transaction start time.** Every row written by one
    transaction gets the same value, and two updates inside one transaction are
    indistinguishable. That is fine for "created at" and wrong for "modified at" — and
    once `updated_at` became Batch 8's concurrency token it was a guard that could not
    detect anything. Migration `009` moves `set_updated_at` to `clock_timestamp()`.
    **The test harness runs each test in one transaction**, so anything that depends on
    time advancing must use `clock_timestamp()` or it will pass for the wrong reason.

25. **A service worker cannot be registered from the tooling available here.** The
    in-app browser pane refuses with "An unknown error occurred when fetching the script"
    even though the file serves correctly, and no Chrome extension is connected.
    Everything else about the PWA is verifiable — the manifest, the icons, the generated
    worker's contents, the queue end to end — but **"it caches the collection offline" and
    "it installs to a home screen" can only be confirmed on a real device.**

26. **`date.today()` reads the *server's* timezone, and this codebase is UTC everywhere
    else.** A test can therefore go red from the clock alone, with nothing changed: the
    watch-log default was computed in UTC and validated against local today, which agree on
    Railway and disagree on a British machine for the hour after midnight. Green in CI all
    day, red at 00:07 BST.

    Use `src/clock.py` — `utcnow()`, `utc_today()`, `latest_plausible_today()` — never
    `date.today()`. And for a date a *person* supplied, "in the future" means "not today
    anywhere on Earth" (UTC+14), not "later than today here": a guard on UTC today refuses
    someone in London logging tonight's film at 00:30 (`DECISIONS.md` #53).

27. **`set -a; . apps/api/.env.local` silently drops `DATABASE_URL`, and pytest then reports
    green while skipping 246 tests.** The Neon URL ends
    `?sslmode=require&channel_binding=require` — **unquoted**, so bash reads the `&` as job
    control: the assignment is backgrounded (no effect on the shell) and
    `channel_binding=require` runs as its own command. `DATABASE_URL` ends up unset, the
    database-backed tests skip rather than fail, and the run exits **0**.

    Hit during Batch 27's close-out: `301 passed, 246 skipped` looked green next to the real
    `547 passed`. Always read the count, not the colour. Export it by hand instead:

    ```
    export DATABASE_URL="$(grep '^DATABASE_URL=' apps/api/.env.local | sed 's/^DATABASE_URL=//')"
    ```

28. **`cryptography` runs at a different version here than in CI, and it is the security
    floor that forces it.** The lock pins **50.0.1**; this machine has **48.0.1** and
    cannot install the pinned one. cryptography 49+ ships no `macosx-10.15-x86_64` wheel,
    so pip falls back to a Rust source build that fails here, while CI's and Railway's
    manylinux wheels install without comment.

    The obvious fix — pin below 49 — was tried and **reverted**: 48.0.1 carries
    PYSEC-2026-3552, -3553 and -3554, and CI's dependency-audit job refused it, correctly.
    A vulnerable crypto library in production is not worth a tidy local install
    (`DECISIONS.md` #115).

    **So CI is the authority for anything touching `cryptography`**, which today means
    Web Push. A local `pytest` run exercises the same tests against a different version of
    the library, and a green local run is therefore weaker evidence than usual — the same
    caveat gotcha 15 puts on anything touching SQL. Lift this when the developer machine's
    platform tag moves past `macosx-10.15-x86_64`.

29. **Prepending Node 22 to `PATH` makes the Railway CLI vanish**, and the error blames
    the wrong thing: `bash: railway: command not found`, which reads as "not installed".

    Two facts collide. The IaC engine needs **Node 22+** (gotcha in `.railway/README.md`),
    but the CLI is installed under **Node 20's** nvm bin — `nvm alias default` is 20 — and
    is an `#!/usr/bin/env node` script. So `PATH="…/v22.23.2/bin:$PATH" railway …` fixes
    the runtime and removes the binary, because `railway` was never in Node 22's bin.

    It is easy to miss from an agent session, where the shell is initialised from the
    user's profile and already has Node 20's bin on `PATH` — the bare `railway` form
    resolves there and fails only in the owner's terminal. **`.railway/README.md` carried
    the broken form** until 2026-09-10.

    Both halves, and it works from a shell with no nvm loaded:

    ```
    PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" \
      "$HOME/.nvm/versions/node/v20.20.2/bin/railway" config plan
    ```

    The general rule this is an instance of: **a command that only works because of the
    ambient shell is not a command worth writing into a doc.** Test it under
    `env -i HOME="$HOME" PATH=/usr/bin:/bin bash -lc '…'` before handing it to anyone.


## Log

- **2026-09-10** — **`railway config apply` would have deleted two live credentials, and
  had been able to since the day they were set.** Found by running the read-only
  `railway config plan` before adding the cron services: it read `2 to add, 3 to change,
  **2 to destroy**`, and the two were `api.ANTHROPIC_API_KEY` and `api.TMDB_READ_TOKEN`.

  Both were set in the Railway console on 2026-09-09 and never declared in
  `.railway/railway.ts`. IaC removes what the file does not declare, so it read them as
  drift. Applying would have **recreated the TMDB outage of 2026-09-09 exactly** — every
  TMDB-backed feature answering 502 behind a fully green gate — and taken the assistant
  with it. The JWT secrets were a quieter version of the same thing: declared as generated
  values but sealed, so they cannot be read back to compare, so every plan reported them as
  changing and an apply would have signed both people out. `DECISIONS.md` #124.

  All ten API variables are now `preserve()` — which names a variable without putting its
  value in the repo — and the plan reads **`2 to add, 1 to change, 0 to destroy`**.

  **The two crons are declared rather than clicked.** `cron-scrape` and `cron-reminders`
  are services in `railway.ts` sharing the API's image at a different entry point, taking
  `DATABASE_URL` and the VAPID keys **by reference** from `api` so each secret has one copy.
  `restartPolicyType` is `NEVER`: they make live requests to real shops, and retrying a
  failed night automatically would turn one bad night into three. All that is left for the
  owner is `railway config apply`, which stays his because it is a hosting change.

  *What made the trap invisible:* `.railway/README.md` warned against running `apply`
  outside close-out, which reads as caution about changes you meant to make. The hazard was
  the opposite — a change nobody authored, produced by the file's silence. The README now
  says to read the destroy count first.

- **2026-09-10** — **Writing out the owner's remaining steps found a live data-loss bug.**
  §5.6 needs a want whose `max_price` sits above its current price, and there was no way to
  set one on a want you already had: the field existed on the add form and nowhere else.

  Adding that control meant reading the update path. `PUT /api/v1/wanted/{id}` **replaces
  the row** — every field on its request model defaults to `None` — and the web app's one
  call site sent `{isActive}` alone. **Every press of "Stop looking" or "Look again" also
  nulled the format, the edition, the maximum price and the notes**, silently, in
  production, with `admin_actions` recording it faithfully as a change nobody had asked
  for. `DECISIONS.md` #123.

  The endpoint is not the bug: `PUT` means replace. The client now sends the complete
  resource with only the changed field overridden, `updateWanted` takes the row's own
  `currency` instead of hard-coding `GBP` where no caller could override it, and two tests
  pin both halves — the toggle round-trips every preference, and the endpoint's
  full-replace contract is asserted so the next person reads it as the contract rather than
  patching the API to be lenient.

  **A verification note worth keeping.** Confirming the new control had deployed by
  comparing the local bundle hash against Vercel's was wrong twice over: Vercel injects
  `VITE_API_URL`, so the hashes can never match, and Vercel answers an unknown
  `/assets/*.js` with `index.html` at **200**, which reads as "the file is there". The
  reliable check is to read the deployed `sw.js` precache manifest, fetch what it names,
  and grep for a string only the new build contains.

- **2026-09-10** — **§3.7's live run found that Batch 23's scraper had never worked, and
  the fix's own re-run found a second bug.** The owner accepted `#110`'s risk and asked for
  the run (`#121`).

  **First pass: ten pages fetched, `200` on all ten, zero specs extracted.** The parser
  looked for `<div class="row"><strong>Codec:</strong>`; the site serves
  `<span class="subheading">Video</span><br>Codec: MPEG-4 AVC<br>` — section headings with
  bare `Label: value` lines and no `<strong>` anywhere. `_label_of` returned `""` for every
  node on every page.

  **The suite could never have caught it.** `test_specs.py`'s `PAGE` was hand-written to
  match the parser. Fixture and parser agreed with each other and neither had ever met the
  site; eleven extraction tests passed against markup that has never existed. This is the
  third time this project has had a green gate over a broken feature — the missing TMDB
  token, the scraper *test* button that saved nothing, and now this.

  **Second pass: one audio track where the page lists six.** With one captured fixture the
  parser passed, but `Blade-Runner-2049-4K/189774` wraps its tracks in a `<span title="…">`
  and Fight Club's page does not, so a `_lines` reading only top-level children flattened
  all six into one string — and gave that one track a channel count belonging to the line
  below it, which is worse than storing nothing. `_flatten` recurses now. **One real page is
  a sample of one**, so the 4K page is a second fixture, kept precisely because it disagrees
  with the first about its own markup. It also carried the only HDR block of the ten, which
  the flattened version was dropping too.

  **Third pass met the criterion:** 10 rows of 1,857, 10 distinct release URLs, no halt, no
  currency symbol in any derived field.

  **What held throughout.** Every one of `#110`'s bounds — sequential requests five seconds
  apart, honest user agent, no redirect following, exact release URLs, never a `403`. And
  `apply_specs` checks `is_empty` before touching a row, so two broken passes cost twenty
  wasted requests and **no data**: a parser that stops matching the site writes nothing
  rather than blanking 1,857 rows. `DECISIONS.md` #121, #122.

  **The guard that matters more than the fix.** `TestTheFixtureIsReal` asserts the fixtures
  stay captured — provenance line present, `<span class="subheading">` rather than
  `<strong>` rows, price cell still in place. A fixture written to match the parser is the
  bug; a test that says so is the guard.

- **2026-09-10** — **The two Railway crons had nothing to run.** Found while walking the
  owner through his remaining close-out steps: `OWNER-ACTIONS.md` told him to point a cron
  at `POST /api/v1/scrapers/daily` and `POST /api/v1/notifications/run-reminders`, but both
  are `AdminUser`-authed and an access token lives 24 hours. **A cron container has no
  browser, no login and nothing to refresh, so neither endpoint was callable by a scheduler
  at all** — the owner action could not have been completed as written. Batches 11 and 20
  each shipped the endpoint half and left the command half unbuilt.

  `src/scripts/daily_scrape.py` and `src/scripts/run_reminders.py` are those jobs as
  commands, matching the precedent `#60` set with `refresh_completion_sets.py` — whose whole
  point was that scheduling should be *"one console action rather than a piece of
  engineering"*. No new credential (the container already holds `DATABASE_URL` and the VAPID
  keys) and no second authentication path on the API; the endpoints are untouched. A shared
  secret was offered as the alternative and the owner chose the scripts. `DECISIONS.md` #119.

  **The exit code is the behaviour worth testing**, because it is the only thing a scheduler
  reads: a failed retailer exits 1 and names the shop and the reason, a shop that simply does
  not stock a film exits 0, and `--dry-run` is opt-in on the scrape — a nightly job that
  defaulted to writing nothing would be indistinguishable from one that works.

  **One seam moved.** `push_sender` left `routers/notifications.py` for
  `src/services/push_transport.py`, so a scheduled job does not import FastAPI and the whole
  route table to obtain a transport; the router re-exports it and a test asserts the two
  names are one object.

  **CI cannot prove the container runs these**, because it never builds the image — so
  `test_deployment_config.py` asserts the contract they depend on instead: `WORKDIR /app`,
  `PYTHONPATH=/app`, the whole `src/` tree copied, and the command line in `OWNER-ACTIONS.md`
  matching the module that exists. A moved `WORKDIR` would otherwise break both crons
  silently, and the first sign would be a scrape that never ran.

  **Also settled with the owner:** the 300 KB photo target is now a recorded decision rather
  than an inference two docs disagreed about (`#120`), and the owner accepted `#110`'s
  Blu-ray.com risk so §3.7's live run can proceed.

- **2026-09-10** — **Batch 23 built: the Blu-ray.com spec scraper, badges and filters.**
  The last of the overnight run's eight batches.

  **#110's bounds are enforced by the code rather than described by it.** Exact release URLs
  only, with the disallowed search routes refused by name; requests sequential and five
  seconds apart, with an honest user agent and no redirect following, because #110 forbids
  evasion; a `403`, `429` or `451` **halts the whole integration** and abandons the rest of
  the batch. The halt is a database row, not a variable — one held in memory lasts until the
  next deploy, and that is precisely the promise that must not break. **Nothing in the runner
  can clear it**, and a test asserts that, because #110 says resuming needs a new owner
  decision.

  **No price, rating or review is extracted, and the page carries all three in the same
  document.** #108 calls the temptation "unusually close to hand", so the parser reads an
  allow-list of labels, the forbidden ones are named, and a test proves the two sets
  disjoint. The fixture deliberately carries a list price, an Amazon price, a rating and a
  review so their absence is demonstrated rather than promised.

  Two more of #108's measured facts changed the code: **audio is rendered twice** behind the
  `(more)`/`(less)` toggle, so extraction targets DOM nodes and de-duplicates; and **Special
  Features was absent** from a real page, so it is nullable rather than assumed.

  §3.8's badges use three genuinely distinct colours — resolution, HDR and audio are three
  different claims, and a row of identical pills makes them one blur. A disc with no specs
  renders **nothing**, not a grey "unknown": the app does not know until it has asked, and a
  placeholder that looks like data is how a catalogue starts lying.

  **§3.7's acceptance is not done and is an owner action.** It needs a live run against ten
  real URLs on a site whose terms prohibit automated access; #110 is the owner's acceptance
  of that risk rather than a permission an agent inherits, and `group-start.md` puts live
  third-party runs in the owner's hands — which is how Batch 19's checkpoint worked too.
  Production reports **0 pages ever fetched**, and `DELETE /api/v1/specs` is there to make
  the whole thing reversible.

- **2026-09-10** — **Batch 25 shipped: photos of a disc.** Bytes in Postgres, resized before
  they get there.

  §3.10 says Supabase Storage and there is no Supabase project; the owner settled storage as
  Neon, so a photo is a `BYTEA` column served by the API — and a real `item_photos` table
  rather than §3.4's `photo_urls`, which designs a list of *external* URLs there is now
  nothing to point at.

  **The resize is why the batch is shaped like this.** §3.10's raw numbers are 5 MB × 5 ×
  1,857 ≈ 46 GB, in a database that measured **36 MB** live today. A phone's 4032×3024
  photo now stores at about 240 KB — measured in a test rather than asserted in a comment.

  **A disagreement between two in-repo docs, resolved by making it cheap.**
  `OWNER-ACTIONS.md` said the 300 KB cap was "proposed… not confirmed"; `STATUS.md`'s own
  run plan and the batch ledger both listed it as *"(owner, 2026-09-09)"* under "settled
  inputs, so no batch has to ask again". No `DECISIONS.md` entry exists either way. It
  shipped at 300 KB — the number both docs name — with the target as the `PHOTO_TARGET_KB`
  **setting**, so the thing that made it an owner choice ("annoying to reverse once photos
  exist") is no longer true: changing it is one variable and a re-upload.

  **Every upload is decoded and re-encoded.** EXIF orientation applied *then dropped* —
  dropping it without applying is how a gallery fills with sideways shelves; transparency
  composited onto white rather than the default black; and Pillow's pixel ceiling refuses a
  decompression bomb, which is a tiny upload that unpacks to gigabytes.

  **Two blockers turned out not to exist.** Group H said Batches 24 and 25 were "both
  blocked on the same two `vercel.json` fixes". Neither was needed: `camera=(self)` has been
  live since Batch 2, and the photos are served from the API origin `connect-src` already
  allows. **`authFetch` did need a fix** — it forced `application/json` onto every body,
  which for multipart omits the boundary and makes the server parse nothing out of a request
  that looks perfectly normal.

  **Nothing failed in CI.** Green on the first push, 21 new tests.

- **2026-09-10** — **Batch 35 shipped: movie night.** Sessions, an invite URL, a swipe deck
  and match detection over Postgres `LISTEN`/`NOTIFY`.

  **The net-new integration turned out not to be needed.** §8.4 names Supabase Realtime and
  the ledger tiered this batch 🔴 partly for it; `DECISIONS.md` #113 replaced it with
  `LISTEN`/`NOTIFY` and SSE the day before, so it shipped with no new service, credential or
  bill.

  **#113's warning shaped the whole realtime module.** `LISTEN` holds a connection for as
  long as it listens, and taking one from the request pool for a whole movie night exhausts
  the pool and reads as the entire app hanging — Batch 8's paused query in another costume.
  One dedicated connection is opened on the first watcher and closed with the last. Unlike
  #60's cron, two containers is *correct* here: both listen on the same channel.

  **A match is derived, never stored** (gotcha 1b), with `announced_at_utc` the only derived
  state kept so it is announced once. The rule is "everyone here" rather than "two" — free
  now, and the difference between a feature that grows and one with a 2 baked in. **The
  other person's votes are invisible**: the stream says only that *a* vote happened, and a
  card vanishing because they swiped it would leak which way.

  `asyncpg-stubs` went in as a dev dependency rather than a mypy override for the module,
  and immediately earned it: asyncpg's listener callback really takes `object`, not `str`,
  because a binary-mode connection delivers bytes.

  **A stale owner action closed on the way past.** `OWNER-ACTIONS.md` still asked "what
  provides realtime for Batch 35?" — a question #113 had answered as an owner decision the
  day before. Marked done rather than asked again.

  **Nothing failed in CI.** Green on the first push, 16 new tests. §8.4's notification
  *arriving on a device* is deferred with 6.2 and 5.6; the match and both notification rows
  are proved.

- **2026-09-10** — **Batch 32 shipped: voice input.** Stage 9 is complete apart from 9.6,
  which `DECISIONS.md` #16 dropped.

  On-device recognition — the browser's engine listens and nothing is uploaded by this app.
  `microphone=(self)` had been in `vercel.json` since Batch 2, so no hosting change.

  **Dictation fills the input and never sends.** The engine mishears; a button that
  submitted on the last word would put a wrong question to the assistant with no chance to
  correct it, and would also make the acceptance criterion uncheckable — "correct
  transcription" is something only the person can confirm, by reading it.

  **Two things that would have been silent bugs.** TypeScript's DOM library declares none
  of the Web Speech API, so the used surface is declared in-repo rather than casting
  `window` to `any` — which accepts a misspelled event name and yields a mic that listens
  and reports nothing. And interim results are reassembled rather than appended: the engine
  revises earlier entries in place, so concatenating each event produces "where where is
  where is Heat".

  **9.5's acceptance is deferred** — it needs a person speaking into a microphone.

- **2026-09-10** — **Batch 31 shipped: role-aware tools, streaming chat, and confirmation
  before any write.** `fe1db05`. Group J is complete.

  **The agent loop is manual and that is the whole design.** The SDK's tool runner drives
  the cycle in one process; §9.4 requires it to stop, hand a request to a browser, and
  resume when a person answers in a *later HTTP request*. So a pending write is a row, not
  an in-memory future — the latter loses every outstanding confirmation on the next deploy.

  **Every call in a turn gets a row, including the reads.** The API insists one
  `tool_result` message answers all of an assistant message's `tool_use` blocks, so a turn
  that both searches and writes cannot send half an answer while it waits. The read runs,
  its result is held, and both go back once the write is resolved. A cancelled call is kept
  and marked, with a result the model reads as a refusal — otherwise its next sentence
  cheerfully reports success.

  **`DECISIONS.md` #12 stays closed.** Tools dispatch to the same endpoint functions the web
  app calls, which are plain async functions taking `(user, db, ...)`, and results come back
  as the same pydantic models the browser parses. No envelope was needed and none was added.

  **"Write" and "admin-only" turned out to be different questions.** Watch history is
  personal — Batch 6 and Batch 37 both scope it to the caller — so `log_watch` writes and a
  viewer keeps it. One axis would have taken it from Mark for no reason.

  Messages store raw content blocks rather than text, because replaying only the text makes
  Claude answer as though a tool call never happened, silently. `sequence` orders them:
  `NOW()` is the transaction's start time and a turn writes several rows in one (gotcha 24).
  The browser parses SSE with `fetch` rather than `EventSource`, which cannot POST or carry
  an Authorization header, and buffers across chunk boundaries — a frame routinely arrives
  split across two reads, and a parser that assumes otherwise drops text with no error.

  **Nothing failed in CI.** Green on the first push, 34 new tests.

  **A stale number corrected while verifying.** The "what the live database holds" block has
  said 3 `wanted_list` rows since 2026-09-09. It is 11, 8 of them live — the three originals
  were soft-deleted and eight boutique titles added during that evening's acceptance run
  (#111). Confirmed that nothing this session wrote to production: 1,857 items untouched,
  8 `price_checks`, and `ai_usage_log` empty.

- **2026-09-10** — **Batch 30 shipped: the Claude client and the AI usage caps.**
  `ecb00dd`. Group J is half done.

  **The model id is config, validated at load.** `docs/phase-batches.md` warned "do not
  guess a model id" — the April spec predates the current lineup by two generations. The
  validator refuses an id this app has no price for, which catches the *worse* failure as
  well as the obvious one: a wrong id 404s loudly, an unpriced one works and silently logs
  every call as free, and a cost cap counting zeros never fires.

  Two more things the spec could not have known: `budget_tokens` returns a **400** on the
  Claude 5 family (adaptive thinking plus an `effort` level replaces it), and assistant
  prefill is gone, so response shaping lives in the system prompt.

  **§9.7 enforces two ceilings, before the call.** A message count alone does not bound
  spend — the same question costs more at the end of a long conversation. Checking after
  the call would still have spent the money, and a test asserts the model is never reached
  once the cap is hit. A refusal is a 200 carrying the sentence, not a 429. The day is the
  person's local day (gotcha 26), and `cost_usd` holds six decimal places because rounding
  a sub-penny call to cents records it as free.

  **Readiness now reports `ai` alongside `push` and `db`,** and live it says `configured` —
  so the Anthropic key really is in Railway, which is the one thing a green gate could not
  have told anyone.

  **Nothing failed in CI.** All five jobs green on the first push, 34 new tests.

  **§9.1's acceptance is deferred and is a one-minute job.** It needs a live call, which
  spends the owner's money on a key held only in Railway; there is no credential on this
  machine and the deployed endpoint needs a login. Open Assistant in the sidebar, ask one
  question — the token count and cost render underneath it.

- **2026-09-10** — **Batch 20 shipped: the nightly price job, drop alerts and the 90-day
  roll-up.** `464e495`. Group F is complete.

  **§5.6 as written could not be built.** *"Postgres trigger after price_check insert …
  queue push"* — a trigger runs inside the writing transaction and cannot make an HTTP
  request. Batch 11's outbox is the queue it would have needed, so detection lives in the
  scrape path and writes a `deals` notification. `price_checks.notification_sent`, the
  column §3.6 designed for the trigger, is still the flag.

  **Alerts fire on the transition, not the condition.** A price at or below `max_price`
  stays that way until the disc is bought; alerting on it nightly would train the owner to
  ignore the category. A substituted format or edition still alerts and **says so** —
  suppressing it hides a real find, sending it silently lets "Deep Red is £15" mean the
  Blu-ray when the want was the 4K.

  **`scrape_runs` is new, and #112's criterion is unverifiable without it.** The counts the
  corrected acceptance is stated in used to exist only inside one HTTP response. They are
  now a row, with every failure carrying its retailer and reason, and a run that dies
  halfway is visible as a run that died halfway rather than as no run at all.

  **One CI failure, and it was the test that was wrong.** The not-stocked fixture used a
  generic whole-page config to exercise `DECISIONS.md` #107's detection, which only exists
  on the card-by-card path — `extract` says so in its own docstring. Batch 19's conservative
  reading is left alone and the fixture is now card-shaped, which is what every enabled
  retailer is. **Recorded because the gap is real for a hand-configured generic retailer:**
  three correct refusals in a row would auto-disable it.

  Verified live: `021` applied, both new tables present, 8 `price_checks` untouched, the new
  endpoints auth-gated. `scrape_runs` is empty and correctly so — **nothing schedules the
  job**, which is why §5.5's *"first overnight run completes"* and §5.6's *"push on a test
  device"* are both deferred to the owner.

- **2026-09-10** — **Batch 11 shipped: notifications and Web Push.** `36d3efa`, plus
  `69d263e` for the readiness check. First of the eight-batch overnight run.

  §6.1's toggles, digest mode and quiet hours; §6.2's per-device subscriptions and test
  button; §5.11's seeded sale seasons and their pre-sale reminder. Web Push is implemented
  directly on `cryptography` against RFC 8291/8292 rather than pulling `pywebpush` and its
  two companions, so `tests/test_webpush.py` can derive the message keys from the
  **receiver** side — the browser's half of the algorithm — instead of proving only that a
  library agrees with itself (`DECISIONS.md` #115).

  **Everything routes through an outbox**, which is what makes §6.1 checkable rather than
  asserted: a disabled category leaves a `suppressed` row naming itself, an evening alert
  leaves a `queued` row due at 07:00, and digest mode leaves three sharing one push. Quiet
  hours carry an IANA timezone — the one place this app is deliberately not UTC, because a
  22:00 window read in UTC is an hour wrong for the seven months of BST (gotcha 26).

  **A hosting step was removed rather than performed** (#114). The plan had the owner
  setting `VITE_VAPID_PUBLIC_KEY` on Vercel; instead the API serves the public key derived
  from the private half, so the two cannot disagree and push works the moment the code
  deploys. And because the remaining key still lives only in a Railway variable — the TMDB
  shape — `/api/v1/health/ready` now reports `push: configured | not_configured | invalid`,
  loading the key rather than checking that a string is present.

  **Two debts paid.** §12.5's overdue-loan push, unmet since Batch 15, now writes that
  batch's unused `loans.reminder_sent`. Batch 9's dropped onboarding notifications step
  (`#50`) is back against real infrastructure: 7 steps for an admin, 6 for a viewer.

  **Three defects CI caught that the local gate could not.** A partial unique index is not
  an `ON CONFLICT` arbiter unless its predicate is repeated — that took down all seven
  deduplicated paths. `UUIDPrimaryKeyMixin`'s `default=` runs when SQLAlchemy builds the
  INSERT, so a hand-built one sent a NULL primary key. And two assertions read the whole
  `notifications` table, where migration `002`'s seeded profiles mean a reminder correctly
  writes more rows than the fixture creates. All three are gotcha 15: a green local run says
  nothing about SQL.

  **The dependency audit rejected `cryptography` 48.0.1** over PYSEC-2026-3552/3553/3554.
  The `<49` pin that produced it was mine, added so this laptop could install a wheel; it
  was removed rather than defended. The cost is that this machine now runs 48.0.1 while CI
  and Railway run 50.0.1 — recorded as gotcha 28 rather than hidden.

  Verified live, not merely green: `020` applied to Neon with all three tables present,
  every notification route `401` while a made-up sibling `404`s, and `push: configured`.
  **§6.2 is deferred to the owner — it needs two real devices.** A daily cron for
  `run-reminders` is a new owner action.

- **2026-09-09** — **An audit session, not a batch session. Three beliefs about what was
  blocking the queue turned out to be false, and one production outage had been invisible
  behind a green gate.**

  **`TMDB_READ_TOKEN` had never been set in Railway.** The *Add a film* panel reported "TMDB
  search is temporarily unavailable"; TMDB was fine, and both credentials in `.env.local`
  returned 200. `config.py:70` defaults the token to `""`, so the API booted happily and sent
  `Authorization: Bearer ` on every call, which TMDB answered 401 and the routers converted
  to a 502 whose wording claimed transience. The blast radius was every TMDB-backed feature in
  the deployed app. Set the same day, along with VAPID keys and `ANTHROPIC_API_KEY`; Mark's
  PIN was set too, so both profiles can now sign in.

  **The scraper acceptance run had never saved a row.** The setup steps had been done — Arrow
  corrected to `arrowfilms.com`, five shops enabled — but `price_checks` and `wanted_list`
  were both empty, so the criterion everyone believed was met had never been attempted. It has
  now produced its **first real price**: Arrow Video, *Misery Limited Edition 4K UHD*, £25.00,
  an exact 4K match with no substitution, verified independently against the live site.

  **A 4K want answered with a Blu-ray turned out to be correct.** Zavvi has no 4K *Nope* at
  all — searched with and without the format term, the only *Nope* disc on the site is
  `/p/blu-ray/nope/`. The fallback and its `substitutedFormat` flag behaved exactly as #102
  specifies. The bare-title search also returned seven Magic: The Gathering and Disney
  t-shirts, every one correctly refused: the Jaws beach towel case, caught.

  **Three working scrapers had been auto-disabled for telling the truth** (`DECISIONS.md`
  #107). 101 Films, Powerhouse and Second Sight each returned a real catalogue page for
  *Misery*, extraction parsed it correctly, and #96's title rule refused every listing because
  none of them was the film. Three correct refusals read as three failures and switched all
  three shops off. `ScrapeOutcome.not_stocked` now separates "the shop answered and has not
  got it" from "the scraper is broken", read from card counts rather than the rejection
  message — because `check_shape` stops at "no price found" before reaching its title rules,
  and Zavvi's real answer for `?q=Nope 4K` leads with a priceless *Cujo* that would otherwise
  have been filed as a broken selector. The three shops were re-enabled with their counters
  zeroed. **Zavvi still carries 2 strikes** from a genuine throttling failure.

  **Batch 23's source settled and Batch 26 dropped** (#108, #109). Specs are scraped from a
  URL supplied per film rather than from the site's search, which `robots.txt` disallows; a
  real page was measured and returns every field §3.7 asks for. **#108's reasoning that this
  therefore "stays inside what the site allows" was wrong**, and #110 — written earlier the
  same day by a parallel session — supersedes it: absence from `robots.txt` is not
  permission, and the access proceeds as an owner-accepted risk instead. Three constraints recorded: the page also carries
  third-party prices the scrape must ignore, `(more)`/`(less)` toggles duplicate the audio and
  subtitle blocks in the flattened text, and `Special Features` can be absent. Shelf QR is
  dropped — Batch 6's location filter already answers the question it existed for. Ledger
  arithmetic re-derived rather than decremented: **37 batches → 24 sessions**.

  *Storage for Batch 25 is settled as Neon* (owner), meaning photo bytes in Postgres. The
  per-photo cap and Batch 35's realtime provider are both proposed but unconfirmed, and sit in
  `OWNER-ACTIONS.md` rather than being taken silently.

- **2026-09-09** — **Batch 27's security review: no findings at its bar, four real defects anyway.**

  The review you asked for ran against `feat/27-gift-links` before the merge. It verified all
  six intended properties with file-and-line evidence and reported **no security findings at
  its confidence bar** — but it surfaced four real defects, all fixed on the branch before it
  merged:

  | Found | Fixed by |
  |---|---|
  | The retailer-link builder ran **inside** the per-film loop — 50 identical `retailers` queries for a 50-film page, on the unauthenticated endpoint | hoisted; a test asserts exactly one `FROM retailers` per page |
  | **The service worker cached `no-store` responses.** It matched any GET under `/api/v1/` by pathname alone, so a gift page a family member opened was stored for 24h in *their* browser — and the route's own comment claiming the API sets no `Cache-Control` had become false | same-origin only, both capability URLs excluded, comment corrected (`DECISIONS.md` #87) |
  | `Decimal("NaN")` **parses**, so the `<= 0` guard raised rather than being caught — a 500 on an admin field in **Batch 18's already-merged code** | `is_finite()`; tests cover NaN, Infinity and sNaN |
  | `view_count += 1` was a read-modify-write in Python | atomic `SET view_count = view_count + 1` |

  Two things it named as conscious trade-offs rather than defects: the slug is stored in
  plaintext (`DECISIONS.md` #84 — a gift link must be re-shareable, unlike Batch 17's hashed
  feed token), and it transits request logs the way any path parameter does.

  **One process failure worth keeping.** The first review attempt failed before doing any work
  (monthly spend limit) — and I had *already* written "Reviewed" into the ledger and the commit
  message. That claim was corrected in `247ee25` and the branch was held unmerged until a
  review genuinely ran. Nothing is a review until it returns findings.



- **2026-09-09** — **Batch 23's Blu-ray.com risk was accepted explicitly, not explained
  away by `robots.txt`.** The site's Legal Notices prohibit automated reuse even for
  private/internal calculations, which supersedes #108's claim that exact release-page
  fetching is allowed. The owner accepts the practical risk, including the one-time
  1,857-item backfill; #110 keeps exact public release URLs, no site search or authentication,
  sequential rate limiting, indefinite caching, provenance for reversible cleanup, and a
  hard stop on `403`, `429`, an objection or a hosting complaint. Written permission is
  preferable but no longer blocks Batch 23.

- **2026-09-09** — **A want can now name an edition, not just a format.** Arrow sells *Deep
  Red* on 4K three times — plain £25, Limited Edition £25, Arte Originale slipcover £35 —
  and page order decided which a `max_price` alert was about. `wanted_list` gained
  `preferred_edition` (migration `019`, free text, nullable; the table was empty).

  **Naming the edition is also what makes it findable.** #96's rule refuses a title with
  meaningful extra words, so the slipcover listing was being *rejected outright* — *arte*
  and *originale* read as another film. The wanted edition's words now join that item's
  allowed vocabulary. Verified live against Arrow: no edition → the plain £25 4K; "Arte
  Originale Slipcover" → the £35 disc; "Limited Edition" → the £25 LE; "Steelbook" (not
  stocked) → falls back to the plain 4K and reports `editionMatched: false`.

  **The edition never narrows the search.** Measured: edition terms promote Arrow's exact
  listing, but on Zavvi `?q=Alien Steelbook 4K` returns seven steelbooks and no Alien at
  all. It is a selection input, not a search input (`DECISIONS.md` #104–#106).

- **2026-09-09** — **A want for a format now means that format.** Asked how a want for a
  specific version of a film would behave. It mostly did — `preferred_format` picks 4K vs
  Blu-ray vs DVD — but three defects were found underneath it (`DECISIONS.md` #101–#103):

  1. **Every 4K disc also says "Blu-ray"**, and format preference matched on mention, so a
     £19.99 4K combo satisfied a want for the £9.99 Blu-ray whenever it ranked first. A
     listing is now the *highest* format it names, because that is what is in the box.
  2. **A fallback was silent.** When the wanted format was not on the shelf, a different one
     was priced with nothing said — and `max_price` compares against whatever was priced, so
     an alert was either missed or wrong with no way to tell which disc it meant. The run
     now reports the format actually priced and the UI says so.
  3. **A digital want priced a disc.** `download` had no search term, so it fell back to
     "Blu-ray". Worse, it counted as a retailer *failure* — and three consecutive failures
     auto-disables a shop, so a digital-only wanted list would have **switched off every
     enabled retailer in the app**. Digital wants are now skipped, reported separately, and
     never counted against a shop that was never asked.

- **2026-09-09** — **The Test button was sending shops an unfilled placeholder.** Reported
  from the app: *Jaws* on Zavvi returned **The Sheriff of Fractured Jaw (Dual Format
  Edition)**. The cause was the previous fix's own doing — `ScraperTester` built its search
  URL in the browser and replaced `{query}` alone, so the new `{format}` placeholder went
  to Zavvi as literal text and matched a dual-**format** western. An unfilled placeholder
  is worse than a broken URL: it is extra search terms a shop happily matches, so the
  failure arrives looking like a result.

  Fixed at the root (`DECISIONS.md` #99, #100): `apply_search_template` is now the only
  function that knows what a placeholder means, the client sends the **template**
  verbatim, and the server fills it with the same call the runner makes. The test endpoint
  also now passes the expected title, the preferred format and the retailer's host into
  `extract`/`check_shape` — it had been doing none of those, so it priced whichever card
  came first and never applied the same-site rule. **A test is now exactly as strict as the
  run it stands for.** The tester gained a format selector to match.

  Re-verified against the live shops through the fixed path: *Jaws* at Zavvi → the 4K disc
  at £19.99, all five supported shops return the right film, *Heat* still correctly refused.

- **2026-09-09** — **The scrapers now filter on films, not on names.** Reported from the
  app: searching Zavvi for *Jaws* returned **a beach towel**. It passed all five of #79's
  shape rules — the film's name in the title, £17.99, GBP, a zavvi.com URL — so the price
  of a towel was being written as the price of the film. Fixed, and two more found while
  fixing it (`DECISIONS.md` #95–#98):

  1. **Merchandise.** A listing must now name a disc format in its title or URL. Zavvi's
     first twelve results for *Jaws* were towels, jumpers, T-shirts and a resin statue.
  2. **The film the shop does not stock.** Zavvi has no Michael Mann *Heat*, so it returns
     *Heat and Dust*, *The Big Heat*, *Red Heat* and *Step Up 4: Miami Heat* — each sharing
     a significant word, each passing the generous title rule, each a different film. A
     title carrying meaningful extra words, once format and edition wording is removed, is
     now refused.
  3. **Page-wide selectors.** Each selector ran over the whole page independently, so a
     card with no price node paired its title with the *next* product's price. Extraction
     now reads product cards, which also makes `preferred_format` work for the first time:
     101 Films lists *Bad Lieutenant* on 4K and Blu-ray, and the want says which.

  **Verified against the live shops, not only fixtures.** *Jaws* at Zavvi now returns the
  4K disc at £19.99; Arrow, 101 Films, Second Sight and Powerhouse all return the right
  film; *Heat* at Zavvi and *Don't Look Now* at Second Sight are both refused with a
  legible reason. **Two built-in search templates changed** (`{format}`) and every verified
  built-in gained an `item` selector — so **"Apply these selectors" must be pressed again**
  before the next run, or the live retailer rows keep the old config.

- **2026-09-09** — **Supported retailer paths.** Live page-shape checks settled which of
  §5.3's shops can actually be scraped: **five pass** — Zavvi, Arrow (on `arrowfilms.com`,
  its UK storefront; the seeded `arrowvideo.com` is the US site and returned USD, which the
  shape guard correctly rejected), plus three UK boutique labels added as supported
  replacements — 101 Films, Second Sight and Powerhouse/Indicator. **Four are permanently
  unverified and stay listed with the reason**: HMV and CEX disallow the search routes,
  Amazon blocks automated access, Blu-ray.com is a catalogue (`DECISIONS.md` #91, #92).

  **Three real defects were found and fixed on the way, none of which a green gate would
  have caught.** (1) `_same_site` compared the last two labels, so **every `.co.uk` host was
  one shop** — a listing link off `secondsightfilms.co.uk` to any other `.co.uk` site passed
  the guard. Latent since Batch 19 because no `.co.uk` retailer had working selectors; the
  two new UK labels are the first to arm it (#93). (2) Retailer pages return **relative**
  product links, which failed `_write_check`'s `http(s)://` test — so it returned without a
  row while `written` was incremented anyway, and the same-site guard was skipped entirely
  because a relative URL has no hostname (#94). (3) A **dry run** claimed to have saved
  prices, because `written` was incremented outside the `if not dry_run` guard.

  The Retailers page now carries the whole owner checkpoint as buttons — *Add missing
  defaults*, *Apply these selectors*, *Preview live run*, *Run and save prices* — and Wanted
  gained an *Add a film* panel, because step 4 of the checkpoint previously had no UI at all.
  **The checkpoint itself is still open**: no live `dryRun=false` run has happened, and
  `price_checks` is still empty.

- **2026-09-09** — **External calendar subscription deprioritised.** The in-app release
  calendar remains primary; its RFC 5545 feed remains available as optional convenience, but
  Apple/Google device verification is no longer a current owner action (Decision #90).

- **2026-09-09** — **eBay production developer application submitted.** The owner received
  eBay's confirmation that account review is pending and takes at least one business day.
  The owner-side application action is complete; Group I remains blocked until eBay approves
  production access.

- **2026-09-09** — **Batch 37 shipped — on-this-day + rewatch** (`50a4828`). Phase 11.6:
  caller-scoped anniversary memories and high-rated, not-recently-watched suggestions are
  parsed through shared schemas and rendered on the dashboard. The acceptance is proved by a
  date-controlled Postgres test: a watch logged exactly one year earlier appears today; CI
  ran it against Postgres 17. `watch_log` remains empty in production, so the dashboard says
  why it has no memories yet rather than rendering a misleading empty card. The optional
  daily push is still Batch 11's VAPID-key-gated work.

  The first full local gate failed only because `test_health.py` deliberately pins every
  public route and needed the two new endpoints named; fixed without weakening it. The final
  local gate: 301 passed, 250 skipped (no local database URL); CI's five jobs passed,
  including Postgres-backed pytest. No hosting, credential or destructive operation. API
  production health reports the merged SHA with `db: ok`. Dashboard browser automation could
  not run: `agent-browser` is unavailable in this environment.

- **2026-09-09** — **Batch 36 shipped — command palette + keyboard shortcuts** (`1425f91`).
  Phases 6.3/6.4. A Cmd/Ctrl+K modal indexing every page, the admin-only write action, and
  films — reusing Batch 5's `/search` endpoint rather than re-implementing it — plus
  recently-viewed films in localStorage. Ten shortcuts (`g`-chords, `/`, `n`, `?`, Esc) and
  a help modal, centralized in one `useKeyboardShortcuts` hook; `SearchBar`'s pre-existing
  `/` handler now defers to it via a `mcu:focus-search` event instead of the two owning
  the same key.

  **§7.5's `.` shortcut and the palette's "recent AI-assistant conversations" index were
  dropped, not built wrong** — both depend on Batch 31's chat, which does not exist yet.
  Same treatment Batches 8/9 gave dead onboarding steps.

  **Verified live in a browser**: Ctrl+K open, the empty-query page index, fuzzy-filtering
  "wanted" to one result, Enter navigating and closing the palette, Escape closing it, and
  a `g s` chord landing on `/stats` — against the dev server with `VITE_SKIP_AUTH`, since
  the local API wasn't running (no Docker/local Postgres — gotcha 15 again, this time for
  the API itself rather than a migration). **`?` and `/` were not independently
  browser-verified** — confirmed via a raw event listener that this environment's browser
  automation tool cannot synthesize a real `key: '?'`/`key: '/'` keydown (both arrive as
  `key: ''`) — nor was "typing 'blade' surfaces Blade Runner films", for lack of a running
  search backend. All three rest on the batch's 27 new unit/integration tests, which
  dispatch real `KeyboardEvent`s and mock the search endpoint directly.

  No backend, hosting or credential changes; no destructive operation. 547 API tests and
  107 web + 65 shared tests, zero skips. Production serves the merged SHA with `db: ok`.

- **2026-09-09** — **Batch 27 closed out (`888dae7`), after its security review ran.** Gift
  links: a 128-bit slug rather than §3.21's UUID PK or §6.26's 32-bit example; four failure
  modes answering identically; a public response model deliberately unrelated to the admin
  one so no ownership, id, slug or count can leak. **The review found no security findings at
  its confidence bar and four real defects** — a per-film N+1 on the unauthenticated
  endpoint, a service worker caching `no-store` gift responses in a family member's browser,
  `Decimal("NaN")` slipping past a `<= 0` guard in Batch 18's *already-merged* code, and a
  non-atomic view counter. All four fixed with tests before the merge (`DECISIONS.md`
  #83–#87). CI green on `main` (all five jobs); production serves the merged SHA with
  `db: ok`.

  Also corrected here: nine rows of `ARCHITECTURE.md`'s §17 table still read "Not yet built"
  for work this session shipped (rows 5, 9, 12, 16, 19, 27, 42, 43, 44). The close-out step
  that would have caught it — "tick the phase line in the roadmap doc" — has been a no-op
  since Batch 10 removed §16, so eight close-outs in a row skipped it without noticing.

- **2026-09-09** — **Batch 27 built but not merged.** The security review the owner asked
  for was launched and **failed before doing any work** (monthly spend limit), so the branch
  was deliberately held — and a first version of the ledger entry claimed it had been
  reviewed, which was corrected in `247ee25`.

- **2026-09-09** — **Batch 19 shipped — scraper framework** (`bf1b4d5`), **and Group F
  stopped at its checkpoint.** Both of 5.3's and 5.4's acceptance criteria need live
  requests to real shops, which `group-start.md` reserves for the owner — so the framework
  is built and fixture-tested (33 tests) and the runs are handed over. The batch is shaped by
  its own risk note: `check_shape` asserts five properties of every result and discards
  anything that fails, because a wrong selector fetches fine and returns a plausible wrong
  number (`DECISIONS.md` #79). Every built-in reported `verified: false` at the time (#80;
  see #91 for what the live checks later settled). The fetcher
  refuses non-public addresses at every redirect hop — the app's first person-supplied URL
  (#81). CI went red because dependencies are locked with `--require-hashes` and
  `pyproject.toml` alone is not enough.

- **2026-09-09** — **Batch 18 shipped — wanted list and retailers** (`f85aa91`). §3.5 and
  §3.16 built, **paying four debts** from Batches 13, 15, 16 and 17. Two of them surfaced as
  tests that had asserted an absence and now assert the presence — which is exactly why they
  were written that way (`DECISIONS.md` #78). A wanted entry can name a film the collection
  has never seen (#75); `is_active` and `deleted_at` stay distinct (#76); the six seeded
  retailers ship with **no selectors** and say so, because a guessed selector persists a
  plausible wrong price rather than erroring (#77).

- **2026-09-09** — **Batch 17 shipped — release calendar and iCal, closing Group E**
  (`a09c172`). Live ingestion put **32 rows** in `release_calendar`; the re-run was
  idempotent. The `.ics` feed is the app's **first unauthenticated surface**, and its token
  is handled as a refresh token — hashed, rotated, one live per person, revoked-answers-like-
  never-existed (`DECISIONS.md` #71–72). **A security review found a real content-injection
  hole**: a URI property is not escaped, so a newline in `release_calendar.url` injected
  iCalendar properties. Not reachable today; **Batch 19's scrapers would have armed it**
  (#73). The first live ingestion also hit a duplicate-page defect a dry run could not reach
  — gotcha 16 again. **Apple Calendar verification is an owner action.**

- **2026-09-09** — **Batch 16 shipped — watch providers and recommendations** (`d2218ab`).
  Live: *North by Northwest* shows HBO Max plus 6 rent and 6 buy options in GB; 20
  recommendations with 7 flagged as already owned. §7.1 assumed a `streaming_region` column
  that did not exist (#70). **A defect found only in the browser, and it was mine**: a 502
  for a TMDB outage made the page say "waiting for the network" — the endpoint now answers
  200 with an `unavailable` flag, because a status code cannot carry "we are fine, they are
  not" (#68). CI went red on gotcha 21's unpinned-mypy trap and was fixed by needing no
  ignore.

- **2026-09-09** — **Batch 15 shipped — trash, audit UI and lending, closing Group D**
  (`20d1eff`). The permanent delete is the app's first irreversible operation; it gets past
  `003`'s soft-delete trigger with a transaction-scoped `SET LOCAL`, **not**
  `DISABLE TRIGGER`, which is global and would make every delete permanent if a process died
  mid-request (`DECISIONS.md` #64). Proved on live data by destroying Batch 12's leftover box
  set: row gone, cascade fired, audit trail outlived it, 1,857 discs untouched. **"Overdue
  triggers a push" is not met** — push is Batch 11 — and no fake toggle was shipped.

- **2026-09-09** — **Batch 14 shipped — stats, activity feed and export** (`20650b3`).
  Stats at 344 ms median (criterion <1s). **Two of five charts have no data** — `watch_log`
  is empty and no disc carries a price — so they say what they are waiting for rather than
  drawing zeros (`DECISIONS.md` #61). CSV/JSON/HTML export all 1,857 discs; **no
  server-side PDF renderer**, because every option needs system libraries in an image
  Railway builds and CI does not (#62). Downloads go through `fetch` into a blob so the
  token stays out of the URL (#63). Also caught and corrected a false claim in my own
  comment: the collection has **zero** non-ASCII titles.

- **2026-09-09** — **Batch 13 shipped — completion sets, closing Group C** (`22680de`).
  40 sets built live from TMDB, zero errors. Hitchcock 12 of 61, where TMDB returns 129
  crew credits and 65 director ones — the filters that get from 65 to 61 are the batch
  (`DECISIONS.md` #58), because "12 of 91" and "12 of 65" are both plausible wrong numbers
  nothing would flag. Sets are seeded from the collection's own `movie_credits`, so there
  is no name-matching step to get wrong (#57). Ownership is never stored (#59). **"Bulk add
  missing to wanted list" was dropped** — the wanted list does not exist and Batch 18 owns
  it. **"Weekly" is not scheduled**: a Railway cron is a hosting change (#60).

- **2026-09-09** — **Batch 12 shipped — box sets + smart collections** (`881f444`). Three
  tables, seven endpoints, 38 tests. The saved-filter blob is closed off twice: validated
  through a model whose fields are `GET /movies`' own parameters, and *evaluated* by the
  same function that serves `GET /movies`, so a saved collection cannot silently drift from
  the filter bar (`DECISIONS.md` #55). `isComplete` is three-valued — an unrecorded box size
  means unmeasured, not incomplete (#56). `sub_category` deliberately untouched. Driven in a
  browser against live Neon: "Unwatched 4Ks from the 2010s" listed 40 real films. CI caught
  one test of mine that assumed the local catalogue was present.

- **2026-09-09** — **`fix/date-guards-read-the-server-timezone` shipped.** A pre-existing
  red on `main` that no change caused: `date.today()` reads the *server's* timezone, so the
  watch-log default (computed in UTC) and its own future-guard (compared in local time)
  disagreed for the hour after midnight BST. Green in CI all day, red at 00:07 locally.
  Fixed at the root rather than in the assertion — `purchaseDate` carried the same guard,
  and comparing a person's calendar date against any single timezone's "today" is wrong in
  both directions. New `apps/api/src/clock.py`; the ceiling is now the latest date that is
  today anywhere on Earth (`DECISIONS.md` #53). `04bfd44`.

- **2026-09-08** — **`fix/pytest-local-live-data-collisions` shipped — the 4 pytest
  failures Batch 10 flagged are fixed, not just flagged.** Not a scheduled ledger batch;
  closed out on its own branch per the guardrail against folding a pre-existing red into a
  batch. All four were testing the wrong thing rather than merely lacking test isolation:
  one asserted current runtime state (`pin_hash IS NULL`) for a claim that's actually about
  a migration's static seed data, and was destined to fail forever the instant a real PIN
  was set — which happened, correctly, before this fix existed. Rewritten to check
  migration `002`'s seed columns directly, with the migration now exposing
  `SEEDED_PROFILE_COLUMNS` and asserting its `sa.table()` declaration matches it, so a
  future edit adding `pin_hash` to the seed fails loudly rather than silently. The other
  three assumed an empty `movies`/`collection_items` table when filtering by `section` or
  `watched`, and collided with real production rows (38 in "Top Big Cabinet", 413 in
  "Digital", ~1,843 counting as unwatched) the moment they ran against live Neon rather
  than CI's disposable Postgres. Fixed by giving each fixture a shared, implausible `year`
  and filtering on it too — the same narrow-filter-combination convention an existing,
  passing test in the same file already used, not a new pattern invented for the fix.

  All 338 `apps/api`, 26 `packages/shared` and 57 `apps/web` tests now pass locally against
  live Neon — the first time that's been true since these four tests were written. No
  schema change; migration `002` gained a runtime assertion and a renamed constant only.
  Production serves the merged SHA `959b1ca85058daee7b5c2bde5283cbe99d227423` with
  `db: ok`.

- **2026-09-08** — **Batch 10 shipped — the architecture doc is split and its decisions
  table is reconciled.** `MCU_Architecture_v2.1_FINAL.md` (2,639 lines) is now
  `ARCHITECTURE.md` plus an 18-line stub at the old path pointing to it; `§16 Build Phases`,
  an 86-phase plan that named a model ("Sonnet 4.6") which no longer exists, is replaced by
  a pointer to `docs/phase-batches.md` as the roadmap of record. `§17 Resolved Decisions`
  now carries a status verdict on all 50 rows rather than only its original April
  resolution — split into shipped, superseded (with the `DECISIONS.md` # that did it), or
  not yet built. `session-log.md.txt` is retired; its content was entirely superseded by
  the re-scaffold and already reconstructed into `DECISIONS.md` #1–8.

  **This batch had no written acceptance criteria anywhere in the repo when the session
  started** — every other batch has a `### Batch N` section in `docs/phase-batches.md`
  with a `**Goal:**`/`**Acceptance:**`; Batch 10 had only its one-line ledger title. Wrote
  the criteria into the ledger first, from `REVIEW_PLAN_2026-09-07.md` Part C's own words,
  with the owner's agreement, before touching any doc.

  **Two rows of the reconciliation were corrected by reading the code rather than trusting
  the batch log.** The working draft called Sentry, structlog and correlation-ID binding
  "not confirmed built" because no `STATUS.md`/`DECISIONS.md` entry claims them. All three
  are actually wired — `sentry_sdk` in `apps/api/src/main.py`, `@sentry/react` in
  `apps/web/src/instrument.ts`, and `structlog.contextvars` bound to `correlation_id` in
  `apps/api/src/middleware.py` — found by grepping the source before finalising those two
  rows. Web Vitals is genuinely absent, and stayed marked as such.

  **Four `apps/api` pytest tests fail locally against live Neon data** — real production
  rows they weren't written to tolerate (a real PIN where one asserts `None`, 1,857 real
  movies swamping a section-filter assertion). Confirmed unrelated to this batch: zero diff
  in `apps/`/`packages/` against `main`, and this batch's own CI run — against CI's
  disposable Postgres, not live Neon — was green. Left unfixed per the guardrail against
  folding a pre-existing red into a batch; flagged in "Next" as worth its own `fix/` batch.

  Production serves the merged SHA `d94a6b828d5e96879b5794d4d11bb308ac01803c` with
  `db: ok`. No migration, no hosting or credential change, nothing destructive.

- **2026-09-08** — **Batch 9 shipped, and Group B is complete.** Batches 7, 8 and 9 all
  landed today, which finishes the "build to first deployment" half of the ledger: the
  collection can be written to, it works with the network off, and a first-time user is
  shown a setup flow whose every step does something.

  **The wizard is rebuilt, not repaired.** Batch 3 had removed it because its completion
  flag was a Supabase column that no longer exists (`DECISIONS.md` #27), so there was
  nothing to repair — migration `010` gives it a real one and `ProtectedRoute` gates on it
  again, closing a TODO it has carried since Batch 3.

  **Half the batch definition's premise was wrong.** It says `StepInstallPWA` and
  `StepNotifications` "now have real infrastructure behind them". The install step does —
  Batch 8's manifest and service worker let `beforeinstallprompt` fire, and the new
  `usePwaInstall` catches it, preventing the default because Chromium gives no second
  chance. **The notifications step does not**: no VAPID key, no subscription, no endpoint,
  no `push_subscription` column, and six toggles for features that do not exist yet.
  Dropped rather than ported (`DECISIONS.md` #50); Batch 11 owns bringing it back with
  infrastructure first.

  **A fourth dead step that gotcha 5 never listed** — the catalogue step read
  `d?.meta?.total`, the envelope `DECISIONS.md` #6 deleted, so it rendered a loading
  skeleton for ever. A dead read can hide behind a plausible loading state indefinitely,
  which is why "no step reads a property nothing sets" was worth checking by grep rather
  than by looking.

  Verified by walking the production bundle in a browser: six steps for an admin, resuming
  at step 3 after a reload, and "Skip setup" landing on a usable `/movies`. 249 API tests
  and 83 web/shared tests, zero skips.

- **2026-09-08** — **Batch 8 shipped — the app works with the network off.** Service
  worker, manifest and icon set, an offline banner, and a durable IndexedDB write queue
  with the two states that make it safe: a write the browser never sent is re-sent
  automatically, and one that left without an answer is *read back*, never re-sent.
  Ported from `the-coupon`'s `usePickEditor` — its reasoning transfers even though its
  storage does not, and `DECISIONS.md` #44 records why this one persists where that one
  deliberately does not.

  **Two spec facts did not survive checking.** Phase 13.9 specifies last-write-wins, which
  is the exact opposite of this batch's own acceptance criterion — a queued edit flushed
  on reconnect *is* written last. Replaced by an optimistic-concurrency check (#42).
  Phase 6.5's acceptance names the wanted list, which is Batch 18 and does not exist.

  **Four defects, none visible to any green check, all found by driving the built app
  against an API that could be switched off.** React Query *pauses* mutations when it
  believes the app is offline, so `mutationFn` never ran and the queue inside it was
  unreachable — the offline write path was dead on arrival, behind a spinner that could
  not stop. The same pause stops a query issuing the fetch a service worker exists to
  answer, which is gotcha 19's empty-state lie seen from the other end. A 5xx on a write
  was treated as a refusal and the write discarded. A 5xx on the profile load signed the
  person out and destroyed the session the queued writes were made under. And
  `updated_at` used `NOW()` — transaction time — so the new concurrency token never
  advanced and the guard passed anything, which this batch's own CI tests caught failing
  *open*.

  **Criterion 3 is proved end to end in a browser**: the edit queued while offline, and on
  reconnect the server received exactly the queued body with its `baseUpdatedAt` attached.
  Criteria 1 and 2 need a phone — see gotcha 25.

  337 API tests and 77 web/shared tests in CI, zero skips. 1,857 items untouched.

- **2026-09-08** — **Batch 7 shipped — the collection stops being read-only.** Add, edit,
  soft-delete and restore, with duplicate detection and condition tracking, and an
  `admin_actions` row written in the same transaction as every change. Migration `008`
  creates the audit table, which **did not exist on the new spine** — gotcha 4's
  speculative-table warning running the other way.

  **The batch's headline criterion is proved by destroying a row.** "The audit log
  survives deletion of the target" cannot be shown by a soft delete, and
  `collection_items_soft_delete` rewrites every `DELETE` into one — so the test disables
  the trigger, genuinely deletes the item, and shows the entry still readable through
  `GET /admin/audit`. `target_id` is TEXT with no foreign key (`DECISIONS.md` #5, #38),
  which is where §3.20's schema table is wrong and the decision is right.

  **Three scope calls, all recorded** (`DECISIONS.md` #37–39): writes are admin-only, as
  §3.1's own acceptance criterion requires; optimistic UI is Batch 8's phase 6.5, not
  this batch's, because building rollback here would mean building what Batch 8 explicitly
  rejects; and the trash ships without permanent delete, leaving the one irreversible
  action with §13.5.

  **`UtcDatetime` was written for real** (#40). `AGENTS.md` has specified it since the
  re-scaffold and nothing implemented it — #14's warning found inside our own conventions
  file. It went unnoticed because Batch 7 is the **first batch to put an instant on the
  wire**: Batch 6's `watchedAt` is a `DATE`, which has no offset to get wrong.

  **Two defects that a green gate could not have caught, and how each surfaced.** A
  `field_validator` that never ran for an absent field turned a malformed body into a 500
  — caught in CI by this batch's own test, which is what those tests are for. And every
  list page claiming to be *empty* when its request had merely been paused — caught only
  by opening the pages in a browser, with the build, the types and 34 web tests all green
  (gotcha 19). The second is fixed app-wide and matters most for Batch 8.

  Also fixed on the way: two test clients sharing one actor, because
  `app.dependency_overrides` is global to the app and the admin and viewer fixtures
  overwrote each other — which would have made §3.1's "viewer immediately sees it" look
  tested without being tested.

  331 tests in CI, zero skips. 1,857 collection items untouched.

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
