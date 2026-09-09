# DECISIONS — MCU App

Append-only. Each entry: the decision + *why*. Don't re-litigate a settled decision —
if you change course, add a new entry that supersedes the old one.
(See `AGENTS.md` for conventions, `STATUS.md` for current state.)

Entries 1–8 were reconstructed on 2026-09-07 from `session-log.md.txt`, the migrations
and git history, and are dated to when the choice was actually made. Entries 9+ are
contemporaneous.

---

### 2026-04-20 — Stack and shape

1. **Monorepo: `apps/api` + `apps/web` + `packages/shared`, FastAPI + React 18 + Vite +
   Tailwind + shadcn/ui on Supabase Postgres.** *Why:* matches the shape used across
   Craig's other apps, so tooling, CI and deploy knowledge transfer between them.

### 2026-04-22 — Auth

2. **Supabase Auth with a `profiles.role` column for admin/viewer.** *Why:* Supabase was
   already the database, so its auth came free rather than needing a login to be built.
   *Superseded by #11.*

### 2026-04-25 — Schema

3. **Alembic lives under `apps/api/migrations`, not at the repo root.** *Why:* it kept
   the Python tooling together. *Consequence, discovered 2026-09-07:* it diverges from
   every sibling project, and `migrations/001_profiles.sql` at the repo root sits outside
   the chain, so no single command builds the schema from scratch and
   `alembic downgrade base` does not fully reverse. Revisit on the re-scaffold.

4. **The whole roadmap's schema was created up front — 25 tables across 17 migrations,
   covering stages 4–11.** *Why:* Phases 1.2/1.3 were written as "create the remaining
   tables" so later stages wouldn't need migrations. *Consequence:* ~22 tables exist for
   features that were never built and may never be. Part D decides which survive.

5. **`admin_actions.target_id` is TEXT, not a foreign key.** *Why:* an audit log has to
   survive deletion of the row it describes. A FK would either block the delete or
   cascade the evidence away.

6. **`notification_preferences.user_id` is both primary key and foreign key.** *Why:*
   exactly one row per user; a surrogate key would allow a second row that means nothing.

### 2026-04-26 — Derived fields

7. **Derived movie fields are recalculated by Postgres triggers, not in Python**
   (`0015_derived_field_triggers.py`). *Why:* the values must stay correct regardless of
   which code path writes, including the bulk import and any future direct SQL.
   *Mechanism worth remembering:* `collection_items_recalc_movie()` fires AFTER
   INSERT/UPDATE/DELETE and handles UPDATE's `movie_id` change by recalculating both NEW
   and OLD. Soft deletes ride the UPDATE branch, because the existing BEFORE DELETE
   trigger converts DELETE into an UPDATE of `deleted_at`.

### 2026-04-29 — Frontend

8. **View mode and column selection persist to `localStorage`**
   (`mcu:view-mode`, `mcu:list-columns`) rather than to the user's profile. *Why:* it is
   a per-device display preference, not user data — a phone and a desktop should be able
   to disagree.

---

### 2026-09-07 — Batch: cross-project review

9. **Deployment is a goal, and the roadmap is re-sequenced around reaching it.** *Why:*
   the app has never been deployed and has no deploy configuration at all. Everything
   built so far exists only on Craig's machine, which means none of it has been tested by
   the one person it is for.

10. **The app is re-scaffolded onto `app-starter`, in this repo, on a branch, bottom-up
    — not retrofitted in place, and not rebuilt as a fresh clone.** *Why:* the deciding
    factor is deployment, not code quality. The deploy spine interlocks — Dockerfile →
    `alembic upgrade head` on boot → healthcheck exposing the commit SHA → fail-closed
    config → CI proving the migration chain reverses — and cannot be added a piece at a
    time. Excluding migrations and tests the app is ~1,657 lines of API source and 3,319
    of web, and 839 of those API lines (the TMDB client, matching engine and spreadsheet
    parser) are framework-independent and port untouched. Sync→async rewrites every
    router regardless, and the auth change is forced regardless, so both may as well land
    in a shell that already works. Order: config/database/models → deploy spine + CI →
    auth → routers → web shell → feature pages, each step independently green.
    *Reversal condition:* if the live Supabase data were irreplaceable this would be
    wrong. It isn't — the parser and matching engine **are** the import pipeline.

11. **Auth becomes display name + PIN + JWT with no public sign-up, taking
    `the-coupon`'s implementation.** Supersedes #2. *Why:* per-request calls to
    `supabase.auth.get_user()` couple every endpoint's latency and availability to
    Supabase's auth service, and admin routes pay two round-trips. Specifically
    the-coupon's, **not** `app-starter`'s: app-starter defines `MAX_FAILED_ATTEMPTS` and
    `LOCKOUT_DURATION` and never enforces them, while its `rate_limit.py` justifies
    in-process counters by citing that non-existent durable guard. the-coupon enforces
    lockout with durable Postgres counters and a separate limiter session, so a failed
    attempt is charged even though the handler's transaction rolls back.
    *Considered and not taken:* `garmin-coach`'s passwordless device tokens, which are
    the newer pattern for a 1–2 user private app. Owner chose PIN.

12. **camelCase JSON and shared-zod response validation; no `{data, meta, errors}`
    envelope.** *Why:* the three are usually bundled but have different price tags.
    camelCase is free — name the Pydantic fields camelCase, as `garmin-coach` does; no
    repo uses an alias generator — and it stops the frontend hand-mapping every field.
    Shared-zod validation is the half that earns its keep, catching wire drift where
    deploy skew actually bites, since the web app deploys ahead of the API on every push.
    The envelope is skipped: 3 of 4 sibling repos don't have one, and this app's genuine
    partial-success cases (bulk import, matching, a future price feed) are batch
    operations that deserve their own shapes rather than taxing every read route.
    *Revisit if* Part D keeps the LLM assistant with tool definitions calling the API — a
    second consumer is when `meta`/`errors` starts paying for itself.

13. **Close-out stays explicit on this project**, following the global default rather
    than overriding it as `the-coupon` and `garmin-coach` do. *Why:* automatic close-out
    is bought by a gate worth trusting, and this repo does not have one — no deploy
    pipeline, no migration check in CI, and the DB-backed tests never run there. Revisit
    once the re-scaffold has landed a real gate.

14. **The house standard is graded by what sibling code does, not what its docs claim.**
    *Why:* `AGENTS.md` in three of the four sibling repos states conventions with no
    implementation behind them — the `{data, meta, errors}` envelope, camelCase JSON,
    `*_utc` columns and shared-schema validation are all asserted in `app-starter` and
    absent from it. A standard transcribed from the prose would have contained four rules
    the reference implementation itself does not follow. See `docs/house-standard.md`.

