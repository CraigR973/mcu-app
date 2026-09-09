# STATUS — MCU App

## Now

**Nine batches shipped, all merged and deployed.**

Production serves `888dae7a5cbcf268fb0914240e7e18594e836144` (Batch 27) with `db: ok`.

| Batch | Result |
|---|---|
| — | `fix/date-guards-read-the-server-timezone` — a pre-existing red on `main`, fixed first (`04bfd44`) |
| 12 | Box sets + smart collections (`881f444`) |
| 13 | Completion sets (`22680de`) — 40 sets from live TMDB |
| 14 | Stats + export (`20650b3`) — 344 ms median, all 1,857 discs exportable |
| 15 | Trash, audit UI, lending (`20d1eff`) — the app's first irreversible operation |
| 16 | Watch providers + recommendations (`d2218ab`) |
| 17 | Release calendar + iCal (`a09c172`) — first unauthenticated surface |
| 18 | Wanted list + retailers (`f85aa91`) — paid four earlier batches' debts |
| 19 | Scraper framework (`bf1b4d5`) — **acceptance deferred to the owner** |
| 27 | Gift links (`888dae7`) — **security review ran; four defects found and fixed** |

### What Batch 27's security review actually found

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

### ⛔ One thing is waiting for you

**Group F is stopped at its checkpoint: live scraper acceptance runs.** Batch 20 depends on
phase 5.3's acceptance, and that acceptance is a live run against real shops — which
`group-start.md` reserves for you. The steps are in "Next" below.

### What tonight's batches left in the live database

Counted against Neon at close-out: 40 `completion_sets`, 32 `release_calendar` and 6
`retailers` rows — all three are acceptance criteria, so they stay. **The six retailers now
carry the built-in selectors** (5 of 6 have them; Criterion has no built-in config and CEX is
not among the seeded six), so step 1 of the checkpoint below is already done — every one is
still marked **unverified**. `price_checks`, `wanted_list`, `gift_links`, `loans`,
`box_sets`, `smart_collections` and `watch_log` are all **empty**: every verification row was
cleaned up, Batch 27's included.

**No `collection_items` row has been created, modified or deleted all session — still 1,857,
all live.**

### Two defects found only by driving the app, both mine

- **Batch 16** returned a 502 when TMDB was unreachable, and `send()` correctly classifies
  any 5xx as a *network* failure — so the page told the reader to check their connection
  while the connection was fine. Now a 200 with an `unavailable` flag (`DECISIONS.md` #68).
- **Batch 17**'s iCal serialiser let a newline in a URL inject arbitrary calendar
  properties. Not reachable today; **Batch 19's scrapers would have armed it** (#73).

**One unexplained flake, recorded rather than ignored:**
`test_the_rate_limit_counter_survives_a_process_restart` failed once in a full-suite run and
passed on the three runs after it. It has not recurred. If it reappears, it is an auth test
and worth taking seriously.

## Next

**⛔ Group F is stopped at its checkpoint: live scraper acceptance runs.** Batch 20 (price
scraping + drop alerts) depends on 5.3's acceptance, and 5.3's acceptance is a live run
against real shops. That is yours to perform.

### What the checkpoint actually needs

The framework is deployed and the endpoints are admin-only. For each of the six shops:

1. **Apply the built-in selectors** — *Retailers → "Apply these selectors to the matching
   retailers"*, or `POST /api/v1/scrapers/apply-built-ins`.
2. **Test one at a time before enabling** — the *Test* button on each retailer row, or
   `POST /api/v1/scrapers/test`. A green tick means "this looks like a real price for this
   film", not "the page loaded". **Expect several to fail**: every selector is a guess.
3. **Fix the selectors that fail.** The tool prints the node it read and why the result was
   rejected, which is usually enough to correct the CSS in *Retailers → edit*.
4. **Put at least one real film on the wanted list**, or the run has nothing to look for.
5. **Run it for real** — `POST /api/v1/scrapers/run?dryRun=false`. 5.3's acceptance is
   ≥ 1 `price_checks` row per scraper and a total above zero.

**Amazon may not be viable at all** — it varies its markup per client and blocks scrapers;
its built-in entry says so. Blu-ray.com is a database rather than a shop, so its prices are
third-party and may be absent. Neither is a defect in the framework.

**Then Batch 20** (5.5, 5.6, 5.8 — daily job and price-drop alerts) can start. Note it will
also want **Batch 11's push**, which is still blocked on its own VAPID credential checkpoint.

### Unblocked work that does not need this checkpoint

**Group J** (30 → 31, AI assistant) is next in the queue — but note that 30 *may need a live
Claude API key in Railway*, which is a credential change and therefore a stop, not something
to work around. Then the solo batches **32** (voice input), **36** (command palette) and
**38** (E2E suite), none of which need a checkpoint.

### Four things the next agent should know

1. **Every planned batch's acceptance criteria are missing from the working tree.** Batch 10
   removed §16. Recover them verbatim from
   `git show d94a6b8~1:MCU_Architecture_v2.1_FINAL.md`, grep for `**Phase X.Y:`, and write
   them into the batch's ledger section **before** writing code (`DECISIONS.md` #54).
2. **Adding a Python dependency means regenerating both locks.** CI installs with
   `pip install --require-hashes -r requirements-dev.lock`; `pyproject.toml` alone is not
   enough. The command is in each lock file's own header.
3. **Batch 11 is still unstarted and still blocked** on generating VAPID keys and setting
   them in Railway — a credential change. It also owes the notifications that Batches 15 and
   19 both deferred to it.
4. **Mark's PIN is still `NULL`**, so he cannot sign in at all:

```
DATABASE_URL='<neon url from apps/api/.env.local>' PYTHONPATH=apps/api \
  apps/api/.venv/bin/python3.12 -m src.scripts.set_pin Mark
```

Two owner actions remain outstanding, unchanged:
1. **Revoke the April PAT at GitHub.** Classic PAT, 40 chars, `ghp_3gLc…`, committed in
   full in `0bfb672` (2026-04-25) and referenced truncated in `4768da8`. Dead (401) but
   never revoked. History rewrite is **not** recommended — the repo is private and the token
   is already invalid.
2. **`VITE_API_URL` is set for Production only.** Add it in the Vercel dashboard if preview
   deploys are wanted.

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

## Log

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
  number (`DECISIONS.md` #79). All six built-ins report `verified: false` (#80). The fetcher
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