15. **`app-starter` is the re-scaffold base but not the standard.** *Why:* it was
    distilled from earlier apps and has been overtaken by `garmin-coach`. Its own
    `SKELETON.md` says so: "the original app is the living reference." Corrections applied
    on the way in: the-coupon's durable lockout, its one-command `ci-local.sh` gate and
    `UtcDatetime` wire mechanism, garmin-coach's shared-zod pattern; and its leaked
    identity (`@coach/web`, `coach_test`, `daily-loop` query keys) and dangling references
    (`docs/runbooks/`, a configured-but-absent `e2e/`) stripped.

### 2026-09-07 — Owner override of Part D's drops

16. **Only Phase 9.6 (Voice Output / TTS) is dropped. Every other phase Part D dropped or
    deferred is reinstated.** Supersedes the drop and defer verdicts in
    `docs/part-d-roadmap.md` for: 3.4 · 4.1 · 4.3 · 5.3 · 5.4 · 5.7 · 6.3 · 6.4 · 8.3 ·
    8.4 · 9.5 · 10.1 · 10.2 · 10.3 · 10.4 · 10.5 · 10.6 · 10.7 · 10.8 · 11.2 · 11.6.
    *Why:* owner decision, 2026-09-07. Part D's reasoning was value- and risk-based, and
    the owner weighs the value differently. The analysis stands as recorded; the verdicts
    do not.

    **What does not change, because it is external rather than a judgement call:**

    - **4.1 — eBay sold-listing comps cannot be obtained.** The Marketplace Insights API
      is limited-release and closed to new applicants. Reinstating the phase does not
      create access. It will be built against the **Browse API's active listings**
      instead, and the UI must label the figure as "current asking prices", not "recent
      sold prices" — the two differ materially and conflating them would mislead a
      pricing decision.
    - **3.4 — no public UPC→film dataset exists.** The phase is reinstated and will be
      built as specified (cached mapping → eBay Browse keyword search → manual fallback),
      but expect a low hit rate on first scan of an unknown disc, and wrong-edition
      matches where it does hit. Confirmation UI is mandatory, not optional.
    - **10.2 — correction to Part D.** Gmail restricted scopes are workable indefinitely
      for two named test users on an unverified consent screen; CASA is only triggered by
      going beyond the test-user allowlist. Part D overstated this as a blocker. The real
      cost is faster refresh-token expiry and periodic re-consent, not a paid assessment.

    **Risks accepted by this decision**, recorded so they are not re-litigated later:
    scraper maintenance and ToS exposure (5.3/5.4/5.5); storage of two people's live
    mailbox credentials on an app whose perimeter is only hardened in Batch 3 (10.1);
    and per-scan LLM spend (10.6).

### 2026-09-07 — Batch 2 deployment spine

17. **MCU uses a dedicated Neon project for Postgres and does not use Neon Auth.**
    Supersedes the Supabase database part of #1; the rest of the stack is unchanged.
    *Why:* the old Supabase project is shared with Garmin Coach and is already
    457,026,707 bytes — 91.4% of its 500,000,000-byte free database limit — with Garmin
    timeseries accounting for most of the space. Neon gives MCU its own free Postgres
    capacity without displacing Garmin. Batch 3's display-name + PIN + JWT design remains
    the settled auth model, so Neon Auth would duplicate it. Storage and Realtime remain
    separate future integration decisions; choosing Neon for Postgres does not silently
    choose their replacements.

18. **Railway infrastructure is defined with `.railway/railway.ts`, not
    `railway.toml`.** *Why:* Railway deprecated Config as Code, prevents new services from
    opting into it, and stops reading legacy files on 2026-12-01. The replacement IaC
    format manages the project/service graph and supports a read-only plan before apply.

19. **Schema migrations land with the batch that owns the schema.** Batch 2's `001` is
    an intentionally empty, reversible re-scaffold marker; Batch 3 adds authentication,
    Batch 4 adds movies/credits/collection items and their triggers, and later features
    add their own tables. *Why:* recreating the old app's speculative 25-table schema in a
    baseline would repeat Decision #4's failure and contradict the bottom-up sequence in
    #10. The 13 legacy derived-trigger tests remain present and automatically resume once
    Batch 4's tables exist.

### 2026-09-07 — Batch 2 close-out

20. **The Railway service domain targets the port Railway injects (`8080`), not the
    Dockerfile's `EXPOSE 8000`.** *Why:* Railway sets `PORT` in the container and the
    Dockerfile honours it (`--port ${PORT:-8000}`), so uvicorn binds 8080 in production and
    the `EXPOSE`d 8000 is only the local fallback. Creating the domain with
    `railway domain --port 8000` produced a public **502 "Application failed to respond"
    while the container was entirely healthy** — the internal healthcheck on
    `/api/v1/health/ready` returned 200 throughout. The symptom points at the app and the
    cause is the edge routing, which is why it is written down. Verify a new domain with
    `railway domain list` and confirm the port matches the `Uvicorn running on` line in
    `railway logs -d`.

21. **Vercel deploys from the connected GitHub repository, not from `vercel deploy`
    uploads.** *Why:* a CLI deploy uploads the working tree, which on this repo routinely
    holds untracked working files — the source spreadsheet and the `import_review` /
    `matching_eval` CSVs. Git-connected deploys build exactly what is on `main`, match how
    Railway is wired (`github()` in `.railway/railway.ts`), and give both hosts one trigger.

22. **The production web app is deployed with `VITE_API_URL` only and does not boot until
    Batch 3.** *Why:* `main.tsx` mounts `AuthProvider`, which imports `lib/supabase.ts`,
    which throws at module load without `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`.
    Supplying the legacy Supabase keys would bind a brand-new production deployment to the
    project #17 moved off and Batch 3 deletes, so the deliberate outcome is a served bundle
    that white-screens. Batch 2's acceptance is the API serving its commit SHA; the web
    half is proving the build/host pipeline only. **Batch 3 must set the auth env vars as
    part of its own close-out** — a green Vercel build is not evidence the app runs.

23. **The production front end is `https://mcu-app-fawn.vercel.app`, and that exact origin
    is what `FRONTEND_ORIGIN` must hold.** *Why:* `mcu-app.vercel.app` was already taken by
    an unrelated app ("Marvel Cinematic Unisearch"), so Vercel assigned a suffixed domain.
    Setting `FRONTEND_ORIGIN` to the guessed bare name put a third party's origin on the
    API's CORS allowlist and left our own front end off it — the failure is silent until a
    browser makes a cross-origin call, which nothing did yet because no routes exist beyond
    health. Verify with `vercel inspect <deployment>` and a preflight against the live API,
    not by assuming the project name is the domain. Any future custom domain replaces this
    value; `vercel.json`'s CSP `connect-src` already covers the API via `*.up.railway.app`.

### 2026-09-07 — Close-out becomes automatic

24. **Close-out on this project is now automatic after a green gate. Supersedes #13.**
    Owner decision, 2026-09-07, taken once Batch 2 delivered the three things #13 named as
    missing: a deploy pipeline, a migration check in CI, and DB-backed tests that actually
    run there. MCU now behaves like `the-coupon` and `garmin-coach`.

    **Automatic close-out fires only when all of these hold.** Any one of them failing
    stops the close-out and is reported instead:
    - every `batch-verify.md` command green locally, from a clean tree;
    - every acceptance criterion for the batch demonstrably met, criterion by criterion;
    - the working tree holds nothing beyond this batch;
    - `main` was green before the batch began — a pre-existing red is still fixed on its
      own `fix/` branch first, never folded in;
    - after the merge, production `/api/v1/health` reports the **merged commit SHA** and
      `/api/v1/health/ready` reports `db: ok`.

    **This means a batch now deploys to production without a second confirmation**, because
    pushing `main` is what deploys. That is the intended consequence, matching the other two
    projects.

    **These stay explicit and are never auto-run:**
    - **hosting or credential changes** — Railway variables and domains, Vercel env and
      domains, Neon, or anything that would appear in `.railway/railway.ts`;
    - **destructive data or history operations** — history rewrite, force push, dropping or
      rewriting columns and tables that hold real rows, or re-running the collection import
      over live data;
    - **a red `main`**, per above.

    *Why the exceptions:* the gate proves the code, not the infrastructure around it. It
    cannot catch a wrong `FRONTEND_ORIGIN`, a domain on the wrong port, or an import that
    overwrites 1,866 rows — all three of which are real events from this repo's history,
    the first two from Batch 2's own close-out.

    **Known limits of the gate, carried deliberately.** It does not build the Docker image
    (Railway does) and it does not run the web bundle it builds — the deployed app can
    white-screen on a green gate, which it does today. The post-merge SHA and readiness
    check is what stands between those blind spots and a silent bad deploy.

### 2026-09-07 — Batch 3 auth

25. **The first PIN is set by a command-line script, not an HTTP route.**
    `src/scripts/set_pin.py`, run against the target database with the PIN read from a
    hidden prompt. *Why:* migration `002` seeds both profiles with `pin_hash = NULL` so
    that no PIN is ever written into a migration, a seed file, or git history — but that
    deadlocks the bootstrap, because `POST /api/v1/auth/pin` needs an access token, a
    token needs a login, and a login needs a PIN. A route that set a first PIN without
    authentication would be a sign-up route wearing a different name, which
    `DECISIONS.md` #11 forbids. Requiring database access to issue someone's first
    credential is the correct bar. The PIN is never a command-line argument, so it does
    not reach `ps`, shell history, or a CI log.

26. **`VITE_SKIP_AUTH` is honoured only in a development build.** *Why:* it was read in
    any build, so a stray environment variable on a deployment would have exposed the
    whole collection to anyone with the URL. It is now behind `import.meta.env.DEV`,
    which the bundler compiles to `false` and eliminates — the branch is absent from a
    production bundle rather than merely unreached. It mattered little while no routes
    existed; it matters now that there is something to protect.

27. **The onboarding wizard and the sign-up page are removed, not ported.** *Why:*
    sign-up is forbidden outright by #11 and by Batch 3's acceptance. Onboarding
    persisted completion to a Supabase `profiles` column that no longer exists, and three
    of its nine steps already pointed at nothing (`STATUS.md` gotcha 5). Carrying it
    forward would have meant a wizard that appears to work and saves nothing. **Batch 9
    owns reinstating it** against the new schema, and must add its own completion column.

28. **A PIN is 4–8 digits; the weak-PIN blocklist covers four-digit values only.**
    *Why:* the published distribution of leaked four-digit PINs is extremely
    concentrated — roughly a quarter of choices fall in about twenty values — so a short
    blocklist there buys a great deal. Beyond four digits the distribution flattens and a
    blocklist would refuse without buying anything. The list is kept deliberately short
    for the same reason it exists: a long one starts refusing PINs people chose for real
    reasons and pushes them toward writing it down.

### 2026-09-07 — Batch 4 domain layer

28. **The §3.4 schema is built as designed, and the 13 derived-field trigger tests are
    re-authored rather than resumed.** Owner decision, 2026-09-07, taken before any code
    was written, because the two halves of Batch 4's own definition contradicted each
    other and neither could be quietly dropped.

    Batch 4 said both "new models per roadmap §3.4" and "port `0015`'s trigger blocks" with
    "the 13 trigger tests **run**, not skip". Those are mutually exclusive. The April schema
    had drifted from §3.2–3.4 in four ways the tests hard-code: `movies.id` was the TMDB
    integer id rather than a UUID with a separate `tmdb_id`; `collection_items.format` was a
    scalar where §3.4 specifies a `formats` array; `hdr_format` and `audio_formats[]` were
    scalars where §3.4 specifies `video_specs`/`audio_specs` JSONB; and the format
    vocabulary was `4k_bluray|bluray|hddvd|…` where §3.2 and the spreadsheet parser both use
    `4k_uhd|blu_ray|dvd|download`, with the importer translating between them.

    *Why §3.4 wins:* the alternative recreates a schema the review had already found
    defective — it is the schema that omitted `location`, `section` and `shelf` — and Batches
    5, 6 and 7 would then build their DTOs, facets and write surface on top of it. That is
    Decision #4's failure repeated in a new place.

    *Why this needed a decision rather than a judgement call:* `AGENTS.md` forbids changing
    a test's expectations as a route to green, and says explicitly that doing so is "a
    decision to report, not to take". All 13 original behaviours are preserved one-for-one
    against the new shape; a 14th was added for a combo pack whose single row holds several
    formats, which the old scalar column could not express. The 14 run in CI against
    Postgres 17 with zero skips (run `34162647232`).

29. **The collection is 1,857 items. 1,866 was wrong everywhere it appeared.**
    Owner decision to correct it, 2026-09-07. The spreadsheet has 1,867 rows = 1 header +
    1,866 data rows, but nine of those data rows are entirely blank — every one of nine
    columns `None`, at sheet-rows 1857–1863, 1865 and 1866. The parser correctly skips them
    and returns 1,857 candidates.

    *Why it matters beyond tidiness:* Phase 1.5's acceptance criterion reads "parser produces
    1,866 structured entries **with no data loss**", which made it unsatisfiable by a correct
    parser and satisfiable only by a broken one. Batch 4's "row count = 1,866" had the same
    problem. Corrected in `MCU_Architecture_v2.1_FINAL.md` and `docs/phase-batches.md`.
    `docs/part-b-audit.md` and `docs/part-d-roadmap.md` still say 1,866 and are deliberately
    left alone — they are dated analysis records, and #16 already establishes that the
    analysis stands as recorded.

30. **Every owned item is catalogued, whether or not TMDB identifies it.** Changed from the
    April importer's behaviour. A row TMDB cannot match now gets a title-only `movies` row
    with `tmdb_id = NULL`, plus its `collection_items` row; the review CSV becomes a queue of
    rows needing enrichment rather than a list of rows that were dropped.
    *Why:* April inserted nothing at all for its 137 unmatched rows, so a disc genuinely on
    the shelf was absent from the catalogue of that shelf, with only an untracked CSV to say
    so. A collection app's first duty is to know what is in the collection; TMDB metadata is
    an enrichment, not a precondition for existing. This is also what makes a row-count
    acceptance criterion meaningful — under the old behaviour it could never reach the
    number of items owned. `movies.tmdb_id` is nullable and uniquely indexed to support it,
    and Postgres treats each NULL as distinct so many such rows coexist.

31. **An ambiguous match is catalogued but not enriched.** Owner decision, 2026-09-07,
    choosing this over importing everything on the matcher's current guess. It is also an
    explicit override of Batch 4's own instruction to port `matching/` **unchanged** — the
    ranking is changed, which is Phase 1.6's territory.

    *What was wrong.* `engine.py` scored a result's `original_title` as well as its `title`
    and took the max, then broke confidence ties by TMDB popularity. Measured across all
    1,857 titles on 2026-09-07: **687 matched rows (39.9%) had two or more candidates tied
    at the top confidence, and 652 of those had no year in the source title** — so for 35%
    of the collection the film was chosen by TMDB's current popularity ranking, which is
    not stable over time and now favours 2025/2026 releases. `Frankenstein` resolved to
    2025 rather than the 1931 Karloff, `Lolita` to 1997 rather than Kubrick's 1962, and
    `Amistad` to `Friendship` (2023), whose original title is "Amistad".

    *The two changes.* `title_is_exact` promotes a candidate whose **displayed** title
    canonically equals the query above one that only matched on `original_title`; it is a
    tiebreak and never moves a confidence. Then `is_ambiguous` marks a match whose leader is
    tied with candidates that are not plausibly the same film — different titles, or the
    same title more than `AMBIGUOUS_YEAR_SPREAD` (3) years apart. A re-release a year later
    is deliberately *not* ambiguous; flagging that would send half the catalogue to review.

    *Why not simply pick better.* Only 10 of the 1,857 rows are fixable by code with
    confidence — the class where the winner is not an exact title match but a tied candidate
    is. The rest are undecidable from the source: the spreadsheet gives a bare title and no
    year, so nothing in the data says which *Frankenstein* is on the shelf. A heuristic —
    prefer the oldest, prefer the most-voted — would replace one guess with another and
    would still be wrong silently.

    *Why the disc is still catalogued.* Deferring the *identification* must not defer the
    *item*. An ambiguous row gets its title-only `movies` row and its `collection_items` row
    with location intact, so the collection is complete and the review queue is about
    metadata, not about missing discs. This is #30 applied to a second case.

    *Cost, accepted:* a review pass over the ambiguous rows before their posters, cast and
    search vectors are correct. The review CSV carries an `alternatives` column listing
    every tied candidate so a row can be settled from the file itself.

32. **Import idempotency is keyed on the spreadsheet line, not on the item's contents,
    and `movie_credits.character_name` is `TEXT`.** Owner decision, 2026-09-07, after the
    first live import surfaced both. Migration `004`.

    *The collapse.* Keying re-run safety on `(movie_id, location, formats)` looked
    sufficient and was not: two spreadsheet rows resolving to the same TMDB film, on the
    same shelf, in the same format, became one item. Three pairs did it in the real sheet.
    Two were genuine duplicate entries — but the third was "French Connection" and "French
    Connection 2", which the matcher put on the same film, so **a disc that exists went
    missing and nothing reported it**. `import_source_row` makes two different lines two
    items whatever TMDB says, keeps a line the owner really did write twice as two items —
    which is what the sheet asserts — and gives the review queue the provenance to trace an
    item back to its source line. Nullable and unique-where-present, because an item added
    by hand in Batch 7 has no source row.

    *The width.* §3.3 sizes `character_name` at `VARCHAR(255)`. TMDB exceeds it whenever
    one performer voices many parts: Dan Castellaneta's credit on *The Simpsons Movie* is
    300 characters, Hank Azaria's 270. Because the importer writes each item in a single
    transaction, the overflow rolled back the film, its credits **and its collection item** —
    the disc disappeared from the catalogue over a cast-list field, reported as one line in
    a summary. `TEXT`, because no fixed width is safe for a slash-separated role list and
    Postgres treats the two types identically.

    *Why a clean re-import rather than a patch.* Both fixes change what a correct import
    produces, and the imported data was an hour old and fully reproducible from the
    spreadsheet — the parser and matching engine **are** the pipeline (`DECISIONS.md` #10).
    `TRUNCATE`, not `DELETE`: `DELETE` fires `collection_items_soft_delete` and would have
    left 1,853 soft-deleted rows behind rather than an empty table.

    *General lesson, worth more than either fix:* both defects were invisible to a green
    gate and to a `--dry-run`. The importer's unit tests mock the database, so no test
    could have hit a column width or a unique constraint, and the dry run never writes. The
    first real write against real data is its own test stage, and this batch should be
    remembered as evidence for that rather than for either individual bug.

### 2026-09-08 — Identifying films in the app

33. **The 764 unidentified items are resolved in the app, on the detail page, not by
    working a CSV.** Owner decision, 2026-09-08. Folded into Batch 5, which moves 🟡 → 🔴.

    Batch 4 deliberately catalogued every disc and deferred the *identification* of 757 of
    them (#31). The queue it produced was a CSV with an `alternatives` column. Resolving it
    in the UI instead: opening a film that has no `tmdb_id` shows the matcher's top five
    **with posters, years and overviews**, and picking one enriches the row.

    *Why:* judging *French Connection II* against *The French Connection* takes a second
    from two posters and is genuinely hard from `1051:The French Connection (1971) |
    10711:French Connection II (1975)` in a spreadsheet cell. It also spreads the work
    across normal use — the question gets asked exactly when someone cares about that disc
    — instead of demanding one 764-row sitting, and there is no parallel artefact to keep
    in step with the database.

    *Why it costs no schema:* the unidentified set is exactly `movies.tmdb_id IS NULL`, so
    no flag column is needed, and those rows already hold the spreadsheet title, which is
    what the matcher searches on. They also have no overview and no poster, so the detail
    page renders conspicuously empty on its own — the prompt to identify is free.

    *Why inside Batch 5 rather than after it:* 41% of the catalogue would otherwise render
    as blank detail pages, which contradicts Batch 5's own goal of Mark being able to
    browse the collection. Shipping the page 41% empty and returning later means designing
    its empty state twice.

    *Second thing it buys:* the same picker, opened from an already-identified film, is how
    the wrong-sibling matches get corrected — French Connection II, X-Men 2, 11.22.63,
    Planet Earth II (`STATUS.md` gotcha 1b). That removes the need for a third change to
    the matching ranking, which would otherwise cost a 45-minute measurement pass over all
    1,857 titles and risk regressing matches that are currently right.

    **Either user can identify a film; it is not restricted to admin.** A narrow exception
    to §3.1's "Admin = full catalog CRUD; Viewer = read-only". *Why:* Mark browsing on his
    phone is the person most likely to open a blank film, and a queue only the admin can
    move is a queue that stays at 757. The choice is one click to undo, and Batch 7's
    `admin_actions` audit records who identified what — attributable without being
    restricted. *Considered and not taken:* Mark's picks as suggestions pending Craig's
    approval, which is net-new state and net-new UI for a two-person app, guarding against
    a mistake that is trivially reversible.

### 2026-09-08 — Batch 6 location and facets

34. **The section vocabulary grows by the four cabinets, and 122 live rows are
    backfilled.** Owner decision, 2026-09-08, taken before any code was written because
    `STATUS.md` had recorded it as the open question Batch 6 must settle.

    §3.4 named five sections. 124 of the 1,857 imported rows named somewhere else and
    were left at `section IS NULL`, so no location filter could reach them — which is
    the whole point of this batch. They are not scattered: **122 of the 124 are four
    named cabinets**, "Top Big Cabinet" (38), "Top Small Cabinet" (38, two spellings),
    "Left Hand Side Small Cabinet Fish Room" (26) and "Black Box next to cabinet" (20).

    *Why grow it rather than leave them searchable by `location` text alone:* a section
    the filter cannot offer is a part of the house the app cannot answer questions
    about, and 122 discs is 6.6% of the collection. The alternative considered was one
    combined "Cabinet" section, rejected because the four are four different pieces of
    furniture in three different rooms and merging them answers "which cabinet?" with
    "a cabinet".

    *What stays unsectioned, correctly:* two rows. `(In with The Killing)` names another
    disc rather than a place, and one row has no location at all. Forcing either into a
    bucket would be inventing data.

    *Cost, accepted:* migration `007` writes to live rows, which is why this batch's
    close-out stops for sign-off instead of deploying itself. The write is derived
    entirely from `location`, which is never modified, so it is reproducible and
    reversible.

35. **`watch_log` is built in Batch 6, because no phase in the roadmap ever built it.**
    Owner decision, 2026-09-08, taken before any code was written.

    Batch 6's definition asked for a "watched status" facet alongside decade and rating,
    as though the three were equivalent-cost additions. They were not. §3.7 designs the
    `watch_log` table and §6.5 lists `POST`/`GET /api/v1/watch-log`, but **no phase in
    §16 creates either** — checked against all 96 phase headings. The ledger's Batch 37
    is defined as *"inert until `watch_log` has ~a year of history"*, waiting on a table
    nothing brings into existence. The facet was not a facet; it was a missing feature.

    *Why build it here rather than defer the facet:* deferring would have shipped Batch 6
    two-thirds done and left Batch 37 permanently blocked on an unowned gap. Building it
    moves the batch 🟢 Mid → 🟡 Large, which is the honest tier.

    *Two shapes differ from §3.7 deliberately.* `deleted_at`, because §13.5 sends deleted
    watch logs to Trash and a hard delete cannot support that — and because the realistic
    failure is a mis-tap on a phone. And `movie_id ON DELETE RESTRICT` rather than the
    `CASCADE` used for `movie_credits`: a credit is a fact *about* a film and dies with
    it, but a watch is something a person did. The app's one hard-delete path for a movie
    is the identify flow's merge, which now repoints watch rows exactly as it already
    repoints `collection_items`.

    *Watched status is per-user, and every route is scoped to the caller.* In a
    two-person app "have I seen it" and "has he seen it" are different questions, and the
    facet exists so Mark can find what *he* has not seen. A shared flag would answer
    neither.

    *An unrated film is excluded by `minRating` rather than treated as zero.* All 757
    unrated films are unidentified, so "rated 7+" quietly meaning "identified and rated
    7+" is the only reading that does not overstate what is known.

36. **The shelf parser requires an ordinal suffix, or the word "shelf" after a digit.**
    Found while building this batch, fixed with it, because Batch 6 owns shelf filtering.

    `_ORDINAL_RE` matched any bare digit anywhere in the location string, so
    `Top small cabinet (Arrow 4 Film Noir Classics Vol 2)` parsed to shelf **"4th"** —
    four live discs that a "4th shelf" filter would have wrongly returned. The same trap
    sits inside `Back 6th Shelf (Arrow 4 Film Noir Classics Vol 1)`, which produced the
    right answer only because `re.search` returns the leftmost match and "6th" happens to
    come first. A correct result for the wrong reason is not a working parser.

    *Why not just require the suffix:* `Front 2 shelf` is a plausible hand-typed location
    and the old behaviour accepted it, so the bare-digit form is kept where the word
    "shelf" follows it. Verified against all 72 distinct location strings in the live
    database: 1,734 rows unchanged, 122 newly sectioned, 4 shelves cleared, and nothing
    produced outside the vocabulary.

    *Three `parse_location` test cases changed their expected values*, which `AGENTS.md`
    otherwise forbids. They asserted that a cabinet has no section — precisely the
    behaviour #34 decided to change — so this is the decision being carried out, not a
    failing assertion being edited to pass.

### 2026-09-08 — Batch 7 write surface

37. **Collection writes are admin-only.** Craig can add, edit and delete discs; Mark
    cannot. *Why:* §3.1 specifies "admin-only form", and its acceptance criterion depends
    on the distinction — *"Admin adds a movie; **viewer** immediately sees it"* is not
    testable if both roles write. #33's "either user can identify a film" was scoped to
    identification, where admin-only contradicted Batch 5's own goal; nothing here
    contradicts Batch 7's. *Revisit if* Mark starts buying discs — this is a one-line
    change from `AdminUser` to `CurrentUser`, and the audit log already records who acted.

38. **`admin_actions.target_id` is TEXT with no foreign key, over §3.20's UUID column.**
    Reaffirms #5 against the schema table that contradicts it. *Why:* the acceptance
    criterion is that the log survives deletion of the row it describes, which a foreign
    key defeats in both directions — it either blocks the delete or cascades the evidence
    away. TEXT rather than a bare UUID so a future non-UUID target (a spreadsheet row for
    `bulk_import`, a composite key) still has somewhere to go. `user_id` is `SET NULL` for
    the same reason applied to the actor. *Proved by a test that disables the soft-delete
    trigger and genuinely destroys the row*, since the trigger otherwise makes a hard
    delete impossible and the criterion untestable.

39. **Optimistic UI stays in Batch 8; Batch 7 ships plain mutations with invalidation.**
    *Why:* §3.1 lists "Optimistic UI" as a bullet, but the ledger assigns phase 6.5 to
    Batch 8, whose definition calls for the-coupon's queued/unconfirmed reconciliation and
    explicitly **not** naive optimistic-with-rollback. Building rollback here would mean
    building the thing the next batch rejects and then deleting it. The same reasoning
    splits the trash: Batch 7 ships list-and-restore for `collection_items`, and §13.5
    keeps permanent delete — the one irreversible action in the area — with the batch that
    specifies it.

40. **`UtcDatetime` now exists, because Batch 7 is the first batch to put an instant on
    the wire.** `AGENTS.md` has always specified "correct at the wire with a `UtcDatetime`
    annotation, not at each call site", and nothing implemented it — #14's warning about
    conventions asserted in prose, found in our own file. It was harmless until now:
    Batch 6's `watchedAt` is a `DATE`, which carries no offset to get wrong. *Why it
    matters:* every domain timestamp is stored `DateTime(timezone=False)` holding UTC, so
    a plain serialisation emits `2026-09-08T14:00:00`, which `new Date()` reads as **local**
    time and renders at the wrong hour — silently, with nothing erroring.

41. **A list must not render its empty state until data has actually arrived.**
    `listState()` in `apps/web/src/lib/query-state.ts`; applied to the trash, the TMDB
    search and the history panel. *Why:* TanStack Query **pauses** a retry when it believes
    the app is offline — `status: 'pending'`, `fetchStatus: 'paused'`, `isError: false`, no
    data, indefinitely. The usual `isLoading → isError → items.length === 0` ladder falls
    straight through to the empty state and asserts something false about the user's
    collection: the trash page said "Nothing has been removed" while the request had never
    come back. *Found by opening the pages in a browser*, not by any green check — the
    build, the types and the tests were all passing. `MovieDetailPage` had avoided it by
    treating `isError || !data` as failure; this states the rule once. **Batch 8 is the
    offline batch and should build its banner on top of this, not around it.**

### 2026-09-08 — Batch 8 PWA and offline

42. **An offline edit carries the version it was based on, and the server refuses it if
    the row moved on.** Supersedes phase 13.9's "conflict resolution (last-write-wins)".
    *Why:* the two cannot both hold. A queued edit flushed on reconnect **is** written
    last, so last-write-wins is precisely what this batch's own acceptance criterion —
    *"an edit made offline lands once reconnected **without overwriting a newer
    change**"* — forbids. `PUT /collection/{id}` takes an optional `baseUpdatedAt` and
    answers 409 with the current row, so the client can say what it would have clobbered.
    Optional, because an online edit that has just read the row needs no guard.

43. **`NetworkError.mayHaveLanded` decides everything, and only one case is certain.**
    *Why:* the browser is authoritative about exactly one thing — that it did not attempt
    a request while reporting itself offline. Everything else, including a connection
    that dropped a millisecond after the bytes went out, might have been applied. Guessing
    "never landed" and re-sending duplicates discs and reverts newer edits; guessing the
    other way costs one cheap read. **A 5xx or a 408 counts as unknown, not as a
    refusal** — a gateway, a proxy, a captive portal and a container still booting all
    produce one and none of them is the application answering.

44. **The queue is persisted in IndexedDB, and sign-out empties it.** Diverges from
    `the-coupon`, which keeps its queue in memory on purpose. *Why the divergence:* its
    queue is a single slot (one pick per member per round), its data is other members',
    and it has no phase asking for durability. Here §13.9 names IndexedDB, the queue holds
    several entity types at once, the data is the owner's own, and the case that matters —
    cataloguing a shelf in a garage with no signal, then closing the tab — is the one a
    memory queue loses. *Why sign-out clears it:* the objection that kept `the-coupon`'s
    queue in memory is real — an unsent write outliving its session would fire under
    whoever signs in next — and it is answered directly rather than by giving up
    persistence.

45. **A response is not an answer unless the application sent it.** See #43. Recorded
    separately because it was a live defect rather than a design choice: `fetch` *resolves*
    for a 503, so a write that never reached the application was being classified as a
    refusal and thrown away. An edit made behind a captive portal vanished silently.

46. **The IndexedDB connection fails fast and is never cached as a failure.** *Why:*
    IndexedDB has no timeout of its own — an upgrade blocked by another tab holding an
    older version open simply never resolves — and the connection promise was cached, so
    one blocked moment made **every** later write hang for the life of the page, behind a
    spinner that could not stop and with nothing thrown or logged. Two tabs open across a
    schema change is enough to reproduce it.

47. **React Query runs with `networkMode: 'always'` for both queries and mutations.**
    *Why:* the default pauses work when it believes the app is offline, and both pauses
    are silent and indistinguishable from a hang. A paused **mutation** never runs
    `mutationFn`, so the offline queue — which lives inside it — is never reached and the
    edit is saved nowhere. A paused **query** never issues its fetch, so the service
    worker, whose entire job is to answer that fetch from cache, is never consulted;
    "browse the collection with the network off" cannot work while the request is not
    made. This is also the root cause of #41's empty-state lie in Batch 7.
    **Neither is catchable by unit-testing the queue**, which never goes through
    react-query at all — both were found by driving the built app with its API switched
    off, with the build, the types and 46 tests all green.

48. **Only a 401 or 403 ends a session.** *Why:* `loadProfile` cleared the tokens for any
    non-ok response, so the first time the app was opened without signal it signed the
    person out — and destroyed the session the queued offline writes had been made under.
    A 5xx, a 408 or anything from a gateway means nobody looked at the credentials. An app
    whose purpose is to work on a phone in a garage cannot log you out for being in the
    garage.

49. **`set_updated_at` uses `clock_timestamp()`, not `NOW()`.** *Why:* `NOW()` is the
    **transaction** start time in Postgres. Batch 8 made `updated_at` a concurrency token,
    and a token that does not advance when the row changes cannot detect that the row
    changed — two updates in one transaction produced identical values and #42's guard
    passed anything. It also made the import stamp all 1,857 rows with the moment the
    import began rather than when each row was written. Caught by this batch's own tests
    in CI, where the guard failed *open*. The `AT TIME ZONE 'utc'` wrapper stays, for the
    reason migration `003` added it.

### 2026-09-08 — Batch 9 onboarding

50. **The notifications step is dropped, not repaired.** The batch definition states that
    `StepInstallPWA` and `StepNotifications` "now have real infrastructure behind them".
    Only the first is true. *Why:* there is no VAPID key, no `pushManager` subscription,
    no endpoint to store one and no `push_subscription` column anywhere on the new spine —
    push is Batch 11 (6.1, 6.2, 5.11). The step also never requested notification
    permission; it was a preferences form offering toggles for **six features that do not
    exist yet** (price drops → B20, deals → B22, new releases → B17, loan reminders → B15,
    purchase suggestions → B18, on-this-day → B37). Keeping it would have broken this
    batch's own acceptance criterion — *"every step of the wizard does what it says"* — so
    the honest options were to drop it or to build push, and building push is another
    batch. **Batch 11 owns re-introducing it**, with infrastructure first.

51. **Onboarding completion is a nullable timestamp, and the flow is skippable to the
    end.** *Why the timestamp:* it answers "finished?" and "when?" in one column, matches
    the `*_utc` convention, and cannot reach the "true but we do not know when" state a
    boolean plus a later audit question would. *Why skipping completes it:* nothing in the
    wizard has to be done — it installs an app, picks a theme and points at three pages —
    so there is no half-finished state worth representing, and a person who skipped should
    not be asked again every time they open the app. §2.8 asks for skippable and
    resumable; the resume position is per-device `localStorage`, following #8.

### 2026-09-08 — Batch 10 architecture doc split

52. **A batch with no written acceptance criteria gets them written into
    `docs/phase-batches.md` before work starts, not invented silently and not treated as a
    reason to skip the batch.** Owner decision, 2026-09-08, taken because Batch 10 was the
    first batch whose ledger row was a bare title — every other batch has a `### Batch N`
    section with `**Goal:**`/`**Acceptance:**`, and `batch-start.md` step 2 requires
    restating them verbatim before any code is written, which is impossible when nothing
    was written down.

    *What was done:* the agent reconstructed a scope from `REVIEW_PLAN_2026-09-07.md` Part
    C (the source the ledger row's title was drawn from) and `MCU_Architecture_v2.1_FINAL.md`
    §17 (what "reconciliation" meant concretely), proposed it to the owner, and on
    agreement wrote it into `docs/phase-batches.md` as a proper `### Batch 10` section
    before touching any other file — so the batch still has a written gate to be verified
    against, and the next agent (or the next `git blame`) can see where it came from.

    *Why this over the alternatives considered:* inventing criteria without surfacing them
    would make `batch-start.md` step 2's "restate verbatim" a fiction — there would be
    nothing on record the work was actually checked against. Skipping the batch until the
    owner writes criteria themselves stalls low-risk, docs-only work on a formality. Asking
    first, as was done, costs one round trip and leaves a durable artifact instead of an
    agent's private judgement call.

    *Scope, so this doesn't become a loophole:* this is for a batch with **no** acceptance
    criteria at all, not for treating an existing criterion as negotiable — `AGENTS.md`'s
    guardrail against weakening the gate to reach green is unaffected. If a future batch
    has the same gap, do the same thing: propose, get agreement, write it down, then start.

### 2026-09-09 — date guards read the server's timezone

53. **A user-supplied calendar date is "in the future" only if it is not today anywhere on
    Earth.** The ceiling is UTC today plus one day (UTC+14, Kiritimati), not any single
    timezone's today. Taken while fixing a pre-existing red on `main`.

    *What was wrong:* `log_watch` defaulted `watched_at` to the **UTC** date and then
    validated it against `date.today()`, which reads the **server's local** timezone.
    `purchaseDate` carried the same guard. On Railway the two agree, because it runs UTC;
    on a British machine they disagree for the hour after midnight, which is why
    `test_logging_a_watch_returns_it_and_defaults_to_today` was green in CI all day and red
    locally at 00:07 BST. `AGENTS.md` says "UTC everywhere" and it was true of timestamps
    and untrue of dates.

    *Why not simply compare against UTC today:* that is stricter **and wrong**. At 00:30 in
    London the wall calendar says the 9th while UTC says the 8th, so a UTC-today guard
    would tell someone logging tonight's film that tonight is in the future. The guard
    exists to catch a typed year of 2126, not to arbitrate timezones, and it has no way to
    know the caller's.

    *Where it lives:* `apps/api/src/clock.py` — `utcnow()`, `utc_today()` and
    `latest_plausible_today()`. Both guards call the last. Two tests hold the boundary:
    tomorrow-in-UTC is accepted, the day after is refused. The pre-existing `_utcnow()`
    copies in the routers were left alone; they are timestamps and were never wrong.

### 2026-09-09 — Batch 12 box sets + smart collections

54. **Batch 10 removed §16 and with it every planned batch's acceptance criteria.** The
    criteria are recovered **verbatim** from git (`d94a6b8~1:MCU_Architecture_v2.1_FINAL.md`)
    and written into the batch's own `docs/phase-batches.md` section as it is started —
    the same treatment #52 gave Batch 10.

    *What was wrong:* `batch-start.md` step 1 says to read "the phase's own entry in the
    roadmap doc" and grep for the `**Phase X.Y:` heading; step 2 says to restate its goal
    and acceptance criteria verbatim before writing code. After Batch 10 that grep returns
    nothing — §16 is a pointer to `docs/phase-batches.md`, and the ledger carries
    `### Batch N` sections with `**Acceptance:**` only for batches 1–10. Every batch from
    11 to 38 has a one-line title and nothing to verify against.

    *Why recovery rather than re-authoring:* the text is not lost, only unreachable — it is
    intact in git history, and copying it verbatim keeps #52's guarantee that the batch was
    checked against something written down rather than against an agent's private reading.
    Re-authoring criteria would quietly replace the owner's spec with the agent's.

    *Why not restore §16 wholesale:* Batch 10 removed it deliberately, because 86 phases of
    decayed model annotations are exactly the rot the ledger exists to stop. Restoring the
    acceptance criteria **per batch, into the ledger section that already has the right
    shape** keeps the roadmap of record singular.

    *Scope:* batches not yet started still have the gap. Whoever runs one does this first.

55. **A saved smart collection and the filter bar evaluate through the same function.**
    `list_movies`' body was extracted into `movie_page()`; `GET /movies` and
    `GET /smart-collections/{id}/results` both call it, and a test asserts the two return
    byte-identical pages for the same filters.

    *Why:* §3.23 stores a collection as a JSONB filter blob. Two dangers, and only one of
    them announces itself. The loud one is injection, closed off by validating the blob
    through `SmartCollectionFilters` (`extra="forbid"`) whose fields *are* the query
    parameters `GET /movies` accepts. The quiet one is **divergence** — a second predicate
    builder that gradually stops agreeing with the first, so a saved "Unwatched 4Ks from
    the 2010s" lists a subtly different set of films from the same filters typed by hand.
    Nothing errors; both pages look plausible. One function is the only fix that does not
    depend on someone noticing.

56. **`box_sets.isComplete` is three-valued, and `NULL` means "nobody recorded how big the
    box is".** Not `false`.

    *Why:* §3.24's `expected_count` is nullable and §11.4 asks for "3 of 4". A set with no
    expected count has no denominator, so it is *unmeasured*, not incomplete — and
    defaulting to `false` would put a permanent red mark against every set an admin had not
    filled in, which reads as a data problem the person cannot fix. The web app renders no
    progress bar at all in that case and says how many discs it holds instead.

### 2026-09-09 — Batch 13 completion sets

57. **A completion set's members come from the collection's own credits, never from a name
    search.** `movie_credits` already holds a real TMDB person id for every identified
    film, put there when the film was identified. The top directors and actors *by owned
    count* become the sets.

    *Why:* the alternative is a list of names — typed, or scraped from `sub_category` — and
    then a TMDB search per name. `STATUS.md` gotcha 1b is the record of what that costs:
    the matching engine once let TMDB popularity decide which film was on the shelf.
    Starting from an id that arrived with the film removes the matching step rather than
    improving it. It also makes every set one this collection has a stake in.

58. **What counts as a member is filtered, and the filters are the batch.** A member is a
    credit with `job=Director` (or, for an actor, `order <= 15`), a release date, and at
    least one vote.

    *Why each one:* TMDB returned **129** crew credits for Hitchcock. 65 have
    `job=Director` — the other 64 are producing and writing credits, and "the Hitchcock
    films" does not mean those. Of the 65, four have no votes: two wardrobe tests, Tippi
    Hedren's screen test for *The Birds*, and a 2026 documentary *about* him. The set holds
    **61**.

    Without the job filter the app would report "12 of 91"; without the vote filter, "12 of
    65". **Both look entirely plausible**, and nothing in the app would ever say they were
    wrong — which is why each filter has its own test rather than a comment.

    An unreleased credit is excluded for a different reason: counting announced projects as
    "missing" makes every set permanently incomplete by construction, so the bar could
    never reach 100% for a living director.

59. **Ownership is computed at read time, never stored.** The insights page intersects the
    cached `member_tmdb_ids` with `movies.tmdb_id` in one query for the whole page.

    *Why:* the members change weekly and what is owned changes whenever a disc is added, so
    a stored `owned_count` would need invalidating from the collection write path — a
    coupling that is invisible when it breaks. Same reasoning as §3.23's smart collections
    (#55): the thing that changes often is the thing not to cache.

    What *is* cached is the display half — title, year and poster for each member — because
    a **missing** film has no row in this database by definition, so §11.2's "missing films
    list with posters" would otherwise be one TMDB call per missing film, per page view,
    forever.

60. **The weekly schedule in 11.1 is not implemented, and that is deliberate.** The refresh
    exists twice — `src/scripts/refresh_completion_sets.py` and
    `POST /api/v1/insights/completion/refresh` — and neither is on a timer.

    *Why:* a Railway cron is a hosting change, which `AGENTS.md`'s close-out protocol keeps
    explicit. An in-process scheduler would be worse than nothing: it would run once per
    container, so scaling to two would double the TMDB spend silently. Wiring the schedule
    is one console action against a job that already works, and it is the owner's.

### 2026-09-09 — Batch 14 stats + export

61. **A chart with no data says what it is waiting for; it never renders as zero.**
    `/collection/stats` returns an empty `mostWatched` and `spendOverTime` **plus**
    `itemsWithPrice`, and the page prints a sentence in place of the chart.

    *Why:* measured before writing anything — `watch_log` holds 0 rows, and
    `purchase_price` is NULL on **all 1,857** items because the imported spreadsheet never
    carried one. A bar chart with no bars and a line at zero both look like a bug in the
    chart, and a reader cannot tell "nothing bought" from "nothing recorded" without the
    denominator. This is `STATUS.md` gotcha 19 — a page that lies confidently is worse than
    one that errors — applied to a dashboard instead of a list.

    *Consequence for the criterion:* §13.1's "all charts populated" is **not** literally
    met and cannot be until the data exists. Recorded rather than worked around.

62. **No server-side PDF renderer. §13.4's PDF is the browser printing §13.4's HTML.**

    *Why:* WeasyPrint needs cairo and pango; wkhtmltopdf and Playwright need a headless
    browser. All of them are system libraries in the image — and `AGENTS.md`'s own note on
    the gate says **the Docker image is built by Railway, not by CI**. A missing shared
    object would therefore pass every check on a pull request and fail at deploy, which is
    the exact failure shape this project has already been bitten by twice.

    *Why it is not a narrowing:* §13.4 asks for two things — "printable PDF with posters"
    and "coffee-table HTML" — and one print-laid-out document is both. The HTML carries
    real `@page` rules, `page-break-inside: avoid` per card, and `print-color-adjust:
    exact` so the posters survive the print dialog. Revisit if a *scheduled* PDF is ever
    wanted, which is the one case a browser cannot serve.

63. **An export download goes through `fetch` into a blob, not through a plain link.**

    *Why:* an `<a href>` cannot carry an `Authorization` header, so making one work means
    putting the access token in the query string — where it lands in server logs, browser
    history and any `Referer` the page emits. The whole collection is ~300 KB of CSV, so
    holding it as a blob costs nothing measurable and keeps the credential in the header.
