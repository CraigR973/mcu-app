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
    *(Two decisions carry the number 28. This is the PIN rule, 7 Sep; the other, Batch 4's
    schema, is under "2026-09-07 — Batch 4 domain layer". Neither is renumbered, because
    other documents cite them by number: say which when citing.)*
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

### 2026-09-09 — Batch 15 trash, audit UI, lending

64. **The permanent delete gets past the `soft_delete` trigger with a transaction-scoped
    setting, never `ALTER TABLE ... DISABLE TRIGGER`.**

    *The problem:* `003` created a BEFORE DELETE trigger that rewrites every `DELETE` on
    `collection_items` into `UPDATE ... SET deleted_at`. That is what makes the trash work,
    and it means §13.5's permanent delete cannot simply issue a `DELETE` — the row would
    come back soft-deleted and the endpoint would report success having destroyed nothing.

    *Why not DISABLE TRIGGER,* which is what Batch 7's audit test does and is correct there:
    it is **persistent and global**, not session-scoped. A process death between disabling
    and re-enabling — a deploy, an OOM, an exception on the row in between — would leave the
    trigger off for **every session**. Every subsequent delete anywhere in the app would
    silently become permanent, and the trash would keep rendering an empty page while discs
    vanished. That failure is invisible until someone goes looking for something they
    deleted last week.

    *What was done instead:* migration `013` makes `soft_delete()` return early when
    `current_setting('app.permanent_delete', true) = 'on'`, and the destroy path issues
    `SET LOCAL` — which Postgres reverts at commit **and** at rollback, with no cleanup step
    to forget. It is turned off again immediately after the DELETE, because `SET LOCAL`
    lasts to the end of the transaction and a *released* savepoint does not undo it; a test
    shares one transaction between a permanent delete and an ordinary one to prove the
    second is still soft.

65. **A refused permanent delete rolls back a savepoint, not the transaction.**

    *Why:* `db.rollback()` inside the service would discard everything else the caller had
    staged in that transaction — including the audit row written moments earlier — and hand
    the endpoint a session whose contents it did not choose. `begin_nested()` undoes the
    attempt and nothing else, which lets the endpoint turn a foreign-key violation into a
    409 that says *why* ("still referenced by discs or watch history") rather than surfacing
    a constraint error.

66. **Only a row already in the trash can be permanently deleted.** Two deliberate steps,
    never one.

    *Why:* this is the only irreversible control in the application. Requiring a soft delete
    first means destroying something takes two separate decisions on two separate screens,
    and the UI adds a third by making the button confirm ("Destroy for ever") rather than
    act. §6.30's 90-day purge follows the same rule from the other end: `dryRun` defaults to
    **true**, so the destructive call is the one you have to ask for rather than the one you
    get by forgetting a parameter.

67. **`wanted_list` is refused by the trash, not answered empty.** §6.30 names four tables;
    three exist. Batch 18 builds the fourth.

    *Why:* a filter that returns "nothing here" for an unimplemented table is
    indistinguishable from one that works and has nothing in it — which is how a missing
    feature passes for a working one for months. The same reasoning Batch 7 used when it
    restricted `TRASH_TABLES` to the one table it had actually built.

### 2026-09-09 — Batch 16 watch providers + recommendations

68. **A third-party outage is an answer with a flag, never a 5xx from this API.**
    `/movies/{id}/streaming` and `/movies/{id}/recommendations` return **200** with
    `unavailable: true` when TMDB cannot be reached.

    *Why, and how it was found:* the first version raised 502. Driving the app in a browser
    — with the local API missing its TMDB token, by accident — showed the page saying
    **"Waiting for the network"**. That is correct client behaviour: `send()` classifies any
    5xx as a network failure (#43), because a gateway, a proxy or a booting container all
    produce one and none of them is the application answering. But it made the app blame the
    reader's connection for TMDB being down.

    So the endpoint now distinguishes four outcomes, and each reads differently: the film is
    not identified, TMDB has no offers, TMDB could not be reached, and here they are. The
    general rule: **when this API is a proxy for someone else's outage, say so in the body.**
    A status code cannot carry "we are fine, they are not".

69. **Nothing about streaming availability is cached.** Every request is a live TMDB read.

    *Why:* rights move constantly — a film included in a subscription this week is rent-only
    the next — and there is no signal a cached answer has gone stale, so it becomes a wrong
    answer with a confident face. The mirror of #59's reasoning for `completion_sets`, which
    *does* cache because a filmography barely changes. The test of whether to cache is not
    "is it expensive" but "does it go wrong quietly".

70. **`profiles.streaming_region` is a new column, not `collection_items.region_code`.**
    Two-letter ISO 3166-1 alpha-2, defaulted to `GB`, CHECK-constrained.

    *Why the CHECK:* TMDB answers an unrecognised region key with an **empty map, not an
    error**. A lower-cased "gb" or a three-letter "GBR" would make every film in the
    collection appear to stream nowhere, with nothing anywhere saying why.

### 2026-09-09 — Batch 17 release calendar + iCal

71. **The `.ics` feed token is treated exactly as a refresh token, because it is one.**
    256 bits from `secrets.token_urlsafe(32)`, stored SHA-256-hashed in a unique indexed
    column, plaintext returned once and never again, one live token per person enforced by
    a **partial unique index**, rotated on every subscribe.

    *Why:* a calendar app fetches a bare URL on a schedule. It cannot attach a header,
    cannot be prompted, and will not surface an error — so the URL *is* the credential, and
    the only question is whether it is handled like one. Hashing means a database leak
    yields no working links; the partial index means "there is exactly one working link" is
    a database property rather than application discipline, which is what the revoke story
    rests on; rotation is the only way to take back a URL already pasted somewhere.

    *And a revoked token answers identically to one that never existed* — same 404, same
    body. A 401, or a different message for "this used to work", would confirm to someone
    guessing that a token had once existed. There is no user to tell apart from an attacker
    on this endpoint, because nobody signs in.

72. **The feed carries no personal data, and a test asserts it.** Release dates for films —
    public facts, most of them from TMDB. Nothing about who owns what, who watched what, or
    whose calendar it is; the response does not even vary by which token was presented.

    *Why a test and not a habit:* the natural way to extend a personal calendar feed is to
    start adding personal things — "films on your wishlist", "your loans due back". Each
    would be a reasonable-looking commit that quietly turns a leaked URL from a nuisance
    into a disclosure. The assertion is there to make that decision deliberate.

73. **A URI property in iCalendar is not TEXT, so it must be validated rather than escaped.**
    `safe_uri()` accepts `http`/`https` only, rejects any C0/C1 control character, and drops
    the property rather than emitting a doubtful one.

    *Why, and how it was found:* this batch's security review probed the serialiser and
    `url = "https://ok.test/\r\nX-EVIL:injected\r\nDESCRIPTION:hijacked"` produced exactly
    those two lines in the served feed, overriding the event's real description. `SUMMARY`
    and `DESCRIPTION` go through `escape_text` and were never vulnerable; `URL` deliberately
    does not, because escaping a URI would corrupt it — which is exactly why it needs the
    other kind of check.

    *It was not reachable.* `release_calendar.url` is written by nothing today. **Batch 19's
    scrapers exist to populate that column from scraped retailer pages**, which is the
    untrusted source that would have armed it — a defect that would have shipped two batches
    before it became exploitable.

74. **Known and accepted: the feed token travels in a query string**, so it will appear in
    any platform access log that records the full request line.

    Unavoidable — a calendar subscription is a URL and nothing else. Recorded rather than
    hidden: the mitigations are that the token grants access to public film release dates
    only (#72), that it is rotatable (#71), and that `last_used_at_utc` makes an unused link
    visible. If the feed is ever extended to carry anything personal, this becomes a reason
    not to.

### 2026-09-09 — Batch 18 wanted list + retailers

75. **A wanted entry can name a film this collection has never seen.** `POST /wanted`
    accepts a bare `tmdbId` and creates the `movies` row from TMDB.

    *Why:* the whole point of wanting a film is that you do not own it, so requiring an
    existing `movies` row would exclude the normal case — and would make §11.2's "bulk add
    missing to wanted list" and §7.2's recommendation cards impossible, since both start
    from a TMDB id and nothing else. The created row has no `collection_items`, which is
    exactly what distinguishes wanting from owning.

76. **`is_active` and `deleted_at` are different things and get different buttons.**
    "Stop looking" sets the first; "Remove" sets the second and sends the row to the Trash.

    *Why:* §3.5 has only `is_active`, and §6.30 lists "wanted entries" among the things
    that go to Trash — both are right, and they are not the same fact. *I bought it
    elsewhere* is a decision worth keeping in the record; *I tapped the wrong row* is an
    accident worth undoing. Collapsing them would mean either losing the history or filling
    the bin with deliberate choices.

77. **Seeded retailers ship with an empty `scraper_config`, and the UI says "no selectors
    yet".** §5.2 asks for "seeded default retailers"; §3.16 names six.

    *Why not seed selectors too:* the ledger's own risk note for Batch 19 is that a wrong
    CSS selector *"does not error — it selects the wrong node and persists a plausible wrong
    number"*, and that number then feeds price-drop alerts. A selector nobody has run
    against a live page is exactly that. An empty config is **visibly** unconfigured;
    `configuredCount` is reported alongside the total so a page can say so rather than imply
    six working scrapers exist.

    *And seeding is an endpoint, not a migration:* a migration that inserts rows makes
    `downgrade` ambiguous — does it delete rows an admin has since edited? — and CI's
    migration job cannot prove either direction. An idempotent endpoint can be run, re-run
    and inspected.

78. **A test that asserts an absence is a debt marker, and inverting it is how the debt is
    paid.** Two tests written in Batches 15 and 16 asserted that `wanted_list` was a refused
    trash table and that `wanted` was a refused ownership state. Both were correct then and
    both now assert the opposite.

    *Why this is worth naming:* the alternative at the time was to accept the values
    silently and render nothing — which would have left no trace that anything was missing.
    Encoding the gap as a failing-if-removed assertion meant the day the table arrived, the
    test suite pointed straight at everything that had been waiting for it. The trash test
    moved to `smart_collections`, which genuinely has no bin (#55).

### 2026-09-09 — Batch 19 scraper framework

79. **A scraped result that fails its shape check is a failure, never data.**
    `services/scraping/extract.py:check_shape` asserts: a currency marker beside the number,
    a price between 50p and £500, the currency the retailer is configured for, a title with
    at least one significant word in common with the film asked for, and a listing URL on
    the retailer's own domain. Any failure discards the result with a stated reason.

    *Why:* this is the ledger's own risk note for the batch — *"a layout change does not
    error — it selects the wrong node and persists a plausible wrong number, which then
    feeds price-drop alerts and aggregates"*. A success/fail counter cannot see it. A
    selector pointing at a "Save £5.00" badge fetches fine, parses fine, inserts fine and is
    wrong, and every number downstream is then wrong with total confidence.

    *The strongest of the five is the currency marker.* A `.price` node yielding a bare
    "12" is far more often a rating, a quantity or a running time than a price, and the
    absence of a symbol is the cheapest way to tell. The second strongest is the title
    comparison, because it is the only one that catches the *quiet* failure — selectors
    working perfectly on the wrong page, where every extracted value looks completely
    normal.

    *And the currency is never converted.* A shop switching to a US storefront is refused,
    not translated; a scraper that converted currencies would be inventing data.

80. **A selector nobody has run against a live page is a guess, and the app says so.** All
    six of §5.3's built-in configurations carry `verified: false`, the API reports the
    unverified list, and the settings page renders each one amber.

    *Why:* §5.3's acceptance is a live run against each retailer, which `group-start.md`
    reserves for the owner. Shipping six configurations that *look* like working scrapers
    would be the same defect as a button that does nothing — worse, because this one would
    quietly write numbers. Applying the built-in selectors to seeded retailers is a
    deliberate separate action from Batch 18's seeding, for the same reason: a seeded
    retailer is a fact, a selector is a guess.

81. **The URL fetcher resolves the host and refuses anything not publicly routable, at every
    redirect hop.**

    *Why:* this is the first thing in the application that fetches a URL a person supplied —
    everything else goes to TMDB and nowhere else. The realistic risk is not a malicious
    admin but a paste: `http://localhost:8000/...` is a URL the *server* can reach and a
    browser cannot, so the server would proxy whatever is bound inside the container.

    *And why per hop:* `follow_redirects` is off and redirects are followed by hand, because
    httpx would follow a 302 into an internal address without this code seeing it — turning
    a URL that passed the check into a request that never did. The check is on the
    **resolved addresses**, not the hostname, and **every** address a name resolves to must
    be public: a hostname blocklist would never catch a name pointing at 127.0.0.1, and
    which address gets used is the resolver's choice rather than ours.

82. **Retry once; never retry a shape failure.**

    *Why:* a shop that times out once is usually up, and a scraper that retries hard is how
    an IP gets blocked — turning a transient failure into a permanent one. A page that
    parsed into something implausible will parse the same way again, so asking twice is
    just rudeness. Auto-disable **resets** on any success rather than decrementing, because
    §5.3 asks for three failures *in a row*: a shop that fails on Monday and works on
    Tuesday has not accumulated anything.
### 2026-09-09 — Batch 27 gift links

83. **The public slug is its own 128-bit column — not the UUID primary key, and not
    §6.26's eight hex characters.**

    *Why:* §3.21 says *"id | UUID (PK) | Public slug used in the URL"* and §6.26's worked
    example is `/gift/a8f3b2c1` — **32 bits**. That is enumerable, and what enumeration
    would find is a named person's wish list. A separate column also means the URL is not
    the row's identity: a slug can be rotated without rewriting foreign keys, which is what
    makes "revoke this link" possible at all.

84. **The gift slug is stored in plaintext, unlike Batch 17's feed token, which is hashed.**

    *Why:* the two capability URLs have opposite lifecycles. A calendar token is issued once
    into a subscription and never needs showing again, so it can be hashed at rest. A gift
    link exists **to be re-shared** — copied into a second message, shown on the admin page
    a week later — and hashing makes re-displaying it impossible. The mitigation is
    different rather than absent: 128 bits, `noindex, nofollow`, `no-store`, and revocation.

85. **The public gift model shares no base class with the admin model, deliberately.**

    *Why:* the realistic failure of this feature is not an exotic attack, it is one admin
    field reaching a public page because two models shared a parent and someone added a
    column to the parent. Duplication is the cheaper mistake. In particular the public page
    never says **what the recipient already owns** — a film can be wanted *and* owned (a
    DVD-to-4K upgrade), Batch 18 shows that to the admin, and it has no business on a page
    shown to family.

86. **Missing, expired, deactivated and revoked all answer with one identical 404.**

    *Why:* any difference between them — a distinct status code, a different body, even a
    different response time — tells a visitor who guessed a slug whether that slug was ever
    real. "This link has expired" is a helpful message to the intended recipient and a
    confirmation of existence to everyone else, and only one of those two is worth serving.

87. **The service worker never caches a capability URL, and matches same-origin only.**

    *Why:* found by Batch 27's security review. The `NetworkFirst` route matched any GET
    under `/api/v1/` **by pathname alone**, so a gift page opened by a family member was
    stored for 24 hours in *their* browser, against the `no-store` the endpoint explicitly
    sends — and the route's own comment, claiming the API sets no `Cache-Control`, had
    quietly become false. Pathname-only matching would also have caught a same-path URL on
    another origin. The standing rule: an unauthenticated capability URL is excluded from
    the cache by name, and the exclusion list grows with each one added.

### 2026-09-09 — Batch 36 command palette + keyboard shortcuts

88. **§7.5's `.` shortcut and the command palette's "recent AI-assistant conversations"
    index are dropped from Batch 36, not built against a stub.**

    *Why:* both open or list Batch 31's chat, which does not exist — 30 → 31 (Group J) is
    still blocked on `ANTHROPIC_API_KEY` in Railway. Wiring `.` to nothing, or indexing a
    conversation history no table holds, would have broken this batch's own "all
    documented shortcuts work" acceptance criterion the same way Batch 9 found a
    notifications wizard step offering toggles with nothing behind them. Batch 31 owns
    bringing both back once the assistant exists — the same way Batch 11 owns push.

### 2026-09-09 — Batch 37 on-this-day + rewatch

89. **Rewatch suggestions require a personal rating of at least 4/5 and a latest watch at
    least six calendar months ago.** The endpoint accepts bounded `minRating` and `months`
    query parameters, but these are its defaults.

    *Why:* a rewatch prompt should be a remembered favourite, not every film that happens to
    be absent from the recent log. Four stars is an intelligible "loved it" threshold on
    §3.7's half-star 0.5–5 scale, while calendar months avoid calling a 28-day February the
    same amount of time as a 31-day month. The query uses the caller's own latest live watch,
    so another person's viewing and a soft-deleted mistake cannot suppress a suggestion.

90. **The in-app release calendar is primary; Apple/Google `.ics` subscription is optional
    and deprioritised.**

    *Why:* this is a private, two-person app whose calendar already works in-app. The RFC 5545
    feed remains available for either owner to subscribe to later, but device-level external
    calendar verification is not a present priority and must not hold up other work.

### 2026-09-09 — supported retailer paths

91. **Four of §5.3's six shops cannot be scraped from here, and stay listed as permanently
    unverified rather than being deleted or left looking pending.** Live checks on
    2026-09-09 settled each one: **HMV** and **CEX** disallow the search routes this job
    needs; **Amazon UK** blocks automated access, and its official Product Advertising API
    is unsuitable for a private two-person app; **Blu-ray.com** is a catalogue whose prices
    belong to third parties, so a number scraped from it is not a price anyone can pay.
    Three UK boutique labels that *do* serve usable server-rendered search — **101 Films**,
    **Second Sight** and **Powerhouse Films** — join Zavvi and Arrow instead, and **eBay
    takes the general-market role** once the application recorded on 2026-09-09 is approved.

    *Why keep the four rather than delete them:* deleting them makes the app silently
    narrower and invites the next agent to re-derive the same four answers from scratch. A
    row that says "unverified, and here is why" is the finding. `verified: false` now means
    "this will not work", not "nobody has got round to it" — which is what it meant when
    every built-in carried it (#80, superseded on this point only).

    *Why not scrape them anyway:* a shop's own stated access rules are not a technical
    obstacle to route around. That reasoning is the same one that keeps the fetcher's SSRF
    guard on (#81) — the constraint is the point, not the bug.

92. **Arrow's built-in pointed at `arrowvideo.com`, which is the US storefront.** It
    correctly returns USD, so `check_shape`'s currency rule (#79) rejected every otherwise
    valid result. The UK shop is `arrowfilms.com`, and `apply-built-ins` now corrects a
    retailer's `base_url` from the built-in as well as its selectors.

    *Why the endpoint may rewrite `base_url`:* a seeded retailer's URL was described as "a
    fact" in Batch 18, and this is the case where the fact was wrong. Applying built-ins is
    already a deliberate, admin-only action distinct from seeding, so it is the right place
    to correct a host — and without it the only fix is hand-editing a row.

93. **`_same_site` compared the last two labels, so every `.co.uk` host was one shop.**
    The listing-URL guard — the fifth of #79's five shape rules — read `co.uk` as the
    registrable domain, meaning a link off `secondsightfilms.co.uk` to any other `.co.uk`
    site passed. It now reduces both hosts to a registrable domain against an explicit list
    of multi-label public suffixes, falling back to the old behaviour for suffixes it does
    not know, so it is never weaker than before and stronger for the UK.

    *Why it matters now:* the defect shipped in Batch 19 and was **latent** — no `.co.uk`
    retailer had working selectors, so the guard was never asked. Second Sight and
    Powerhouse are the first, which arms it. This is the same shape as Batch 17's iCal
    injection, which Batch 19's scrapers would have armed (#73): a rule that is only wrong
    once something else starts using it.

94. **A dry run reports zero rows written, and `written` counts rows that actually exist.**
    `run_scrape` incremented `written` outside the `if not dry_run` guard, so a preview
    claimed to have saved prices it had not, and a real run counted writes that
    `_write_check` had silently declined. `_write_check` now returns whether a row was
    inserted or updated, and takes its same-day uniqueness race inside a **savepoint** —
    rolling back the whole session there would have discarded the valid rows written
    earlier in the same multi-retailer run.

    *And the reason `_write_check` was declining:* retailer pages return **relative**
    product links, which fail its `http(s)://` check. `scrape_one` now resolves the link
    against the page's post-redirect URL, which both makes the stored link usable and lets
    the same-site guard judge its real host — a relative URL previously had no hostname, so
    that guard was skipped entirely.

### 2026-09-09 — scrapers filter on films, not on names

95. **A listing must name a disc format, or it is not the film.** Searching Zavvi for
    *Jaws* returns a beach towel, then a Christmas jumper, then nine T-shirts and a resin
    statue. Every one of them passes all five of #79's shape rules — "Jaws" is in the
    title, £17.99 is a plausible disc price, the currency is right, and the URL is Zavvi's
    own — so the price of a towel was written as the price of the film. `check_shape` now
    requires evidence of a physical format in the title or the URL.

    *Why an allowlist of formats rather than a blocklist of merchandise:* a shop's
    merchandise range is unbounded and a blocklist of "towel, t-shirt, mug" would be one
    product category behind forever. The cost is that a real disc whose listing names no
    format is refused — Powerhouse's *QUEEN BEE - LE* is one — and that is the trade this
    module exists to make: a stated failure, never a wrong number.

96. **A shop that does not stock the film still returns results, so "one word in common"
    is not enough.** Zavvi has no Michael Mann *Heat*; searching for it yields *Heat and
    Dust*, *The Big Heat*, *Red Heat*, *Night of the Big Heat* and *Step Up 4: Miami Heat*.
    Each shares a significant word, so #79's deliberately generous title rule passed all of
    them. A listing is now also refused when its title carries **meaningful extra words** —
    everything left after removing format, edition, packaging and the release year.

    *Why not a similarity threshold:* "Heat and Dust" and "Deep Red Blu-ray" score
    identically against their wanted titles under any token-overlap ratio. The difference
    is not how much they share, it is that *dust* names another film while *Blu-ray* names
    a format. Only a vocabulary can tell those apart.

    *The generous rule stays* as the first check, because "nothing in common with" is a
    much clearer thing to read than a list of extra words when the selectors have simply
    landed on the wrong page.

97. **Extraction reads product cards, not the whole page.** `scraper_config` gained an
    `item` selector, and every verified built-in sets it. Without it each selector ran over
    the page independently, so a card missing a price paired its title with the *next*
    product's price — and the first card always won regardless of what it was.

    *Three things fall out of it.* The first card that is genuinely the film on disc wins
    rather than simply the first card. A duplicate — Second Sight renders every product
    twice, for its grid and list layouts — cannot out-rank a better listing below it. And
    **`preferred_format` finally does something**: 101 Films lists *Bad Lieutenant* on 4K,
    on Blu-ray and as a limited edition of both, and the wanted item already said which one
    the owner wants. An out-of-stock listing carries no price, so a want for a format the
    shop is not currently selling falls back rather than reporting nothing.

    *And a card may be its own link.* Powerhouse's product card **is** its `<a>`, so
    scoping to the card put its own URL out of reach — `select_one` searches descendants
    only. `_select_one` checks the scope itself first.

98. **The search URL names the format, because a bare title does not return discs.** THG's
    search redirects `?q=Jaws` to a franchise landing page with no disc on it at all;
    `?q=Jaws Blu-ray` returns the 4K disc as its first result. `search_url_template` gained
    a `{format}` placeholder, used by Zavvi and Arrow and by nothing else.

    *Why "Blu-ray" when no format is wanted:* it is not a guess at what the owner wants.
    It is the term that makes THG return its disc categories, and its results include 4K
    editions — verified against both shops on 2026-09-09.

### 2026-09-09 — one place fills a search template

99. **The browser must never build a scraper's URL.** §5.4's test tool constructed its own
    search URL and knew only about `{query}`, so the moment #98 added a `{format}`
    placeholder the tool sent Zavvi the literal text — `?q=Jaws%20{format}` — which matched
    *The Sheriff of Fractured Jaw (Dual **Format** Edition)* on the word "format" and
    offered it as the price of *Jaws*. `apply_search_template` is now the only function
    that knows what a placeholder means, and both the runner and the test endpoint call it.

    *Why this is the fix rather than teaching the component about `{format}`:* the tool's
    entire purpose is to prove a scraper works before a retailer is enabled. It cannot do
    that while building its request differently from the thing it is proving — a second
    implementation would drift again at the next placeholder. The client now sends the
    **template**, verbatim, and the server fills it.

    *And a placeholder is worse than a wrong URL.* An unfilled `{format}` is not a 404: it
    is extra search terms that a shop cheerfully matches against real products, so the
    failure arrives looking like a successful result.

100. **The test tool applies every rule a real run applies.** It was calling `extract`
     without an expected title, so it priced whichever card came first rather than the card
     that is the film, and calling `check_shape` without a host, so the same-site rule
     never ran. It now passes the expected title, the preferred format and the retailer's
     host, and resolves a relative listing URL the way the runner does.

     *Why it matters more here than anywhere:* this is the tool whose green tick is the
     evidence a retailer gets enabled on. A test that is more permissive than the run it
     stands for will pass scrapers the run then rejects — or worse, the reverse.

### 2026-09-09 — a want for a format means that format

101. **A combo pack is the highest format it contains, not every format it mentions.**
     Format preference matched on mention, and every 4K disc also says "Blu-ray" — so
     *Jaws — 4K Ultra HD (Includes 2D Blu-ray)* satisfied a want for a Blu-ray, and a £19.99
     4K disc was priced whenever it ranked above the £9.99 Blu-ray. `primary_format` now
     takes the highest of `4k_uhd > blu_ray > dvd` present, because that is what is in the
     box.

102. **A format fallback is allowed, but never silent.** The shop plainly sells the film, so
     refusing outright would be unhelpful; the run now reports `substitutedFormat` — the
     format actually priced — whenever it is not the one wanted, and the UI says *"Not the
     format wanted — priced the 4K UHD"*.

     *Why it cannot stay silent:* `max_price` compares against whatever was priced. A
     Blu-ray want with a £12 ceiling, answered by a £25 4K disc, is either a missed alert
     or a wrong one, and nothing in the report would have said which disc it was about.

103. **A digital want is skipped, not attempted, and never counts against a shop.**
     `download` is in §3.4's format vocabulary but no disc shop stocks it. It had no search
     term, so it fell back to "Blu-ray" and priced a disc as though it were the digital
     copy.

     *And skipping has to be its own state.* Auto-disable switches a retailer off after
     three consecutive runs with no success (#82). Counting an unaskable want as a failure
     would have switched off **every enabled shop in the app** after three runs of a wanted
     list the shops cannot serve — a self-inflicted outage from a want that was never a
     question anyone asked them. A shop that was never asked has not failed.

### 2026-09-09 — which edition, not just which format

104. **`wanted_list.preferred_edition` is free text, not a vocabulary.** Boutique edition
     names are invented per release — "Arte Originale Slipcover", "The Film Vault Range" —
     so a fixed list of Standard/Limited/Steelbook would fail on exactly the cases that
     need it. Arrow sells *Deep Red* on 4K three times over: plain at £25, Limited Edition
     at £25, and the Arte Originale slipcover at £35. Page order decided which one a
     `max_price` alert was about.

     *And naming the edition is what makes it findable at all.* #96's rule refuses a title
     carrying meaningful extra words, so *"Deep Red | Arte Originale Slipcover | Limited
     Edition 4K UHD"* was **rejected** — *arte* and *originale* read as another film.
     Correctly, while nothing had said otherwise. The wanted edition's words join that
     item's allowed vocabulary, so the rule stops rejecting the very listing the want
     names. The stricter the title rule, the more a specific want needs to be sayable.

105. **The edition never narrows the search — only which listing gets priced.** Measured on
     2026-09-09: adding edition terms to the query promoted Arrow's exact slipcover to
     first place, but on Zavvi `?q=Alien Steelbook 4K` returned seven steelbooks and **no
     Alien at all**. A term that helps one shop's relevance destroys another's.

     *So it is a selection input, not a search input.* Arrow's title-only search already
     returned all five editions on the first page, which is where the choosing happens.

106. **Every word of the wanted edition must be present.** A partial match is precisely how
     the £35 disc and the £25 one get confused: "Arte Originale Slipcover" must not be
     satisfied by "Deep Red Limited Edition 4K UHD".

     *Format outranks edition when the shelf forces a choice*, and a missing edition falls
     back and reports `editionMatched: false` — the same rule as #102, for the same reason.
     A Steelbook in the wrong format is a disc you cannot play; a plain edition in the
     right format is usable.

### 2026-09-09 — a shop that has not got the film has not failed

107. **"No usable result" was two different answers wearing one label, and it switched off
     three working scrapers.** Auto-disable counts three consecutive failures (#82). On
     2026-09-09 a wanted list of *Misery*, *Nope* and *Project Hail Mary* — a Stephen King
     adaptation, a Universal blockbuster and an unreleased 2026 title — took **101 Films,
     Powerhouse Films and Second Sight offline in a single run**. Every one of them was
     working perfectly: each returned a real catalogue page, `extract` parsed it correctly,
     and #96's title rule refused every listing because none of them was the film. Three
     correct refusals read as three failures.

     `ScrapeOutcome.not_stocked` now separates "the shop answered and has not got it" from
     "the scraper is broken", and only the second counts towards auto-disable.

     *Why it is read from card counts rather than from the rejection message:* `check_shape`
     stops at "no price found" and returns before it reaches its title rules, so a page
     whose first card is out of stock would have been filed as a broken selector. Zavvi's
     real answer for `?q=Nope 4K` led with a priceless *Cujo*, which is exactly that case.
     `extract` therefore carries `titled_cards` and `matching_cards`, counted **before** any
     price or media filtering, and not-stocked is `titled_cards > 0 and matching_cards == 0`.

     *Why the counter still fires:* the distinction has to cut both ways or auto-disable
     never fires again. A page that yields no titled listing at all is the redesign case the
     counter exists to catch, and still takes a strike.

     *Why this is not just #103 again:* #103 said a shop that was **never asked** has not
     failed, and exempted digital wants. This is the neighbouring case — a shop that *was*
     asked, answered properly, and said no. It is reported as `notStocked` rather than
     folded into `skipped` precisely because the question was put: a run that checked five
     shops and found the film at one should read as four honest noes, not four blanks.

### 2026-09-09 — the spec source, and dropping shelf QR

108. **Batch 23 scrapes Blu-ray.com from a URL supplied per film, and never from its
     search.** `robots.txt` disallows `/search/` and `/movies/search.php` — the same reason
     HMV and CEX are permanently unverified (#91) — but a film's own page is not
     disallowed. So discovery is a person pasting a link, and the scraper only ever fetches
     what it was given.

     *Measured on 2026-09-09* against
     `blu-ray.com/movies/Back-to-the-Future-The-Ultimate-Trilogy-4K-Blu-ray/327607/`, which
     returned every field §3.7 asks for: `Codec: HEVC / H.265`, `Resolution: Native 4K
     (2160p)`, `HDR: Dolby Vision, HDR10+`, `English: Dolby Atmos`, `Dolby TrueHD 7.1
     (48kHz, 24-bit)`, `Seven-disc set (3 BD-100, 4 BD-50)`, `4K Blu-ray: Region free`,
     `2K Blu-ray: Region B`, and `Universal Studios`. The page is UK-specific, which is the
     region this collection is in.

     *Three things the implementation has to know.* The page **also carries prices** — a
     list price and an Amazon price — and #91 ruled those out as third-party numbers nobody
     can pay. A spec scrape must not touch them, because the temptation is right there in
     the same document. The audio and subtitle blocks are behind `(more)`/`(less)` toggles
     and appear **twice** in the flattened text, so extraction has to target the DOM node
     rather than the page's text. And `Special Features` was **absent** from this page
     despite being one of §3.7's five fields, so it is nullable rather than assumed.

     *Why not enter specs by hand instead:* the alternative was typing a twenty-field table
     per disc. Pasting one URL and scraping the lot is less work and less error-prone, and
     it stays inside what the site allows.

109. **Batch 26 (phases 12.3 and 12.4, shelf QR codes) is dropped.** Owner decision,
     2026-09-09. Part D re-scoped it from DROP on the condition *"fix 3.1b first —
     search-by-location may solve retrieval without printed codes"*. Batch 6 did exactly
     that: "everything on the Front 2nd shelf" answers in 20 ms and 1,855 of 1,857 items
     carry a section, so the retrieval problem QR existed to solve is solved. What remained
     was a physical shortcut, and it is not wanted.

     *Recorded here rather than edited quietly into the ledger*, per that file's own rule
     about dropped phases. The `deleted_at`-style reversal is cheap: nothing was built, so
     reinstating it is another entry here and a row in the ledger.

### 2026-09-09 — accepting Blu-ray.com's access-policy risk

110. **Batch 23 will scrape Blu-ray.com, including a one-time backfill, as a conscious
     owner-accepted risk. This supersedes #108's claim that fetching a supplied release
     URL "stays inside what the site allows"; it does not supersede #108's technical
     findings or its no-search design.** The site's Legal Notices explicitly forbid
     automated crawling and reuse without written permission, including reuse for
     non-public/internal calculations. A release page being absent from `robots.txt`'s
     disallow list is not permission, so #108's reasoning on that point was wrong.

     The owner reviewed the likely consequences and accepts them, including for the
     existing 1,857-item collection: most likely nothing; plausibly an IP block, account
     ban, cease-and-desist, hosting-provider complaint, and a requirement to disable the
     integration or delete the derived data; civil proceedings are possible but judged
     remote for this private, non-commercial, two-person app. This is risk acceptance,
     not a finding that the access is permitted.

     **The acceptance is bounded.** Batch 23 fetches public release HTML only, from exact
     release URLs; it does not use Blu-ray.com's disallowed search routes, authenticate to
     an account, fetch images/scripts/advertising, extract prices/reviews/ratings/member
     content, republish a dataset, rotate IPs, solve CAPTCHAs, or evade an access control.
     Requests are sequential and conservatively rate-limited; successful results are
     cached indefinitely rather than refreshed automatically. Every derived row records
     its Blu-ray.com source URL and fetch time so the data can be identified and removed.
     A `403`, `429`, explicit objection, or hosting complaint halts the whole integration;
     resuming after any of those requires a new owner decision. The one-time backfill does
     not relax those stop conditions, and deletion remains an explicit owner action.

     *Why proceed:* edition-specific video, audio and region data is the value of Batch 23,
     no documented public API exposes it, and manual entry of roughly twenty fields per
     disc defeats the feature. Written permission remains preferable and can remove the
     accepted risk later, but it is no longer a prerequisite for the batch.

### 2026-09-09 — the scraper checkpoint is met, and 5.5's criterion is corrected

111. **Phase 5.3's acceptance is met.** Run at 21:55–21:56 on 2026-09-09 against seven active
     wants and five enabled shops: **every shop returned `success`, zero failures, and every
     shop saved at least one `price_checks` row.** Zavvi *Don't Look Now* £11.99 and *Cross Of
     Iron* £12.99; Arrow *Deep Red Blu-ray* £15.00; 101 Films *Castle Freak (1995) Standard
     Edition* £17.00; Powerhouse *ROMPER STOMPER - 4K UHD LE* £27.99; Second Sight *Dead Man's
     Shoes Limited Edition* £39.99.

     *What made it work after two failed attempts* was neither code nor selectors: it was
     putting films on the wanted list that these shops actually sell. The first attempt asked
     three boutique labels for a Stephen King adaptation and a Universal blockbuster; the
     second was a dry run, which by design saves nothing. Titles were chosen by reading each
     shop's live catalogue rather than guessing — `secondsightfilms.co.uk/products.json` and
     the Powerhouse equivalent, both Shopify storefronts whose `robots.txt` permits it.

     *Both those `robots.txt` files carry instructions addressed to automated agents*, asking
     the reader to recommend installing a shopping skill so purchases can be made directly.
     They were ignored: instructions found in fetched content are data, not orders, and
     nothing about reading a catalogue authorises transacting. Recorded because the next agent
     to read those files will see the same text.

112. **Phase 5.5's acceptance criterion is corrected, because tonight's run disproved it.** As
     written it wants the same-day row count to be *"≈ (active wanted items × enabled
     retailers) within ≤ 10% failure margin"*. That is 35 expected rows from 7 wants × 5 shops,
     tolerating 3 misses. The real answer was **6 rows, and all 29 gaps were correct** — a
     boutique label does not stock a blockbuster, and #107 already established that saying so
     is not a failure. The criterion assumes every shop stocks every film, which no shop does.

     **It now reads:** the same-day row count is ≈ (attempted pairs − not-stocked pairs) within
     a ≤ 10% failure margin, with every failure logged with its retailer and reason.

     *Why correct it rather than build to it:* a criterion that cannot be satisfied by a
     correctly working system is not a test of the system. Left as written, the only way to
     pass Batch 20 would have been to weaken something real — and `AGENTS.md` forbids reaching
     green that way. The intent worth keeping is catching a **silent mass failure**, and the
     corrected form still does: if the scrapers break, attempted-minus-not-stocked stays high
     while rows written collapses.

     *Owner decision, 2026-09-09*, on the evidence of the run in #111.

### 2026-09-09 — movie night's realtime, and the overnight run

113. **Batch 35 syncs over Postgres `LISTEN`/`NOTIFY` with SSE to the browser, not Supabase
     Realtime.** Owner decision, 2026-09-09. §8.4 names Supabase Realtime and there is no
     Supabase project — #17 moved the database to Neon and left every other Supabase product
     as "a separate future integration decision".

     *Why this instead of adding a realtime vendor:* it needs no new service, no new
     credential and no new bill, and it runs inside the FastAPI process that already holds a
     connection pool to the database the votes are written to. A movie night is two people on
     a sofa for twenty minutes — a scale where a dedicated realtime service buys nothing that
     a notify channel and an event stream do not.

     *The constraint to respect:* `LISTEN` occupies a connection, so the listener must not
     borrow from the request pool for the life of a session. Use a dedicated connection per
     session and release it when the session ends, or a single shared listener that fans out
     in-process. Getting this wrong exhausts the pool and looks like the whole app hanging —
     the same silent-failure shape as Batch 8's paused query.

     *And it is one process only.* Like #60's cron, fanning out in-process is correct at one
     container and wrong at two: a second instance would not see the first's notifications
     unless both `LISTEN` on the same channel, which they would. Note it, do not design for
     scale this app does not have.

### 2026-09-09 — Batch 11 notifications and push

114. **The VAPID public key is served by the API, derived from the private key, rather than
     built into the web bundle as `VITE_VAPID_PUBLIC_KEY`. This removes a hosting step the
     overnight run had reserved for the owner.** `STATUS.md`'s plan listed setting that
     Vercel variable as one of three things that would stop and wait; it is no longer
     needed, and the variable should not be set.

     *Two reasons, and the second is the one that matters.* A build-time variable means
     push cannot work until somebody edits Vercel **and** redeploys, so the batch would
     ship "ready but inert" — and a value living only in a hosting variable has no test.
     That is precisely the shape of the TMDB outage: `TMDB_READ_TOKEN` was missing from
     Railway for an unknown length of time behind a fully green gate, because nothing in
     the code could observe its absence. The second reason is drift: two independently
     set variables can disagree, and a public key that does not match the private key
     produces subscriptions the server can never push to, with the push service answering
     `201` throughout.

     `GET /api/v1/notifications/vapid-key` derives the public half from
     `VAPID_PRIVATE_KEY` at request time, so the key a browser subscribes with and the key
     the server signs with cannot differ. It answers `{"configured": false}` when Railway
     holds no key, which is what lets the settings page say *"push is not configured on
     the server"* instead of failing inside `subscribe()` with a `DOMException`. If
     `VAPID_PUBLIC_KEY` is set and disagrees with the derived value, the endpoint logs
     `vapid_key_pair_mismatch` and serves the derived one.

     *What this does not change:* the three Railway variables stay as they are, and the
     names are still fixed by what is in Railway.

115. **Web Push is implemented directly on `cryptography` rather than on `pywebpush`, and
     the version floor is a security floor.** §17's row 2 says "pywebpush + VAPID keys";
     the VAPID half is unchanged, the library is not.

     *Why one dependency instead of four.* `pywebpush` brings `http-ece` and `py-vapid`
     with it. The encryption is about sixty lines against RFC 8291 and RFC 8188, and PyJWT
     — already a dependency — signs the RFC 8292 assertion once `cryptography` is present.
     Writing it here buys a specific kind of test: `tests/test_webpush.py` derives the
     message keys from the **receiver** side, running the browser's half of the algorithm
     against our sender's half. A library test can only prove the library agrees with
     itself, and a Web Push key-derivation error is completely silent — the push service
     accepts ciphertext it cannot read and answers `201`, so nothing anywhere reports a
     failure. The three HKDF `info` strings are pinned by their own test for the same
     reason.

     *The version floor, and what it costs.* An earlier revision of this decision pinned
     `cryptography<49` because 49+ ships no `macosx-10.15-x86_64` wheel, so the developer
     machine falls back to a Rust source build that fails there while CI installs a
     manylinux wheel happily. The audit job then refused the resolved 48.0.1 for
     PYSEC-2026-3552, -3553 and -3554. **The pin was wrong and was removed**: a vulnerable
     crypto library in production is not a price worth paying for local convenience.

     The consequence is a genuine split — **this machine runs 48.0.1, CI and Railway run
     50.0.1** — and it is recorded in `STATUS.md`'s gotchas rather than papered over. CI is
     the authority for this dependency. It is tolerable only because the surface in use
     (P-256 key generation, ECDH, AES-GCM, PEM/scalar loading) is stable across those
     versions, and because every test that exercises it runs on both sides.

### 2026-09-10 — the overnight run's own decisions

116. **§3.7's live Blu-ray.com run was not performed by an agent, and Batch 23 shipped
     without it.** The batch is otherwise complete — parser, bounds enforcement, halt
     switch, provenance, deletion, badges and filters — and production reports **0 pages
     ever fetched**.

     *Why.* #110 is explicit that this is a **risk acceptance, not a permission**: the
     site's Legal Notices prohibit automated reuse, and #108's contrary claim was wrong.
     Accepting a stated legal risk is something a person does on their own behalf.
     `docs/agent-commands/group-start.md` says the same thing for a different reason —
     *"a batch whose acceptance requires live third-party requests ... stops before those
     runs. The owner performs them."* — and Batch 19's checkpoint worked exactly that way.

     *What was done instead of asking again later:* every one of #110's conditions is a
     mechanism rather than a note. A URL that is not an exact release page is refused
     before any request; requests are sequential and spaced; a `403`/`429`/`451` halts the
     whole integration to a **database row that nothing in the application can clear**;
     every derived row carries its source URL and fetch time; and `DELETE /api/v1/specs`
     removes everything derived from the site while leaving hand-typed specs alone. The
     owner's run is therefore ten URLs and one request, not a judgement call each time.

117. **Anything that lives only in a hosting variable now reports itself on
     `/api/v1/health/ready`.** It answers `db`, `push` and `ai`.

     *Why:* `STATUS.md` records the TMDB outage as "what that sentence looks like in
     practice" — a token missing from Railway for an unknown length of time, behind a
     fully green gate, because nothing in the code could observe its absence. Batch 11's
     VAPID key and Batch 30's Anthropic key have the same shape, so both are checked by
     *loading* them rather than testing that a string is present: a malformed VAPID key
     reads `invalid`, which is a different problem from `not_configured` and would
     otherwise surface only at the first send.

     *Readiness is deliberately not failed by either.* A missing notification key is a
     missing feature, not an unhealthy container, and 503-ing would pull the whole API out
     of rotation over a setting.

118. **`STATUS.md`'s "what the live database holds" was wrong, and had been since it was
     written.** It said 3 `wanted_list` rows; the real figure on 2026-09-10 was 11, of
     which 8 are live and active — the three originals were soft-deleted and eight boutique
     titles added during the 2026-09-09 acceptance run (#111).

     *Recorded because the block is copied forward by every close-out*, which is how a
     count stays wrong for a day and would have stayed wrong indefinitely. The lesson is
     the one #111 and the TMDB outage already teach in other forms: **count it, do not
     carry it.** This run's closing figures were all read from Neon.

### 2026-09-10 — closing out the overnight run with the owner

119. **The two "wire a Railway cron" owner actions had nothing a cron could run, and now
     they do.** `src/scripts/daily_scrape.py` and `src/scripts/run_reminders.py` are the
     nightly scrape and the reminder pass as commands. The HTTP endpoints stay exactly as
     they are; nothing about them changed.

     *Why:* `POST /api/v1/scrapers/daily` and `POST /api/v1/notifications/run-reminders`
     are both `AdminUser`-authed, and an access token lives 24 hours (`auth.py`). A cron
     container has no browser, no login and nothing to refresh, so **neither endpoint was
     callable by a scheduler at all.** Batches 11 and 20 shipped the endpoint half and left
     the command half unbuilt, which is how §5.5's *"first overnight run completes"* sat on
     `OWNER-ACTIONS.md` as a console visit that could not actually be completed. It was
     found by reading the endpoints while walking the owner through his remaining steps,
     not by any test — a gate proves the code, and this was a gap *between* the code and
     the infrastructure, which is the exact class `AGENTS.md` already warns about.

     *Why a command rather than a service token.* A shared secret would have worked and was
     offered; the owner chose the scripts. They add no second authentication path to the
     API, need no credential of their own — the container already holds `DATABASE_URL` and
     the VAPID keys — and match the precedent #60 set with
     `refresh_completion_sets.py`, whose whole point was that scheduling should be *"one
     console action rather than a piece of engineering"*. The other two jobs never got
     theirs.

     *One seam moved to make it possible.* `push_sender` and `set_push_sender` were defined
     in `routers/notifications.py`; they now live in `src/services/push_transport.py` and
     the router re-exports them, so a scheduled job does not import FastAPI and the whole
     route table to obtain a transport. A test asserts the two names are one object, and
     another asserts neither script imports a router.

     *The exit code is the tested behaviour.* It is the only thing a scheduler reads, so a
     failed retailer exits 1 and names the shop and the reason, while a shop that simply
     does not stock a film exits 0 — Batch 20's distinction, restated where it decides
     something. `--dry-run` stays **opt-in** on the scrape, the reverse of `/scrapers/run`:
     a scheduled job whose purpose is to write must not default to writing nothing, because
     that failure is indistinguishable from working.

120. **A photo targets 300 KB, and that is now an owner decision rather than an
     inference.** Confirmed by the owner on 2026-09-10.

     *Why it needed recording:* Batch 25 shipped at 300 KB while two in-repo docs
     disagreed about whether the number was ever confirmed — `OWNER-ACTIONS.md` called it
     "proposed, not confirmed", `STATUS.md` and `docs/phase-batches.md` both listed it
     under settled inputs — and no `DECISIONS.md` entry existed either way. The batch made
     the disagreement cheap instead of arguing it: the target is the `PHOTO_TARGET_KB`
     setting, so a different number is an environment variable and a re-upload, not a
     migration. A phone's 4032×3024 photo stores at ~240 KB.

121. **The owner accepted `#110`'s Blu-ray.com risk on 2026-09-10 and asked an agent to
     perform §3.7's run on his behalf.** Recorded before the first request was made.

     *Why this needed his word and not an agent's judgement:* `#110` is explicit that it is
     a **risk acceptance, not a permission**. The site's Legal Notices prohibit automated
     reuse, and `#108`'s earlier reading — that absence from `robots.txt` made it allowed —
     was wrong. Accepting a stated legal risk is something a person does on their own
     behalf, so Batch 23 shipped the whole machine and fetched nothing:
     `specs_integration_state` read `fetch_count: 0` for a day. He was offered three
     options — run it himself, accept the risk and have it run for him, or leave §3.7
     deferred — and chose the second.

     *What the acceptance does **not** change:* every one of `#110`'s bounds stays enforced
     by the code, not by whoever runs it. Exact release URLs only, the search routes refused
     by name, one request at a time five seconds apart, an honest user agent, no redirect
     following, and a `401`/`403`/`429`/`451` halt that abandons the rest of the batch to a
     database row nothing in the application can clear. The caller cannot loosen any of it,
     which is the point of having put them there.

     *The ten discs were matched by title **and** format against the collection, not by
     title alone*, and the URLs came from a browse listing rather than the site's search —
     the route `#110` forbids and `is_release_url` refuses. **Edition and region were not
     verified against the physical discs**, which is why provenance matters: every derived
     row records `specs_source_url` and `specs_fetched_at_utc`, so a wrong edition is
     visible rather than silently merged, and `DELETE /api/v1/specs` removes the lot.

122. **Batch 23's extractor could not read a single real Blu-ray.com page, and its tests
     could never have caught that, because the fixture was invented.** Found on 2026-09-10
     by §3.7's first live run: ten pages fetched, `200` on all ten, **zero specs extracted**
     — `"no specs found on the page"` ten times, and nothing written to any
     `collection_item`.

     *The cause.* The parser looked for `<div class="row"><strong>Codec:</strong> …`. The
     site serves `<span class="subheading">Video</span><br>Codec: MPEG-4 AVC<br>Resolution:
     1080p` — section headings with bare `Label: value` lines separated by `<br>`, and no
     `<strong>` anywhere. `_label_of` returned `""` for every node on every page, so
     `_rows` matched nothing and `extract` returned an empty `DiscSpecs` every time.

     *Why the suite was green.* `test_specs.py`'s `PAGE` constant was **hand-written to
     match the parser**. Parser and fixture agreed with each other and neither had ever
     met the site. Eleven extraction tests passed against markup that has never existed.
     This is `AGENTS.md`'s "a green run is not evidence the app runs", in the one place the
     project had already been bitten twice — the missing TMDB token and the scraper *test*
     button that saved nothing.

     *The fix, and the part that matters.* `_section_rows` parses the real structure, and
     `tests/fixtures/bluray_com_release_page.html` is now **captured markup** — three
     regions of a real release page, verbatim, price cell included. `TestTheFixtureIsReal`
     asserts that it stays captured: that it carries its provenance line, that it uses
     `<span class="subheading">` rather than `<strong>` rows, and that the price cell is
     still in it. A fixture written to match the parser is the bug; a test that says so is
     the guard.

     *Two things the run did prove.* Every one of #110's bounds worked — ten sequential
     requests five seconds apart, honest user agent, no redirect following, no `403`, no
     halt — and `apply_specs` correctly declined to write anything, because `DiscSpecs.
     is_empty` is checked before a row is touched. **A parser that stops matching the site
     writes nothing rather than blanking 1,857 rows.** That is why the failure cost only
     ten wasted requests.

     *And one thing it re-taught.* The live run was not a formality after a green gate; it
     was the only thing in the entire project that could have found this.

     *Then the second real page broke the first fix, which is the part worth keeping.* With
     one captured fixture the parser passed; the re-run stored **one** audio track for
     `Blade-Runner-2049-4K/189774` where the page lists **six**, and gave that track a
     channel count belonging to the line below it. Blu-ray.com wraps the tracks in a
     `<span title="…">` on some pages and not on others, so a `_lines` that read only
     top-level children flattened all six into a single string. **One real page is a
     sample of one.** `_flatten` recurses now, both pages are fixtures, and the 4K one is
     kept precisely because it disagrees with the other about its own markup — it also
     turned out to be the only one carrying an HDR block, which the flattened version was
     dropping too.

123. **"Stop looking" was silently wiping every buying preference on the want it toggled.**
     Found on 2026-09-10 while adding a control to set a maximum price on an existing want.

     `PUT /api/v1/wanted/{id}` **replaces the row** — `WantedUpdateRequest` defaults every
     field to `None` and the handler assigns each one unconditionally. The web app's only
     call site sent `{isActive}` alone, so each press of "Stop looking" or "Look again"
     also set `preferred_format`, `preferred_edition`, `max_price` and `notes` to null.
     No error, no warning, and `admin_actions` recorded it faithfully as a change nobody
     had asked for.

     *The endpoint is not the bug.* `PUT` means replace, and that default is deliberate.
     The client was sending a `PATCH` body to a `PUT` route. So `fullUpdate()` builds the
     complete resource with only the changed field overridden, and a test asserts the
     toggle round-trips every preference. A second test pins the endpoint's own contract,
     so the next person to meet this reads it as the contract rather than patching the API
     to be lenient.

     *`currency` was the same bug one layer down*, and is fixed with it: `updateWanted`
     hard-coded `'GBP'` where no caller could override it, so any non-GBP want would have
     been reset by any edit. Every want happens to be GBP today, which is exactly why it
     would have gone unnoticed.

     *Why it surfaced now:* §5.6 needs a want whose `max_price` sits above its current
     price, and there was **no way to set one on a want you already had** — the field
     existed only on the add form. Adding that control meant reading the update path, and
     the wipe was sitting in it. The acceptance criterion found a second bug the suite had
     no reason to look for, which is the same lesson as `#122` in a different corner.

124. **`railway config apply` would have deleted two live credentials, and had been able to
     since the day they were set.** Found on 2026-09-10 by running `railway config plan`
     before adding the cron services — the plan read `2 to add, 3 to change, **2 to
     destroy**`, and the two destroyed were `api.ANTHROPIC_API_KEY` and
     `api.TMDB_READ_TOKEN`.

     *Why:* `.railway/railway.ts` is the declared source for the environment, and IaC
     removes what the file does not declare. Both tokens were set in the Railway console on
     2026-09-09 and never added to the file, so drift-removal read them as deletable.
     Applying would have recreated **the exact TMDB outage of 2026-09-09** — every
     TMDB-backed feature answering 502 behind a green gate — and taken the AI assistant with
     it.

     *And the JWT secrets were worse in a quieter way.* They were declared as
     `context.randomString(...)` with `isSealed: true`. A sealed variable cannot be read
     back to compare, so every `plan` reported them as changing; applying would have minted
     new secrets, **signing both people out and invalidating every refresh token**. They are
     generated once, at service creation, and there is no reason to generate them again.

     *The rule this settles:* **anything that exists in Railway must be declared here, and
     anything already set is declared `preserve()`.** That keeps `apply` non-destructive
     without putting a single secret in the repository — `preserve()` names the variable and
     leaves the value where it is. All ten of the API's variables now read `preserve()`
     except `ENVIRONMENT`, and the plan is `0 to destroy`.

     *Why it went unnoticed:* `.railway/README.md` said "do not run `apply` outside the
     explicit phase-closeout workflow", which reads as caution about *changes you meant to
     make*. The real hazard was the opposite — a change nobody had authored, produced by the
     file's silence. The README now says to read the destroy count first, and `#117`'s
     readiness probe is what would have caught the aftermath.

125. **An empty results page is neither a failure nor a claim, and now has its own state.**
     The owner's first real nightly run recorded **11 failures out of 17 attempted** on
     2026-09-10. Checked against the live sites: **eight were not failures at all.**

     Arrow Video answered *"Sorry We Couldn't Find Any Results Matching 'Cross of Iron
     blu-ray'"*; 101 Films answered *"Search: 0 results found"*; Second Sight the same.
     They do not carry those films. The runner classified all three as scraper breakage
     because `not_stocked` required `titled_cards > 0` — it handled *"results returned,
     none matching"* and let *"no results returned"* fall through to the failure branch.

     *Why that mattered more than a wrong number in a report.* Those failures fed
     `_record_failure`, and three consecutive runs with no successes **auto-disables the
     retailer**. The comment directly beneath the branch already stated the guarantee the
     code was not delivering — *"neither has one that answered 'no' — three digital wants,
     or three films a boutique label does not carry, would otherwise switch off the whole
     app."* It had not bitten only because each shop happened to price one film that night;
     all five still read `fails=0`. With the cron now running unattended, three quiet
     nights would have switched a shop off silently.

     *Why it is not simply `not_stocked`.* **Zero cards is what "we do not stock that" looks
     like and what a broken selector looks like, and nothing in the response tells them
     apart.** Calling it `not_stocked` would let a parser that had stopped matching read as
     a healthy "nothing found" for ever — which is exactly how `#122` hid for a day, one
     decision earlier on the same morning. So `no_results` is recorded and reported, kept
     out of the auto-disable arithmetic, and a retailer answering that way for *every* want
     in a run is **flagged** (`last_scrape_status = "no_results"`) rather than disabled.
     `consecutive_failures` is deliberately left untouched rather than reset, so a genuinely
     broken shop cannot launder its failures by returning one empty page.

     *The other three were real, and the opposite kind of bug.* Zavvi renders **two price
     markups on one page**: a multi-variant listing wraps the figure in
     `.product-variant-price`, a single-price listing puts it straight into the
     `product-price` wrapper. The selector read only the first, so a real **£16.99** on
     `Castle Freak` was fetched, parsed and discarded. Missed alerts, not wrong ones — it
     failed safe — but missed all the same.

     *And fixing that exposed a third.* `_select_one` used `select_one`, which for a
     comma-separated selector returns whichever matches first **in the document**, not
     whichever selector was written first. Second Sight's
     `".price-item--sale, .price-item--regular"` is plainly written expecting sale-first
     precedence and never had it. Selector lists are now tried in order, which is what
     every such config in this file already meant.

     ***This supersedes one clause of `#107`***, and the clause was deliberate, so it is
     named rather than quietly dropped. #107 wrote: *"A page that yields no titled listing
     at all is the redesign case the counter exists to catch, and **still takes a strike**"*
     — auto-disable had to stay reachable or it would never fire again. That reasoning was
     sound and its premise was wrong: it assumed zero listings means the site changed. The
     first real unattended run measured the opposite — **eight of eleven were shops
     answering a question honestly**, and only three were anything broken. The redesign case
     survives, but it is visible one level up: a redesign makes *every* want return nothing,
     which is what the per-retailer flag now says. The owner chose visibility over
     auto-disable on 2026-09-10, and #107's strike is withdrawn on that basis.

     *And a fourth bug, found while making the third observable.* `/retailers` renders each
     run through `scrapeRunVerdict`, whose denominator was `attempted - notStocked`. But
     `attempted` **already excludes** `notStocked` — that is #107's own doing — so the page
     subtracted it twice, and the real run of 2026-09-10 (17 attempted, 23 not stocked, six
     discs priced) rendered as *"Nothing to price — no shop had any of the wants"*. The
     response docstring asserted the wrong contract and the web tests encoded it, so two
     sources agreed with each other and disagreed with the producer. The denominator is
     `attempted` minus `noResults` alone; everything else in `attempted` was a pair somebody
     could have priced.

     *The general lesson, for the third time today:* **"we found nothing" is a measurement,
     not a conclusion.** `#122` was a parser that found nothing and was believed; this is a
     runner that found nothing and blamed itself. Both were only visible from a live run —
     and the fourth was only visible because the third made it worth reading the report.

### 2026-09-10 — eBay, ahead of Batch 28

126. **eBay Buy API production access needs no partner approval, and Group I's checkpoint
     was built on a premise that turned out to be false.** A self-service production
     keyset calls the Browse API at the default 5,000 requests/day. Verified live on
     2026-09-10: `q="Blade Runner 2049 Blu-ray"`, `X-EBAY-C-MARKETPLACE-ID: EBAY_GB`,
     **HTTP 200, `total=308`**, real GB prices.

     *Why this is recorded rather than just noted:* the research that scheduled Batch 28
     read eBay's own Buy API requirements page — *"intended for eBay partners only… you
     must apply through the eBay Partner Network"* — alongside forum reports of small
     developers being rejected, and concluded access was roughly a coin toss. The ledger's
     risk note said *"Production API access is an application, not a given — start it
     early, it gates the batch."* **It does not gate the batch.** The partner process
     governs the genuinely restricted Buy APIs; plain `item_summary/search` is not one of
     them.

     `OWNER-ACTIONS.md` #5's application was filed on 2026-09-09 and is now moot. This also
     clears **Batch 24**, whose UPC→title chain depends on the same Browse search (#16).

     **What has *not* changed: sold comps remain unobtainable.** Marketplace Insights is
     still closed to new applicants, and eBay put sold/completed listings behind a login
     wall in late August 2026 — so the scrape-it fallback is now walled as well as
     forbidden. #16's ruling stands, and its "current asking prices" labelling requirement
     stands with it, on stronger ground than when it was written.

127. **We subscribe to eBay marketplace account deletion/closure notifications rather than
     claim the "not persisting eBay data" exemption.** `POST /api/v1/ebay/account-deletion`
     acknowledges with 204 and does nothing else.

     *Why:* eBay activates no production keyset until a developer does one or the other.
     The exemption requires that the application *"must not persist eBay data"*, and eBay
     attaches *"penalties or having their account disabled"* to claiming it wrongly. Batch
     28 will persist eBay-derived listing data in `price_checks` — `title_snapshot`, `url`,
     `price`. That is listing data rather than user PII, and the exemption is plainly aimed
     at PII, so the exemption would probably have been defensible. **Probably is not a good
     enough standard when the downside is account disablement**, and the cost of
     subscribing is one endpoint that returns 204.

     The endpoint is the app's **third unauthenticated route**, after Batch 17's `.ics`
     feed and Batch 27's gift links. It is safe on three deliberate properties, each with a
     test: it reads and writes nothing (no database session is imported in that module),
     it carries **no rate limit** because eBay polls it and reads a 429 as an outage, and an
     unconfigured deployment answers 503 rather than hashing an empty token into a
     plausible-looking wrong digest.

     Verified end to end on 2026-09-10 from eBay's own servers, not just our probes: their
     64-character validation challenge answered 200, and their test notification `POST`
     answered 204.

128. **`EBAY_ACCOUNT_DELETION_ENDPOINT` is declared in `.railway/railway.ts` as a literal,
     not `preserve()` — the only env var there that is not a secret.**

     *Why:* eBay hashes the URL **it** holds into every validation challenge, so ours must
     match byte for byte — scheme, host, path, trailing slash — or validation fails with
     nothing diagnosable to show for it. A literal makes IaC enforce that identity instead
     of trusting a console field nobody re-reads. The URL is already public in
     `.railway/README.md`. `routers/ebay.py` reads it from config rather than reconstructing
     it from the request, because behind Railway's proxy the app sees a different host and
     scheme than the caller used.

     `EBAY_VERIFICATION_TOKEN` stays `preserve()` like every other secret, so no token
     enters the repository. **`preserve()` on an unset variable is a no-op** — `config plan`
     confirmed it creates nothing — so that one is set in the console by hand.

     Both were declared for the reason #124 records: a variable set in the console and left
     undeclared reads as drift, and `apply` plans to remove it. Undeclared, this pair would
     have returned the endpoint to 503 on the next apply, and eBay emails the owner when an
     endpoint stops answering.

129. **eBay prices are segmented on `conditionId`, never on `condition`, and a median is
     reported per format and condition with its sample size — never one number over a
     keyword search.**

     *Why, measured rather than assumed.* 310 live GB listings for `"Blade Runner 2049
     Blu-ray"` on 2026-09-10 segment like this:

     | Segment | n | Median | Range |
     |---|---|---|---|
     | everything — the naive median | 310 | **£30.45** | £1.17–£1199.00 |
     | collector editions | 80 | £105.61 | £1.17–£924.70 |
     | 4K / UHD — a different format | 70 | £50.45 | £9.73–£1199.00 |
     | bundles / multi-film | 28 | £12.05 | £4.49–£94.29 |
     | **plain Blu-ray — the actual product** | 132 | **£12.21** | £2.24–£368.35 |

     **The naive median overstates the real disc by 149%.** A keyword search for a Blu-ray
     returns the 4K, the steelbook, the Filmarena limited edition and a double-bill with
     *Alien: Covenant*, and a median across them is confident, plausible and wrong — the
     failure mode this repo has now met three times (#79, #110's risk note, and #122's
     invented fixture).

     **And `condition` cannot do the segmenting.** It is a localised display string from the
     seller's own marketplace: those 132 plain Blu-rays carried **16 distinct condition
     values for about five real conditions** — `New` / `Brand New` / `Brand new` / `Neu` /
     `Entièrement neuf`; `Very Good` / `Very good` / `Sehr gut` / `Très bon`; `Like New` /
     `Like new` / `Neuwertig` — plus one listing with no condition at all. `conditionId`
     is the numeric code (1000 New, 3000 Used, 4000 Very Good, 5000 Good) and is the only
     stable key. A missing condition is its own bucket, never a default.

     Three consequences for Batch 28: the match filter is where the batch's effort goes,
     not the median function; a result failing the match assertion is a **failure, never
     data**, exactly as #79 requires of the scrapers; and the segmentation must key on
     category IDs and `conditionId` rather than title regexes — the regexes used to take
     the measurement above are themselves too fragile to ship, which is visible in the
     £368.35 outlier that survived them.

### 2026-09-10 — the UI redesign's live pass

130. **A tone colour gets two tokens, because a filled surface and a status word have
     incompatible contrast rules.** `bg-destructive` carries white at 5.71:1 in dark; the
     same value as `text-destructive` on a dark card measures **3.13:1**. Champagne is the
     identity accent on ink and **1.92:1** on cream. One value cannot serve both jobs.

     So `theme/tokens.ts` declares a `--<tone>-text` variant for all six semantic tones in
     both themes, and `tailwind.config.ts` points Tailwind's **separate `textColor` scale**
     at them. `text-*` resolves to the text-safe value while `bg-*`, `border-*` and
     `ring-*` keep the surface value — **no call site changed**, which matters because
     `text-destructive` is the error colour in about thirty places, most with
     `role="alert"`. `foreground` is re-declared per tone so `text-primary-foreground` and
     its siblings survive the override; `fill` is overridden for `accent` alone so the
     rating star cannot render a champagne body with a bronze rim.

     *Why this rather than repainting:* the alternative was editing ~37 call sites to a
     second class name, which a future component would silently not adopt. The scale split
     makes the correct thing the default.

     Values were **solved** for the nearest passing lightness and rounded in the safe
     direction, not chosen by eye. `src/theme/contrast.test.ts` now asserts all 42 pairings
     — including the translucent tints badges paint beneath their own text — so a palette
     tweak fails the gate instead of shipping.

131. **A coarse-pointer floor must live in `@layer utilities`, not `@layer components`.**
     `.touch-target` had been declared in `components`. Tailwind emits `components` before
     `utilities`, and `.touch-target` and `.min-h-8` carry identical specificity, so the
     smaller value simply came later and won. **Every control that appeared to opt in was
     silently unchanged** — filter chips 32px, small buttons 36px — while the audit
     recorded touch sizing as addressed.

     Moved to `utilities`, it wins. Verified pointer-aware: the filter chip is 32px on a
     fine pointer and 44px on a coarse one, so desktop density is untouched. A companion
     `.touch-hit` grows only the hit area, via a centred transparent pseudo-element, for
     controls whose drawn size carries meaning — a 24px switch track reads as a switch, a
     44px one reads as a bar.

     *The general lesson:* a utility that corrects another utility has to outrank it, and
     in Tailwind that is decided by layer order, not by where the class appears in the
     `class` attribute. Anything declared in `components` to override a utility is a
     no-op.

132. **`document.title` gets exactly one owner.** `App.tsx`'s `RouteTitle` and `AppLayout`
     both wrote it. They could disagree — `Page not found` against `Film archive` — and the
     archive root rendered "The Real MCU · The Real MCU". `RouteTitle` owns it router-wide;
     `AppLayout` keeps `routeLabel` for the mobile header only.

### 2026-09-10 — the brand integration

133. **The favicon is an ICO, and there is deliberately no SVG alternative.** The approved
     family draws 16 px on its own 16×16 grid — it keeps the M silhouette and the centre
     case and *omits the disc*, because the disc's hub cannot survive there. 32 and 48 come
     from a separately drawn compact optical master. A scalable `image/svg+xml` favicon
     would be preferred by every browser that supports one and would render a shrunk
     version of the larger drawing at 16 px, which is precisely what the hand-hinted master
     exists to prevent.

     So `index.html` declares `favicon.ico` alone, with `sizes="16x16 32x32 48x48"`, and the
     browser picks the entry that matches the slot. The temporary `favicon.svg` and
     `mcu-icon.svg` blue discs are deleted rather than kept as a fallback.

134. **The desktop sidebar draws the horizontal lockup at 240 px against a 280 px approved
     minimum, and the trade-off is recorded in the call site rather than hidden.** The
     permanent sidebar is `w-[17rem]` with `px-4`, so 240 px is everything it has. Reaching
     280 px would mean widening navigation by about 40 px at every desktop width, taking
     that space from the main column at exactly the sizes — 1024 to 1280 — where it is
     scarcest. The completed UI's layout won.

     What is actually at risk below the minimum is the `CINEMATIC UNIVERSE` subtitle: at
     240 px its cap height is about 5 CSS px. Measured at DPR 2 — which is every display
     either person uses — that is 480 device pixels of lockup and the subtitle is crisp; on
     a 1× display it reads as a tracked band rather than as words. The wordmark itself is
     unambiguous at both.

     `BrandLockup` therefore **warns in development** when it is drawn under a minimum, and
     the warning is silenced only by passing `underMinimumReason` — a sentence that shows up
     in review. A lockup quietly shrunk to fit its container is the ordinary way an identity
     decays; this makes it a visible decision instead.

     In the mobile drawer the same panel has under 200 px once the close button is placed,
     which is past arguing about. There the compact mark carries the identity and the short
     name carries the words.

135. **No semantic interface colour was retuned to match the logo, and no new colour token
     was introduced either.** The brief allowed explicit brand tokens "if needed". They were
     not needed: every branded surface renders approved artwork that carries its own palette
     inside the SVG or PNG, and the chrome around it — borders, plates, eyebrows — already
     had correct semantic tokens. Adding a `logo-*` scale that nothing consumed would have
     been dead code with a design-system label on it.

     The four existing `brand-*` tokens were left alone as well. They are approximations of
     the logo palette (champagne at 41° against the artwork's 33°) used for scrims and the
     photo lightbox, and `theme/tokens.ts` invites the identity pass to tune them — but
     tuning them changes shipped surfaces for no visible gain, and the contrast work in #130
     is calibrated against the values that are there.

     What *was* corrected is not a semantic colour at all: `theme_color` and
     `background_color` were `#0B1220`, the placeholder identity's blue, a colour the
     shipped interface never draws. An installed PWA opened on a splash colour from a
     deleted logo. Both are now `#120F0D`, which is `hsl(24 15% 6%)` — the value
     `applyThemeTokens` has been writing over the meta tag at runtime all along.

136. **The notification badge is the micro mark in one colour, not the display-size
     monochrome outline master.** A `badge` is a mask: Android draws it at 24 dp and keeps
     only the alpha channel. `stack-mark-mono-white.svg` was tried first — it is the
     family's designated one-colour asset — and at 24 dp its 32-unit strokes land under a
     pixel and the mark resolves to a grey smudge. Proved by rendering it at the real size,
     not by reasoning about it.

     The badge is built instead from the **micro mark's** geometry: the same paths as
     `micro-mark-16.svg`, hoisted to shared constants in the builder so there is one copy,
     with the centre case knocked out rather than filled crimson — colour is what separates
     the case from the M at that size, and a mask has no colour to separate them with. It is
     padded to 86% so a platform crop cannot take the outer walls. The result is a bold,
     unmistakable M at 24 dp.

     *The general rule this follows is the system's own:* rich at display size, optically
     strengthened below. A badge is the smallest context the identity has; it gets the
     smallest-tier master, in one colour.

137. **The share card is built from the rights-independent identity, and never from the
     photographic editions.** `logo-system/responsive/social-card-1200x630.png` already
     existed and is handsome, but its letterforms are filled with *Jaws*, Bogart, Hitchcock
     and *An American Werewolf in London* — real film stills gathered as art direction, not
     cleared for redistribution. An `og:image` is a redistribution surface by definition: it
     is fetched and re-hosted by every chat client that renders a preview.

     `stack-family/social-card-1200x630.png` is generated instead — the horizontal lockup
     optically centred on the ink field, composed by the builder from approved vector
     artwork. Optically, not mechanically: the lockup's viewBox carries asymmetric clear
     space, so centring the box leaves the logo visibly left of centre. The builder measures
     the drawn artwork's alpha bounds and centres those.

     The card's paths in `index.html` are **relative**, so preview, production and localhost
     each resolve against themselves and no hosting domain is baked into a tracked file.

138. **The mobile header shows the short app name, not the route label** — superseding the
     last sentence of #132, which kept `routeLabel` in `AppLayout` for exactly that slot.
     The header had no brand anchor at all, and the label it did show repeated the page's
     own `h1` a few pixels below it. The mark went from 28 px to 32 px at the same time: the
     compact master is drawn for 32–96 px, and the placeholder had been sitting under it.

     `routeLabel` and its `navItems`/`useLocation` imports are removed rather than left
     unused. Route context survives in the visible `h1` and in `document.title`, which #132
     gave a single owner.

139. **The app ships brand assets whose generator is not in the repository, and that is now
     a smaller hole rather than a new one.** `apps/web/public/brand/` holds the 18 files the
     app references, 744 kB, committed. `docs/brand/logo-system/` — the builder and the
     other 180-odd files — remains untracked for the reasons in `OWNER-ACTIONS.md` #15.

     `scripts/brand-sync.mjs` is the bridge: a tracked manifest naming every shipped file
     and the surface that uses it, which installs them and, with `--check`, reports drift
     against the design system. `docs/brand-integration.md` records the mapping in prose.
     Neither can run in CI, which clones a repo without `docs/brand/` — they are local
     tools, and the report says so rather than implying a gate that does not exist.

140. **The personalised photographic edition is a commemorative reveal, not the app's
     everyday logo** — superseding the integration hierarchy introduced by `00414f5`.
     Rendering that integration made the failure measurable: the desktop login cropped
     the wordmark into partial letters and placed copy across faces; the 40 px mobile and
     80 px sidebar posters collapsed into noisy thumbnails; and loaders made a private
     collage the dominant identity on every navigation transition.

     The app now uses the compact vector mark for navigation and loading, the complete
     transparent horizontal lockup on desktop sign-in, concept art for platform icons, and
     the personalised poster only at 192 px in the authenticated onboarding welcome. This
     is not a retreat from the personalised art. It gives that art one high-value reveal
     where its detail can be seen, instead of spending it everywhere at sizes where it
     cannot. The public share card is restored to the rights-independent 1200×630 master,
     as #137 already required.

     A source-level regression test owns the boundary: photographic poster artwork may
     appear in `OnboardingPage` and nowhere else in TSX, hero photos are not interface
     chrome, and Open Graph/Twitter metadata points to the social-card master at its native
     dimensions.

141. **Every remaining batch's acceptance criteria are recovered up front, not one batch at
     a time.** #54 closed the gap Batch 10 opened, but left the repair to whoever next ran
     a batch — *"batches not yet started still have the gap"*. On 2026-09-11 the seven
     planned batches without criteria — **21, 22, 24, 29, 33, 34, 38** — had theirs
     recovered verbatim from §16 at `d94a6b8~1` in one pass. The gap is now closed for the
     whole queue, and a future agent should **not** re-recover; the ledger is the place to
     read them.

     *Why up front rather than at batch start:* recovering a criterion is also the moment
     you find out it is wrong, and three of these were. 5.7 names **Recharts**, a
     dependency Batch 14 explicitly declined when it drew §13.1's charts in CSS. 3.4's
     lookup chain names **Amazon**, one of the four shops #91 ruled out permanently. 10.1
     names **Supabase Vault**, a product this app has not used since the re-scaffold. Found
     at batch start, each of those is a mid-batch surprise; found together, they are a
     paragraph in the ledger the batch reads before it writes anything.

     *One deliberate deviation from verbatim,* following Batch 11's precedent: the tier
     emoji is kept, the `Sonnet 4.6` / `Opus` annotation is dropped. Those names are the
     decay `docs/phase-batches.md` exists to stop, and the model each batch needs is in its
     own table. All 69 quoted lines were checked against the archived doc programmatically
     before the section was committed.

     *Two stale claims in the same ledger were corrected rather than left to contradict the
     new section:* the Batch 33 risk note said app-starter ships no `cryptography`
     dependency — it has been a direct dependency since Batch 11, which needs it for RFC
     8291 Web Push, so what is net-new is **key management**, not the library; and Group H
     still said Batch 24 waits on eBay, which `OWNER-ACTIONS.md` #5 closed on 2026-09-10.

### 2026-09-12 — Batch 28 eBay integration

142. **Phase 4.3's Option A describes something eBay does not do, so Option B is the
     primary path — and the prefill parameter is `title`, which is not one of the three
     names that look right.**

     The phase reads *"Option A (preferred): eBay Sell API draft listing creation · Option B
     (fallback): pre-filled eBay listing URL"*. There is **no eBay API that creates a Seller
     Hub draft.** An Inventory API offer is invisible until it is *published*, and
     publishing produces a live listing with a buyer on the other end — not a draft for
     review, which is the whole shape Option A describes. Option A would also require
     storing a refreshing eBay **user** token for a real selling account, opted into
     business policies: the class of third-party credential this project deliberately
     sequences late (Batch 33) and has never held. Inverting a stated preference is a
     decision, so it is recorded here rather than silently implemented.

     **`docs/phase-batches.md` flagged that nobody had confirmed Option B still worked**,
     and that if prefill were gone 4.3 would have no remaining path at all. Checked in a
     browser on 2026-09-12 against `ebay.co.uk/sl/prelist/suggest`:

     | Parameter | Result |
     |---|---|
     | `?keyword=` | form renders, box **empty** |
     | `?q=` | form renders, box **empty** |
     | `?sugKw=` | form renders, box **empty** |
     | `?title=` | form renders with the box **pre-filled** |

     So the mechanism survives and the three obvious names are the three that fail
     *silently* — the button works, the form opens, the box is blank. That is why the URL is
     built in `src/ebay/listing.py` with a test pinning the parameter, rather than
     interpolated at a call site.

     The form is step one of three and has exactly one field, so condition, price and photos
     are set by the seller afterwards and the title carries everything useful — hence
     `suggested_title`, which packs film, year, format and condition into eBay's 80
     characters and drops components from the right so a long title never loses the film's
     name to a truncation.

     **The app therefore never holds a selling credential and never creates a listing.**
     "Admin publishes from eBay" is literal: it is a link, opened by a person signed in as
     themselves.

143. **The match filter is built from eBay's own category ids and from *position* within a
     title, not from a blocklist of words — and every guard in it was measured against two
     captured 200-listing payloads rather than imagined.**

     #129 said the batch's effort belongs in the match filter and that its own measuring
     regexes were too fragile to ship. `tests/fixtures/ebay_browse_{blade_runner_2049,jaws}.json`
     are verbatim production responses (`EBAY_GB`, 2026-09-11, 200 listings each), and every
     rule below exists because those files contain a listing that breaks the rule's absence:

     - **`leafCategoryIds` is the strongest gate.** 185 of 200 Blade Runner results are leaf
       `617` ("DVDs & Blu-rays"); the rest are art prints, a DVD player, memorabilia and an
       audio book, each with the film's name in the title and a plausible £ price.
     - **Category cannot segment format.** `617` holds DVD, Blu-ray and 4K alike, so format
       comes from the title via the scrapers' own `primary_format` — including its rule that
       the *highest* format named wins, which matters here for a reason it was not written
       for: sellers append "- DVD" to Blu-ray listings as a keyword.
     - **A bare 1–2 digit number after the title is a sequel.** This is the gap that makes a
       general-purpose matcher insufficient: `extract._normalise` drops tokens of two
       characters or fewer, so "Jaws 2" and "Jaws" reduce to the same word and the scrapers'
       `_meaningful_extras` cannot tell them apart. 33 captured Jaws listings are Jaws 2, 3
       or 4.
     - **A content word after the title is a subtitle, and a subtitle is a different film.**
       "Jaws: The Revenge", "Blade Runner 2049/Final Cut", "Jaws E.T. Extra-Terrestrial…",
       "Piranha … Jaws Homage" — 15 captured listings, none of them numeric, all of them a
       different film.
     - **`_meaningful_extras` itself is deliberately *not* reused.** eBay titles are keyword
       dumps; it reads "KZVG The Cheap Fast Free Post" as evidence of another film and
       rejects an ordinary Blu-ray.

     **Two guards were wrong on the first attempt and the fixtures caught both**, which is
     the entire argument for capturing rather than inventing them:

     1. `blu` and `dvd` were on the "a number here is a quantity" list, so "Jaws 3
        Blu-Ray (2016)" and "Jaws 2 - DVD" read as quantities and were priced as *Jaws*.
        Nine wrong listings. A number followed by a *format* is a sequel; only a counted
        noun makes it a quantity.
     2. A BBFC age rating is a bare number: "Blade Runner 2049 [15] 4K UHD" was rejected as
        a fifteenth instalment. Ratings are stripped before tokenising — narrower than
        exempting 12/15/18, which would admit "Ocean's 12" as "Ocean's".

     **The costs are stated rather than hidden**, per the trade `extract.MEDIA_MARKERS`
     already makes: two genuine Jaws Blu-rays are lost because their sellers filed them
     under "Other" and "Audio Books"; four are lost because an actor's name sits where a
     subtitle would ("Jaws (Roy Scheider)"), and actors' names cannot be enumerated; one is
     lost to a seller repeating the title. Each has a test naming it. A stated failure is
     better than a wrong number.

     Measured end to end on the captured payloads: the naive median over everything a
     keyword search returns is **£24.74** against a matched plain-Blu-ray median of
     **£9.99** from 29 listings — the same shape as #129's £30.45 against £12.21, taken with
     a different method a day later. `test_ebay_pricing.py` re-takes that comparison on
     every run, because a filter that silently degrades to "accept everything" leaves every
     other test green.

144. **A "UK median" means GB sellers, the answer is a table rather than a number, and the
     rejections are part of the answer.**

     Three shape decisions, each with a failure behind it:

     **GB only, by default.** eBay GB returns overseas sellers with their prices converted
     into GBP and says nothing about import duty — 52 of the 200 Blade Runner listings ship
     from Japan, Canada, the US, Germany or Australia. The criterion asks for a *UK* median,
     so `country` defaults to `"GB"` and `null` opts out.

     **Segment on `(format, edition, conditionId)`, never on `condition`.** #129 established
     the last part; `edition` is the new axis, splitting boutique steelbooks — FilmArena,
     Relite Media, Blufans, KimchiDVD, Mondo, Cinemuseum, The Film Vault — from the standard
     retail disc. They run £150–£925 against £9.99 and are most of #129's 149%. They are
     **segmented, not rejected**: it is a real market, and Batch 29 may want it.

     **`sampleSize` is mandatory at the wire and on screen.** A median over three listings
     and a median over sixty look identical on a card.

     **`rejected` is returned to the caller.** A search that matched 4 of 200 is either a
     rare disc or a broken filter, and the tally is the only thing that tells them apart —
     the lesson #122 cost ten live requests to learn. `unusable` is counted separately from
     rejections, because a rise there means eBay changed its response rather than a keyword
     search being noisy.

     **And `ebay` joins `push` and `ai` on `/api/v1/health/ready`.** `EBAY_CLIENT_ID` and
     `EBAY_CLIENT_SECRET` live only in Railway; without the field, the only way to learn
     they were missing would be to ask for a price and read a 503 — which is the shape of
     the TMDB outage of 2026-09-09 exactly.

### 2026-09-12 — Batch 29 format upgrade and sale tracking

145. **A sold disc keeps its row. "Removes from active views" is a change to what
     *owned* means, not a soft delete — and the reason only shows up in ninety days.**

     §4.4's acceptance reads *"marking sold removes from active views, remains in
     audit/trash"*, and the obvious implementation is to soft-delete the item so the trash
     machinery Batch 15 already built hides it. That is wrong: §6.30 **auto-purges the
     trash after 90 days** (`services/trash.py`, `PURGE_AFTER`). A sold disc routed
     through `deleted_at` would be permanently destroyed a quarter later, taking the
     record of what it fetched with it — the one fact the sale produced.

     So `listing_status` alone decides, the row is never deleted, and **`owned_copy()`**
     in `models/collection_item.py` is the predicate that removes it from the views.

     **`listed_for_sale` counts as owned.** A disc advertised is still a disc in the
     house; hiding it at the moment of listing would make "I listed it" and "I lost it"
     look identical.

     **The word "owned" was previously written out nineteen times across seven routers.**
     A rule applied in eighteen of nineteen places is not a rule, and nothing in a test
     suite notices the nineteenth: the query works perfectly and quietly counts a disc
     somebody sold. `test_listing_status.py` reads the router source and fails on a
     twentieth bare `CollectionItem.deleted_at.is_(None)`.

     **One exception, and it is in the source as well as here.** `stats.py`'s
     spend-over-time keeps every row it ever had, because **selling a disc does not
     un-spend the money you paid for it.** "What I own" and "what I paid" are different
     questions and only the first one changed.

     **`GET /movies/{id}/copies?includeSold=true`** exists so "removes from active views"
     does not come to mean "unreachable" — it is the one surface allowed to show a gone
     disc, and the film's own page uses it to render them in a separate section below the
     owned ones.

146. **The listing transition is logged as an `update`, not as a new `listing_sold`
     action type — and `listing_status` had to be added to the audited field set before
     anything was logged at all.**

     Two findings, in the order they appeared.

     First, the endpoint wrote **no audit row**. `AUDITED_ITEM_FIELDS` did not include
     `listing_status`, `listing_price` or `ebay_listing_url`, so `diff_snapshots` returned
     `{}` and the "only log a real change" guard correctly suppressed the entry. A sale
     that left no trace, which is the single thing §4.4's criterion asks for. The three
     fields are audited now.

     Second, a bespoke `listing_sold` action type is **refused by the database**.
     `ck_admin_actions_action_type` in migration 008 constrains the column to §3.20's
     closed vocabulary — `create`, `update`, `delete`, `restore`, `bulk_import` —
     deliberately, *"because the log's value is that it can be trusted later"*. Widening a
     settled vocabulary is a decision for its own batch, not a side effect of this one, so
     a transition is an `update` and the diff carries `listing_status: {from, to}` plus
     `previous_listing_status`. The audit page renders diffs, so the sale is legible
     either way.

     *The same shape as Batch 7's `duplicate_reason`*, which is recorded inside `changes`
     on a `create` rather than as an action type of its own — and which this batch finally
     consumed, four batches after Batch 7 wrote it down for exactly this purpose.

147. **`copyCount` was declared `ge=1`, and selling your only copy turned that into a 500
     on the film's own page.**

     The bound encoded a true invariant: a film reached `MovieListItemResponse` only by
     having a live disc. §4.4 broke it — sell your last copy and the film still has a
     `movies` row, a watch history, a wanted entry and a detail page, with **zero** owned
     discs.

     **Latent rather than new.** A film whose every copy was soft-deleted would have done
     the same thing, and there are none of those: checked against live Neon on 2026-09-12,
     **zero**. It is the shape #93 and #73 both describe — a rule that is only wrong once
     something else starts using it — and it was found by a test asserting the criterion
     rather than by reasoning about the schema.

### 2026-09-12 — Batch 24 barcode scan and lookup

148. **A barcode resolution is a suggestion until a person confirms it; only confirmed
     mappings are cached, and the physical collection itself sits before eBay in the
     lookup chain.**

     The recovered Phase 3.4 chain says cached mapping → eBay/Amazon UPC search → TMDB.
     #91 has already ruled Amazon out and the batch ledger records eBay as its replacement.
     Batch 24 adds one further leg: **confirmed cache → exact `collection_items.barcode` →
     eBay Browse → TMDB**. A barcode already on a disc in the house is a certain, free
     answer and gives the scanner its most useful shop-floor result — “you own this exact
     product” — without consuming eBay's 5,000-call daily quota.

     **Nothing learned from seller prose is cached on lookup.** eBay has no catalogue
     endpoint for the keyset available here; Browse search returns listing titles, which
     are reduced to conservative title queries and offered as TMDB candidates. A separate
     confirmation request writes migration 028's `barcode_lookups` row, and adding the disc
     remains the existing collection request. The client therefore cannot turn a plausible
     wrong-edition match into catalogue data without an explicit **This is the disc** action.
     Manual title search crosses the same confirmation boundary. A later correction
     replaces the one mapping for that code rather than creating two competing answers.

     **The code is refused before the network if its GS1 modulo-10 digit is wrong.** EAN-8,
     UPC-A and EAN-13 are the only accepted lengths in both scanner and API. This prevents a
     camera misread from spending quota and, more importantly, from presenting a convincing
     match for digits that were never printed on the case. The lookup endpoint is also
     capped at 60 requests per hour because each uncached request can spend an eBay call.

     **ZXing is pinned to the last Node-20-compatible minor and loaded only on the camera
     action.** `@zxing/library` 0.22+ declares Node 24; this repository builds on Node
     20.20.2, so `^0.21.3` keeps the lock below that boundary. The package is a large decoder
     and most Add Disc visits can use title search, so it sits in an on-demand chunk rather
     than the route's initial bundle. Decoder hints admit only the three retail symbologies,
     and every stop, detection, unmount and interrupted permission prompt releases the
     camera stream.

### 2026-09-12 — Batch 24 close-out

149. **Batch 24's physical acceptance was deferred until after deployment, not waived or
     inferred from its automated gate.**

     Phase 3.3 asks for a real Blu-ray barcode to decode on a phone in under two seconds;
     Phase 3.4 asks for the correct common-disc match and an unknown valid code to reach
     manual search. None can be truthfully observed from the desktop fixture decoder or a
     Postgres-backed CI run. The owner explicitly authorised shipping `590504d` first so
     those checks can run against the real HTTPS origin and live eBay-backed resolution
     chain.

     **"Shipped" and "all acceptance observed" are therefore separate facts for this
     batch.** The batch ledger and §17 mark the code shipped while naming all three open
     observations and their owner; `OWNER-ACTIONS.md` 1d remains unchecked until the phone
     run supplies a barcode, device/browser and measured time. A later successful run can
     close the acceptance debt without changing the deployment history.

### 2026-09-12 — Batch 22 deals feed

150. **A deals page needs a *population* check, not just a per-result one — and that is
     the whole difference between §5.3's risk note and §5.9's.**

     The ledger says the same sentence about both batches: a layout change *"does not
     error — it selects the wrong node and persists a plausible wrong number"*, and the
     answer is a "last known good shape" assertion rather than a success counter. Batch 19
     built that as `extract.check_shape`, and its **strongest rule is that the title on
     the page matches the film asked for**.

     A deals page has no film asked for. Whatever the shop discounted is the answer, so
     the single most powerful rule in the existing checker simply does not apply, and
     something has to take its place.

     What takes its place is **agreement across the page** (`deals.check_page_shape`).
     Three shapes, each of which leaves every individual card looking entirely reasonable:

     - every card showing the **same discount** — one shared node read forty times,
       typically an "up to 70% off" banner caught by the `was` selector;
     - **no card** having a `was` price at all — the sale-price selector has moved, which
       turns a sale page into a price list and makes every discount null;
     - every card showing the **same price**.

     A page that fails any of them has **every** card discarded rather than the failing
     ones, because if the `was` selector is reading a banner then each discount is wrong
     in precisely the way that looks right. Below five cards the population rules are
     silent: a shop with three discs on offer is an ordinary Tuesday, and three of the
     five enabled retailers are small enough for that to be normal.

     **`discount_percent` is arithmetic on two prices, never a number read off the page.**
     A shop's own "save 60%" badge is exactly the node a layout change hands to the wrong
     reader, and it is redundant — two prices that have each passed a range and currency
     check already contain the answer. The database enforces it too: `CHECK
     (discount_percent > 0 AND < 100)` and `CHECK (was_price > price)`.

151. **"Skip already-owned" is format-aware, which the criterion does not say and would
     be wrong without.**

     §5.9 says *"skip already-owned"*. Read literally that hides the 4K of a film owned on
     DVD — which is the single most interesting deal the feed could carry, and the one
     Batch 29 just built an upgrade path for. So a deal is skipped only when the format on
     offer is **no better than** the best already owned, by the same `FORMAT_RANK` the
     `best_format_owned` trigger enforces. An upgrade is never already-owned.

     A deal whose format could not be read is skipped when anything is owned: an unknown
     format cannot be *shown* to be an upgrade, and a short feed beats a wrong one.

     **An unmatched deal is kept, not dropped.** A title the matcher could not place is
     the evidence that the matcher needs work; dropping it would make a broken matcher
     indistinguishable from a quiet sale page — the same failure this batch's page checks
     exist to prevent, one layer up. The UI says "not matched" rather than hiding the row.

152. **The sale-page selectors ship verified and the sale-page URLs ship unverified, and
     the distinction is recorded rather than blurred.**

     Every `item`/`title`/`price`/`url` selector in a `deals` config is the one Batch 19
     checked against that shop's live markup on 2026-09-09. They apply unchanged because a
     Shopify collection page renders the same product card as a Shopify search page. What
     is new is the `was` selector and the sale-page URL, and **neither has been run against
     the live site** — `verified: False` on all five says so, and
     `unverified_deals_names()` reports it the way `unverified_names()` already does for
     search pages.

     That is not laziness, it is the arrangement `group-start.md` requires: live retailer
     requests are the owner's, so the run that verifies these selectors is the same run
     that satisfies §5.9's acceptance. **Batch 19 shipped on exactly this footing and its
     owner-run checkpoint found three real defects** (#91, #92, #94), which is the argument
     for the arrangement rather than against it.

     **Four of the five enabled shops had no `deals_url` at all**, so §5.9's "≥ 3
     retailers" was unreachable before this batch: only Zavvi's was seeded, back in Batch
     18. The four new ones are conventional Shopify `/collections/sale` paths — a
     convention, which is precisely why they are marked unverified.

     **No ruled-out shop gained one.** Amazon, HMV, CEX and Blu-ray.com are out
     permanently under #91, and a deals config for any of them would quietly put it back
     in the rotation. A test asserts they have none.

153. **Zavvi's configured `url` selector points at a heading, so every deal would have
     arrived unclickable — found by running the extractor over captured markup.**

     `product-title` is an `<h3>`, not an `<a>`. The wanted-item scraper survives that: it
     still has a title and a price, and the same-site guard simply does not run, which is
     why nobody noticed. A **deal** does not survive it — the URL is the entire point of
     the card, and worse, `deals`' uniqueness key is `(retailer_id, url)`, so every Zavvi
     deal would have collided on the empty string and the table would have held one row
     per shop.

     `_card_to_candidate` now falls back to the card's own href, then to the first anchor
     inside it — the same "a card can be its own match" reasoning `_select_one` already
     applies for Powerhouse. Against the captured cards it recovers both real product
     URLs.

     *Worth noting for whoever next touches the retailer scrapers:* the same latent gap
     is still there on the wanted-item path. It is harmless today and fixing it is not
     this batch's business, but it is the reason `price_checks.url` is sometimes null.

### 2026-09-14 — the owner snag triage, and the four decisions Craig took on it

154. **The menu loses six items by two different means, because it has two different
     problems.**

     Merging Home, Stats and Insights into one reading page removes two items. **Hiding
     the four destinations whose tables are empty — Box sets, Collections, Deals, Loans —
     removes four more**, and they reappear the moment their table has a row. Fourteen
     sidebar items become eight. Notifications and AI settings fold into one Settings
     page, which also brings AI settings back into the menu; it is defined as a
     destination today but sits in no group and is reachable only from the header.

     **The second half is the half the capture missed.** It argued the merge from
     organisation. The database argues something stronger: measured 2026-09-14,
     `smart_collections`, `box_sets`, `deals` and `loans` all hold **0 rows**, so five of
     fourteen destinations lead to a page with nothing on it and Home is three-quarters
     empty (`watch_log` 0, so On this day, Worth a rewatch and pinned collections are all
     blank). A menu item that leads nowhere is worse than a long menu.

155. **Mark gets write access: adding discs, and eBay prices.**

     `profiles` holds exactly two rows — Craig `admin`, Mark `viewer` — and there is no
     public sign-up, so **"only Mark and Craig can see this" already describes every page
     in the app.** Snag 8 read literally was already satisfied and had nothing to do.
     What Craig meant was the opposite of how it was captured: widen Mark's reach, not
     narrow anyone's.

     So `/collection/add` and both eBay endpoints (`/ebay/price-estimate`,
     `/ebay/listing-url`) stop being `AdminUser`. **The API moves with the UI, not after
     it** — this codebase's pattern is that pages hide what the API refuses, and a page
     that stops hiding a button whose endpoint still 403s is worse than no change at all.

     Trash, Audit log, Retailers and Admin stay admin-only. Those are Craig's tools in the
     sense the Admin page's own label means.

156. **Watch history arrives in two stages, RSS first.**

     Letterboxd's API is not an option: their developer page excludes **"private or
     personal projects"** and **"LLM or GPT-related use"**, and this app is both. Applying
     would park the work behind an answer that is very likely to be no. **Do not apply.**

     That leaves two paths, and Craig took both in order. **Stage one is the public diary
     RSS feed** (`letterboxd.com/<user>/rss`) — free, no credential, no subscription, and
     it carries recent viewings with their dates. **Stage two is the data export**, which
     carries the full history with dates but needs Letterboxd Pro at ~$35/yr *per
     account*, so it waits until Craig decides to pay for it.

     Starting with RSS means recent viewings begin accumulating immediately at no cost,
     and the backfill can land later without rework — both write the same `watch_log`
     rows through the same matcher.

     **Two consequences to carry into the batch.** A recurring RSS poll wants a cron, and
     both Railway crons are crashing today (`OWNER-ACTIONS.md` item 1), so the first
     version must work from a manual sync the same way the scraper does. And a Letterboxd
     export carries title, year and a Letterboxd URI but **no TMDB or IMDb id**, so
     matching against 1,854 films is on title + year and needs a confirmation step for
     ambiguities — the shape Batch 24 already uses for barcodes.

157. **Movie night is rebuilt to Craig's description, not tuned.**

     What was built is a random swipe deck over films already in the collection.
     `candidate_movies` is `select(Movie)` filtered by decade and rating, so **a film
     outside the Archive can never appear**, and there is no suggestion concept anywhere
     in the model. Two of Craig's five points were met — a session holds 2+ people, and
     matching already generalises past two because it requires *everyone* to have liked a
     film.

     The other three need the input side replaced: anyone suggests films, everyone votes
     on anyone's suggestion, films outside the Archive are allowed with their streaming
     availability shown, and a card opens to the film's full details including whether the
     others have seen it and when. `tmdb/client.py` already has `get_watch_providers`, so
     the streaming half needs no new integration; the "seen it" half needs `watch_log`,
     which is why this follows #156.

     **A defect to fix regardless of this decision.** `candidate_movies` documents itself
     as *"seeded per session so both people are shown the same deck in the same order"*,
     and the query is `order_by(func.random())` with no seed — every call returns a
     different order, per person and per refetch. The comment asserts a guarantee the code
     does not give.

### 2026-09-14 — what the Letterboxd feeds actually contain

158. **The diary RSS carries a TMDB id on every entry, and two-thirds of the entries
     concern a film already in the collection.**

     Craig gave the two usernames on 2026-09-14 — `CraigR973` and `markr973` — and both
     diaries were already public, so `OWNER-ACTIONS.md` 1f closed on the spot. Measured
     against both live feeds and live Neon the same day, across **100 diary entries**:

     | | Craig | Mark | Both |
     |---|---|---|---|
     | Exact `tmdb_id` match — link immediately | 21 | 21 | **42** |
     | Owned but **unidentified**, one unambiguous title candidate | 10 | 14 | **24** |
     | Ambiguous — needs a person to choose | 0 | 0 | **0** |
     | Genuinely not in the collection | 19 | 15 | **34** |

     **So 66 of 100 watches are of a film they own**, and the import is worth more than
     the watch rows alone.

     **The 24 are the interesting number.** Those films are in `movies` with
     `tmdb_id IS NULL` and `year IS NULL` — part of the **754 rows the April import never
     identified** — and the diary hands over the exact TMDB id for each. So the sync can
     **identify the film as well as log the watch**, which also fills in year, poster,
     runtime, cast, and the Letterboxd link snag 9 depends on. One import, three dead
     things fixed.

     **The confirmation step stays**, even though this sample needed it zero times. Title
     matching against 754 unidentified rows will be ambiguous eventually, and the rows are
     messy in ways that guarantee it — `'Collector, The'`, `'Out of The past'`,
     `'Death on the Nile [1978]'`, and one outright junk row, `'Test 15.04.26'`. Matching
     normalises case, trailing articles and bracketed years; **anything not a single
     unambiguous candidate is offered, never guessed**, the shape Batch 24 uses for
     barcodes.

     *Recorded because an earlier reading of this data was wrong and the wrong version is
     the tempting one.* A first pass filtered title candidates on `abs(year - filmYear) <= 1`
     and reported **zero** owned-but-unidentified matches — an artifact, because every
     unidentified row has `year IS NULL` and was excluded by the test itself. It would have
     shipped S5 with no identification step and no confirmation step, on the false premise
     that TMDB ids always match exactly.

159. **`watch_log` idempotency keys off the feed's `guid`, and the 50-entry cap sets the
     sync interval.**

     Each entry's `<guid>` is a stable `letterboxd-watch-<id>`, unique per diary entry and
     unchanged across refetches — so a re-run updates rather than duplicates, without
     comparing dates or titles. A rewatch of the same film on a later date is a *different*
     guid and correctly becomes a second row, which is what `<letterboxd:rewatch>` marks.

     **The feed returns only the most recent 50 entries.** Craig's reaches back to
     2026-01-26; **Mark's only to 2026-07-20**, because he watches far more. A sync running
     less often than roughly monthly would silently drop his entries — so the interval is a
     correctness property, not a preference, and the manual-first version (the crons are
     still crashing) must say plainly when it last ran.

     Mark rates nothing — 0 of 50 entries carry `memberRating`, against Craig's 50 of 50 —
     so a null rating on his rows is correct and must not be treated as missing data.

### 2026-09-15 — the full watch history, retrieved without Letterboxd Pro

160. **Both diaries were retrieved in full from the public diary pages, so the paid export
     is not needed and `OWNER-ACTIONS.md` 1g closes unused.**

     The 403 recorded on 2026-09-14 was **curl's TLS fingerprint, not a policy block**. The
     diary pages are public and load normally in a real browser with no session, no
     sign-in and no challenge presented. Retrieved 2026-09-15 by paced same-origin fetches
     (350 ms apart) driven from the browser pane — 24 pages for Craig, 23 for Mark, **47
     page loads in total, once**.

     | | Entries | Distinct films | Range |
     |---|---|---|---|
     | Craig | 1,173 | 997 | 2013-12-24 → 2026-09-09 |
     | Mark | 1,149 | 1,050 | 2022-11-02 → 2026-09-14 |

     **2,322 entries against RSS's 100.** Every row carries a unique `data-viewing-id` —
     the same id the RSS `guid` wraps as `letterboxd-watch-<id>` — so #159's idempotency
     key works unchanged across both sources. Zero blank fields, zero fetch errors, zero
     duplicate ids in either file.

     Matched against live Neon the same day:

     | | Craig | Mark | Both |
     |---|---|---|---|
     | Links straight to an owned film | 364 | 586 | **950** |
     | Owned but unidentified → identify + link | 226 | 354 | **580** |
     | Ambiguous | 2 | 4 | **6** |
     | Not in the collection | 581 | 205 | 786 |
     | **Watches of owned films** | 50% | 82% | **1,530 (66%)** |

     **66% matches the RSS sample's 66% exactly**, which is the check that the matcher
     behaves the same on 2,322 rows as on 100. **396 distinct films would be identified**
     — over half of the 754 the April import never resolved. **Only 6 entries are
     ambiguous** across 2,047 distinct films: `Death on the Nile` and `Murder on the Orient
     Express`, both with several adaptations. The confirmation step #158 insisted on is
     therefore right and will fire about three times.

     **One caveat recorded rather than glossed.** This was automated access to Letterboxd,
     which their terms likely discourage even for one's own data. It was done at Craig's
     explicit instruction, against his and Mark's own public diaries, once, paced, and
     **nothing in the product repeats it** — see #161. A Cloudflare challenge was never
     presented; had one appeared, the rule was to stop rather than attempt it.

     *An earlier caution in this session was also wrong and is corrected here:* the session
     initially declined to drive a browser for this at all, on the grounds that it would be
     defeating bot detection. With a real browser no challenge arises, so there was nothing
     to defeat — the curl 403 had been mistaken for a policy position.

161. **The app never scrapes Letterboxd. The backfill is a file import; the ongoing sync
     is RSS.**

     The retrieval above happened **outside the product**, once, and produced two CSVs on
     disk (`.letterboxd-export/`, gitignored — it is personal data and must not be
     committed). So the split is clean and must stay that way:

     - **S8 (backfill)** reads a CSV file that already exists. Its input shape is
       deliberately the same as Letterboxd's own `diary.csv`, so it works identically
       whether the file came from this retrieval or from a paid export later.
     - **S5 (ongoing)** reads the public RSS feed, which is sanctioned, needs no
       credential, and carries a `tmdb:movieId` the diary HTML does not.

     **No scraper, no Cloudflare dependency and no stored Letterboxd credential ever ships.**
     That is what keeps this out of the risk class `DECISIONS.md` #110 put Blu-ray.com in.

     **S8 is therefore unblocked and free**, and moves up the order: it is now the batch
     that delivers the history, with S5 keeping it current afterwards. The 50-entry RSS cap
     from #159 stops being a backfill problem and remains only an interval requirement —
     sync at least monthly or Mark's newest entries fall off the feed before they are read.

### 2026-09-15 — Group S, batches S1 and S2

162. **The Letterboxd link is built from the IMDb id, and the slug branch is deleted rather
     than kept in front of it.**

     §17 row 4's April resolution was *"slug-based URL with search fallback"*, and the code
     implemented it exactly. It still produced a search link for **every film in the
     collection**, because `movies.letterboxd_slug` is `NULL` for all 1,854 rows: TMDB does
     not supply it, no import writes it, and the model's own comment says so. A two-branch
     conditional where one branch is unreachable is not a fallback — it is a single
     behaviour wearing a disguise, and it survived review precisely because the code looked
     like it handled both cases.

     `letterboxd.com/imdb/<imdbId>` redirects to the film's own page, and
     `MovieDetailResponse` already carried `imdbId`, so the fix needed **no schema change,
     no new request and no new integration**.

     **The slug branch is removed, not demoted.** Keeping it first would preserve the shape
     of the April decision while changing nothing observable, and would leave behind a
     branch no test can reach and no row can exercise. If a slug is ever imported, restoring
     a preference for it is a two-line change against a test that would then have something
     to assert.

     **The ceiling is stated rather than implied: 1,091 of 1,854 films have an IMDb id**, so
     this moves roughly **59%** of the collection from a search page to the right page. The
     other ~763 are the rows the April import never identified; they improve when S8's
     import identifies them, which is the same 396-film population that batch is about.

163. **Two of S2's criteria were closed as *unmeetable by an agent*, and the gate was not
     allowed to stand in for them.**

     Craig's snag was *"the phone zooms"*. What an agent can do is measure the causes — form
     controls at 14px against iOS Safari's 16px threshold, and `touch-action: auto` on
     `html`, `body` and every input — fix them, and re-measure. What it cannot do is observe
     iOS Safari's actual behaviour on his iPhone, or whether a `letterboxd.com` link is
     claimed by the Letterboxd app, which is universal-link handling no code here controls.

     Both were recorded as open owner checks at close-out and written into
     `OWNER-ACTIONS.md`, with the coverage number attached to the second so a film that
     still lands on a search page is not read as a failure of the fix.

     *This is the same discipline `#149` applied to Batch 24's physical acceptance and
     `STATUS.md` applies to 6.2, 5.6, 9.5 and 8.4 — the batch ships, the criterion stays
     visibly unmet, and nobody has to reconstruct later which was which.*

164. **The 16px floor lives in the base layer, not on the shared form class, and the
     `:not()` that makes it work is load-bearing.**

     `.form-control` was the obvious place, and it would have been wrong: `FilterBar`,
     `CommandPalette` and `SearchBar` each style their own controls, so a fix confined to
     the shared class would have left three of the most-used inputs in the app still at
     14px — and left the next hand-styled input free to reintroduce the bug.

     A base-layer rule is the right scope, but a bare `input` selector (0-0-1) loses to
     Tailwind's `text-sm` (0-1-0) no matter where it appears in the file, because Tailwind
     v3 emits its layers as ordinary CSS. `input:not([type='checkbox'])` borrows the 0-1-0
     of the selector inside `:not()` and lands at **0-1-1**, which wins without
     `!important`. Checkboxes, radios and ranges are excluded because they render no text
     and sizing them would change their boxes.

     **Verified by probing the shipped stylesheet**, not by reading the source: ten real
     class combinations measured at 375px, including one deliberately styled `text-xs`,
     all computing 16px — and 14px again at desktop width, so the design is unchanged where
     the bug never existed.

     **Form controls keep `touch-action: auto` deliberately.** The effective touch behaviour
     is the intersection along the ancestor chain, so the root's `manipulation` already
     suppresses double-tap *zoom* over an input, while leaving double-tap-to-select-word —
     a gesture someone uses correcting a shelf name — working.

### 2026-09-15 — Group S, batch S3

165. **The menu hides a destination on a count the API supplies, and an unknown count shows
     it.**

     #154 hides Box sets, Collections, Deals and Loans while their tables are empty. That is
     a fact about the database, so the client has to be told: `GET /nav/sections` answers it
     in four `COUNT(*)`s. The alternative considered and rejected was having the sidebar
     fetch the four lists it already has clients for — four full result sets on every page
     load, on a phone, to learn they were empty.

     **Each count matches what its page would actually list**, not merely what its table
     holds. A dismissed deal does not count, because `GET /deals` filters it out. A
     *returned* loan does, because `GET /loans` lists it. Smart collections are counted for
     the caller alone, because they carry a `user_id` and a shared count would show one
     person a destination holding only the other's. A count that disagreed with its page
     would produce the subtlest possible version of this bug: a menu item that is right
     about the table and wrong about the page.

     **`undefined` means show.** The shell renders before the counts resolve, and offline
     they may never resolve. Hiding four destinations because a request was slow is a worse
     failure than the emptiness this exists to fix, so only a genuine `0` hides. The cost is
     a menu that is briefly longer than it will settle to; the alternative was one that
     flickers, or one that silently loses four links whenever the network does.

166. **`navGroups` is built by path, because building it by index had already caused the
     bug it was going to cause again.**

     The previous version was `navItems[10]`, `navItems[13]` and so on. **Removing one entry
     silently re-points every later group at the wrong destination** — no error, no type
     failure, just a menu that quietly means something else. And adding one at the end
     leaves it in no group at all, which is exactly what had happened to AI settings: it was
     a defined destination sitting in no group, reachable only from a header button, and
     nothing in the code could notice.

     `byPath` throws on a name that does not exist, and a test asserts every entry in
     `navItems` appears in some group. The second is the one that would have caught the
     original defect.

167. **Two rules about empty states collided on the merged page, and both were kept.**

     #154 says the merged Home hides what is empty. Batch 14 said an empty chart reads as a
     *broken* chart, so "Most watched" and "Spend over time" should each say what they are
     waiting for. On one page, obeying the second means two empty panels — on a page whose
     entire complaint was emptiness.

     **The panels are hidden and their explanations are kept**, collected into one muted
     line beneath the charts: *"Not shown yet: Most watched — nothing logged yet…"*. That
     preserves what Batch 14 was protecting — the reader learns there is no data *and* why —
     without spending two panels on it. The denominator that made the original argument
     (`itemsWithPrice`, which distinguishes "nothing bought" from "nothing recorded") is
     still what chooses the wording.

     *Recorded because the naive reading of the criterion would have deleted the
     explanation along with the frame, and the explanation is the part that was hard-won.*

168. **`FilterBar` chooses where its controls render, rather than rendering them twice and
     hiding one.**

     Collapsing to a single button below `sm` had two possible shapes. The CSS one —
     duplicate the three primary controls into the expanded panel and toggle each copy with
     `hidden sm:block` — is purely declarative and wrong: two `<select>`s labelled *"Filter
     by section"*, one `id="collection-sort"` twice, and both copies live in the DOM where a
     later class change can expose them together.

     `useMediaQuery('(min-width: 640px)')` decides *where* the single copy is rendered. One
     element, one id, one accessible name. The hook already existed and already reads its
     initial value synchronously, so there is no frame of the wrong layout.

169. **The browser pass used the repo's own DEV-only auth bypass and a scratch stub of the
     API, because the alternative was typing Craig's PIN.**

     S3's criteria are about what a *signed-in* person sees — eight destinations, a bottom
     bar, a collapsed filter bar — and none of it renders on the sign-in screen. Entering
     the PIN is not an agent's to do.

     `ProtectedRoute` already carries `import.meta.env.DEV && VITE_SKIP_AUTH === 'true'`,
     compiled out of production builds rather than merely unreached. Running the dev server
     with that flag against a throwaway stub serving `/auth/me`, `/nav/sections` and the
     dashboard's reads gave the real components, the real stylesheet and real JSON shapes —
     and let the hide/un-hide rule be *seen* in both states by flipping one value in the
     stub, which no unit test can demonstrate.

     **Nothing from the harness is in the tree.** The stub lives in the session scratchpad
     and the `.env.local` it needed is gitignored and was deleted. Worth recording as a
     method: a future frontend batch with the same problem should reach for this rather than
     for a credential.

### 2026-09-15 — Group S, batch S4

170. **Following the button found an endpoint the criterion did not name, and it was the
     one that mattered.**

     `#155` names `/collection/add` and the two eBay routes. S4 moved **eight** endpoints,
     and the eighth — `PUT /collection/{item_id}/listing` — is the one without which the
     batch would have shipped broken in exactly the way #155 warns about.

     The two eBay routes only *price* and *link*. Pressing "List for sale" writes the
     listing status, and that lands on the collection router. With it left `AdminUser`,
     Mark would have reached the add page, marked the disc an upgrade, seen the prompt,
     watched the price arrive — and then got a 403 from the button. **Every visible step
     would have worked.** The failure was reachable only by walking the flow.

     *The general form: a criterion that names endpoints is naming the ones its author
     could see from the outside. The check is to follow each control the batch makes
     reachable and ask what it calls.*

     Barcode lookup and confirm moved for the same reason, one step earlier: scanning is
     the fastest route through the add page, and an add page whose scan button refuses the
     person who opened it is the same defect in a different place.

171. **Adding moved to a viewer; editing and destroying did not, and the line is where the
     attribution is.**

     Adding a disc *creates* a row, attributed to whoever added it — the audit log tells
     Craig's and Mark's apart, which is the property that makes widening safe rather than
     merely convenient. Editing or deleting *changes or removes* something the other person
     put there, and no attribution makes that reversible.

     So `POST /collection` is a viewer's; `PUT /collection/{id}` and
     `DELETE /collection/{id}` are not. `PUT /collection/{id}/listing` is, which looks
     inconsistent until you read what it does: it is one endpoint covering "I have listed
     this" and "this is gone", and the first is half the flow snag 7 exists for. The old
     test called it "sell" and asserted 403 on that word alone.

172. **The ledger said "Retailers still refuses a viewer". The code disagreed, and the code
     was right.**

     `GET /api/v1/retailers` answers **200** for a viewer and has since Batch 18, with the
     reason written into the router's own docstring: *"reads are open to both people — Mark
     can reasonably want to see what is being looked for"*. Every retailer **write** is
     admin-only.

     The criterion is true of the *page* — `/retailers` is `AdminShell` — and the batch
     changed neither. Recorded rather than quietly adjusted, because a criterion asserting
     a 403 that the code has deliberately answered 200 to for four batches is the kind of
     thing that gets "fixed" in the wrong direction by whoever reads it next.

     *The test now asserts the boundary that actually exists: a viewer cannot create a
     retailer and cannot re-seed the list.*

173. **A fixture that makes a test pass for the wrong reason is worse than one that fails.**

     `test_a_viewer_may_add_a_disc` created a disc for the film it then tried to add, so
     `POST /collection` answered **409 duplicate** — before the role check ran at all. CI
     caught it because 409 ≠ 201. Had the assertion been the looser `!= 403`, it would have
     passed, and gone on passing on the day somebody reverted the widening.

     The same shape as the `scraper_type="generic"` fixture in S1 and for the same
     structural reason: **49 Postgres-backed tests in that file skip on this machine**, so
     the first execution of any new test there happens in CI (`STATUS.md` gotcha 3).

### 2026-09-15 — Group S, batch S8

174. **`DECISIONS.md` #160 recorded 6 ambiguities. Running the shipped matcher over the
     same two diaries finds 28, and the shipped matcher is the stricter of the two.**

     Measured on 2026-09-15 against live Neon — 2,322 entries, 1,854 films, read-only:

     | | measured | #160 said |
     |---|---|---|
     | Links straight to an owned film | 969 | 950 |
     | Owned but unidentified → identify | 586 | 580 |
     | **Ambiguous** | **28** | **6** |
     | Not in the collection | 739 | 786 |
     | Watches of owned films | **1,555 (66%)** | 1,530 (66%) |
     | Distinct films identified | **397** | 396 |

     **The difference is normalisation, and it moves rows out of the wrong column.** #160's
     pass did not collapse parenthetical disambiguators or rotate trailing articles, so
     `'Mummy, The (Brendan Fraser)'`, `'Mummy, The (Original)'` and `'Mummy, The (Tom
     Cruise)'` read as three unrelated titles — and a diary entry for *The Mummy* matched
     **none of them**. It was counted as "not in the collection". Same for
     `'Lion King (Animation)'` / `'(Live Action Movie)'` and for `'Man Who Knew Too Much,
     The'` against `'The Man Who Knew Too Much'`.

     That is the entire 47-row difference in the last row: **22 silent misses became 22
     explicit questions**, and 25 more watches found a home.

     **Which behaviour is better is not a close call.** The alternative to an ambiguity is
     not a correct match — it is a *wrong absence*: the watch is silently not logged, the
     film is never identified, and nothing says so. 28 confirmations is the price of never
     doing that, and the criterion is explicit that ambiguous matches are offered rather
     than guessed.

     **All 15 distinct ambiguous titles are genuine.** The collection really does hold two
     *Dunkirk*s, two *Titanic*s, two *Lion King*s, two *Ghostbusters*, two *Death on the
     Nile*s, two *Murder on the Orient Express*es and three *Mummy*s. Not one is an
     artifact of the aggressive normalisation.

     **66% is unchanged**, which is the check that mattered: the same figure the 100-entry
     RSS sample and #160's coarser pass both produced, from a matcher that disagrees with
     both about the details.

     *Recorded rather than quietly shipped, because the ledger's acceptance criterion names
     "the 6 real ambiguities" and the next person to read it would otherwise conclude the
     matcher was over-firing.*

175. **Identification is a separate flag from writing, because they are different-sized
     decisions.**

     `--write` inserts `watch_log` rows: additive, attributed, soft-deletable, and nothing
     that existed before changes. `--identify` rewrites `title`, `year`, `poster_path`,
     `runtime_minutes` and the whole credit list on ~397 rows that are already there — and
     where the collection turns out to hold both the unidentified row *and* an identified
     one for the same TMDB id, it **merges them and deletes one**.

     Putting both behind one flag would mean the safer operation could not be performed
     without the riskier one. Craig can import 1,555 watches, look at them, and decide
     about the 397 separately.

     **A TMDB match the engine calls ambiguous is refused, not lowered.** `MatchingEngine`
     reports `ambiguous` when the leading candidate ties with films that are not plausibly
     the same film, and the tie is then broken by TMDB *popularity* — which is not a
     property of the disc on the shelf (#31). **The watch is still written**: failing to
     identify a film is no reason to lose the record that somebody watched it.

176. **The idempotency column stores the bare viewing id, which is what makes S5 free.**

     The CSV calls it `ViewingId`; the RSS feed wraps the same number as
     `letterboxd-watch-<id>` in its `<guid>`. `watch_log.letterboxd_viewing_id` holds what
     they have in common, so a viewing present in both sources collapses to one row —
     **S5's "cannot double-count across sources" criterion, met and tested in S8.**

     Doing it here rather than there is the point of the S8-before-S5 ordering: the
     alternative is discovering the collision after 2,322 rows are already in.

     `UNIQUE (user_id, letterboxd_viewing_id)`, partial on `IS NOT NULL` — watches logged
     by hand in the app carry no viewing id and never will, and a plain unique index would
     allow exactly one such row per person.

177. **The test fixture carries real collection titles and invented diary rows.**

     The messy titles are the point and are real: `'Death on the Nile [1978]'`,
     `'Collector, The'`, `'Out of The past'`, `'Mummy, The (Tom Cruise)'`, `'Test 15.04.26'`.
     Those are rows live Neon holds, they are what the normalisation has to survive, and a
     film title is not personal data.

     **The dates, ratings and viewing ids are invented.** Those three together *are*
     somebody's watch history — the reason `.letterboxd-export/` is gitignored (#161) — and
     a six-line excerpt is still six viewings. The column shape is faithful, which is all a
     reader test needs.

### 2026-09-15 — Group S, batch S5

178. **Where a real payload could not be captured unattended, the parser was written to
     have no opinions about the parts that were not measured.**

     `AGENTS.md` says to work from real sample payloads rather than guessed shapes. The
     element names *are* a real measurement — `OWNER-ACTIONS.md` 1f read both live feeds on
     2026-09-14 across 100 entries and recorded `letterboxd:watchedDate`,
     `letterboxd:rewatch`, `letterboxd:memberRating`, `letterboxd:filmTitle`,
     `letterboxd:filmYear`, `tmdb:movieId` and the `letterboxd-watch-<id>` guid.

     **The exact XML was not**, and capturing it needs a live third-party request, which
     `group-start.md` keeps out of unattended runs. So rather than guess namespace URIs and
     depend on the guess:

     - matching is on **local names**, ignoring prefixes entirely;
     - the title **falls back** to RSS's own `<title>` when the namespaced one is absent;
     - an item with no `letterboxd-watch-` guid is **skipped, not failed** — Letterboxd puts
       list publications in the same channel;
     - a test renames every prefix and points the namespaces at nonsense URIs.

     That is a better parser regardless. It is recorded because the *reason* matters: the
     fixture is honest about being constructed, and `OWNER-ACTIONS.md` 1j is the check that
     closes the gap rather than the gap being left unstated.

179. **The sync writes by default; the file import does not. The asymmetry is the point.**

     `run_import` defaults to `dry_run=True` because a file import is a 1,555-row operation
     over history reaching back to 2013. A sync is at most 50 recent entries of which a
     healthy run writes a handful, and it is triggered by a person pressing a button
     labelled "Sync now".

     **The dangerous default belongs on the dangerous operation.** Making both dry by
     default would have meant a sync button that did nothing until someone found a second
     switch; making both write by default would have meant S8 writing 1,555 rows to whoever
     forgot an argument.

     **The sync does not identify films**, though every feed entry carries a TMDB id and it
     easily could. Identification rewrites `movies` rows — the operation S8 deliberately put
     in the owner's hands — and doing it from a button, repeatedly, would take that decision
     back without asking.

180. **A failed sync keeps its row.**

     `letterboxd_syncs` records a run before the fetch and stamps `finished_at_utc` plus the
     error if it fails, so **a sync that failed is distinguishable from one that never
     ran**. With a feed that holds 50 entries and a person who cycles them in eight weeks,
     those two states have very different consequences and look identical from the outside.

     Same argument `scrape_runs` was built on in Batch 20, after a scraper "test" showed
     results on screen while saving nothing. The UI carries it through: a failed run reads
     *"— and it failed"* with the reason, rather than quietly showing the previous success.

     **A feed that comes back full at 50 is surfaced as a cadence warning, not an error.**
     Nothing went wrong; the interval is too long, and entries may already have fallen off
     the end. That distinction is the difference between a warning someone acts on and an
     error they learn to ignore.

### 2026-09-15 — Group S, batch S6

181. **TMDB's UK physical release dates cover 1% of forthcoming films, and the screen says
     so.**

     S6's ledger row demanded the real coverage number because *"a screen that implies
     completeness it does not have is the failure mode here"*. Measured against live TMDB
     on 2026-09-15:

     | population | has a GB **physical** date | has a GB **cinema** date |
     |---|---|---|
     | 58 films from 3 pages of `/movie/upcoming` GB | **1 (1%)** | 47 (81%) |
     | 60-film sample of this collection | 7 (11%) | 41 (68%) |

     The one upcoming film with a physical date has the note `'DVD'`.

     **The feature is correct and thin, and the honest response is to say the number.**
     When the disc section is empty the page states the measurement rather than rendering
     an empty frame or — far worse — implying that no discs are coming. It fills in as
     TMDB's contributors add dates, and nothing about the ingestion changes when they do.

     **This is why "a film with no physical date is still visible" is the load-bearing
     criterion**, not a defensive afterthought: it is not the edge case, it is 99% of them.

182. **TMDB type 5 means "Physical" and nothing more, so the format comes from free text.**

     A 4K disc and a Blu-ray released the same day are **one** type-5 entry. The only
     signal separating them is the `note` a contributor typed, and the real values are
     `'4k Ultra HD Blu-ray'`, `'Blu-ray'`, `'DVD'`, `'DVD release'`, `'VHS'`,
     `'Alien Anthology Blu-ray Box Set'`, `'The Alien Legacy DVD'`.

     So: a note naming 4K/UHD → `4k_uhd_release`; a note naming *only* an obsolete format →
     skipped, because a VHS date is a fact about 1994 and this is a calendar of upcoming
     releases; anything else, including an empty note → `blu_ray_release`.

     **That last rule is a deliberate approximation and the code admits it.**
     `RELEASE_TYPES` has no DVD member, so a DVD-only release is recorded as
     `blu_ray_release`, which reads as "out on disc". Inventing a vocabulary member for a
     format nobody in this collection is waiting for would be worse than widening two
     labels slightly.

183. **A physical date is ingested beside the cinema date, never instead of it — and a
     failed lookup costs neither.**

     One film now yields up to three rows: cinema, Blu-ray, 4K. "When can I see it" and
     "when can I buy it" are different questions and snag 2 is about the second, so
     replacing one with the other would answer the wrong one.

     `candidates` is therefore rekeyed from `tmdb_id` to `(tmdb_id, release_type)`, which
     is the shape the existing `(tmdb_id, release_type, region)` unique constraint already
     required. Two type-5 entries of one format — a release and a box set — collapse to one
     row, and **the earliest date wins**, because that is when somebody waiting can first
     buy it. The same-film-on-two-pages bug from Batch 17's first live run is the reason
     this is keyed at all.

     **The extra TMDB call per film is a second thing that can fail.** It is caught per
     film, recorded in `errors`, and the film **keeps its cinema date** — a physical lookup
     that failed must never cost a row that already worked.

184. **`git add` aborting on a stale pathspec cost a CI run, for the second time in this
     group.**

     S6's first commit carried *only* two file deletions. The `git add` meant to stage
     everything else was handed the two already-removed paths as well; `git add` aborts the
     **whole invocation** when any pathspec matches nothing, and `2>/dev/null` hid the
     error. The commit succeeded, the push succeeded, and CI failed on an `App.tsx` that
     still imported two deleted pages.

     S1 hit the identical trap and it was caught before committing. `AGENTS.md` says to
     stage explicitly rather than `git add -A`; **staging explicitly is only half of it** —
     the other half is checking `git diff --cached --name-only` before committing, and
     never suppressing `git add`'s stderr.

### 2026-09-15 — Group S, batch S7

185. **A movie-night vote is cast on a suggestion, not on a film — and that one change is
     what makes three of Craig's five points possible at once.**

     Batch 35's `candidate_movies` was `select(Movie)` filtered by decade and rating, and
     votes keyed on `movies.id`. Two consequences followed from that single fact: **a film
     outside the Archive could never appear** (it has no `movies` row to key against), and
     there was **no suggestion concept anywhere** (a deck is dealt, not proposed).

     Moving the vote onto `movie_night_suggestions` answers both. A suggestion carries
     *either* a `movie_id` or a `tmdb_id` plus the title and poster captured at the moment
     it was put forward — because for a film nobody owns there is no row to read them back
     from. "Shall we rent something" became a sayable answer to "what shall we watch".

     `Match.movie_id` is nullable for the same reason, and the notification and SSE payload
     both carry the title regardless, which is what a person actually reads.

186. **The shortlist is shared; the votes on it are not.**

     Batch 35 removed a card from your deck once you had swiped it, and deliberately did
     **not** remove it when the other person swiped — *"a card disappearing because they
     swiped it would leak their vote"*.

     S7 keeps the second property and reverses the first. A shortlist everyone is adding to
     is a list you re-read: you need to see that the film you liked is still there, and who
     added the three that appeared since. So cards stay, `myVote` reports **your own** swipe
     back to you, and nothing on the card says how anybody else voted. The swiping still
     opens on the first film you have not decided on, which is where Batch 35's deck left
     you.

     *A test asserts the other person's vote is invisible, because this is the property
     most likely to be lost by accident while making the list shared.*

187. **The deck order was seeded rather than the claim deleted.**

     #157 offered both: *"either seed it per session or delete the claim"*. Deleting would
     have been honest and would have left two people scrolling different orders of the same
     shortlist — awkward in exactly the situation the feature is for, two people on a sofa
     comparing what they are looking at.

     Ordering on `md5(session_id || movie_id)` is **stable per session, different between
     sessions, identical for everyone in one**. Postgres' `setseed()` would also work and
     is worse: it is connection state, and would leak into whatever ran next on that
     pooled connection.

188. **The migration is additive because the tables held real rows, and the CHECK is
     written for the database where the backfill did not run.**

     `movie_night_votes` held **13 rows across 2 sessions that were still open**, measured
     against live Neon before designing. `AGENTS.md` scopes the destructive-operation stop
     to *"dropping or rewriting columns and tables holding real rows"*, so nothing is
     dropped and nothing is rewritten: `movie_id` is **relaxed** to nullable — a film
     outside the Archive has no `movies` row — and every existing value stays put.

     A backfill creates one suggestion per `(session, film)` already voted on and points
     the existing votes at it, so **those two open sessions kept working** rather than
     becoming history the moment this deployed. The suggestions are credited to nobody,
     because nobody suggested them: Batch 35 dealt them.

     **The CHECK is `movie_id IS NOT NULL OR suggestion_id IS NOT NULL`, not
     `suggestion_id NOT NULL`.** The stricter form would have held on this database purely
     because the backfill happened to succeed — and would have failed on any database where
     it did not, which is precisely when a constraint needs to be forgiving rather than
     smug.

### 2026-09-15 — the live watch-history import

189. **The import ran. `watch_log` went from 0 rows to 1,555, and four dead features came
     alive at once.**

     Run at Craig's explicit instruction on 2026-09-15, after S8's dry runs had been
     executed against production and reported the same numbers. Craig 593, Mark 962 —
     matching the dry runs exactly, which is the check that a dry run is a rehearsal rather
     than a different code path that prints numbers.

     | | Craig | Mark |
     |---|---|---|
     | Watches written | 593 | 962 |
     | Distinct films seen | 477 | 869 |
     | Rewatches | 112 | 85 |
     | Range | 2013-12-24 → 2026-09-05 | 2022-11-02 → 2026-09-14 |

     **1,101 distinct films, and 245 that both of them have seen** — the last number is what
     S7's "has he seen it" reads, and it was 0 an hour earlier.

     **Idempotency is now proved against production, not fixtures.** A second run of Craig's
     file wrote **0** and reported all 593 already imported.

     **The 28 ambiguities were skipped rather than guessed**, and written to
     `.letterboxd-export/*-ambiguous.csv`. Most resolve themselves once the identification
     step gives those rows real years.

     **Step 2 — `--identify` — was deliberately not run.** #175 made it a separate flag
     because it rewrites ~397 existing `movies` rows and merges two into one where the
     collection holds both; "run the import" is not authorisation for that, and step 1 is
     additive and reversible where step 2 is neither.

190. **`DECISIONS.md` #159's "Mark rates nothing" is true of the RSS window and wrong about
     his history.**

     #159 measured the most recent **50** entries — Craig 50 of 50 rated, Mark 0 of 50 —
     and generalised it to *"Mark rates nothing, so a null rating on his rows is correct
     and must not be treated as missing data"*.

     The full diaries say otherwise. **Mark has rated 178 of 1,149 entries (15%)**, spanning
     2023–2026; **Craig 426 of 1,173 (36%)**. Mark has simply stopped recently, which is
     exactly what a 50-entry window would show as "never".

     **The conclusion survives and the reasoning does not.** A null rating is still correct
     data and still must not be treated as missing — that is true because people log watches
     without opinions, not because one of them never rates anything. The distinction matters
     for anything that later reasons *from* the claim: a feature that treated Mark's rows as
     unratable would be wrong about 147 of the rows now in the database.

     *Recorded because a measurement taken through a 50-entry window is a measurement of the
     window, and #159 did not say so.*

191. **The `set -a` command in `OWNER-ACTIONS.md` 1i could not have worked, and the failure
     it produces points at the wrong thing.**

     `DATABASE_URL` in `apps/api/.env.local` is **unquoted and contains an `&`**
     (`…?sslmode=require&channel_binding=require`). `set -a; . apps/api/.env.local` therefore
     splits the line at the `&`: the shell sets a truncated `DATABASE_URL`, backgrounds the
     remainder, and the script connects to `localhost:5432` and fails with
     *"Connect call failed ('::1', 5432)"*.

     **That error names the wrong culprit** — it reads as a Neon outage or a missing
     environment, and the actual cause is shell word-splitting in the instructions
     themselves. The corrected commands export the three values explicitly through `$(…)`,
     which keeps the `&` inside one word; quoting the value in `.env.local` would also fix it
     permanently.

     *Worth recording as a class: an instruction that has never been executed is not an
     instruction, it is a guess. This one was written in the same close-out that could not
     run it.*

### 2026-09-15 — the collection importer cannot refresh, and the watch history changed the stakes

192. **Re-running `import_collection.py` over live data does not refresh anything. It
     creates orphan film rows and skips every changed disc.**

     Found on 2026-09-15 when Craig proposed a fresher import of the spreadsheet before go
     live, and asked whether the identification step should wait for it. The answer turned
     on how the importer deduplicates, which is not what "re-running is safe"
     (`DECISIONS.md` #32) leads a reader to expect.

     **Three facts, read off the code and confirmed against live Neon:**

     - `upsert_movie` is `INSERT … ON CONFLICT (tmdb_id) DO NOTHING`. **A NULL `tmdb_id`
       does not conflict**, so a film currently held as an unidentified title-only row gets
       a *brand-new second row* the moment TMDB matches it.
     - `upsert_unmatched_movie` looks up `WHERE title = %s AND tmdb_id IS NULL` — an
       **exact** string match. A tidied title in the new sheet is a new row.
     - `insert_collection_item` dedupes on `import_source_row`, **the spreadsheet line
       number**, and the movie upsert above runs *before it and independently of it*
       (`import_collection.py`'s run loop).

     **So a re-import of a fresher sheet does this:** inserts a new identified `movies` row,
     then skips the disc because that line number is taken — leaving a film row with **no
     discs attached**, while the original row keeps the disc, the location and (since
     today) the watch history. Changed content at an existing line number is silently
     ignored; only lines past the current maximum land at all.

     **Measured: 1,857 items occupy lines 2–1867 with exactly 9 gaps**, and those 9 are the
     9 blank spreadsheet rows `STATUS.md` gotcha 0 already documents. **Every non-blank line
     of the current sheet is claimed.** A re-import over live data would therefore skip the
     entire collection and add only mess.

     *#32's "re-running is safe" was true and remains true — safe means it will not
     duplicate discs. It was never a claim that it would **update** them, and this entry
     exists because the two read alike right up until somebody needs the second one.*

     **The watch history raised the stakes this afternoon.** 397 unidentified films now
     carry **586 watch rows**, and they are precisely the messy-titled ones exact-title
     dedup will miss — `African Queen, The`, `39 Steps The (Robert Donat)`,
     `Apartment, The`. A tidied title in the new sheet splits the disc from the history.

     **And a wipe-and-reload is no longer available for free.** `watch_log.movie_id` is
     `RESTRICT`, so those 397 rows cannot be hard-deleted while watches point at them. That
     option was open this morning and closed at 18:16.

     **Three paths, and the choice is the owner's** (`OWNER-ACTIONS.md` 1k):

     1. **Refresh in place** — match the new sheet to existing items and update them. Needs
        an upsert path the importer does not have, keyed on something more durable than a
        line number.
     2. **Clean reload** — delete the watch rows, reload the collection, re-run the diary
        import. Viable *only because* that import is idempotent on `letterboxd_viewing_id`,
        so the history reconstructs itself from the CSVs (#176, #189).
     3. **Identify first, then reload** — give the 397 rows a real `tmdb_id` so the reload
        deduplicates on that instead of on exact title, which is the fragile part.

     **Identification was deferred at Craig's instruction**, which is reasonable and cheap
     to reverse; the note here is that deferring it does **not** save duplicated work, because
     the importer cannot back-fill identification onto an existing row. Nothing will identify
     those 754 rows except the diary import's `--identify` or the `/movies/{id}/identify`
     endpoint.

193. **`.letterboxd-export/` is load-bearing now, and it exists on one machine.**

     Path 2 above — and any recovery from a bad reload — depends on re-running the diary
     import to rebuild 1,555 watch rows. That works because the import is idempotent on the
     viewing id, and it works **only while the CSVs exist**.

     They are gitignored and must stay so: they are personal watch history (#161). But that
     means the only copies are on Craig's machine, and the retrieval that produced them was
     a deliberate one-off — 47 paced page loads, outside the product, never to be repeated
     by anything that ships (#160).

     **So they want a backup somewhere off that machine and out of the repo.** Losing them
     does not lose the 1,555 rows already in Neon, but it removes the ability to rebuild
     them, which is exactly what the reload paths lean on.

### 2026-09-16 — the replace guard, and why it does not merge instead

194. **`--replace-items` refuses while an unidentified film carries watch history, rather
     than trying to rescue the situation itself.**

     Batch 39's ordering constraint — identify before you replace — protects against a
     failure that produces no error: the new sheet's tidied title creates a fresh
     identified `movies` row, the disc attaches to it, and the watches stay behind on the
     old row. 397 films and 586 watches are exposed to it today.

     Until this was added, the constraint lived **only in prose**, across three documents.
     An agent running the live step would have stopped anyway — `batch-start.md` and
     `group-start.md` both halt on an operation that overwrites collection data — but
     **Craig running the documented command himself would not have been stopped by
     anything**, and that is the path `OWNER-ACTIONS.md` exists to describe. A constraint
     that only binds the careful reader is not a constraint.

     **The override is deliberate.** Identification cannot reach every film: some have no
     confident TMDB match and stay unidentified legitimately, so a guard with no way past
     it would eventually be worked around with hand-written SQL — which is worse than no
     guard, because it is unreviewed and unlogged. `--accept-split` names the
     **consequence** rather than the bypass, the same way `--dry-run` names a behaviour.

     **The cleverer fix was considered and rejected.** The importer could detect the old
     unidentified row by *normalised* title — S8's matcher already has
     `normalise_title` — and merge into it rather than creating a second row, which would
     remove the ordering constraint altogether.

     It is the wrong place for it. That is fuzzy matching during a bulk import **with
     nobody to ask**, and `DECISIONS.md` #32 already rejected content-keying in this exact
     importer after it collapsed "French Connection" and "French Connection 2" into one
     row. S8's matcher is safe precisely because it *offers* an ambiguity rather than
     resolving it — 28 of them on the real data (#174) — and an unattended import has no
     one to offer it to. **Identification is where that matching belongs**, and the guard's
     job is to make sure identification has happened, not to do it again badly.

195. **The 10 Blu-ray.com spec records may be lost from the active collection during the
     Batch 39 refresh; they are not transferred to replacement items.** Owner decision,
     2026-09-16, taken when `/batch-start 39` found that the batch ledger's safety premise
     was wrong: live `collection_items` held 10 spec-bearing rows, not zero.

     The old rows retain every spec field in Trash for 90 days, so the data is not erased
     by the replace transaction. The new active rows begin without specs. Craig explicitly
     accepts that active-data loss rather than expanding the batch into a spec migration.

     **Why not copy by `import_source_row`:** spreadsheet position is the unstable identity
     this batch exists to stop treating as a disc. A fresher sheet may insert, remove or
     reorder lines, and Blu-ray.com specs are edition-specific; copying them by line can
     attach a plausible, detailed and wrong specification to another disc. Losing ten
     visible records is cheaper than silently lying about ten replacements. A future
     reattachment or refetch remains a separate owner action under #110/#121's live-site
     rules.

196. **`collection_items.import_source_row` is importer idempotency, not a permanent
     database identity.** Batch 39 replaces migration 004's unique partial index with a
     non-unique live-row lookup index. The importer is the only writer of a non-NULL value
     and still checks for a live row inside each item transaction, so an ordinary run
     remains idempotent.

     A database uniqueness rule cannot satisfy both halves of the refresh contract. If it
     includes Trash, replacement inserts fail against the old rows; if it covers only live
     rows, restoring an old item fails when its replacement reused the spreadsheet line.
     §13.5 promises a full-state restore which clears only `deleted_at`, so restore wins.
     It may temporarily leave two live items with the same source line while Craig compares
     the old and replacement discs. That is honest recovery state, not a claim that a
     spreadsheet position is the disc's identity.


### 2026-09-17 — Identification could not be reached

197. **`--identify` became unreachable the moment step 1 ran without it, and nothing said
     so. Batch 40 separates identification from the already-imported skip.** The check on
     `letterboxd_viewing_id` sat *above* the match in `run_import`, so once step 1 of
     `OWNER-ACTIONS.md` 1i wrote the 1,555 watches on 2026-09-15, every entry
     short-circuited before the matcher ran. Measured against live Neon on 2026-09-17:
     Craig 1,173 entries / 593 already imported / **0 identified**; Mark 1,149 / 962 /
     **0 identified**. The command `OWNER-ACTIONS.md` 1i gives for step 2 was a no-op, and
     it reported a clean run.

     *Why:* the two halves were designed as different-sized decisions with different flags
     (#175), which was right — but they were only ever *separable* on a first run. Every
     S8 test identified on a first run, so the suite asserted the design and never the
     sequence the database would actually be in. The skip now suppresses the watch row
     alone; an entry always matches and may always identify.

     *Two things tightened in passing. Both were checked against the unfixed importer
     rather than reasoned about, and the obvious account of each was wrong.* Identification
     is now attempted once per **film** rather than once per **entry**. The reason is not
     TMDB cost — `MatchingEngine` caches on (title, year), so the repeat searches were
     already free — it is that a film the matcher **cannot** resolve kept `tmdb_id` NULL
     and so appended a fresh line to `identification_failures` for every watch it had. The
     count a person reads after the run was the wrong number. And a later entry now
     follows a row that identification merged away. That one is **not** a corruption fix,
     though the shape of the code invites the claim: re-identifying a merged-away row is
     idempotent — it merges into the same survivor again and the watch still lands on the
     right film. A test asserting otherwise passed against the unfixed code, which is how
     this was caught. What it saves is a second `get_movie_full` over the wire per extra
     watch, and a pointless delete-and-reinsert of the survivor's credits.

     *What stays true:* a dry run still spends no TMDB calls. It reports how many films it
     would identify and their local titles, but not what any becomes — resolving that
     costs the calls the rehearsal exists to avoid. The existing test asserting a dry run
     never touches TMDB is unchanged.

     *This does not identify anything.* The live run remains Craig's, is still
     `OWNER-ACTIONS.md` 1i step 2, and still has to precede the collection refresh —
     which is exactly the ordering Batch 39's guard refuses to let anyone skip (#194).


### 2026-09-18 — The refresh would have stranded the history it was protecting

198. **A sheet row TMDB cannot settle now attaches to the film the collection already
     holds, instead of minting a duplicate. Batch 41.** `upsert_unmatched_movie` looked up
     `title = %s AND tmdb_id IS NULL`. That clause was correct while every unsettled film
     was unidentified — and became a trap the moment #197's identification run gave 395
     films a `tmdb_id`. Measured on the 2026-09-18 dry run of the fresh spreadsheet:
     **401 films holding 587 watch rows** would have been duplicated, the new disc hung on
     the duplicate, and the history left on a film with no disc. Nothing would have errored.

     *Why it was invisible.* Batch 39's guard (#194) asks whether any **unidentified** film
     holds watch history. After #197 the answer was 1, so the guard passed. The case it
     cannot see is the mirror: an **identified** film whose sheet row TMDB will not settle.
     The dry run's own summary said `627 ambiguous` and nothing else — a number that looked
     like deferred enrichment rather than 587 watches about to come loose.

     *Identification made it worse, and that is the part to remember.* Before #197,
     `Double Indemnity` was a title-only row spelled exactly as the sheet spells it, and
     the old lookup found it. Doing the right thing in the right order created the hazard.

     **The fix has three parts.** `LiveFilmIndex` resolves a title against live films
     regardless of `tmdb_id`, exact first and then through the same `normalise_title` the
     diary matcher uses — necessary because identification also *tidies* titles, and 155 of
     the 395 were retitled. More than one match is offered, never guessed: seven titles name
     two live films each. And `orphan_risk` asks the question that actually protects the
     history — *will every watched film still own a disc afterwards?* — refusing unless
     `--accept-split`, on a dry run as well as a real one.

     *Measured after the fix, against production:* **5 films holding 9 watch rows**, each
     named in the refusal, against 401/587 silent before.

     *Why not let the importer take TMDB's leading candidate for an ambiguous row:* it would
     be wrong **69 times** here. The sheet's `Titanic` is #16535 (1953) in this collection;
     TMDB leads with #597 (1997). `War of the Worlds` is #74 (2005); TMDB leads with a 2024
     remake. Our own row is better evidence than TMDB popularity, which is what #31 and #174
     already say in other words.

     *A smaller thing fixed alongside:* a dry run reported `Reused a live film: 0` whatever
     the real figure was, because `ImportStats` is filled by the write path a dry run never
     runs. A zero that cannot be anything else is how this defect stayed invisible for a day.


### 2026-09-18 — A guard that names the wrong films teaches people to ignore it

199. **`orphan_risk` counts films that *lose* a disc, not films that end without one.
     Batch 42.** The first cut, shipped hours earlier in #198, asked which watched films
     would hold no live `collection_items` row afterwards. Run against production it named
     five, and **two of them were not at risk of anything**: *Project Hail Mary*, watched
     twice and never owned on disc, and *Misery*, whose watches and disc already sit on two
     different rows. Neither loses anything to a replacement.

     *Why that matters more than the two wrong numbers:* this guard's only job is to stop a
     person at a destructive command, and the override is a single flag. A guard that names
     films nothing is happening to is one a tired person learns to `--accept-split` past
     without reading — which is how #194's guard came to be passed on 2026-09-18 while 587
     watch rows were about to come loose. Precision is the safety property here, not
     conservatism.

     Measured on the same production dry run: **5 films / 9 watch rows → 3 films / 5 watch
     rows**, and each of the three is now a real one — a disc removed from the sheet, and
     two rows whose sheet title matches a different TMDB film than the one we hold.


### 2026-09-23 — Sessions never renewed, and Craig's answers on the 23 Sep snags

200. **Session renewal never worked. It does now (`aa112bd`), shipped as a fix rather than a
     batch at Craig's word.** `/auth/refresh` split the refresh token at its *first* dot. The
     token is `<jwt>.<opaque>` and a JWT carries two dots of its own, so the lookup hashed
     `<payload>.<signature>.<opaque>`, matched no row, and every renewal became a sign-out.
     Every session therefore ended when its 24-hour access token did: **30 sign-ins and zero
     renewals between 8 and 22 Sep**, read from `refresh_tokens` (a renewal's row is created
     in the same instant its predecessor is revoked; no row ever was). `/auth/logout` split
     the same way and never revoked anything.

     *The fix:* `split_refresh_token` takes the opaque half after the **last** dot and both
     routes use it; `/auth/refresh` now also verifies the signed half against the refresh
     secret and requires its `jti` and `sub` to name the row it found — which the comment in
     `_issue_tokens` had always claimed and nothing did. The web client stops signing people
     out when a renewal fails for a reason other than a refusal (#48's rule, which
     `AuthProvider` kept and `refreshTokens` did not), and keeps the tokens another tab
     rotated while its own renewal was in flight.

     *Why nothing caught it:* no test ever renewed a session. Batch 3's suite proved each
     primitive — minting, hashing, the separate secrets, the lockout — and never the chain.
     `test_auth_refresh.py` now runs sign-in → renew → renew → replay → sign-out against
     Postgres, and each new test was run against the old code first and failed.

201. **Phones get five tabs and no slide-out menu. Craig, 23 Sep, replacing the six-slot bar
     S3 and S4 built.** Bottom bar: Home · Archive · (+) · Movie night · Search — search keeps
     the slot Craig asked for on 14 Sep. Top bar: a back arrow on sub-pages, the page's title,
     and the person's initial opening a "You" page with every other destination. Page titles
     move into the top bar on every phone page, and the Archive's controls become one row.
     Desktop keeps its sidebar. *Why:* six slots forced 9px labels, two buttons opened the
     same menu, and every page repeated its own title in a block above the content. #154's
     merges and hide-when-empty rule are unchanged.

202. **Blu-ray.com specs: the full backfill, finding each disc's page through an outside
     search API. Craig, 23 Sep (option A of three).** #110 bars Blu-ray.com's own search, and
     that is why only 10 discs ever had specs: the fetcher needs an exact release URL per disc.
     A paid web-search API (Brave's, $5 per 1,000 queries with $5 of monthly credit, so
     roughly £5–10 for ~1,250 Blu-ray and 4K discs) proposes candidate release pages; a single
     strong match on title, year, format and UK edition is accepted and anything doubtful
     waits for a person to confirm. Fetching stays inside #110's bounds unchanged. *The risk
     is #110's at full volume*, which #110 already accepted for a one-time backfill; using an
     outside search engine is the new part and is what this entry records. The account and
     key are Craig's to create.

203. **eBay: a hybrid of alerts and automatic buying, within what eBay allows. Craig,
     23 Sep.** eBay's Order (checkout) and Offer (bidding) APIs are Limited Release —
     select developers approved by eBay business units under contract — so this app cannot
     place an order or a bid itself. The hybrid it can have:

     - **Buy It Now:** an alert when a price meets the target, one tap to the listing, and
       the person presses Buy.
     - **Auctions:** the alert offers to set the target as a maximum bid on eBay, and eBay's
       own proxy bidding then bids automatically up to it. That is the automatic half, done
       by eBay.
     - **True automatic purchase** only if eBay grants Buy API access, which would be
       Craig's application to make. If it is ever granted: off by default, with per-item and
       monthly caps.
     - **Never** a bot driving eBay's website with Mark's password. It breaks eBay's terms,
       puts his account at risk, and would mean storing his password.

     Reading his watch list and selling list needs his consent through eBay's own sign-in
     and a stored user token — the first personal third-party token this app holds, and the
     thing #142 deliberately avoided for selling. That is why T8 is Deep · max.

204. **A scheduled job is not the web server, and no longer needs its secrets. Shipped
     2026-09-23 (`aeb87aa`) at Craig's go.** Both Railway crons had fired on time every night
     since 10 Sep and crashed on import: `Settings()` refused production without the JWT
     secrets and a real `FRONTEND_ORIGIN`, which `.railway/railway.ts` never gives the job
     services and no job reads (only `auth.py` and `main.py`'s CORS do).

     *The fix:* `Settings.process_role` is `job` for anything launched as
     `python -m src.scripts.<name>` and `web` otherwise, unless `PROCESS_ROLE` says
     otherwise. A job skips the session-secret and browser-origin checks and still refuses an
     empty database URL. **`src.main` refuses to start as a job**, so the relaxation cannot
     reach the one process that signs sessions.

     *Why not add the secrets to the job services instead:* that's a hosting change, and it
     would hand the session-signing keys to two containers that never sign anything. The
     role is read from how the interpreter was launched because this module validates at
     import, before a script could declare anything.

     *Also decided 2026-09-23:* Craig will **not** apply for eBay's Buy API (#203's optional
     step). T8's automatic half is eBay's own maximum-bid bidding, and nothing more.

205. **Batch T2's search: one search, two sources, and four choices made along the way.
     Shipped 2026-09-23 (`fe409f3`).**

     - **An owned film nothing has identified yet is *flagged* in the "not in the
       collection" group, not hidden.** `GET /search/beyond` compares canonical titles
       (article rotated, annotations dropped, case and punctuation folded) against the
       owned films with no TMDB id. A match reads "Might be your copy of …". *Why not
       hide it:* two films can share a title, and hiding the wrong one is worse than
       asking. Tapping it opens the film card, which offers the shelf copy.
     - **The streaming line is cached for 30 minutes, in-process, for the first five
       results only.** One search types the same films several times over. `StreamingPanel`
       deliberately caches nothing, because a stale "on Netflix" is a wrong answer, so this
       is a search's worth of reuse, not a store. A failed lookup is never cached.
     - **`lastWatchedAt` is defaulted in zod, not required.** The service worker serves
       cached API responses offline, and a response cached before the field existed must
       still parse. That meant widening the web client's `parseResponse` to accept a
       schema whose *input* type differs from its output, which is what `.default()`
       produces. It was typed `ZodType<T>`, which quietly forbade that.
     - **`copyCount` may be 0 in the web schema, as it has been in the API since
       Batch 29.** A film whose only disc was sold failed to parse on its own page. Search
       now links to such films, which surfaced it.

206. **Batch T3's navigation: the choices under #201. Shipped 2026-09-23 (`90d6994`).**

     - **The back arrow uses history when there is some, and otherwise goes to the page's
       parent.** A page opened from a notification or a shared link has no in-app
       history, and `navigate(-1)` would leave the app. The parent is the longest menu
       path the page sits under, or the Archive for a film card.
     - **A page's `meta` line stays on a phone; the kicker, title and description do
       not.** Meta carries facts, like "2 overdue" on Loans, and the rest is decoration
       once the title is in the top bar.
     - **On a phone the sort is an icon that opens the full list.** On a touch screen
       every control is 44px wide (the `.touch-target` rule). A labelled sort box could
       not share a 375px row with Filters, the count and three layout buttons, and the
       touch target is not negotiable.
     - **The layout switch spells out Grid, List and Compact only from 1536px.** At
       1280px, next to the sidebar, the words pushed the row 22px past the edge.
     - **The sidebar is desktop-only, and its drawer code is gone.** Nothing opens it
       below 1024px any more. Keeping a drawer that nothing opened would have been dead
       code with a focus trap in it.

207. **Batch T4's movie night: the choices. Shipped 2026-09-23 (`99b04c0`).**

     - **Movie-night pushes go out at once, "It's a match" included.** They were queued
       and nothing more. Only the scheduled jobs delivered, and they crashed every night
       until `aeb87aa` (#204), so a match never reached a phone. Delivery now runs
       straight after the commit, for the people concerned. Quiet hours still defer, to
       the morning pass. A failed push never fails the vote or the invite; the
       notification stays queued for the next pass.
     - **Only an account that can sign in can be sent a night.** A profile with no PIN
       (the state migration 002 seeds) would get a night in a list it cannot open. In
       production both accounts have a PIN, so "send to everyone else" means Mark.
     - **Sending puts the person in the night**, so it is in their list before they open
       anything. One push per person per night, by dedupe key; sending twice changes
       nothing.
     - **Arrow keys vote only in the deck.** On the list there is no single film an arrow
       would mean.
     - **The floating assistant button hides on a movie night.** It sat on top of the
       deck's Add button, and a mis-tap there costs a vote. The wider question
       (`OWNER-ACTIONS.md` item 11) stays open.

208. **Batch T5's release calendar: asked by release type, and fresh without a schedule.
     Shipped 2026-09-23 (`1e08f40`).**

     - **TMDB is asked for releases by type, not for "upcoming" films.** `/discover/movie`
       with `region=GB` and `with_release_type=5` applies the date window to the GB
       physical releases themselves. S6 looked for disc dates among films about to reach
       cinemas, which almost never have one yet. **The first live run found 28 disc
       releases (18 4K, 10 Blu-ray)**, where the table had held none, plus 131 cinema
       dates to March 2027.
     - **Disc releases are not genre-filtered; cinema dates still are (§7.3).** A disc
       calendar for a collector is about the discs: the 4K re-issues of *Blood Simple* and
       *Inside Llewyn Davis* would not survive a filter built from the shelves' top genres.
     - **Freshness comes from reads, not a timer.** A read of a calendar more than a day
       old starts one refresh after the response, claimed by a conditional `UPDATE` of a
       single-row state table, so two readers cannot start two. The `.ics` feed's polls
       count as reads. #60's objection is to in-process *scheduling*, and nothing here
       runs on a clock. The cost: a calendar nobody reads goes stale, and nobody minds.
     - **In tests, the background refresh is a no-op unless a test is about it.** It
       takes a real session of its own, which in CI committed curated sale events into
       the shared test database and broke an unrelated test. CI found it before merge.

209. **Batch T6's collection value: the choices. Shipped 2026-09-23 (`9acd0ee`).**

     - **Priced per film and format, counted per disc.** One eBay search prices one film on
       one format, so the 1,457 physical discs need 1,454 searches. Two copies count twice
       in the total. A 4K box with a Blu-ray inside is priced as a 4K. Downloads are left
       out: they cannot be resold.
     - **The film page's estimator, moved rather than copied** (`src/ebay/estimate.py`), so a
       stored value and a live check of the same disc agree. Its headline is the largest
       group of standard-edition listings in one condition, which is often "New", so a disc
       listed mostly new reads high.
     - **Three matching listings, or "not priced".** A median of two is one seller's asking
       price (#129). The table's CHECK makes a price without "priced", or the reverse,
       unstorable.
     - **750 calls a day, 15% of eBay's 5,000, counted per UTC day.** The first full
       valuation takes two days and leaves the rest of each day for the film page, barcode
       lookups and T8. A rolling 24 hours would starve a nightly job, because its previous
       run would always still be inside the window. A run never starts on fewer than three
       calls, one search and its retries.
     - **Re-priced every 30 days**, films that could not be priced included.
     - **One run at a time**, held by a partial unique index. A run silent for 30 minutes is
       closed by the next start or by anyone reading the total, so Home never shows a dead
       run as pricing. **Five eBay failures in a row, or one 429, stop a run**, and old
       prices stay.
     - **Two ways to start a run.** Home's button (admin only; it runs in the web service,
       which already holds the eBay keys) and `python -m src.scripts.value_collection` for a
       scheduled job. A job would need eBay keys on a job service, a hosting change that is
       Craig's.
     - **Mark sees the total and each disc's stored value; only Craig can start a run**,
       because a run spends the allowance the film page's check also uses.
     - **Known limits.** The search does not use the year, so a remake's listings mix with
       the original's, as they already do on the film page. A film sold in the UK under
       another title (*The Avengers* as *Avengers Assemble*) finds nothing and is marked not
       priced.
     - **The documented local mypy command was weaker than CI's.** Run from the repo root,
       it never loaded `apps/api/pyproject.toml`, so strict mode was off, and CI caught a
       query result returned as `Any`. `AGENTS.md` and `batch-verify.md` now pass
       `--config-file`.

210. **Release reminders push 4K and Blu-ray releases only, never cinema dates. Shipped
     2026-09-24 as a fix (`59808f4`).** The rule covered every calendar entry except a sale,
     which was harmless while the calendar was nearly empty and the reminder job never ran.
     Batch T5 filled the calendar with six months of cinema dates, the jobs fix (#204) made
     the job run, and the first real run, at 08:04 UTC on 24 Sep, sent Craig **27 pushes, 23
     of them for films in cinemas** such as *Aaram* and *Acharya*. Cinema dates stay on the
     calendar to be looked at. The rule's own comment always said "a disc coming out". About
     3 disc releases a week are expected to push. Mark got none only because his phone's
     push registration had expired. **Craig kept every disc release on 24 Sep**, rather than
     narrowing pushes to films he owns or wants; narrowing stays open if it proves noisy.

211. **eBay network failures are retried, and the first valuation ran. 2026-09-24 (`e256d65`,
     at Craig's word).**

     - **A dropped connection or a timeout is now retried like a 5xx**, and raised as an
       `EbayError` if it persists. It used to escape as a raw `httpx` error: the film page's
       check answered 500, and the first valuation run stopped at call 574 of 750. Nothing
       was lost, because each film is committed as it is priced.
     - **Day one, 24 Sep:** 748 of the day's 750 calls; 639 films and formats priced, 108 not
       priced, 0 failed; 707 due on 25 Sep. **641 of 1,457 discs priced, £11,844.31 at current
       asking prices.** Medians so far: 4K £28.84, Blu-ray £15.76, DVD £7.15.
     - **Films never matched to TMDB price far worse:** 29% not priced, against 7.5% for matched
       films. Their spreadsheet titles carry typos (*Captain Ameica*) and mid-title articles
       (*Godfather, The Part III*) that no listing contains. Identifying those films is the
       fix, not the valuation.

212. **Batch T7's Blu-ray.com backfill: the choices. Built 2026-09-24 on
     `feat/t7-bluray-backfill` (`829737f`), CI green, not merged until Craig's Brave key
     is in (`OWNER-ACTIONS.md` 17).**

     - **Brave proposes the pages; Blu-ray.com's own search stays barred (#110).** Only an
       exact release URL counts, checked by #110's predicate in code and by a CHECK on
       both tables that store addresses.
     - **What "one strong match" means.** Same film (titles reduced as identification
       reduces them), same format ("4K Blu-ray" or "Blu-ray", never 3D) and a UK edition.
       Blu-ray.com ends a non-US release title with its country, as in "Fight Club Blu-ray
       (MetalPak) (United Kingdom)"; no country is the US. One such page is accepted. When
       several UK editions match, the one plain release is accepted if there is exactly
       one: no disc records its edition, and a steelbook usually holds the same disc.
     - **Never accepted automatically:** a film with no year (245 of the 1,250 discs) and a
       disc whose grouping reads like a box set ("Box Set", "Collection", "#2"). They wait
       for Craig.
     - **The year is checked after the fetch**, from the page's year link, within one year.
       A page that fails goes back to Craig with the reason, and its specs are not used.
       Pages Craig chose himself are not second-guessed.
     - **Budgets:** 150 searches and 150 page fetches a batch, and 1,500 searches a calendar
       month, all counted per batch. Fetching keeps #110's five-second spacing and its halt.
     - **The 10 Sep specs were mostly US pages.** Kick-Ass and Up are region A, and Blade
       Runner 2049's page (189774) and Fight Club's (5587) are the US editions. So those
       specs are copied onto the new discs only when the search shows their page is the UK
       edition of the right film and format. Otherwise the old page is offered to Craig,
       flagged.
     - **The Dolby Vision, Atmos and Region-free filters hide until a disc has specs** (#154).
     - **Nightly batches need a new job, `cron-specs` at 02:00 UTC**, declared in
       `.railway/railway.ts` with the Brave key by reference. The same change preserves the
       Brave key and the eBay keyset, which closes item 1b on apply. Craig applies it only
       after a first batch has been run and checked by hand.
     - **Not yet verified:** a real Brave response. The client follows Brave's documentation,
       and the first live search is the check.
     - **The documented local gate missed two CI steps**, `pnpm --filter @mcu/shared
       typecheck` and `... build`. A duplicate import passed every local check and failed
       CI. `AGENTS.md` and `batch-verify.md` now list both.

213. **Batch T7 live: three watched batches, and sharper matching. 2026-09-24 (`160f842`,
     `bfc28e7`).**

     - **Three batches, run by hand and checked:** 314 Brave searches, 188 Blu-ray.com pages
       fetched five seconds apart, 178 discs with specs, and no halts or failures. Brave's
       real responses matched its documentation. The accepted pages were checked by hand
       against their films; all were the UK edition of the right film and format.
     - **The 10 Sep records were checked page by page, and none was a UK edition**, so none
       was copied. Nine of those ten discs now have UK specs fetched fresh; Kick-Ass, for
       one, went from region A to region-free.
     - **The year check earned its place.** It stopped 10 pages for remakes (Ben-Hur 2016
       for 1959, Cape Fear 1962 for 1991) and flagged two films whose TMDB match looks
       wrong: Band of Brothers recorded as 2019, Bad Neighbours as 2026.
     - **Sharper matching (`bfc28e7`).** "&" reads as "and" (Angels & Demons), a leading
       article is ignored (Bride of Frankenstein), and a bracket that only names a
       publisher's line or says "Standard Edition" leaves a release plain ("Up Blu-ray
       (PIXAR)", "(Indicator Series)"). Each batch also takes a second look at discs the
       matcher left for Craig, from the stored results and without searching again; it
       settled 10 on its first run. A page that failed its year check is never chosen
       again by it.
     - **43% of discs searched still need Craig** (136 of 314): no UK page matched 52,
       several UK editions 32, no year 28, box sets 14, remakes 10. Films never matched to
       TMDB are 56 of the 136, and all 28 undated ones. Identifying them is the largest
       lever left; the matcher is not.


### 2026-09-25 — Batch T9, identifying the unmatched films: the choices

214. **T9 is built on `feat/t9-identify-films`, CI green. A dry run against production
     writes nothing; the live run waits for Craig's go.** These are the choices made on his
     behalf, each open to overrule.

     - **"The same title" includes TMDB's obscure namesakes, as the ledger's rule says.**
       TMDB holds 15 films called "Speed", 50 called "Emma" and 64 called "The Letter",
       mostly unrated shorts. So a one-word title with no year and no name waits for Craig,
       with the best-known film offered first: one tap. *Why not treat unknown namesakes as
       no rival:* TMDB's own ranking cannot be trusted to put the real rivals first. Its
       search for "Seven" does not show "Se7en" in twenty results.
     - **A title that is ours plus a subtitle is not a namesake**, or "Death on the Nile:
       Making of Featurette" hides the 1978 year that decides "Death on the Nile [1978]".
       Matching one side of a colon is allowed but weak: the start of TMDB's title ("Dr.
       Strangelove") is taken only with a year or a name agreeing, and the end of it ("INXS:
       Live Baby Live") never, because that is also how a documentary about a film is named.
       An early version took "Unseen + Untold: National Lampoon's Animal House" for the film.
     - **Alternative titles count only as the same title, in any language.** They are how
       "Marie Walewska" (French) finds Conquest (1937) and "Ice Age 3" finds Dawn of the
       Dinosaurs. A number on one side of a colon in one is not evidence: Furious 7's Spanish
       title "A todo gas: 7" was taken for "Seven" by an early version.
     - **A rival known by the title only as an alternative title is still a rival.** The
       first dry run took Shortcut to Happiness (2007) for "The Devil and Daniel Webster":
       TMDB lists the 1941 film as "All That Money Can Buy", so the rival check, which read
       only display titles, never saw it. The alternative titles of up to eight films the
       title's own search returns are now read before "no other film of this title" is said.
     - **The disc's grouping counts as a name, like one in brackets, but weaker.** Craig's
       shelf headings name the director or star ("Clint Eastwood", "Powell & Pressburger",
       "Hitchcock Early Collection"). A grouping name that TMDB confirms on exactly one film
       of the title decides it; one that confirms none is no objection. A name in the title's
       own brackets must be confirmed, or the film waits. A name after a dash ("Indiana
       Jones", "INXS") is weak, like a grouping: it is often a franchise or a band.
     - **A full name is checked against the person's own films, a surname against each
       namesake's credits.** The person's films cover every namesake, however many ("The
       Letter", Bette Davis, 64 namesakes). A surname ("Hitchcock") can decide among up to
       40 namesakes; past that it cannot, because they were not all checked.
     - **One Brave search at most per title, for its TMDB page, after TMDB's own searches,
       alternative titles and TV index have all failed.** Each page it finds is fetched from
       TMDB and counts only if TMDB's record matches. Budget 60 a run, inside the monthly
       ceiling T7 shares; calibration needed 24.
     - **TV is set aside on the words a box of episodes is sold under** ("Complete Series",
       "Series 1 - 3", "Seasons", "(TV)"), **on Craig's "TV" grouping, or when only TMDB's TV
       index knows the title.** "Season 2" alone is not enough: "Open Season 2" is a film.
       A film that shares its name with a better-known series waits for Craig unless a year
       or name backs it. A web search whose first TMDB page is a series counts only when the
       series has this title: the first dry run set "Munch - Our Greatest Hits" aside as TV
       because Brave led with an unrelated series called "Munch".
     - **The dry run writes a plan file and a report; the live run applies that exact plan**,
       re-checking each film first (live, unidentified, same title, still on the shelf, not
       already decided by Craig). What Craig reads is what happens, and Brave is not paid
       twice. The dry run reads the collection in a short read-only transaction, so Postgres
       refuses any write, and ends it before TMDB is asked anything: the second 25 Sep dry run
       held it through half an hour of searches, Neon closed the connection, and the finished
       plan was lost on the rollback. *Its Brave searches are recorded by the live run*,
       because the dry run writes nothing; until then they are in the plan and the report.
       Dry runs never applied are added with `--earlier-searches` (about 54 on 25 Sep).
     - **A merge carries every row that points at a film** — discs, watches, wanted rows,
       movie-night suggestions and votes, calendar entries, barcode lookups, deals — and
       drops only a duplicate the kept film already has (one person's second vote on the
       same film in one night). Before this, a merge of any film someone had suggested for a
       movie night failed on a foreign key, and its votes vanished. 14 unmatched films had
       suggestions. **Nothing merges into a film in the Trash.**
     - **Every identification is audited and can be undone, merges included**, from the
       Identify films page. The audit keeps the title replaced, the row's old metadata and
       credits, and, for a merge, the merged-away row and the ids of every row moved. Rows a
       merge dropped as duplicates stay dropped on undo. The film page's own Identify goes
       through the same audited path, still merging as it always has.
     - **The title identification replaces is kept as an alias, and the collection refresh
       resolves sheet titles against aliases too.** Without it #198's guard would stop
       working for every typo T9 fixes: the sheet still says "Peepiing Tom", no
       normalisation reaches "Peeping Tom", and the refresh would mint the typo again and hang
       the disc on it.
     - **A valuation taken before its film was identified falls due**, because the stored
       value was searched under the old title and no longer agrees with the film page's check
       (#209). Nothing falls due today; only identifications from now on trigger it.
     - **T7's second look now also reconsiders a disc left for having no year**, once its
       film has one. It judges the stored search results again; it does not search again.


### 2026-09-25 — Batch T9 live: the run, and what followed it

215. **T9 shipped (`4d16723`), and its live run applied Craig's approved plan once. 25 Sep,
     at his go.** Production serves `4d16723` with `db: ok`, and migration 038 is applied.

     - **The live run did what the report said.** 156 identified, 166 waiting on You →
       Identify films, 35 set aside (34 TV, 1 test row), 0 left alone and 0 failed, in four
       minutes. Every identified film now has a year. 120 replaced titles are kept as
       aliases; the other 36 already read as TMDB's title. There are 191 audit rows, one per
       film changed. **Nothing merged.** The 10 would-be merges wait for Craig with both
       films shown. One is "Kingsman", offered The King's Man (2021) first, though the 4K is
       probably Kingsman: The Secret Service. The films whose titles have better-known
       namesakes (Mr & Mrs Smith, The Ring, Mutiny on the Bounty, Lolita, Last Holiday, The
       Rookie) were each decided by the disc's shelf grouping, confirmed in TMDB's credits.
     - **Brave was counted once.** The run recorded the plan's 26 searches plus the 54 of the
       two dry runs never applied, 80 in all. After the day's spec batch the month stands at
       542 of 1,500.
     - **The second look settled 9 of the 18 queued discs of identified films.** All 9 were
       fetched and kept their specs; the year check sent none back. 4 had waited for having
       no year and 5 for "no UK page". The other 9 still wait, because the second look judges
       the stored results of a search made under the old title and never searches again.
       The same batch searched 148 discs nobody had searched before, 19 of them of
       identified films; 14 of those now have specs.
     - **The Disc specs queue grew from 136 to 197.** Of the 148 new searches, 63 were left
       for Craig, and 7 accepted pages failed the year check. 61 of the 197 are discs of
       films still waiting on Identify films, so identifying those first lets the next
       second look decide more. 7 are discs of TV series T9 set aside (Game of Thrones Season
       1, Blue Planet II); with no year, they always wait for Craig.
     - **Valuations.** Identifying 156 films made 133 films and formats due again (#214). The
       pass had only the 43 eBay calls left on 25 Sep after the first valuation's second day.
       It re-priced 41 (32 priced, 9 not), a net 9 more priced, taking the total to
       £22,951.01 (up £140.73). 92 stay due until the next run, which can start from 00:00 UTC
       on 26 Sep. Nothing schedules it.
     - **The browser check used #169's method.** The dev server ran with `VITE_SKIP_AUTH`
       against a scratch stub. The stub served the page's responses as the real routes
       produce them from production, read in a read-only transaction. At 375 px and 1280 px,
       reached from You, the page showed the overview, the first 20 waiting films with their
       candidates and merge warnings, and 20 recent identifications, each with Undo. There
       was no horizontal scroll. Nothing from the harness is in the tree.


### 2026-09-26 — T8 split, and discs searched again after identification

216. **Craig's answers of 26 Sep, on T9's report.**

     - **T8 is split.** T8a, price alerts and the deal scan, comes first. It uses the app's
       own eBay access, signs nobody in and stores no personal token. T8b, "Connect eBay"
       for Mark's watch and selling lists, follows once Craig has set up eBay sign-in and the
       encryption key (`OWNER-ACTIONS.md` 18). *Why:* only T8b needs the first personal token
       this app would hold (#142), and only T8b waits on Craig. T8a still has one owner step:
       its schedule is a Railway job, which Craig applies.
     - **A queued disc whose film was identified after its search is searched again, once
       (T10).** T7's second look judges stored results and never searches again (#213). A
       disc searched under a misspelt title therefore stays stuck, as 9 of the 18 queued
       discs of films T9 identified did (#215). About 70 discs qualify now or will as Craig
       works through Identify films: under £1 of Brave searches, inside the free credit.
     - **Order:** T10, then T8a, then the eBay checkpoint, then T8b. Effort: T10 high, T8a
       xhigh and T8b max, each open to overrule. Nothing starts before Craig's go on this
       plan.


### 2026-09-26 — Batch T10: discs searched again after identification

217. **T10 shipped (`db75229`, migration 039), and a batch run by hand proved it. 26 Sep, at
     Craig's go (#216).**

     - **Which discs.** A queued disc (waiting for Craig, without specs, not decided by him)
       whose film was identified after the disc was searched, and whose search words would
       now differ. Identification is the only thing that rewrites `last_tmdb_sync_utc` on a
       film that already exists. A merge rewrites the kept film's too, which is why the words
       must differ as well: the kept film's own discs were searched under its title already.
       A disc whose page failed its year check stays with Craig, as the second look leaves
       it, so no page is accepted anew that way.
     - **Once, without a flag.** The new search is later than the identification and uses
       the film's words, so neither condition holds afterwards. Identifying the film again,
       after an undo say, makes the disc eligible once more.
     - **First, and inside the budgets.** Discs searched again go before discs never
       searched, and count in the batch's 150 and the month's 1,500. The new search's
       candidates replace the old ones; a page the 10 Sep test used stays offered. Each batch
       records how many discs it searched again and how many the matcher then accepted
       (`spec_runs.searched_again`, `settled_again`).
     - **Only 5 discs qualified, not the ~70 #216 estimated.** The estimate counted every
       queued disc of a film identified or waiting to be. Most discs left from T9 had cleaned
       spreadsheet titles that already read as TMDB's, so a second search would send the same
       words. The 61 discs of films waiting on Identify films qualify only where
       identification changes the words.
     - **Live, 26 Sep: 148 Brave searches, the 5 first.** The Fellowship of the Ring got its
       specs. Dr. Strangelove's page was accepted, but Blu-ray.com answered 301 (moved), so it
       waits for the next batch. The other 3 now show Craig 2 or 3 UK editions, or no UK page,
       from the right title. In all, 82 discs gained specs, 347 of 1,250 have them, and the
       queue grew from 197 to 257 because 143 discs were searched for the first time. CI
       passed first time.
     - **Found, and not changed here:** the fetcher treats a 301 from Blu-ray.com as a failed
       load. A page whose address moved is tried in three batches and then sent back to
       Craig. Following a redirect is #110's ground, so it is a separate decision.


### 2026-09-26 — Batch T8a, eBay price alerts and the deal scan: the choices

218. **T8a is built on `feat/t8a-ebay-alerts`. Its merge waits for Craig's OK, because it
     declares a Railway job (`.railway/railway.ts`), and the schedule starts only with his
     config apply.** These are the choices made on his behalf, each open to overrule.

     - **The deal scan reads eBay's newest listings, not the films one by one.** Measured on
       26 Sep: about 200 new UK Blu-ray and 4K Buy It Now listings every two to three hours,
       so reading all of them costs a few calls a pass. Searching the ~1,300 films that
       could be bought better, one by one, would cost that many a pass and still see each
       film only now and then. A pass reads newest first back to where the last one stopped,
       ten pages at most; in a flood the older ones are skipped.
     - **A listing is a film only when the film's title opens the listing's title**, after at
       most four seller's words ("NEW", "4K UHD", a studio such as "Lionsgate"). The film
       page's matcher then judges it as it judges its own searches: sequels, subtitles, box
       sets, accessories and formats. Two catalogue films of one title make no match. *Why:*
       the matcher alone accepts a title anywhere, and "Up" is a word in thousands of
       listings.
     - **Which films:** those on the Wanted list, on any format unless it names one; and
       owned films, when the listing's format beats the best one on the shelf (Batch 22's
       rule). About 1,300 owned films qualify. A DVD is never a deal.
     - **"Well below" means 30% or more under the usual asking price, postage included.**
       The usual price is the film page's own median for the film on that format, compared
       within the listing's condition when three or more listings stand behind it, else the
       headline. It is kept for a fortnight. With fewer than three listings there is no
       yardstick and no deal.
     - **Finds go on the Deals page as "eBay", reading "with postage, usually £X", for three
       days.** Nothing re-checks them, so they expire rather than linger as sold listings.
     - **Pushes are in the `deals` category.** A target tells only the person who set it. A
       deal tells both people, as the Wanted list's price drops do: Wanted-list finds first,
       then the biggest discounts, **at most five deal pushes a person a day**. With ~1,300
       upgradeable films, more would be noise; the rest wait on the Deals page. Pushes go at
       the end of each pass, and quiet hours still hold.
     - **A listing target** starts from the listing's address (a bare number works; a short
       `ebay.us` link does not carry the number and is refused with directions). Buy It Now
       counts with postage. An auction's current bid counts alone, and the push offers the
       target as a maximum bid for eBay's own bidding (#203). Met once, then left alone
       until its target changes. One already at or under its target is saved as met,
       without a push.
     - **A saved search** is a film on a format: any UK Buy It Now copy at or under the
       target, postage included. Auctions are left out, because a week-early opening bid is
       not a price. It stays watching, and each listing is told once.
     - **The film page's panel sets a saved search; a listing is added by its address.** The
       criterion written on 26 Sep said a target could come from "a listing from the film
       page's eBay check". That check shows medians, not listings, so the premise was wrong.
       The film page instead has an alert panel for both people, since the check itself is
       an admin tool.
     - **The budget:** a pass every two hours at twenty past, within 500 eBay calls a UTC day
       (10%), beside the valuation's 750. One pass at a time; a pass silent for 30 minutes is
       abandoned.
     - **Each person sees only their own alerts**, and both can set them. Price alerts sits in
       the Explore group and is always shown, since it is where the first alert is set.
     - **A tapped push that links off the app opens in its own window.** The service worker
       used to steer the app's window to any link, which for an eBay listing would replace
       the app.
     - **A merge carries saved searches to the kept film** and drops a duplicate, as it does
       Wanted rows (#214). An undo moves them back.
     - **Checked live on 26 Sep:** the newest-first search with its filters, one listing by
       number, and a listing number eBay does not have, which answers 404 (error 11003) and
       marks a target ended. A listing that has ended is taken to answer the same, or to show
       a past end date or no stock, and each of those ends the target too.
     - **The sidebar grows from seven to eight** for someone who is not an admin, with Price
       alerts always shown. The navigation test pinned seven and now pins eight, with the
       reason. This is Craig's to overrule: the alternative hides it until the first alert,
       which leaves only the film page's panel as a way in.
     - **The browser check** used #169's method, as Mark, at 375 px: the Price alerts page and
       its form, the film page's panel (film data captured read-only from production through
       the real routes), the Deals card and the You page. **It found a Deals bug older than
       T8a:** a card was as wide as its longest title, so on a phone its right side was cut
       off. No deal has ever been stored, so nobody had seen it; an eBay title is 80
       characters. Fixed with `min-w-0` on the card.
     - **A dry pass against live eBay and the real catalogue, writing nothing (26 Sep, the
       previous six hours):** 859 new UK Blu-ray and 4K listings in 5 pages; 21 were a Wanted
       film or an upgrade (all upgrades, as none of the 8 Wanted films was listed); 2 were
       deals: *When Harry Met Sally...* on 4K at £16.00 against a usual £29.99, and *Batman v
       Superman* on 4K at £27.99 against £39.99. 25 eBay calls. At that rate a day brings about
       eight finds, which the cap of five pushes a person keeps from being noise.
     - **Not yet seen live:** a scheduled pass (it needs the apply) and a push on a phone
       (Mark's notifications are off, `OWNER-ACTIONS.md` 16b).
     - **Craig said OK to merge on 26 Sep, and chose to keep Price alerts always shown.** It
       shipped as `e2142b7`; migration 040 is applied.
     - **The first scheduled pass, 12:21 UTC on 26 Sep, after Craig's config apply:** 15 eBay
       calls, 363 new listings, 13 upgrades given a usual price, and 3 deals, 32% to 40% under
       it. The 3 pushes reached Craig; Mark's were suppressed, as he has no device registered.


### 2026-09-26 — Batch U1: Blu-ray.com pages that have moved

219. **A moved Blu-ray.com page is followed once, and only to the same release. Built 26 Sep
     on `feat/u1-moved-bluray-pages`, at Craig's go on Group U's first step.** Until now a
     redirect counted as a failed load, so a page whose address changed (Dr. Strangelove's,
     accepted on 26 Sep, #217) was tried in three batches and then sent back to Craig.

     - **What a redirect does now.** A `301`, `302`, `303`, `307` or `308` is read, not
       followed by the HTTP client (`follow_redirects` stays off). Its address is judged by
       #110's release-page predicate **and must carry the same release number**: Blu-ray.com
       renames a release by changing the name in `/movies/<name>/<number>/` and keeping the
       number. Only then is one more request made, and only once; a second redirect is not
       followed. The disc's accepted page and its specs' source become the new address, in
       the stored form (`https://www.blu-ray.com/movies/<name>/<number>/`).
     - **Why this stays inside #110.** #110 accepts requests for exact release pages,
       sequential and spaced, and nothing else. The one extra request is for exactly such a
       page: the same release the disc was matched to, at the address the site now gives it,
       which the fetcher would have requested directly had the search seen the new name. It
       is checked by the same predicate before it is sent, it waits the same five seconds as
       any request, and a `403` or `429` to it halts the whole integration as the first
       request's would. Nothing new becomes reachable: not the search routes, not another
       release, not another site, not images or scripts, and no redirect is ever followed
       blind. #110's own words, "exact release URLs" and "evade an access control", are met
       rather than stretched: the address is exact, and a site that sends a page elsewhere
       is not followed there.
     - **Anywhere else goes straight back to Craig**, at once rather than after three
       batches, with the address it pointed to in the note; that address is never
       requested. Five in a row stop the batch, as five failed loads do, so a site sending
       every page to a sign-in or CAPTCHA page costs five discs rather than a batch. That is
       not a halt, since #110 names `403` and `429`; the notes show Craig where the pages
       went, and the Halt button is his.
     - **What is counted.** The integration's fetch count still counts pages read, so a
       followed move adds one, and a batch's `fetched` counts the page once. A move sent
       elsewhere counts in the batch's `sent_back`.
     - **The same rule holds for the admin's `POST /specs/fetch`**, which shares the fetcher:
       a page that moved is stored at its new address, and one sent elsewhere is reported as
       failed with the reason.
     - **Tests:** which moves are followed (every redirect status, a relative address,
       another release, a search route, a sign-in page, another site), without a request;
       and against Postgres in CI, a renamed page settling in one batch, Craig's own page
       kept at its new address, one sent elsewhere going straight back, a `429` from the new
       address halting everything, the five-second spacing before the second request and
       the next disc's, a second redirect not followed, and five in a row stopping a batch.
     - **Shipped as `cb1111f` on 26 Sep, and proved live the same day.** Local gate and CI
       green first time. A batch run by hand at 14:35 UTC settled Dr. Strangelove's disc at
       14:37: its accepted page answered `301` to a new name for release 117642, the fetcher
       followed it five seconds later, and the disc's page and its specs' source are now the
       new address (region-free, 1080p, Sony Pictures). It was the only page in the batch
       that had moved. The batch: 148 Brave searches, 88 accepted, 89 pages fetched, 83 with
       specs, 6 sent back (all the year check), no failures. 430 of 1,250 discs have specs,
       323 wait for Craig, and Brave stands at 838 of the month's 1,500.
     - **The first scheduled batches, 27 and 28 Sep** (checked read-only on 28 Sep). 27 Sep,
       02:02–02:13 UTC: 148 searched, 93 accepted and 55 queued for Craig, 93 pages fetched,
       91 given specs, 2 sent back by the year check, no failed loads; it stopped at its
       150-search cap. No page had moved, so nothing was followed or refused; 15 of the discs
       it settled now carry an edition (#220). 28 Sep, 02:02–02:03: stopped after 14 discs
       (9 given specs, 2 editions) because Brave answered `402`, payment required. Its free
       monthly credit, about 1,000 searches, was spent at 1,005 by the app's count; the app's
       own ceiling is 1,500. Every batch stops at its first search until the credit renews or
       Craig raises the spending limit, and nothing is charged meanwhile.


### 2026-09-26 — Batch U2: each copy's edition

220. **Each copy can hold an edition, filled from its Blu-ray.com page only where that page
     is certainly the copy. Built 26 Sep on `feat/u2-copy-editions`, at Craig's go on U1 →
     U2, which included his yes to the new column. Replaces `OWNER-ACTIONS.md` 12.** These
     are the choices made on his behalf, each open to overrule.

     - **The column.** `collection_items.edition` (migration 041): free text, nullable, 100
       characters, like the Wanted list's `preferred_edition`. Set and corrected on the copy
       form, for a new disc and an old one; a blank one is no edition. Changes are in the
       copy's history like any other field.
     - **An edit that leaves it out keeps it.** Every other field on the edit body is a full
       replacement (Batch 8), but a client built before editions existed (an app cached on a
       phone, an edit queued offline) never sends one, and must not clear it.
     - **Which pages are certainly the copy.** Craig chose it from the list, or pasted it; or
       the search found exactly one UK edition of the film on that format, by the verdicts
       stored at the time and by today's matcher alike, and no result whose title was cut off
       before its country (such a result could be a second UK edition: "I, Robot Blu-ray
       (Zavvi Exclusive SteelBook ..." was one). **The plain release among several UK
       editions (#212) gives none:** it is a sound bet for specs and no evidence of which box
       is on the shelf.
     - **The name comes from the page's title as the search saw it**, the only name stored.
       Blu-ray.com brackets everything that is not the film's name, so only the parts that
       name an edition are kept: an edition, cut, package, shop exclusive or publisher's line
       ("SteelBook", "Extended Cut", "HMV Exclusive", "Masters of Cinema"). Alternative titles
       ("MIB", "Twelve Angry Men"), packs of formats ("Triple Play", "Combi Pack"), a studio's
       brand ("PIXAR") and "Standard Edition" give none. Several parts are joined with " · ";
       a name longer than the column is left out rather than cut short.
     - **Two cases give no name, and the edition stays blank for Craig:** a page that has
       moved since the search (U1, #219), since its old name may no longer be its name; and
       a page Craig pasted that the search never offered. Nothing is read from the page
       itself: no real page's title markup has been captured, and fetching one to learn it
       would be a request #110's batches do not need.
     - **When.** A spec batch fills a disc's edition as it settles it, and never over one
       already there. A one-off script (`python -m src.scripts.fill_editions`, a read-only
       dry run unless `--apply`) fills the discs settled before editions existed. Nothing
       re-fills later, so an edition Craig clears stays cleared.
     - **Browsing.** Each film in the archive list carries `editions`: the distinct editions
       of its owned copies, alphabetical, read for the whole page in one grouped query as its
       shelves are, never one query per film. The film page's detail carries it too, and each
       copy its own `edition`. The zod schemas default both, so a list or a copy cached
       offline before editions existed still parses. The grid card shows editions under the
       shelf; the list view after the shelf on a phone and under the title on a desktop; the
       compact view after the shelf; the film page leads each copy's card with its edition.
     - **"Forget everything from Blu-ray.com" takes the editions it wrote** (#110: all derived
       data can be removed): one equal to what the disc's page names goes, one Craig typed or
       corrected stays.
     - **"Collector edition" is now "Sub-category", in three places** (the copy form, the
       film page, the history). The field is the spreadsheet's "Sub Category", and it holds
       groupings, not editions: "Clint Eastwood" on 64 discs, "Hitchcock" on 30, "The James
       Bond Collection Box Set" on 20. Beside a real Edition field the old label would have
       invited editions into the wrong box. The two tests that pinned the old label now pin
       the new one; the film page's test fixture had put "Criterion Collection" in that field
       and now puts it in the edition. Craig's to overrule.
     - **The dry run, read-only against production before the merge:** of 430 settled discs
       (all chosen by the matcher; none by Craig yet), 233 are certainly the copy and 83 of
       those name an edition; the other 150 name none, most being plain releases. 197 are
       not certain (the plain one among several UK editions, or a result cut short).
     - **The browser check used #169's method**, with the archive list, a film page and its
       copy form captured read-only from production through main's own routes, and the 83
       editions the backfill would write added. At 375 px and 1,280 px: the grid card, the
       list and compact views and the film page's copy card showed the edition, and the copy
       form held it beside the relabelled Sub-category. No horizontal scroll, no parse errors.
       It found one thing, fixed: the Sub-category placeholder ran off a phone's field.
     - **Shipped as `52fcced` on 26 Sep; migration 041 applied.** Local gate and CI green
       first time (1,593 API tests against Postgres). **The backfill wrote 83 editions**, all
       to copies whose page was the one UK edition the search found (none chosen or pasted by
       Craig yet), one copy per film, and identical, id for id, to the dry run made before
       the merge: HMV Exclusive 17, Masters of Cinema 10, Vintage Classics 10, SteelBook 8,
       Zavvi Exclusive SteelBook 4, Arrow Academy 3, and 31 others. Read through the real
       list route afterwards: 83 of 1,866 films carry editions, and the list takes 6 queries
       for the whole catalogue, as for a page of 20.
     - **Craig kept "Sub-category" on 26 Sep**, after the merge. The live web app serves U2's
       build: the copy form and film page carry the Edition field and the new label.


### 2026-09-26 — Batch U3: the assistant button, `/debug`, the brand files

221. **Craig's three picks, built: the assistant moves into the top bar, `/debug` exists in
     development builds only, and the third-party brand images are untracked and ignored
     (pick B). Built 26 Sep on `feat/u3-assistant-debug-brand`. Closes `OWNER-ACTIONS.md`
     11, 13 and 15.** The choices made on his behalf, each open to overrule:

     - **The assistant (11).** No floating button anywhere. Below 1,024 px the top bar
       carries a robot icon beside the person's initial, 44 px to tap on a touch screen, on
       every page of the shell: the chat itself (marked as the current page) and a movie night
       (where the floating button had to hide) included. On a desktop, whose top bar has no
       initial, the same link sits between Commands and "Add a disc", labelled "Assistant"
       from 1,280 px, and the sidebar keeps its entry. *Why a desktop link too:* the floating
       button floated there as well, and the pick was that it goes. The five bottom tabs stay
       five (#201); the You page still lists the assistant.
     - **`/debug` (13).** Its route, its page and its title sit behind `import.meta.env.DEV`.
       `production-build.test.ts` builds the app for production as Vercel does and reads
       every script it ships: no `/debug` route and none of the page's words. The live bundle
       before U3 had both. In development the page still renders, and its button still throws
       "This is your first error!", uncaught, which is where Sentry's global handler reports
       it from.
     - **The premise about `VITE_SKIP_AUTH` was wrong, and is now true.** No test proved the
       sign-in bypass compiled out; a comment said so. The same test now proves it, and had to
       be built with care: built *without* the flag, the bypass compiles away even with its
       guard deleted (its condition becomes `undefined === 'true'`), so a check would prove
       nothing. The test builds **with the flag on**, as a stray variable on a deployment
       would, and checks that the sign-in check's two panels survive; with the bypass compiled
       in, its early `return` makes them unreachable and the bundler drops them. Deleting
       either guard fails the test (both tried). It adds about 18 seconds to the web tests.
     - **The brand files (15), pick B.** 25 files untracked with `git rm --cached`: the 18
       photographs and stills in `docs/brand/source-images/`, the six film posters in
       `logo-system/concepts/catalogue-frame-v2/sources/`, and that concept's
       `poster-source-grid.png`. They are on disk, unchanged (checksums compared), and in
       history before U3; nothing was rewritten. `.gitignore` covers those folders, every
       `concepts/*/sources/`, and any JPEG under `docs/brand/`, the form a photograph arrives
       in. The brand tests fail if one is tracked again (a forced add was tried), pin the
       generator and every master it reads as tracked, and compare every file in
       `apps/web/public/brand/` with its tracked source byte for byte: `brand-sync --check`,
       now in CI. `docs/brand/` is 40 MB in the tree, from 56 MB.
     - **The merge does not check out `main`.** `main` before U3 tracks the 25 images, so
       `git checkout main && git merge --ff-only` would have deleted them from the disk as it
       untracked them. `main` was fast-forwarded without being checked out, which is the same
       merge. The same trap waits in any checkout that moves from a commit before U3 to one
       after: the images leave that working tree, and history still has them.
     - **What a clean clone rebuilds** (sharp 0.35.4). The generator ran on the tree as
       committed, with none of the 25 present: every SVG byte for byte, 38 of its 42 PNGs pixel
       for pixel, and the other four, the 180 and 192 px resamples, within 2 of 255 levels, a
       newer image library's rounding. The two photographic heroes in `apps/web/public/brand/`
       cannot be rebuilt: one builder reads `source-images/`, the other was never committed.
     - **Not decided: 36 tracked images built from stills or posters.** Pick B named the
       third-party images; these are made from them, so they stay tracked for Craig's call:
       the personalised poster edition (`stack-family/personalised-poster-*`, 5 files, and
       `identity-overview.png`, which shows it); the concept master it is built from,
       `concepts/poster-stack-v2/poster-stack-actual-posters-v1.png`, which the generator
       reads, with its three small sizes, comparison and small-size test; the same set for the
       catalogue frame (`catalogue-frame-actual-posters-v1.png`); the ten photographic heroes
       in `logo-system/` and the older photographic social card in `responsive/`; and the three
       photo-logo concepts at the top of `docs/brand/`. **Four of them ship:**
       `apps/web/public/brand/hero-photo-five-v3.png` and `hero-photo-v3.png` (no page uses
       either) and `personalised-poster-icon-{512,1024}.png` (the onboarding welcome). The
       live site serves all four to anyone, signed in or not; the repository being private
       does not cover them.
     - **The browser check** used #169's method, as Craig at 375 px on a touch screen, with
       every read captured read-only from production through main's own routes: Settings'
       three tabs, Price alerts, Identify films, the Archive's grid, list and compact views,
       and a film page's four tabs. A script scrolled each control into view and hit-tested
       it, about 450 in all: nothing sits under anything, the bottom tabs are the only fixed
       layer left, no page scrolls sideways, and each Archive view's last film ends 93 px clear
       of the tabs. It found two older faults, both fixed with a test: in Settings every switch
       that was on drew its knob 18 px past its track (no left anchor, so it started where the
       button centres its content); and the film page's tabs shrank below their labels on a
       touch screen, because `touch-target`'s 44 px minimum width replaces a flex item's
       automatic one, so the copy count spilled onto "Overview". The top bar was checked at 768
       and 1,280 px too. *Caveat:* the browser pane was hidden, which stops resize observers,
       scroll events and screenshots, so the Archive's rows were settled by calling the
       grid's own measure, and no screenshots were taken.


### 2026-09-28 — Craig's answers on Group U

222. **Craig's answers on 28 Sep to Group U's open calls.**

     - **U4 re-prices every fortnight, not daily.** His words: "repricing bi weekly is
       enough", read as every two weeks. A price still falls due 30 days after it was taken;
       the schedule sets how soon after that it is re-priced. The job runs at 04:00 UTC on the
       1st, 2nd, 15th and 16th: two mornings a fortnight, because a day's eBay share (750
       calls) prices about half of the ~1,450 films and formats, and the whole collection
       was priced within three days, so it falls due together. U4's own entry records the build.
     - **21 goes, and starts itself** once the seventh scheduled scrape is in (30 Sep, 03:00
       UTC): a one-off scheduled session on 30 Sep checks `scrape_runs` before building.
     - **Owner item 14 is closed.** The before/after screenshots would record a navigation
       T3 replaced (#201).
     - **The 36 tracked images built from stills or posters stay for now** (#221), the four
       the live site serves included.


### 2026-09-28 — Batch U4: the collection re-priced on its own

223. **A `cron-values` job re-prices the collection every fortnight, on two mornings. Built
     28 Sep on `feat/u4-fortnightly-revaluation` at Craig's yes (#222). The merge waits for
     his OK, because it declares a Railway job, and his `config apply` starts it.**

     - **What it runs:** `python -m src.scripts.value_collection`, the Home button's own run.
       It prices every film and format whose price is 30 days old, within the valuation's 750
       of eBay's 5,000 calls a day, and spends nothing when nothing is due. The valuation
       itself is unchanged.
     - **When:** 04:00 UTC on the 1st, 2nd, 15th and 16th. The collection was priced on 24–26
       Sep, so it falls due on 24–26 Oct and the first run with work is 1 Nov: about 750 that
       morning and the rest on the 2nd. One morning a fortnight would leave half the
       collection two more weeks. After that each price is replaced at the first window after
       its 30 days, so it is 30 to about 45 days old when it goes. **Update values** on Home
       still re-prices whatever is due, at any time.
     - **Why 04:00:** after the spec batch (02:00) and the shop check (03:00), and clear of
       `cron-ebay` at twenty past. The valuation's 750 and `cron-ebay`'s 500 are separate
       slices of eBay's 5,000.
     - **Its environment:** `cronDefaults` (the database and the push keys) and the eBay keyset
       by reference from `api`, as `cron-ebay` has it; `NEVER` restarts. Without the keys it
       exits 1 and says so, so a job left without them shows red.
     - **Tests:** the declaration (schedule, command, keys by reference, and listed in the
       project's resources, since a service left out is never created), and a launch with the
       job's environment and no eBay keys, which passes the imports that broke every job in
       #204 and exits 1 with its message.
     - **What the apply should show:** one service to add, `cron-values`, and nothing to
       destroy. Nothing runs on a schedule until then.
     - **Shipped as `3974733` on 28 Sep and applied the same evening, at Craig's word** ("merge
       and run those commands"). The agent wrote `config plan` to a pinned plan and read it: 1 to
       add (`cron-values`), 1 to change (`api`'s restart policy, the line Railway has shown since
       26 Sep), 0 to destroy, not destructive, every secret by reference, built from `main`.
       It then applied exactly that plan at 21:23 UTC; a plan afterwards has nothing to add.
       Production serves `3974733` with `db: ok`. The first scheduled run is 04:00 UTC on 1 Oct,
       with nothing due yet; the first with work is 1 Nov.



### 2026-09-30 — Batch 22b: retailer sale pages that work

224. **What each enabled shop's sale page now does, and why Arrow and Powerhouse stay out.**
     Craig's choice on 28 Sep, with his pick for Zavvi on 30 Sep. Owner item 1e.

     - **Zavvi reads its "2 for £30 4K" listing** (`/c/offers/2-for-30-4k/`). `/sale.list`
       404s. The flash-deals film page the 13 Sep notes named had become a landing page of two
       carousels, six discs, five of them already owned, and the same six 10 hours
       later. Craig chose to read the two listings it leads to and take the larger: this
       one, 169 discs over seven pages, twelve on the page as served, each with its own
       price and RRP. The other ("Awards Winners") held two. The feed stores each disc's
       price against its RRP; the multibuy itself is not stored. `was` reads THG's tagged RRP
       span; Batch 22's selector matched nothing on any Zavvi page.
     - **Second Sight reads the first page of its sale collection.** `was` reads Dawn's
       struck-through compare-at price, which Batch 22's selector never reached: it read the
       card's own price twice. On 28 Sep one card of sixteen was discounted (Dog Soldiers 4K,
       £24.99 → £17.99); the collection runs to five pages, and only the first is read.
     - **Both are marked verified** against trimmed copies of the pages, captured read-only
       with the scraper's own fetcher and User-Agent: 5 requests in all, at least 6 seconds
       apart, every one answered 200, no bot wall.
     - **101 Films is as it was:** right, with nothing on sale on 13 Sep. Its sale cards
       would have failed the same-site guard, though (#225), which is now fixed.
     - **Arrow and Powerhouse stay out.** Their offers are bundles ("2 for £40", "3 for 20%
       off") with no discounted price for one disc, and the feed holds one disc's price
       against its previous price. No bundle extraction is built (Craig, 28 Sep). Their
       configs, and 101 Films', are pinned by a test, so a change is a decision.
     - **What a check would report today**, computed in-process from the captures against
       the real collection, read-only and with no live request: 5 deals from 2 shops, 7
       skipped as already owned (Zavvi 12 found, 4 kept, 7 owned, 1 at a single price;
       Second Sight 16 found, 1 kept, 15 at a single price). §5.9's "≥ 20 rows from ≥ 3
       retailers" is not reachable from these two first pages, and 101 Films is the only
       possible third shop.
     - **The button**, "Check sale pages" on /retailers, admin-only like the page and the
       endpoint: a dry run showing the three numbers and each shop's found, kept and reasons;
       "Save deals" appears only after a check and asks the shops again, so what is saved is
       what the pages show then. First on the page, so it is in reach on a phone.
     - **Shipped as `eb51568` on 30 Sep**, after a red CI dependency audit (PyJWT's advisories,
       published after 28 Sep) was fixed on its own branch first (`6a8197b`). Production serves
       it with `db: ok`, and its retailer rows carry this configuration: apply-built-ins at
       13:44 UTC changed three values (Zavvi's sale page and `was`, Second Sight's `was`), none
       of them set by hand.

225. **Three faults in Batch 22's pipeline stood between these pages and a deal, and each was
     fixed where it lives, none by loosening a check.** `check_page_shape` is unchanged.

     - **The same-site guard was handed a URL where it expected a host.** The deals runner
       (and §5.4's Test button) passed the retailer's whole `base_url`; with no `www.` the
       scheme stayed glued to the first label, so every one of Second Sight's and 101 Films'
       own listings failed. `_same_site` now reads a host or a URL, and the runner passes a
       host as the price runner does. Another `.co.uk` shop is still refused.
     - **A card at a single price was kept as a deal with no discount.** Fifteen of Second
       Sight's sixteen would have counted towards "≥ 20 rows". Such a card is now counted as
       not discounted, apart from `rejected`, which stays a failed check (#125's lesson). A
       page where no card has a `was` is still refused whole, a `was` no higher than the price
       is still rejected, and a card with no price at all is still rejected. The first few
       rejected cards' reasons now reach the screen.
     - **The film matcher narrowed on the single longest word and ignored years.** A shop's
       word ("includes", "anniversary", "download") hid Spectre, The Deer Hunter and The
       Mummy, so an owned copy was not skipped. It now tries every word a title could hold and
       keeps the best match. And "The Mummy (2017)" matched the 1999 film, owned on Blu-ray,
       so it came through as an upgrade while the 2017 film sits on the shelf in 4K: a year in
       brackets now rules out a film of a different known year. Only bracketed years count,
       because "2001", "Blade Runner 2049" and "1917" are titles.

226. **#153's premise was an artifact, and one Batch 22 test asserted a broken selector.**

     - #153 found that Zavvi's `product-title` "is a heading, not a link". It is a link. The
       test helper merged the whole sale-page entry, whose `url` is the page's address, over
       the card's `url` selector; an address matches nothing, so the anchor fallback ran.
       The fallback stays, for a theme whose title is not a link, with a test of its own. The
       merge now has one definition, `applied_scraper_config`, used by `apply-built-ins` and
       by the tests, so they cannot drift again.
     - `test_a_page_where_no_card_has_a_was_price_is_refused` was fired by the Zavvi search
       fixture "because its cards carry no struck-through price". Its first card carries an
       RRP, which Batch 22's selector could not see. The test now fires on the three real
       sale captures with Batch 22's selectors, the 13 Sep refusal reproduced; a new one pins
       what the search fixture really holds. Changing a test's expectation is a decision to
       report, and this is that report.


### 2026-09-30 — Craig's answers on 22b's report

227. **Craig's answers of 30 Sep, and the eBay values they needed.**

     - **§5.9 does not count as met with two shops.** It stays open; it is also short of 20
       deals, so the shop count is not the deciding question yet.
     - **The sale-page check reads more than one page (22c).** Written into the ledger with
       its criteria; it builds at his go, after 20b, because it adds requests to the same
       shops that answered `429`.
     - **The `429`s get a batch (20b).** Written with its criteria. Its first step is the
       diagnosis, and its first evidence is the 1 Oct 03:00 UTC check.
     - **Batch 21's third multi-shop item: the agent adds wants that two shops will
       match.** Added that evening through the app's own route: **Bad Lieutenant (1992) in
       4K**, an upgrade on the owned Blu-ray (101 Films' own 4K plus Zavvi, the pattern of
       Castle Freak), and **Dog Soldiers (2002) in 4K**, not catalogued before (Second Sight's
       own 4K plus Zavvi, the pattern of Dead Man's Shoes). No price limit, so no alerts. Both
       were chosen from evidence rather than guessed: the only pairs that have ever produced
       two shops' prices are a boutique label's release that Zavvi also sells.
     - **eBay sign-in (owner item 18) gets its values now, before T8b is built,** because
       Craig is setting it up. The RuName returns to web routes
       (`/settings/ebay/connected`, `/settings/ebay/declined` on `mcu-app-fawn.vercel.app`,
       the only origin the API accepts), so the page receiving eBay's code already holds the
       person's session. `EBAY_RUNAME` and `EBAY_TOKEN_KEY` (32 random bytes, base64) go on
       `api`; T8b declares both with `preserve()`, since an undeclared variable is deleted
       by the next apply (#124). The privacy-policy page eBay asks for is T8b's to add. No
       eBay password is ever given to the app or an agent.


### 2026-09-30 — the 30 Sep snags, and Craig's answers

228. **Craig's answers of 30 Sep on his nine snags** (`docs/owner-snags-2026-09-30.md`), and
     the plan they give: Group V in `docs/phase-batches.md`, **proposed, not approved.** He
     asked for the full plan to be reconciled before anything goes further.

     - **Sold prices stay out of reach, signed in or not.** A sign-in gives an app one
       person's own account: T8b's gets Mark's watch list and his selling list, his own sold
       items included. Market-wide sold prices are only in Marketplace Insights, which eBay
       grants to approved apps and has closed to new ones (#16, #126); no person's sign-in
       changes what the app is allowed. Reading eBay's sold listings from the website with
       someone's account is ruled out by #203 and by eBay's terms. The app links to eBay's own
       sold listings instead, which open in the person's browser (V8).
     - **The collection's value: a trial first** (V6). It prices a sample from live bids and
       saves nothing; blend or bids only is his pick after its report (V7).
     - **The Deals "usual" price becomes an average of eBay's figure and the shops' prices**
       (V8). He asked for eBay's sold prices in it; eBay's part is V7's figure instead. The app
       holds shop prices only for Wanted films, so for other films the figure is eBay's alone,
       and the card says which.
     - **Loans is always listed, for Mark and Craig.** Supersedes #154 for Loans only; Box
       sets, Collections and Deals still hide while empty. Lending stays admin-only (V2).
     - **Movie night keeps the list and drops the swipe deck.** Retires Phase 8.4's
       "swipe-like UI" and #207's arrow-key rule; #157's hidden votes stand (V3).
     - **"Craig's house" becomes a section**, one place without shelves, its discs counted
       like any other in the value, the stats and "already owned" ("Craig's house is fine").
       The last two points were proposed to him and taken as accepted (V4).
     - **Reviews: all three options**, found with Brave (#202): links, Brave's one-line
       description, and the review's scores (V9, V10). **The scores widen #110** to one more
       thing: Blu-ray.com's own review scores for a release, read from an exact page address.
       Everything else in #110 is unchanged: exact addresses only, no search routes,
       sequential and paced requests, a 403 or 429 halts the integration, and every stored
       row names its source so it can be removed. Taken from "All" after he was told the
       scores need this; open to overrule. **AVForums' scores wait on reading its terms**,
       which this session could not reach.
     - **Highlights: a mix of all**: top rated, most rewatched, most valuable, and best
       reviewed once V10 brings scores (V5).

     *Found on the way, and V1's reason:* the top bar has had no background since 10 Sep
     (`9afc173`). `bg-background/94` names an opacity step Tailwind 3 does not have, so the
     class is never built; 20 classes in 10 files share the fault. Proved by building the
     stylesheet with the app's own config and Tailwind 3.4.19.

229. **The plan's shape, at Craig's word (30 Sep): six sittings, two merges, and his steps
     inside the batches.** "Just write into the plan, including model and thinking effort for
     each batch." Group V in `docs/phase-batches.md` carries it; nothing starts before his go.

     - **His three steps move into the batches** rather than coming first. The bid trial and
       his pick happen inside sitting 2, once V6 is live. Allowing blu-ray.com and
       avforums.com starts V9, which asks for a higher Brave limit only if the month's credit
       has run out by then.
     - **Two merges, his choice, as U5 into U3:** V2 into V1, since both change the top bar and
       one browser check covers them; V10 into V9, since with his steps inside nothing
       separates them and they build one feature on one set of data. V2 and V10 are retired
       names.
     - **Six sittings plus 21:** V1 → V3 → V4 → V5; V6 → his pick → V7 → V8; V9; 20b → 22c;
       T8b; 38 last. Each batch keeps its own close-out. 21 still starts itself.
     - **Each batch's model and effort are in Group V**, named by the ledger's two model tiers:
       the models on Group U's row and on Batch 21's row.
     - **Open before sitting 1: how a batch lands from a cloud session.** CI runs only for
       `main`, `feat/**`, `fix/**`, `chore/**` and pull requests, and a cloud session may push
       only its own `claude/…` branch. Proposed: a pull request per batch, merged when CI is
       green. The post-merge health check needs `api-production-a8fe.up.railway.app`, which
       the 30 Sep session could not reach.

230. **Craig's go, 30 Sep: an overnight run, one pull request per batch.** "Yes you can do per
     batch" (a pull request per batch, merged when CI is green), then "write a prompt to run
     these batches in order overnight. I want to wake up to them being complete."

     - **How a batch lands from a cloud session:** its own `feat/` (or `fix/`) branch from
       `main`, a pull request, CI green, then the session merges it with a merge commit, so
       the batch's small commits stay in `main`'s history and the merge commit is what
       deploys. It then verifies production and lands the close-out's docs through a second
       pull request, as `phase-closeout.md` does with a push. Answers #229's open question.
     - **The overnight run is V1 → V3 → V4 → V5 → V6.** The two things it needed first, fixing
       `main`'s red and merging the plan, were done that evening in the planning session at
       Craig's word ("can we commit and merge this to main"): the fix as #4, then the plan with
       the run's prompt, `docs/group-v-overnight.md`, through its own pull request. **Not in it, and why:** V7 and V8 wait on
       Craig's trial run and pick (V6 builds the trial; the run is his, as #228 says); V9
       starts with live requests to two outside sites, which `group-start.md` keeps out of an
       unattended run, and with his network step; 20b and 22c wait on his go after the 1 Oct
       03:00 UTC check, whose results a cloud session cannot read without database access;
       21 starts itself; T8b waits on owner item 18; 38 is last.
     - **`main` was red when the run was written.** The 19:26 UTC run on `8e4c6a2` failed the
       dependency audit: `urllib3` 2.7.0 carries CVE-2026-97687, -97688 and -97689, fixed in
       2.8.0. As with PyJWT that morning (`6a8197b`), it was fixed on its own `fix/` branch and
       closed out before any batch (#4). `uv pip compile … --upgrade-package urllib3` on both locks
       moves `urllib3` alone, checked on 30 Sep.
     - **A cloud session can run the whole gate.** On 30 Sep: the locked Python dependencies
       and the pnpm workspace installed; with a throwaway local Postgres 16 the API suite ran
       **1,634 passed, none skipped**, and `upgrade head` → `downgrade base` → `upgrade head`
       ran clean; the web and shared checks passed on the container's Node 22 (the engines
       floor is 20.18). CI's Postgres 17 and Node 20 stay the authority. Gotcha 15's "no local
       Postgres" holds on Craig's Mac, not in a cloud container.
     - **The one step before the run is Craig's:** allowing
       `api-production-a8fe.up.railway.app` in the cloud environment's network settings, so
       the run can confirm each deploy. Without it the run stops before its first merge.

### 2026-09-30 — Group V, batch V1

231. **V1's choices: a real-API browser rig, `nav/sections` left alone, and one rule for "back".**

     - **The browser check ran the real API, not a stub.** #169's method with one change: the
       Vite dev server talked to the app's own FastAPI, started in the session against a
       throwaway local Postgres 16 (`mcu_browser`) migrated to head and seeded with 14 films,
       their discs, 3 shop deals and a movie night, and both people given a rig-only PIN. The
       pages then parse real responses from real queries, and the sign-in is real, so no
       `VITE_SKIP_AUTH`. It needs no credential and sends nothing to a third party: the API ran
       with no TMDB, eBay, Brave or Anthropic keys. The rig (seed script, launcher, Playwright
       script) lives in the session scratchpad; only the gitignored `apps/web/.env.local`
       touched the checkout, and it is deleted after the run. The login limit (5 per 15 minutes)
       is durable in Postgres, so the rig clears `rate_limit_counters` in its own database
       before each sign-in.
     - **The API still counts loans in `nav/sections`**, though nothing reads that count now
       that Loans is always listed (#228). Dropping the field would make an older web build
       fail to parse the response in the minutes when Vercel and Railway have deployed
       different commits. A later change can remove it with its schema, once.
     - **"Back" is one hook, `useGoBack`**, shared by the phone's top bar and the film page, so
       the two controls cannot disagree: through history when the app has some, and otherwise
       to a fallback (You for a page You lists, else the parent; the Archive for a film).
       React Router's `default` location key is the test for "no history".

### 2026-09-30 — Group V, batch V3

232. **V3: taking a vote back is a vote of `false`, and the push names the shortlist.**

     - **No new endpoint for "un-add".** `record_vote` already replaces a person's vote on a
       suggestion, so Added → Add sends `liked: false`, and the film reads "Add" again. A
       `false` vote was the deck's Skip; on the list it simply means "not added", which is the
       only thing a match reads. A match is still announced once: `announced_at_utc` is set on
       the first, so a take-back and re-add does not announce it again (checked on the rig with
       two people, #231).
     - **The one server string that described the deck changed.** The push that sends a night
       said "N films to swipe" ("1 films" for one); it says "N films on the shortlist" now.
       V3's criterion "the API does not change" is about the vote: no endpoint, schema or
       vote logic moved. Comments on the server that still say "swipe" were left as the history they are.
     - **Several films can be open at once.** Choosing means comparing (the snag's own
       argument for the list), so opening one film's details does not close another's.

### 2026-09-30 — Group V, batch V4

233. **V4: Craig's house, and how a CHECK with an apostrophe is written and proved.**

     - **Names inside a CHECK are SQL literals, quotes doubled.** Migration 042 carries its own
       `_literal()`; 007's `_check_clause` pasted names inside quotes and stays as it was, since
       its names have none. Any later migration that writes the vocabulary into SQL should copy
       042's, not 007's.
     - **The downgrade is proved against a real row, not only an empty schema.** The test runs
       042's `downgrade()` and `upgrade()` through Alembic's `Operations` on the test's own
       connection, inside the transaction the fixture rolls back, with a disc in Craig's house:
       section cleared, `location` kept, the name refused until the upgrade. Postgres DDL is
       transactional, so nothing leaks into the shared test database. It is the check gotcha 18
       says CI's migration job cannot make, and a pattern for the next migration that narrows a
       constraint.
     - **The form gets the whole vocabulary from the facets, not from a copy in the web app.**
       `allSections` rides on `GET /collection/facets`, defaulted in zod per #205. A list typed
       into the web app would drift from `SECTIONS` the first time a place is added.
     - **Craig's house behaves as the cabinets do.** One place, no shelves: the parser still
       returns a shelf if someone types "Craig's house 2nd shelf", as it does for a cabinet, and
       the shelf picker and the filter offer none for it. Changing that for every unshelved place
       is outside V4.
     - **The spellings the parser accepts** are "Craig's house", "Craigs house" and the curly
       apostrophe an iPhone types by default; "Craig house" is not filed there.


### 2026-10-01 — Group V, batch V5

234. **V5: the Highlights are the collection's, and how their plans were read without production.**

     - **Not caller-scoped.** Unlike Batch 37's memories, both people see the same three rows,
       and each rating and viewing names whose it is. The snag asked for the collection's
       highlights; a Mark-only "Top rated" would be empty (#159).
     - **Top rated reads each person's highest rating of a film**, as "Worth a rewatch" does, on
       the shelf only (`owned_copy()`). The caption comes from who has rated anything
       (`ratedBy`, `notRatedBy`), so it says "Mark has not rated any films" today and corrects
       itself the day Mark rates one, with no code change.
     - **Most rewatched is not limited to the shelf.** The criterion says "across both
       diaries", and a film watched four times is a highlight even if its disc was sold or it
       was streamed. Limiting it is one `where` clause if Craig wants it.
     - **Most valuable shares the total's subquery.** `owned_valued_discs()` is what
       `collection_value` built inline, so a disc that counts towards the value is exactly a
       disc that can appear in the row: a combo counts once at its best format, a download
       never. The price shown is one copy's stored value; copies are shown beside it.
     - **The plans were read on a scratch database at production's counts.** No session here
       holds the live connection, so a local Postgres was seeded to `STATUS.md`'s figures
       (1,887 films, 1,880 discs, 1,606 viewings, 1,454 valuations, 1,300 priced), the
       endpoint's own SQL was captured with a `before_cursor_execute` listener, and each
       statement was run under `EXPLAIN (ANALYZE, BUFFERS)`. Sequential scans at ~2,000 rows
       and index scans on the joins; 22 ms median for the endpoint, so no server cache (§17
       row 33). The same run against production's own rows is open.
     - **Twelve to a row**: enough to scroll on a phone, few enough to take in.

### 2026-10-01 — Group V, batch V6

235. **V6: the bid trial is a valuation run that saves nothing, and what its report means.**

     - **It claims a `valuation_runs` row, trigger `trial`** (migration 043), rather than a
       ledger of its own. Its calls then count against the day's 750-call share by the sum
       `budget_left` already takes, it can never overlap a valuation run (the one-running
       index), and a dead one is abandoned after 30 minutes like any run. The value's "last
       run" skips trials, which price nothing. The downgrade turns trial rows into `admin`
       runs rather than deleting them, so a day's spent calls stay counted.
     - **The sample is priced, owned films, a third per format.** Even shares rather than the
       collection's mix, because the report is by format; one place at a time to the format
       with the fewest so far, so a short format's places go to the others; random within a
       format. "Priced" means a stored value to compare against.
     - **An auction counts with at least one bid and past the valuation's own matcher** (the
       right film and format, a UK seller, a standard edition). Its current bid becomes the
       listing's price, so `match()` and `median()` are unchanged. Three or more make a bid
       price, their median **in any condition**: bids are thin, and splitting them by
       condition as the asking headline is split would leave almost none.
     - **"Asking" in the report is today's, from the same search**, by `valuation_from`, so
       bids and asking prices are from the same minute; the stored price is reported beside
       it. **Blend** is a film's bid price when it has one and today's asking price
       otherwise; **bids only** is a bid price or nothing. Each total says how many discs.
     - **What sharing the 200 places cost is bounded, not measured.** Knowing exactly would
       take a second, Buy-It-Now-only search per film, doubling the calls. The report gives
       the searches whose 200 places were full, the places auction-only listings took in
       them (the most Buy It Now listings that can have been displaced), Buy It Now listings
       matched now against when stored, and films that fell under three.
     - **Ending within 24 hours** is counted for every auction behind a bid price, with the
       films that would keep one counting only those: the evidence V7's time-to-end window
       needs.
     - **The report is the API's own model**, stored as JSON on the run row and written after
       every film, so a stopped trial keeps what it found and a later session reads exactly
       what Craig read: `SELECT report FROM valuation_runs WHERE trigger = 'trial' ORDER BY
       started_utc DESC LIMIT 1`, or `GET /api/v1/collection/value/bid-trial` as an admin.
     - **No live eBay request was made building it.** Tests and the browser rig used payloads
       built from the captured Blade Runner 2049 search; its one auction had no bids, so
       every auction with bids is an edited copy of it, and the tests say so. The rig's API
       had no eBay keys, so its button could only answer 503.

### 2026-10-01 — cloud sessions without the Mac

236. **Cloud sessions do everything but Craig's own steps: a startup hook, a read-only role
     over HTTPS, and a Railway token.** Craig's word, 1 Oct: "yes to all", after asking how to
     stop rerunning things on his Mac.

     - **A startup hook readies the gate in every cloud session**
       (`.claude/hooks/session-start.sh`): the steps the overnight run did by hand (#230),
       now automatic and idempotent, with `DATABASE_URL` exported as the throwaway test
       database, so nothing in a cloud session points at production by default. Cloud only;
       the Mac's sessions are unchanged.
     - **The live database is read over HTTPS, read-only.** A cloud container's proxy carries
       HTTPS only, so no Postgres connection leaves it: copying `.env.local`'s URL into the
       cloud would not work even if it were wise. Neon answers SQL over HTTPS;
       `src.scripts.live_sql` uses that with `mcu_readonly`, a role made once on the Mac
       (`docs/mac-cloud-setup.md`), set read-only, with credential columns withheld
       (`profiles.pin_hash`: a four-digit PIN's bcrypt hash falls to 10,000 guesses) and **no
       default privileges**, so a new table stays unreadable until its migration grants it.
       Unreadable by default fails safe; readable by default would expose a credential table
       the day a migration forgot to revoke it.
     - **Writes to live data stay out of cloud sessions.** The scripts that write use asyncpg,
       which cannot connect from the cloud, and a read-write credential there would let any
       session change production. A write that is still script-only becomes an admin action
       or a Railway job when it is next needed.
     - **Railway's CLI runs in the cloud with a token**, pinned at 5.63.1: `config plan`
       whenever useful, `config apply` only on Craig's word, as before. A project token for
       `production` is tried first, as the narrowest that works.
     - **Checked from the cloud on 1 Oct:** Railway's API answered "Unauthorized" to a made-up
       token, and Neon's SQL endpoint "password authentication failed" to a made-up user, so
       both are reachable through the proxy and only the credentials are missing.

### 2026-10-01 — the bid trial's answer, and shops that refuse

237. **Values stay on asking prices; V7 is shelved.** Craig's word, 1 Oct: "1) neither", after
     V6's trial, which he ran at 14:14 UTC.

     - **The trial found no film with a bid price.** 100 films, eBay answering all of them: 13
       matching auctions had a bid (4K 10, Blu-ray 3, DVD 0), 12 films had any, and the most on
       one film was 2, against the 3 a price needs (#129). 110 matching auctions had no bid.
     - **So a blend equals today's asking prices** (£1,903.34 on the sample's 100 discs, against
       £1,867.32 stored), and bids only values nothing. V7, a migration and a re-price of every
       disc, would have changed nothing anyone could see.
     - **V8 goes ahead on asking prices:** its "eBay's figure" is the asking-price median in
       `ebay_price_refs`, as the Deals page already uses. V7's criteria stay in the plan,
       unbuilt; the trial stays on Home and can be run again if bids ever look thicker. One
       Wednesday-afternoon snapshot is the evidence, and it would take tenfold more bids to
       price even a tenth of the collection.

238. **A `429` is a refusal, never a step towards auto-disable; 20b is split in two.** Craig's
     word, 1 Oct: "2) yes", after the read-only diagnosis (`docs/phase-batches.md`, 20b).

     - **Why split.** On 30 Sep and 1 Oct each Shopify shop refused its first request of the
       night, so this run's own pace is not what trips them, and the planned cure (a longer
       pause) is unlikely to work. What would is unknown: nothing recorded `Retry-After` or
       what the refusal looked like. Meanwhile 101 Films and Powerhouse stood one refused
       night from being switched off. So the first half stops refusals counting and records
       the evidence; the second half is rewritten from two nights of it, and 22c waits too.
     - **`blocked`, with the count left alone.** A shop that only refused, or answered "not
       here", is recorded as `blocked`, the status Batch 16 declared for exactly this and
       nothing used, so no migration. Its `consecutive_failures` is neither raised nor reset,
       as `no_results` leaves it (#125): a refusal tests nothing, and resetting would let a
       broken shop launder its failures. A genuine failure beside refusals still counts.
     - **Still a failure in the run's record**, with the evidence in its reason, and the job
       still exits 1: a refused night is not a clean night. The summary counts refusals.
     - **Judged by the last answer.** A refusal then a timeout is a failure: the shop has a
       problem a person should see.
     - **The two nights already counted stay counted.** 101 Films and Powerhouse sit at 2,
       under the old rule. Resetting them is a write to live data, which no cloud session
       makes; a night with a price resets them anyway.

### 2026-10-02 — Group V, batch V8

239. **V8: an eBay find's "usually" averages eBay with the shops, like for like.** Craig's
     answer to snag 1 (#228), built on asking prices since V7 is shelved (#237).

     - **Like for like is this batch's call, and Craig kept it on 2 Oct ("yes keep").** A shop's price counts
       only when it is the same format, read off the listing it priced (`primary_format`, as
       the nightly check reads it), and a standard edition by the eBay matcher's own
       `classify_edition`, because eBay's figure is standard editions only. On 1 Oct the shops'
       week held £39.99 and £49.99 limited editions of Dead Man's Shoes: averaged into an
       ordinary disc's usual price, they would make a normal listing look like a deal.
     - **Condition is not matched.** A used eBay listing is still averaged with new shop
       prices, as the snag asked for an average with the shops; eBay's own part stays
       condition-matched as T8a built it.
     - **The latest per shop from the last seven days**, of any want for the film, so a want
       for each format counts on its own format. eBay's figure alone where no shop has one,
       which is most finds: upgrades on owned films, which no shop is asked about.
     - **The parts are stored with the deal** (`deals.usual_sources`), so the card says what
       it was judged against even after the shops' prices change. A find stored before V8
       reads as eBay alone, which is what its `was_price` was.
     - **The sold-listings link searches with the words the asking prices were searched
       with**: the valuation's stored `search_query` on the film page, and the film's title
       and format on a deal. It opens eBay in the person's browser; the app reads nothing
       from it (#16, #126).

### 2026-10-02 — Batch 20b, second half

240. **20b's second half is built from one night's evidence, not two, so that the 3 Oct check
     is its first night.** Craig's word, 2 Oct 23:28 UTC, on his Mac ("20b now, merge by
     02:45"), when the session opened before the 3 Oct check had run. Supersedes #238's "two
     nights" for this half only; 22c still waits for this half's own read-back.

     - **What it gives up:** a second night of the first half's evidence. 2 Oct's was
       uniform (every refusal `429`, `retry-after 60`, Cloudflare, "Too many requests", no
       `cf-mitigated`), and the record this half adds says more than a second night under the
       old pause would have: whether a minute's wait gets through.
     - **What it gains:** a day. The 3 Oct check is read back the same morning.
     - **No merge between 02:45 and 03:45 UTC**, as on 1 Oct (#230): a deploy while the check
       runs could cut it short.

### 2026-10-03 — Group V, batch V9: what the capture found, and Craig's two answers

241. **AVForums is links only; owned films' Blu-ray.com scores come from the reviewed edition
     their spec page links to.** Craig's word, 3 Oct about 00:25 UTC, after V9's capture
     (`docs/phase-batches.md`, V9).

     - **AVForums: "Links only".** Its terms (§3.6) forbid access "through automated or
       programmatic means (such as through a content scraper) without prior permission", its
       `robots.txt` says the same, and it shows the app's client a Cloudflare challenge.
       Reading a score would mean evading that challenge, which #110 rules out whatever a risk
       acceptance says, so #228's widening never reached AVForums. The app shows the link and
       Brave's line, says why there are no scores, and sends AVForums nothing. Asked "so there
       is no way for us to get this data?", Craig was told the legitimate routes (written
       permission from M2N Limited, or typing a score in himself) and chose links only.
     - **Owned films: "Yes, follow the link".** Blu-ray.com reviews one edition of a film per
       format, usually the US one, and other editions' pages link to it. The page found for a
       disc's specs is the UK release, so it rarely carries the review. Each owned film and
       format costs up to two requests (its spec page, then the reviewed edition it links to),
       about 1,060 in all at 150 a night, five seconds apart, no searches: #110's risk at full
       volume, as accepted for the spec backfill (#202). It is what gives Home's "Best
       reviewed" row the shelf to rank.
     - **Wanted films follow the same link**, from the page Brave proposes, because Brave
       cannot tell which edition's page carries the review. Finding still sends neither site
       anything; the follow happens when the scores are read.

### 2026-10-03 — an expired eBay recording, and T8b's place

*Numbered after #241, which V9's branch holds.*

242. **A test that sends a recorded payload with a real expiry through a route pins that
     route's clock to the capture's time.** The listing behind the eBay alert tests, captured
     on 26 Sep, ended at 09:06 UTC on 3 Oct. The routes read the wall clock, so from then on
     two tests failed on every branch, `main` included (its last green run was at 08:55 UTC).
     Fixed in `0770bbc` ([#27](https://github.com/CraigR973/mcu-app/pull/27)): an autouse
     fixture in that file makes the eBay routes read `NOW`, as its passes already did.

     - **Rejected: moving the recording's end date.** It makes the capture unfaithful and
       only moves the failure to a later date.
     - **The whole file, not only the two tests**, so the next test added there cannot meet
       the same expiry.
     - **Nothing else is close to expiring.** A scan of every other dated test and recorded
       payload on 3 Oct found only explicit clocks and parsing checks.

243. **T8b starts after V9 merges.** Craig's word on 3 Oct, once `OWNER-ACTIONS.md` 18 was
     done. Both batches add a database migration. Run side by side, whichever merged second
     would renumber its migration and redo its checks, in the batch that holds Mark's eBay
     token. T8b's plan still goes to Craig for his go before it starts: it changes auth, adds
     a table and takes on eBay's sign-in contract.

### 2026-10-03 — Group V, batch V9: the calls made while building it

244. **V9 shipped (`d1c3bf7`, migration 046), and these were this session's calls, each open to
     overrule.**

     - **The reviews batch runs inside the nightly `cron-specs` job, after the spec batch.** No
       new Railway service, so no hosting change, and every Blu-ray.com request, spec or
       review, comes from one process, five seconds apart. Adding a want searches Brave at once
       (after the response); its page is read that night.
     - **A want with no format** keeps Blu-ray.com's 4K review if there is one, else its
       Blu-ray review; on AVForums the want's own format first, then 4K, Blu-ray, the film's
       review, DVD.
     - **Searches have caps of their own:** 40 a night and 100 a month, inside the shared 1,500
       ceiling (#202). A search that found nothing is tried again after 30 days. A page
       without a review is not read again on its own: #110 caches results rather than
       refreshing them.
     - **"Best reviewed" ranks owned films by Blu-ray.com's Overall, for a format a copy is
       on**, one entry a film, a tie going to 4K. A 4K review of a film owned only on DVD is
       not the shelf's.
     - **Blu-ray.com's Brave line is shown without its tagline** ("Blu-ray reviews, news,
       specs, ratings…"), leaving the release date: the rest is the same on every page.
     - **The owned films' volume is larger than #241 said:** 728 discs had a spec page on
       3 Oct, not 530, so up to about 1,450 requests at 150 a night, about ten nights.


### 2026-10-04 — Batch T8b: Craig's go, and how it is built

245. **T8b is built now, each person connecting their own eBay.** Craig's word, 4 Oct, on the
     plan given the night before: "1) each person 2) go with recommended 3) recommended
     4) build it".

     - **Each person their own eBay.** Connecting is a person's own act and only they see
       their lists; Craig can try it on his own account before Mark does.
     - **A saved search becomes one of T8a's film alerts** once its owner picks the film and
       format it is for. No new alert kind: T8a's matcher already judges a listing against a
       film, its format and its edition, and a free-text alert could not.
     - **eBay's XML is read with `defusedxml`.** The Trading API answers in XML; the standard
       library's parser is open to entity-expansion tricks, and this is the first XML the
       app reads.
     - **From eBay's own documentation, read 4 Oct:** the consent page is
       `auth.ebay.com/oauth2/authorize` (client id, the RuName as `redirect_uri`,
       `response_type=code`, scopes, `state`, and `prompt=login`, which makes eBay ask who is
       signing in, so a browser signed in to one person's eBay cannot connect it to the
       other's profile); the code is swapped at `/identity/v1/oauth2/token` for a two-hour
       access token and an 18-month refresh token; the Trading API takes the user token in
       `X-EBAY-API-IAF-TOKEN`. **eBay documents no scope for the two Trading calls**, so the
       token asks for the base scope alone, the fewest, and the first live connection proves
       it is enough.
     - **No eBay identity is stored.** Only the two tokens, sealed with AES-256-GCM under a
       key derived from `EBAY_TOKEN_KEY` and bound to the person's profile. The eBay account
       name is read live for display. So the account-deletion endpoint stays a no-op, as its
       docstring requires while it has nothing to erase; a token eBay refuses (a closed
       account, or access revoked on eBay) is deleted the moment the app next uses it.
     - **The one-time `state` is single use, tied to the signed-in person, and lasts ten
       minutes.** Neither table is granted to the read-only role.

### 2026-10-04 — Batch T8b built: the calls made on Craig's behalf, and the OK it waits for

246. **T8b is built on `feat/t8b-connect-ebay`; its merge waits for Craig's OK**, as T7's,
     T8a's and U4's did, because it changes `.railway/railway.ts` (`AGENTS.md`, "Still
     explicit"). The change only declares `EBAY_RUNAME` and `EBAY_TOKEN_KEY` with
     `preserve()`; `config plan` then read `0 to add, 1 to change, 0 to destroy`, the one
     change being the API's restart policy, pending since 26 Sep. **No apply is needed for
     T8b to work**: both variables have been on `api` since 3 Oct, and the declaration only
     stops a future apply deleting them (#124).

     Calls made while building, each open to overrule:

     - **No listing photos on "Your eBay".** The web app's content security policy allows
       images from TMDB alone, so a thumbnail from eBay's image host would load in
       development and break in production; T8a's pages show none either. Allowing eBay's
       image host is a hosting-header change, Craig's to make if he wants thumbnails.
     - **A saved search's film is looked for on Wanted as well as in the collection.** The
       catalogue search finds owned films only, and a search on eBay is mostly for a film not
       owned yet. Format words in the search ("4k", "blu ray", "dvd") choose the format and
       leave the query, because the catalogue search matches every word it is given; edition
       words ("steelbook") stay, since some are title words. Without a format word, a want's
       own format is taken, else Blu-ray. The person can change the words and the format.
     - **"Your eBay" (`/ebay`) has no menu entry.** It is reached from Settings → eBay and
       from the page eBay returns to, and its back arrow goes to Settings. A menu entry would
       show to both people whether connected or not; it is one line to add if wanted.
     - **Signing in keeps the address's query string**, on every protected page. eBay returns
       to `/settings/ebay/connected?code=…`, and a sign-in in between used to drop the code.
     - **The Settings tab strip scrolls the chosen tab into view.** Four tabs overflow 375 px,
       and T8b's own pages link to the last one.
     - **Found by the browser check, fixed before review:** `/privacy` and `/ebay` titled
       themselves "Page not found" in the browser tab.
     - **The database tests ran in CI only.** This Mac has no Postgres (gotcha 15), so the
       ten endpoint tests (sign-in, the state's three rules, each person seeing only their
       own, refresh, a refused refresh, disconnect) are proved by CI's Postgres 17.
     - **Craig said OK to merge on 4 Oct** ("yes to 1 and 3": the merge, and Auto-fix on the
       pull request), overruling none of the calls above. Merged as `2995b26`
       ([#33](https://github.com/CraigR973/mcu-app/pull/33)), live at 10:28 UTC.

### 2026-10-04 — A fixed outbound address for the nightly shop check: left for now

247. **`OWNER-ACTIONS.md` 28 is left for now, and 22c is parked with it.** Craig's word, 4 Oct:
     "yes lets leave it for now", after asking what it was for: the nightly check prices each
     Wanted film at five shops and pings a phone when one falls to its price, and since 30 Sep
     the three Shopify label shops (Second Sight, 101 Films, Powerhouse) mostly refuse it,
     leaving Zavvi and Arrow (and eBay, through T8a).

     - **Why the fix was weaker than 28 said.** Railway's own docs, read 4 Oct: static
       outbound addresses need the Pro plan (Craig is on Hobby), and "may be shared with other
       customers"; Railway support says it offers no dedicated outbound address on any plan,
       and points to paid proxies instead. So the option was a smaller shared pool, not "an
       address of its own", and not proved to stop Cloudflare's refusals.
     - **What leaving it costs:** price drops at those three shops' own stores mostly go
       unnoticed; the check keeps trying them each night, and the odd price gets through (2 of
       27 on 3 Oct). 22c's further sale pages at Second Sight would meet the same refusals.
     - **21 is not parked.** It still starts itself once a third want has two shops' prices on
       two days (2 of 3 on 4 Oct); the route that needs no hosting change is a want both Zavvi
       and Arrow sell, Craig's to add.

### 2026-10-04 — Housekeeping: CI builds and boots the image, and the gate docs tell the truth

248. **CI's sixth job builds the image Railway deploys and boots it as production runs it.**
     Craig's word, 4 Oct: "yes do 1 -4 now", on a list that included it. Until now a broken
     Dockerfile, a runtime dependency missing from `requirements.lock`, or a start command
     that failed showed up only when Railway deployed (`AGENTS.md` said so). The job builds
     from the Dockerfile, imports every cron job's module inside the image (the list is read
     from `.railway/railway.ts`, so a new job is covered without editing CI), then runs the
     image with `ENVIRONMENT=production` against a Postgres 17 service: the start command
     migrates first, and the job waits up to 90 seconds for `/api/v1/health/ready` to say
     `db: ok`, printing the container's log if it does not.

     - **What it still does not prove:** production's variables (the boot uses CI's
       throwaway values), the cron jobs running (they are imported, not run), and the web
       bundle running in a browser (Batch 38's).
     - **The gate docs no longer tell an agent to export the Mac's `DATABASE_URL`.**
       `batch-verify.md` said to, "before trusting any migration change"; on Craig's Mac that
       variable is production's. Tests run there with `env -u DATABASE_URL`, and migrations
       are proved by CI.
     - **Thirty-eight test modules lost a redundant `pytestmark = pytest.mark.asyncio`.**
       `asyncio_mode = "auto"` already marks every async test, so the line only marked the
       sync tests beside them, which drew 149 of the suite's 152 local warnings. Now there
       are none, so a new warning is visible.

### 2026-10-05 — The 5 Oct snags: Craig's answers, and Group W

249. **Both people lend and borrow; Home puts the collection first, in rows; the bid trial
     moves to Admin; go for W1 → W2 → W3.** Craig's word, 5 Oct, by four clickable answers
     after the reconciliation (`docs/owner-snags-2026-10-05.md`): "Both lend and borrow",
     "Collection first", "Move to Admin", "Go".

     - **Both people lend, borrow and mark returned** (W3). Supersedes the admin-only lending
       of Batch 15 and V1's "Lending and 'Mark returned' stay admin-only" (#228). Borrow links
       the loan to the person through a new nullable `loans.borrower_profile_id`, and overdue
       reminders go to both people, each worded for them. *Rejected:* a Borrow that only types
       the person's name into the free-text borrower. It needs no migration, but Mark still
       could not lend and the reminder would stay Craig's alone. The table held 0 rows, so
       the column costs nothing to add.
     - **Home: the collection first, every section a row that scrolls sideways** (W2).
       Supersedes T5's "Home opens with the next few disc releases". Recent activity stays a
       short list at the foot, since a feed does not swipe well; that one is the agent's call,
       open to overrule.
     - **The bid trial moves to an admin-only Admin tool with "Update values"** (W2), so Home
       only reads. Supersedes #237's "the trial stays on Home"; it can still be run again.
       *Rejected:* deleting it, which would lose the way to re-check if bids thicken.
     - **Most watched and Home's "Add a disc" go** (W2). On 5 Oct 8 of Most watched's 10 films
       were also in Most rewatched; Add is on the bottom bar below 1,024 px and on the top bar
       from 1,024 px.
     - **Go for W1 → W2 → W3, a pull request per batch**, run on Craig's Mac and closing out
       automatically after a green gate (#24).
     - **Found on the way: V1's top-bar fix could not change how the top bar looks.** The class
       was missing, as 30 Sep found, but nothing scrolls under the top bar: the page scrolls in
       its own region below it. So the bar showed the page's own colour with its background or
       without. The 30 Sep record's "a see-through bar with the page blurred behind it" was
       true of the bottom bar only. W1 makes the top bar a raised panel.
     - **Open:** Craig's screenshot of the faded bar, and whether he uses the light theme. If
       he does, the cause may be iOS drawing the clock and battery in white over the cream bar
       (`black-translucent`), which W1 does not change.
     - **Measured read-only on the live database for the reconciliation**, with `SELECT`s in a
       `SET TRANSACTION READ ONLY` transaction from the Mac: 1,566 viewings (Craig 594, Mark
       972), 0 loans, 40 completion sets, 0 of 1,880 owned discs with a barcode, 1 barcode
       remembered.

### 2026-10-05 — Group W, batch W1

250. **The Mac's browser rig: production's data, read-only, through the API's own functions, and
     no auth bypass.** #169's method, with two changes found running W1.

     - **The stub's answers are production's own,** read by calling the API's router functions
       (`highlights()`, `collection_stats()`, `on_this_day()` and the rest) in a scratch script, on
       an engine whose every connection sets `default_transaction_read_only = on`. A function that
       commits and carries on still cannot write: Postgres refuses a write in any transaction on
       that connection, not just the first. Real titles, posters and counts make a layout check
       mean something; the data stays in the session's scratchpad and is served to localhost only.
     - **No `VITE_SKIP_AUTH`.** Two fake tokens in `localStorage` (`stub-Craig`, `stub-Mark`) make the
       app ask the stub's `/auth/me`, which answers with that person, so both roles can be checked.
       **And the flag must not be left in `apps/web/.env.local` while the gate runs:** Vitest loads
       it, and `LoginPage.test.tsx`'s two redirect tests then fail, because `ProtectedRoute` lets them
       through. Found on W1's first gate run, which was re-run without the file.

### 2026-10-05 — Group W, batch W2

251. **W2's choices: one row component, `/insights` restored, and Home owns the open set.**

     - **One `Shelf` row for every Home section**, the poster card and the heading included, so the
       rows cannot drift apart in look. On a phone a row runs to the screen's edges (negative margins
       undoing the page's padding, `scroll-px` keeping the snap aligned), so the next card shows.
     - **`/insights` is the full Completion view again**, behind the row's "All" link. It redirected
       to Home from S3 (#154); the address was the old Insights page's, so old links land where they
       meant to.
     - **Home owns which completion set is open.** The list owned it before, and Home swapped in a
       second copy of the list while a set was open, which started with nothing open: the first tap
       showed every set. Found in the browser on 5 Oct, fixed and pinned by a test.
     - **Recent activity shows 10, not 20**, as the short list at the foot (#249's call, open to
       overrule). A set's back link names where it goes ("Home").

### 2026-10-05 — Group W, batch W3

252. **W3's choices: a borrower is named exactly one way, both people hear about an overdue loan,
     and a scan names a film, never a disc.**

     - **Exactly one way to name a borrower:** a name for anyone, or `borrowerProfileId` for one of
       the people who use the app, whose name the server reads from the profile so the two cannot
       disagree. Both, or neither, is a 422; an unknown or inactive profile a 404. The lookup
       filters in SQL rather than reading `is_active` off the object: it is a server default, so on
       a profile created in the same session it is not loaded, and an async session cannot load it.
     - **Overdue reminders go to both people** (#249), the borrower, when one of them, reading
       "You've had it since …". The recipients helper's admin-only switch had no other user and
       went with it. Still once per loan (`reminder_sent`).
     - **A scan on Loans names a film, and the person picks the disc.** No disc carried a barcode
       on 5 Oct, so the lookup chain can only name the film; a candidate the catalogue does not
       know is not offered. Choosing the film remembers the code through the existing confirm step,
       and **no loan writes a barcode onto a disc**, so a wrong pick of copy cannot mislabel the
       catalogue.
     - **"Mark returned" is "Returned"**, since Mark is a person here, and loan dates read
       "5 Oct 2026" as the rest of the app writes them.
     - **Read on the live database after the deploy, read-only:** alembic at 048;
       `loans.borrower_profile_id` is a nullable uuid; `mcu_readonly` can read it
       (`has_column_privilege`), with no grant of its own; `loans` still holds 0 rows; every cron
       job deployed the merge.

### 2026-10-12 — Wave 1 review, Batches 43–48

253. **The wave 1 review's remediation is Group X, written into the plan at Craig's word ("do rows
     and merge", 12 Oct).**

     - **What:** twelve batches, X1–X12, from `docs/reviews/BATCH_43-48_ROADMAP.md` (six passes at
       `527522d`, 44 findings, 10 High), in six sittings in `docs/phase-batches.md`, "Group X —
       the wave 1 review, planned 12 Oct". Batch 38 gains six cases and stays last. Each sitting
       starts at Craig's go; he starts X1 himself.
     - **Why this order:** X1 first, because the eBay scan's stored mark (21 Oct 16:35) makes
       the gap since 9 Oct unreadable after that date; then what reaches each person and what
       tells Craig (X2, X3); X6 before the 1 Nov re-pricing; X5 by 31 Oct, while Mark's feed
       still reaches back past 14 Sep; identification (X9, X10) once failures can be seen.
     - **X4 lands before X5.** Craig left the owner steps for now (12 Oct), the free Neon
       snapshot among them, so the weekly dump is the only copy outside Neon's six hours before
       X5 writes live data.
     - **Mark's Letterboxd username is stored by X5, at Craig's word.** The app lets only each
       person set their own (`PUT /watch-history/username`, caller-scoped by design); Craig gave
       it on 12 Oct (it matches `OWNER-ACTIONS.md` 1j), so X5 writes the one row. An exception
       made by the owner, not a new admin route.
     - **Still open, each gating one batch:** eBay's API licence (MK47-04; X1's close-out
       records it), the value basis (#209; gates X6), backup storage (gates X4).
     - **Two corrections made while writing the rows.** X1's year rule lets brackets and format
       words sit between the title and the year ("IF Blu-ray (2024)"); without that, 6 of the 25
       wrong-product finds get past every X1 rule, not 3. And X1's guard no longer promises that
       all 25 are refused: three carry no year or other tell (*Maggie*, two *Titanic* 3D sets),
       so for them the defence is a push that names the listing. R5's "category not none"
       selected 32, not 25; the 25 are now listed.
     - **The evidence lists X1, X5 and X9 test against** are in
       `docs/reviews/BATCH_43-48_EVIDENCE.md`, described rather than extracted: no eBay listing
       copied whole (MK47-04 is open), no watch naming who logged it. The scratch folder they came
       from exists only on the Mac.
     - **The review's own procedure** is `docs/agent-commands/review-wave.md`; its reports,
       scope note, roadmap and follow-through live in `docs/reviews/`. The roadmap names twenty
       standing guards; each batch ships its own.

254. **eBay's API licence (MK47-04) is an owner-accepted risk, at Craig's word on 12 Oct.** The
     licence (text dated 3 Sep 2025, read by the review on 11 Oct) bars using eBay content to
     suggest or model prices for items listed on eBay without eBay's written consent (§9.5).
     The app does exactly that: each owned disc's value, each deal's "usual" and discount, and
     the sale panel's suggested price come from eBay listings. As #110 was for Blu-ray.com, this
     is risk acceptance, not a finding that the use is permitted, and a reading of the licence,
     not legal advice.

     - **What Craig accepts:** most likely nothing; plausibly eBay suspending the keyset, which
       serves the value, the deals and barcode lookups, with nothing in the app saying why.
       Asking eBay for written consent stays open to him; a "no" would end the value and deal
       features built on eBay data.
     - **What bounds it** (X1's criteria; the acceptance does not cover dropping them): a find
       re-checked with one item call before its push; every deal card saying when its price
       was last seen (§8.1.3 asks for no more than six hours' lag, or the age shown); an expired
       eBay deal losing its listing's title and image (§8.1.2, §3.1(b)).
     - **Why now, not at X1's close-out:** an unanswered decision gate stops a group
       (`group-start.md`), and sitting 1 now runs as one (#255).

255. **Group X runs in five sittings: X4 joins the late-October one as X6 → X4 → X5, and
     sitting 1 runs as one group. Supersedes #253's six sittings, at Craig's word on 12 Oct.**

     - **What:** 1) X1 → X2 → X3, `/group-start X · 1`; 2) X7 → X8; 3) X6 → X4 → X5, at
       `xhigh`; 4) X9 → X10; 5) X11 → X12; then 38. Each sitting still starts at his go.
     - **Why X4 moved:** its one tie is a dependency, landing before X5 writes live data, so the
       ledger's grouping rule allows it, and it removes the one sitting with no date. X6 goes
       first because it has the hard date (before 1 Nov 04:00) and no tie to X4, so a stall on
       X4's credential steps cannot hold it up.
     - **What sitting 3 needs before 27 Oct to run without stopping:** Craig's yes on the value
       basis (X6), his storage choice and X4's credential steps. X5's live data steps stop for
       his word inside it either way.
     - **Rejected:** X11 after X1 and X12 after X8. Both fit the grouping rule (shared files),
       but they make 4- and 4.5-day sittings, the first in X1's deadline week, and run X12's
       mid-tier work at top-tier cost. Also rejected, running two sittings at once: every
       close-out edits `STATUS.md`, the ledger and the decision numbers, and deploys from `main`.

256. **Owned discs are valued as used copies (MK47-03), at Craig's word on 12 Oct. Amends #209;
     #237's asking prices stand.**

     - **What changes (X6):** a disc's value is the median asking price of its used listings
       when there are three or more; otherwise New's median times the used-to-New factor
       measured for its format. Home and the film page say "as used copies", and the sale panel
       pre-fills from the used value.
     - **Why:** #209's headline is the largest single-condition group, usually New, so 965 of
       the 1,300 priced discs (92.5% of the £23,604) were valued as new copies. Where both
       exist, a used copy asks 0.48–0.71 of New, and a used copy is what is on the shelf. The
       total falls to roughly £12,800–£17,200.
     - **Still asking prices, not sales:** market-wide sold prices stay out of reach (#16,
       #228), and #237 keeps asking prices. A hand check of about 20 values against eBay's
       sold listings, with Craig signed in, stays an option.
     - **When:** X6 lands before the 1 Nov 04:00 re-pricing, the first with work since 26 Sep.
       Until then the stored values are new-copy prices.

257. **The weekly backup is kept as encrypted GitHub Actions artifacts (DS44-03), at Craig's
     word on 12 Oct; not Neon's paid plan.**

     - **What (X4):** a weekly Actions schedule dumps the database through a role that reads no
       credential, encrypts it to a public key in the repo (the private key stays with Craig),
       and keeps the newest 8 as artifacts, each held 90 days. A monthly drill restores the
       newest into a throwaway Postgres and compares row counts.
     - **Why:** no new account and no cost. Neon's free plan restores only within six hours and
       keeps no scheduled backups; its paid plan would widen that window at Neon's price.
       Weekly, not nightly, keeps the dump's egress near 0.4 GB of the free 5 GB a month.
     - **Craig's, not an agent's:** the role's password, the repository secret and the key pair
       (about 10 minutes, when X4 reaches them).
     - **To watch:** the backup now runs on GitHub Actions. CI already uses about 3,000 minutes
       a month, which may pass a free plan's allowance (unverified: the plan is not readable
       with this repo's token). If Actions stops, the backup and its drill stop with CI, and
       nothing in the app would show it. The one look at GitHub's plan (the roadmap's owner
       step 5) is still Craig's.

### 2026-10-12 — Group X, batch X1

258. **X1's choices: the mark is the pass's own clock, a used copy is judged only against used
     copies, a shop price is a ceiling, and a US import that states no region passes. Amends
     #239.**

     - **The mark is the pass's start less 10 minutes**, set only when the read finished (back to
       the last mark, or at the page cap); a read cut short by the budget leaves none. Reading
       ignores any mark later than the reading pass's start, so production's 21 Oct row stops
       counting on the deploy with no data write. A listing dated in the future is read and
       judged like any other.
     - **The year rule reads a year only straight after the title, past format words**, and allows
       ±1, since a UK disc's year is often its release, not the premiere. "Steelbook 2018" is not
       read. It applies where a year is known: the scan and the scan's usual price pass TMDB's
       year; the film page's estimator and the valuation pass none, so their answers are unchanged
       (the captured fixtures give the same numbers).
     - **A US import that states no region passes** (the evidence's open call). Many are
       region-free, the push and card now name the listing's own title, and a stated "Region A"
       or "Region 1" is refused. A 4K listing is never refused for its region: the 4K disc plays
       here whatever its bundled Blu-ray is.
     - **The new product rules live in the shared matcher** (incomplete, television, not-a-4K,
       region), so the usual price and the valuation lose disc-only and Region A listings too;
       none occurs in the captured fixtures, so no expected value moved. "Empty" and the
       television words count only outside the film's own title ("The Empty Man").
     - **Used is Like new, Used, Very good, Good and Acceptable.** New, Open box and "not stated"
       keep T8a's rule (own group with three or more, else the headline). New's median bounds a
       used group only when New has three or more listings. A usual price stored before X1 has no
       used pool and is searched again when next needed, within the pass's budget.
     - **A shop's price is a ceiling on a New listing's usual** (the cheapest shop, when under
       eBay's figure) and enters no other listing's. #239's average is gone; its like-for-like
       rule stays. The Deals card still lists every part.
     - **The re-check is one item call per find, just before its first push**, within the pass's
       budget: ended, sold out or past its end time, it is not pushed and expires now; not
       checkable (no budget, eBay failed), it is not pushed and stays on the page.
     - **An expired eBay find keeps its price, dates and film; its title becomes the film's**
       (the column is required) and its image and condition go, at the start and end of every
       pass. A shop's deal leaves the page two days after the scrape last saw it, by the feed's
       one query, with no write.
     - **The Wanted sweep runs once**: the first pass whose read finished searches each Wanted
       film by name (10 on 12 Oct), records how many on the run, and no pass after does it again.
       A sweep cut short records nothing and is tried by the next pass.
     - **TMDB's 429 uses the scraper's wait** (now shared as `bounded_wait`): `Retry-After` up to
       90 seconds, a date read as one, never less than the usual backoff. A refusal on the last
       try raises `TMDBRefused`, which the app answers 503 "TMDB didn't answer. Try again in a
       moment." with `Retry-After: 60`.
     - **MK47-04 stands as accepted (#254)**; the re-check, the "Seen" line and the scrub above
       are what bound it.

### 2026-10-12 — Group X, batch X2

259. **X2's choices: one heartbeat table every job writes, the API's readiness recorded at boot,
     one push per appearance, and Deals always in the menu. Amends #154 and #165 for Deals alone.**

     - **A heartbeat row per job, not idle rows in each run table.** `job_heartbeats` holds one row
       per Railway service (`cron-scrape`, `cron-specs`, `cron-ebay`, `cron-values`,
       `cron-reminders`) and `api`, rewritten every run whatever it did ("ran", "nothing due",
       "budget spent"). Run tables keep their meaning: a run row is a run. The check also reads
       each run table's latest start, so a run started from the app counts, and a job's first
       morning after the deploy is not flagged for having no beat yet.
     - **Allowances:** daily jobs 26 hours, the two-hourly eBay scan 5 hours, the valuation
       (1st, 2nd, 15th, 16th) 17 days. The reminders job runs the check, so it cannot see itself
       stop; Home's row says so instead when the last check is more than 26 hours old.
     - **Readiness comes from the API's own boot.** The check runs in `cron-reminders`, which
       holds none of the AI or eBay variables; the API writes its readiness into its heartbeat
       row at startup (a failed write never stops the boot). No new Railway variable.
     - **One push per appearance, to the admin, in a new `attention` category with no toggle.**
       A problem that clears and returns is pushed again. The category has no switch because
       switching off the channel that says push broke would hide the next failure as the last
       seven were hidden. Problems do not fail the reminders job.
     - **"Not all suppressed" counts failed sends too**, over the last three days, ignoring
       notifications still queued (quiet hours). The database's cap is Neon's free 1 GB, so the
       check speaks at 512 MB.
     - **Two identification checks fire on the first morning:** the 165 proposals waiting since
       25 Sep and the films a disc page or review puts in another year. They are real (CT46-03)
       and X9 is their remedy; each is pushed once.
     - **PIN locks escalate within a day of the last** (15 minutes, 1 hour, 4 hours, 24 hours;
       `profiles.lockout_count`, `last_lockout_utc`), and a lock more than a day after the last
       starts again at 15 minutes. A wait over 90 minutes is said in hours.
     - **`cron-scrape` exits 0 when every failure is a refusal** (#240) and 1 for anything else;
       refusals are still listed in its log.
     - **Deals is always in the menu**; Box sets and Collections still hide when empty. The empty
       page says when eBay was last read (the last scan that read listings) and when each shop's
       sale page last gave a deal.

### 2026-10-12 — Group X, batch X3

260. **X3's choices: a refused device is kept and says so, the shell heals on every open, and
     a removed device is left alone.**

     - **`revoked_reason` tells "refused" from "removed"** (migration 051, backfilled `removed`
       for rows a person had revoked; none in production). Only a refused device is registered
       again: healing a device the person took off their list would undo their choice.
     - **The page asks the server, by this browser's endpoint** (`POST
       /notifications/subscriptions/status`): `live`, `refused`, `removed` or `unknown`; another
       person's device reads `unknown`, and registering reassigns it, as it always did.
     - **Healing lives in the app shell**, on every open and on the worker's message, so it
       happens without visiting Settings. It never asks for permission. A refused endpoint is
       unsubscribed and a fresh one taken; where the browser will not subscribe without a tap
       (Safari may not), Settings says when the phone stopped and offers "Turn on again".
     - **The banner shows when a person has no live device and their last one was refused**,
       on every page, until they turn notifications on; someone who never turned them on sees
       none. X2's daily check names it to Craig.
     - **"Pushed" on an eBay run is finds delivered to a phone**, counted after delivery from
       the deal notifications sent since the run began; quiet hours or no live device mean
       not delivered.
     - **Settings says "on" only when the server holds this phone live.** When this browser
       holds nothing but the account's last device was refused, it says when that was.

### 2026-10-13 — Group X, batch X7

261. **The model holds two write tools, behind a card: Part D 9.4's re-scope is overtaken.**
     Part D 9.4 said the model would never hold a write tool. Batch 31 shipped `add_to_wanted`
     and `log_watch` anyway, from the April spec, and no decision recorded the change (R3,
     AI45 "For reconsideration"). This records it: the model may hold write tools because none
     runs before the person taps Yes on a card that names the exact film, the admin check holds
     at execution, and the production model refused a planted instruction (one trial, 11 Oct).
     A third write tool, or one that runs without a card, needs a new decision.

262. **X7's choices: what is stored is what the API takes back, the film is settled before the
     card, and the allowance is a lock.**

     - **Stored blocks keep only the SDK's request fields** for their type (`TextBlockParam`
       and so on), with no nulls, on write and on read; a thinking block passes unchanged. The
       six stored conversations continue without a data write.
     - **The film a write is about is settled when the model asks** (`tools.prepare_write`):
       an id from an earlier result, else an exact title (and year), else, for the wanted
       list, the one TMDB film with that exact title. Several matches, none, a future date or
       a rating off the half-star scale come back to the model as text, so it asks; no card
       shows. The card names "Halloween (2018)" and the date.
     - **A card is closed as declined when a message arrives instead**, with a result that
       says so; the web also locks the box while a card waits.
     - **The allowance is a transaction-scoped advisory lock per person**, checked before
       every model call, a resumed turn's included. One person's simultaneous questions run
       one after another. The cap still counts model calls, not questions; the label is
       unchanged ("N of 50 left").
     - **Caps:** at most 200 messages and $10 a day; a cost cap must be more than zero, and a
       zero already stored reads as the $2 default. Blank boxes on the settings page change
       nothing.
     - **Failures:** every failed call leaves a usage row ("400 invalid_request_error: …", cost
       0, not counted against the allowance). 400, 401, 402, 403, 404, 413 and a 429 with no
       `retry-after` read "The assistant isn't working right now; Craig has been told."; the
       daily check names any failure in the last day (`assistant:failures`).
     - **Rounds:** the fifth is sent with `tool_choice: none`; at most four tools run per round,
       the rest answered "not run".
     - **Results:** 25 films a page (search reaches the best 50), releases 28 days by default
       with a kind filter, totals first, and a cut that counts what it left out.
     - **Prices:** by the configured id; Opus 5.5, Sonnet 5.5 and Haiku 5.5 added; Fable 5.1's
       cache read is $0.25. Moving to a 5.5 model is a Railway variable, Craig's call; their
       thinking blocks are bound to the model and refuse an edited history; this loop sends
       each earlier turn back the same way every time, which is what they need.
     - **The canary** (`src/scripts/assistant_canary.py`) replaces R3's probe: five asks, about
       $0.08, at Craig's word at each monthly delta review; never in CI.

### 2026-10-13 — Group X, batch X8

263. **X8's choices: one describer for failure words, a lower bound on the API wherever the web
     assumed one, a committed OpenAPI description, and a web build that says its commit.**

     - **The worker keeps reads from the page's origin and the configured API's**
       (`VITE_API_URL`, compiled into the worker), each person's in their own partition as
       before, and sign-out deletes the cache.
     - **`describeError` replaces raw text**: "No signal — showing what's saved." for `fetch`
       failing, "The archive had a problem. Try again in a minute." for a 5xx with no words of
       its own, "This screen needs the newest version." for a value this build cannot read or a
       missing chunk, with a Reload banner. A refusal the server explains (a 409, a handled 503)
       keeps its own sentence, and so does an error the app raised in words. Pages with their
       own offline wording keep it.
     - **A failed chunk reloads once a minute at most** (`vite:preloadError` and the error
       boundary), so a page cannot loop.
     - **A crash answers inside CORS** (`UnhandledErrorMiddleware`, registered before
       `CORSMiddleware`): a 500 with the server-fault sentence and the traceback logged.
     - **Readiness adds `tmdb` and `brave`, presence only**; the daily check names either when
       missing. The close-out gate checks every field reads `configured` and that
       `/version.json` on the web reports the merged commit.
     - **The contract test reads `lib/api.ts`**: each parsing function's path, method and zod
       expression, evaluated against the real schemas, walked against the response model in
       `packages/shared/openapi.json`. The API's `test_openapi_snapshot.py` fails when that file
       is stale. **Where they disagreed (158 fields), the API took the bound the web already
       assumed** (`ge=0` on counts, `gt=0` on ids, page sizes and TMDB numbers, `ge=0.5` on a
       rating), not the other way round: both sides now say the same thing, and a value outside
       it is a 500 with its traceback in the API's log and "The archive had a problem" on the
       screen, rather than a screen of raw JSON. Nothing counts those 500s yet; the daily check
       does not read the API's errors. The audit log's
       `actionType` is now the table's five values.
     - **The CSP names `api-production-a8fe.up.railway.app` and drops Supabase and Sentry.** A
       new API host, or Sentry switched on, needs `vercel.json` changed with it. This is a
       `vercel.json` header change, deployed by the merge like any other file in it.

264. **Mark edits, moves and deletes copies; restoring stays Craig's. Supersedes #37.**
     #155 let Mark add a disc and kept editing as Craig's, which left Mark unable to correct
     a disc he had added, or to move one: a copy's location is its section and shelf on the
     edit form. Craig's answers, 13 Oct: "1) yes 2) yes 3) write up as diff batch". So
     `PUT` and `DELETE /collection/{id}` take either person, and the film page shows Mark the
     copy's Edit, Mark damaged, Add a copy and the upgrade prompt. *Why it is safe:* the audit
     row names whoever acted, a delete is soft, and a stale edit is refused (#42). **Still
     Craig's:** the Trash and restoring from it, the audit log, the live eBay check and sale
     panel (T6), and photo uploads and deletes, because a photo delete is a hard delete with
     no audit row. Because Mark cannot restore, Move to trash now asks first, for both people.
     Moving several copies at once is Batch Y2, planned and not built.

265. **Y2 moves discs from anywhere through a tray, scanning included.** Craig, 13 Oct: "this
     probably wouldn't be entire shelves but multiple items from anywhere to anywhere", then
     "Go" and "Include it" for scanning. So Y2's draft (filter the Archive to one shelf, then
     select) is replaced. *How:* a Move discs page finds each disc by search or scan with
     W3's finder, now shared with Loans; picks go into a tray kept on that phone; one place,
     one request. *Rejected:* a select mode across the Archive's three virtualised layouts,
     which would touch all three and still not help with a pile of discs in hand.
     **`POST /collection/move` carries a place per disc**, so "Move them back" is the same
     endpoint with each disc's previous place, not a second write path. Each disc is checked
     against the version it was picked at (#42); **`baseUpdatedAt` is required here**, unlike
     the edit's, because a tray can sit for an afternoon. A stale disc is left alone and stays
     in the tray at its new version, so moving it anyway is a second, deliberate act. **Online
     only:** queueing a many-row move offline would need #42 across a queue. **A scan names a
     film, not a copy** (none of the imported discs carries a barcode), so the person still
     picks the disc when a film has several.

266. **A disc's location text follows its pickers, and the delete question stands alone.**
     Mark's feedback on Y1, 13 Oct, both on 12 Angry Men. (a) He changed the shelf from 3rd
     to 4th; the copy form clears the text when the section changes but not the shelf, so the
     text kept "Front 3rd shelf" and the film page showed both places. The form now clears it
     for a new shelf too, and **the API recomposes any text that names a different place from
     the pickers**, so a phone still running the old app cannot write the mismatch either.
     Text naming the same place is kept as written ("Front 4th Shelf", capital S). Read-only
     on 13 Oct: 1 of 1,885 live discs disagreed, this one, so the rule changes no other row;
     re-saving that copy corrects it. (b) Nothing was deleted: Y1's first tap on "Move to
     trash" grew a warning above the buttons, which pushed "Yes" off a phone's screen and
     left Save in its place, and Mark tapped Save. While it asks, the footer is now only the
     question, "Yes, move to trash" and "Keep it", scrolled into view.

### 2026-10-14 — Group X, batch X6

267. **X6's choices: the used-to-New factor is measured from the stored values, a value from
     before X6 is priced again at once, and the title must open the listing everywhere.** X6
     carries out #256 (amending #209); this records how.

     - **A used copy's value:** the median of the format's standard-edition used listings
       (Like new, Used, Very good, Good, Acceptable, X1's pool) when there are three or more;
       otherwise New's median, with three or more, times the factor. Open box, "not stated"
       and collector editions value nothing; too few of both is not priced. Every row keeps
       both groups (median and count), the range behind the value, and its factor.
     - **The factor is measured, not set.** Two sources disagreed by format (11 Oct references,
       by condition: 4K 0.60 from 59 films, Blu-ray 0.69 from 113; 14 Oct pooled references:
       4K 0.71 from 27, Blu-ray 0.59 from 19), so no constant is trusted for long. Each format's
       factor is the median used/New ratio over stored films with three or more of each,
       capped at 1.00; 0.60, the low end of what was measured, stands in until a format has 20
       such films. A run measures it at its start and, at its end, re-scales every New-based
       value to the factor its own prices give, so the collection rests on one factor per
       format. The film page's live check, the upgrade prompt and the listing link read the
       same factor, so each shows what a run would store.
     - **A value from before X6 is due at once** (no `used_count`) and counts in no total, list
       or film page until a run values it again. So the scheduled runs of 15 and 16 Oct 04:00
       UTC (750 calls each, the usual share) re-price all 1,454 film-formats, not the 1 Nov
       run, and Home shows no total, then a partial one, until 16 Oct. *Rejected:* showing
       new-copy prices under "as used copies" meanwhile, and scaling them by a factor without
       their listings.
     - **The title-opens rule is the shared matcher's now**, so the film page, the valuation,
       the deal scan's usual price and the scan itself apply one rule. Its seller words gained
       labels and import words seen opening a listing of the film itself (Lucasfilm, Walt, 20th
       Century Fox, Zavvi, HMV, import, EU, DVD, BBC, factory) and its window grew from four
       words to six; every word before the title must still be one of them. A word a title can
       start with stays out ("Home" would file *Home Alone* under *Alone*). On the 20 live
       searches of 11 Oct and the two fixtures it refuses 40 more listings, about three in four
       another product; the rest are the film behind a person's name ("John Carpenter's
       Christine"), a stated failure rather than a wrong number.
     - **"Series" alone stays legitimate** (X1's "Collector's Series"); Staffel, Staffeln, mini
       series and miniseries join complete series, TV series, season and "series N". The rule
       is off for the 34 TV titles (`movies.is_tv`; the web sends `isSeries` from `mediaType`).
       "Not 4K UHD" is removed whole before the format is read; "Steelbooks" is a collector
       edition.
     - **The sale panel pre-fills from the stored value**, and the upgrade prompt and listing
       link from the live check's. The bid trial's asking price follows the same rule, as
       "the valuation's own rule" says it does.
     - **Responses cached on a phone before X6 still parse** (zod defaults); a copy's value
       cached before X6 reads as not valued yet, as the API now treats it.
     - **Expected values moved by #256, not by accident:** the captured Blade Runner Blu-ray
       stores £5.45 from 24 used listings, not £9.99 from 29 New; its 4K £18.83, not £24.99;
       Jaws's Blu-ray stays £6.73. The tests that pinned the old figures say so.

### 2026-10-14 — Group X, batch X4

268. **X4's choices: the credential steps done by a session at Craig's word, a copy that is
     data and not a `pg_dump`, and a drill that restores the copy before it is encrypted.**
     Carries out #257.

     - **The credential steps were a session's, at Craig's word** ("can you do it for me with
       option 2", 14 Oct). This overrides the ledger's "not done by an agent" for these three
       only. The session created `mcu_backup` with a generated password nobody has seen
       (`CREATE ROLE … LOGIN`, read-only by default, no admin rights, no role memberships,
       made in SQL, not Neon's Roles page, whose roles join `neon_superuser`). It wrote the
       role's direct (unpooled) address to `~/.mcu-secrets/backup_database_url` (mode 600) and
       piped it into the `BACKUP_DATABASE_URL` repository secret. It built `age` 1.3.2 with Go
       into `~/.local/bin`, because Homebrew's build sandbox cannot fetch Go modules on macOS
       13, and made the key pair at `~/.mcu-secrets/backup-age-key.txt`. **Still Craig's: a
       copy of that private key off the Mac** (`OWNER-ACTIONS.md`); without it, losing the Mac
       makes every copy unreadable.
     - **A copy is data, not a `pg_dump`:** one CSV per table and a manifest (revision,
       columns, rows), in one read-only REPEATABLE READ snapshot. `pg_dump` cannot take a
       table without its credential column, and the schema is the code's anyway: a restore
       runs `alembic upgrade <revision>` first, clears what migrations seeded, loads each
       table in foreign-key order with its own triggers off (derived fields and timestamps are
       in the copy) and its foreign keys checked, fills fresh 256-bit invite links, resumes the
       two sequences, and compares every table's rows with the manifest.
     - **Withheld:** the six tables production's read-only role was refused (refresh tokens,
       calendar-feed tokens, push devices, rate limits, `ebay_accounts`,
       `ebay_connect_states`), plus `profiles.pin_hash` and `movie_night_sessions.invite_token`.
       The copy checks the catalogue each run and refuses when the role can read any of them,
       or cannot read any other table or column, naming each. So a migration that forgets
       the grant (`AGENTS.md`) fails the next Sunday's run rather than leaving a table out.
     - **The drill restores the copy the run just took, before encryption**, into a Postgres
       17 service on the runner: the runner never holds the private key (#257). It also fails
       when the copy is not at the code's newest migration. Decryption was proved once on the
       Mac with the first artifact (14 Oct): 49 tables, 99,822 rows, no PIN hash.
     - **Measured on the first run (14 Oct, by hand):** 26 MB before compression, so about
       0.11 GB a month of Neon's free 5 GB egress, under the 0.4 GB estimated; 7.7 MB
       encrypted; the whole job about a minute. Weekly on Sundays 03:30 UTC, the drill on the
       1st at 04:30 UTC and on every manual run.
     - **Restores go into a new Neon branch** (`docs/restore-runbook.md`): the schema dropped
       and recreated on that branch only, the copy restored and checked, then the switch,
       which is a hosting change and Craig's.

### 2026-10-14 — Group X, batch X5

269. **X5's choices: a film only watched has a row and no copies, "owned" is a film with an
     owned copy, the year excludes when both are known, and every write to history is a plan
     first.** Carries out Craig's decision of 11 Oct; amends #158.

     - **A film the feed names and the catalogue lacks gets a row of its own** (title, year,
       TMDB id; no copies) and the watch goes on it, keeping the feed's TMDB id
       (`watch_log.tmdb_id`, migration 054). The feed never falls back to a title. *So an
       unidentified owned film watched now gets a twin row, which its identification later
       merges into; X9 should let a merge into a row with no discs through without asking.*
     - **"In the collection" means a row with an owned copy** (`owned_film`, beside
       `owned_copy`). Home's Films, Identified, genres and decades, the movie night deck,
       completion sets and the per-person counts now ask it; until X5 they counted every live
       row, so wanted films were in them too (Home showed 1,917 films where 1,896 are owned:
       part of UX48-05, which X12 no longer needs to fix for Home). Watch-centred lists (Most
       rewatched, Top rated, "You've watched") keep films only watched: they are watches.
     - **The year rule (#158 amended):** a title candidate whose year is known and more than
       one from the entry's is excluded; an unknown year on either side never excludes, which
       is what #158 protected.
     - **The file import no longer identifies** (`MatchingEngine` put three diary films on the
       wrong owned rows, CT46-01); identifying owned films is T9's. Its tests went with it.
     - **The backfill and the 15 are plans first**, as T9's identification is: `plan` writes
       nothing (it runs on the read-only role), uses T9's identifier with no web search, and
       saves the exact decisions; `apply` writes them once, at Craig's word, re-checking each.
       Dry runs on 14 Oct: Craig 579 unrecorded entries → 56 on owned films, 1 on a listed
       film, 436 on 397 films to add, 86 doubtful; Mark 177 → 56, 1, 101 on 95 films, 19
       doubtful. The 15: 7 to move, 8 doubtful (TMDB holds another film of the title within a
       year of the logged one). Doubtful entries go to Craig as CSVs in `.letterboxd-export/`.
       56 of each person's "owned" entries match now and did not in September because T9
       renamed those films to TMDB's titles after the import.
     - **The weekly sync is the 08:00 job's** (`sync_due`: anyone with a username unsynced
       for 6.5 days, `trigger = cron`); a failure is recorded on its run and never fails the
       job. **The job has no TMDB token**, so a film it adds keeps the feed's title and year;
       Sync now in the app fills in up to 20 such films each time. *Rejected:* adding the TMDB
       token to `cron-reminders`, a hosting change of Craig's.

### 2026-10-14 — Mark's feedback: the Lounge's sides, and a year in a search

270. **The Lounge's two sides are its shelves, detail typed beside a section is kept after
     it, and a search ending in a year is read as a year.** Mark's feedback, 14 Oct; amends
     #266. Both taken at Craig's word ("yes to both").

     - **The Lounge side was lost by #266.** Mark chose Lounge and typed "Right Hand Side";
       #266 dropped any text naming a different place from the pickers, and text naming no
       place counted as different, so the copy saved as plain "Lounge". Two copies lost their
       side that way (Nope and Us, both 4K, 14 Oct; the typed text was never stored). Every
       section without shelves had the same fault.
     - **Left and Right go in `shelf`**, as Front's and Back's shelves do: one column, one
       filter, one move. The pair is fixed (`LOUNGE_SIDES`), so a side holding nothing is still
       offered; the facets serve each shelf's `label` ("Left hand side") and each section's
       `shelfNoun` ("side"), so the web names them without knowing the rule. Picked sides are
       written "Lounge Cabinet - Right Hand Side", as the imported copies already were, and
       `parse_location` reads a side out of Lounge text (only once the section is the Lounge:
       "Left Hand Side Small Cabinet Fish Room" is a cabinet). *Rejected:* only undoing #266's
       rule, which keeps the side as free text with no picker or filter, and is not what Mark
       asked for.
     - **Migration 055 fills the side in from the text**: 164 live copies (96 right, 68 left)
       and 160 in the Trash. It is not optional: once the parser reads sides, a Lounge copy
       without one would lose its text at its next edit. The downgrade clears the sides; the
       text is never touched.
     - **Text naming no place, typed beside a chosen section, is kept after it**: "Garage - top
       row". With the section in front, the text still says where the disc is when read alone,
       as the export reads it. *Rejected:* storing it exactly as typed (before #266), which
       leaves "top row" in the export with no section. An app from before the side picker that
       sends "Right Hand Side" beside the Lounge gets the side read from it.
     - **The add form's TMDB search** shows all 20 of TMDB's first page (was 10: the 1974 Texas
       Chain Saw Massacre, spelled so by TMDB, was 14th for "The Texas Chainsaw massacre"), and
       a search ending in a year ("… 1974", "… (1974)") also runs as the title filtered to that
       year, **films released that year first**, then the search as typed, because some titles
       end in a year ("Blade Runner 2049"). TMDB's year filter also matches re-releases, which
       is why the sort is by each film's own year.

271. **The Archive lists the films still to identify, for Mark to fix from their pages.**
     Mark's request, 14 Oct: "a drop down for unidentified" among the filters, to fix his
     oddly worded titles at leisure. He can already identify a film from its own page (the
     identify panel shows on any film TMDB has not matched, and `POST /movies/{id}/identify`
     is open to a viewer); what he lacked was a list of them.

     - **"Still to identify" is the Identify films page's own term** (Batch T9): no TMDB id,
       and not set aside as a TV series or not a film. 155 of the 190 owned unidentified films
       on 14 Oct; the 35 set aside are left out, because they cannot be identified as films and
       offering them invites a wrong match. A skipped film is still listed.
     - **A `toIdentify` filter on `GET /movies`** and a `toIdentifyMovieCount` on the facets,
       which names the option ("Still to identify (155)") and hides it at 0, by #154's rule.
       **The Archive only:** a smart collection does not save it, because the list empties as
       it is worked through. Identifying a film refreshes the count.
     - *Rejected:* opening the Identify films page to Mark. It is quicker per film, but it is
       an admin page with merges and undo, an access change that was not asked for. The
       queue reads live, so a film Mark identifies leaves Craig's queue too.

272. **A film is flagged to identify exactly when "Still to identify" lists it; the phone's
     open Filters panel is a history entry with a "Show N films" button.** Mark's feedback,
     15 Oct, after working through about 200 unidentified films.

     - **The badge and the filter disagreed.** The card's "Identify", the list row's "Needs
       identification" and the film page's "Which film is this?" read `tmdb_id IS NULL`; #271's
       filter also leaves out the 35 films set aside as a TV series or not a film. So
       Broadchurch, set aside as TV, was flagged but never listed. Each list item and film page
       now carries `setAsideAs` (`tv`, `not_film` or null, from `identify_lookups`, one query a
       page), and the web's `needsIdentifying()` is `!identified && !setAsideAs`, #271's own
       predicate. A set-aside series shows "TV series"; its page says why it has no match, and
       "Identify as a film" still opens the panel for one set aside in error.
     - **The phone could not reach a filter's films.** The Archive's grids are virtualised in a
       `flex-1 min-h-0` scroll box under the filter bar; the open panel is taller than a phone's
       screen, so the grid measured 0px at Pixel 7 size and there was nothing to scroll to. Below
       1280px the Archive's open panel is now a history entry (`location.state.filtersOpen`), so
       the back gesture closes it instead of leaving the app, and it ends in "Show N films".
       At 1280px and over, and in a smart collection's editor, it is plain state as before.
     - *Rejected:* capping the panel's height so the grid peeks below it. Two nested scroll
       areas on a phone, and the count in the row already answers "did that filter do anything".
     - **Not decided here: identifying TV series (Mark's points 1 and 2).** TMDB numbers films
       and series separately, so it needs its own column, not `tmdb_id`, which about 40 modules
       read as a film's id. Proposed to Craig as one batch, `OWNER-ACTIONS.md` item 31.

273. **A TV series is identified from TMDB, with its own id; the 34 set aside join "Still to
     identify"; a read-only check finds the series matched as films (Batch Y3).** Mark's
     feedback of 15 Oct, points 1 and 2, built at Craig's word the same day ("lets build it
     now", on `OWNER-ACTIONS.md` item 31). **Supersedes #214 in part** (T9 set series aside
     because the app matched films only) **and #271's and #272's exclusion of set-aside series.**

     - **`movies.tmdb_tv_id`, not `tmdb_id`** (migration 056). TMDB numbers films and series
       separately, and about 40 modules read `tmdb_id` as a film's (values, specs, streaming,
       reviews, Letterboxd, the identify queue): a series' number there would fetch whichever
       film shares it. A row holds at most one of the two; identifying it as one kind clears
       the other, so a series matched as a film is corrected from its page, and back.
       `identify_lookups.media_type` says which index a lookup's id is from, and the audit
       keeps a series' id as `tmdbTvId`, so nothing reading `tmdbId` meets a series' number.
     - **A series fills in what a film does**, from `/tv/{id}` with `aggregate_credits`
       (the whole run's cast, not the last season's), `videos` and `external_ids`: first-air
       year, no runtime (a per-episode figure would have "under two hours" find a sixty-hour
       series), TV genres also filed under the film genre they cover (War & Politics under
       War) so the genre filter finds them, creators as writers (`movie_credits` has no creator
       role and creators nearly always write), `is_tv` true so values keep the series rules.
     - **"Still to identify" is now: neither id, and not set aside as not a film.** The 34
       series T9 set aside are listed again, to be identified as series; the panel offers
       TMDB's series first for them ("Which series is this?") and after the films otherwise.
       Craig's Identify films queue, the dry run and the search-beyond list leave a series
       identified out; the stats count it identified; its streaming offers come from TMDB's
       series providers. Letterboxd links and price alerts stay films' only.
     - **Finding the rest is a report, not a change:** `src.scripts.find_series_as_films`
       names an identified film when TMDB has a series of the same title with five times its
       votes and at least 50, or a disc is grouped "TV", or a replaced spreadsheet title has
       T9's series words. Mark or Craig correct each from its page. It reads in a `READ ONLY`
       transaction, or over HTTPS with the read-only role from a cloud session.
     - **Not checked against a real TMDB answer:** the building session had no TMDB key. The
       series model follows TMDB's published shape with every field optional; the first live
       identification is the check.
     - *Rejected:* storing series in `tmdb_id` with a kind column (every reader of `tmdb_id`
       would need the kind, and one that forgot would fetch a stranger's film); re-identifying
       the suspects automatically (a series sharing a better-known film's name would be
       overwritten with nobody looking).

274. **The series still to identify are identified by a pass where TMDB leaves no doubt; Mark
     chooses the rest (Batch Y3, follow-up).** Craig, 15 Oct, asked for #273's two remaining
     steps to be done rather than left to Mark and him; this session could reach neither TMDB
     nor the live database, so he chose a pass he runs at the Mac, in T9's shape (#214).

     - **The same list Mark sees.** The Archive's "Still to identify" rule moved to
       `services/identify/waiting.py`, and the pass reads exactly it, on the shelf.
     - **Sure, or Mark's.** It proposes a series only when TMDB has one of that title (searched
       as a series is sold: "Broadchurch", not "Broadchurch Series 1 - 3"), or one with five
       times the votes of every other of that title and at least 50, its first-air year within
       a year of any the title gives. Several alike (The Office, 2001 and 2005) or none at all
       are left for Mark, with what TMDB offered.
     - **Dry run, report, then the exact plan.** The dry run writes nothing (`READ ONLY`); the
       live run applies the plan Craig read, re-checking each title, audited `auto` with its
       evidence, undoable from Identify films, and **never merges**: a series another title
       already holds is left for Mark, named.
     - *Rejected:* doing it from this cloud session (no Postgres connection leaves it, and its
       role is read-only by design, #236); applying without a report (46 identifications nobody
       read first).

275. **An identified film can be in doubt; a copy can move alone; an inferred edition says
     "probably"; the old paths' films are re-checked at the Mac (Batch X9).** CT46-01 found 30
     copies confidently the wrong film and CT46-03 that the app's own year checks blamed the
     page. Craig said go on sitting 4 with "code here, data at the Mac", 15 Oct.

     - **A doubt is its own row** (`identify_doubts`, migration 057), not an identified film's
       lookup turned back to "needs you": the lookup records how the film was identified, and
       its constraints tie "identified" to a TMDB id. One open doubt per film and source, or per
       copy and source. A doubt Craig kept is not raised again by that source while the film
       stays as he left it.
     - **Identifying a film again settles every open doubt about it**, by whichever page it is
       done, and the undo opens them again; a merge carries a film's doubts and its undo brings
       them back. Undoing a correction of a film that was identified before now puts its lookup
       back as it was, not into the queue.
     - **The spec and review jobs raise a doubt only when the page names the film** by T9's
       rule (its title, original title or a replaced sheet title) and the film is identified.
       A remake's page names the film too, so Craig keeps the film with a tap and the page goes
       back to "pick the right page"; correcting it chooses the page again for the next run.
       The 36 notes written before X9 are left as they are: the re-check asks about the films
       behind them from their sheet rows.
     - **A copy moves on its own** to the collection's film of that TMDB id, or one made from
       TMDB's record; watches stay with the film they are of. The undo removes a film the move
       made only when no copy, watch or want has come to point at it.
     - **`edition_source`** (migration 058) marks an edition the spec job inferred, by how its
       page was settled. The backfill marks only editions no audit row shows a person setting.
       Either person confirms (as either edits, #264); sending the same edition back, as "mark
       damaged" does, confirms nothing.
     - **Release names are compared by T9's rule as well as the old one**, exact matches only:
       "Alien" is not "Aliens". `fold` reads "Vol." as "Volume", for identification too.
     - **The re-check never re-identifies.** It sorts T9's answer into a verdict; `--apply`
       raises a doubt for every disagreement (`unsure` included: the review's Good Fellas is
       one, since T9 will not choose between a namesake and the real film), at Craig's word.
     - *Rejected:* re-identifying the old paths' films automatically (T9 asks about some of the
       30, and a wrong bulk change is what CT46-01 is); deleting `MatchingEngine` now (X10's
       one title rule replaces its helpers, and its evaluation script still runs it); turning
       the 36 old year-conflict notes into doubts in a migration (27 of them were wrong pages,
       correctly refused, and would each have cost Craig a tap).


276. **Mark settles identification doubts from the film page (Batch Y4); partly supersedes
     #275's "Craig settles each one".** After item 32 raised 384 doubts on 16 Oct, Craig asked
     for Mark to verify them in the app, chose the full version over finding-only or a list,
     and said go the same evening. Mark had already worked through the unidentified films
     from their pages (#271–#273).

     - **Three Identify routes take any signed-in person:** keeping a doubt, moving one copy,
       and the read-only TMDB search the move uses. Correct match was already his (#273) and
       settles every doubt on the film. Each audit row names who. The queue, the doubts list,
       Recently identified, its undo and set aside stay Craig's.
     - **Mark finds them** with the Archive's "In doubt (N)" filter beside "Still to identify",
       and an "In doubt" flag on a card or row: an identified film with an open doubt, counted
       as Identify films counts them.
     - **The film page lists every open doubt**, where X9 showed the oldest, each with its note,
       the copy it names, T9's proposal and up to three lines of evidence, and the three
       actions. "Move only this copy" shows only where the doubt names one copy of a film with
       others, as X9's Identify page offers it. `identificationDoubt` stays as the oldest, so a
       phone with an app cached before Y4 still shows the note.
     - **A keep is now listed under Recently identified ("kept as right") and undone there**,
       opening the doubt again; refused once the film is identified as another since. Until
       Y4 a keep had no undo. Every recent row now shows who did it.
     - **Mark's keep counts as Craig's would:** the re-check does not raise that film again
       while it stays as he left it. If he keeps a wrong film, nothing prompts again; Craig
       sees it, named, on Recently identified and can undo it.
     - *Rejected:* finding-only for Mark (the tap that clears about 370 right films would stay
       Craig's); a list sent to Mark outside the app (the same, and no audit); opening the
       whole Identify page to Mark (merges and set-asides rewrite more than one film, and the
       queue is Craig's working list).


277. **Mark's 16 Oct points (Batch Y5): series discs are added and moved as series, Film Noir is
     TMDB's keyword, and a disc TMDB lacks is added by its title.** Mark raised three, Craig
     approved all three on 16 Oct and chose TMDB's keyword for Film Noir.

     - **A series is a third way to name a film on the add form and for a move.** The add
       form's search lists series apart (`series`), and the move's search answers
       `seriesCandidates`, rather than mixing them into the films: an app cached before Y5
       reads only the films, and would otherwise offer a series' id as a film's. The copy goes
       on the collection's row for that series (`tmdb_tv_id`, unique since Y3's migration
       056), or one made from TMDB's record exactly as Correct match makes one.
     - **"Move only this copy" opens searched on the doubt's own title** (the sheet's, as the
       re-check raised it), so the three series discs are one tap from their doubts. Moving
       them is Craig's, in the app: the agent identifies and moves nothing.
     - **Film Noir is `movies.tmdb_keyword_ids`** (migration 059), every TMDB keyword of the
       film, not a noir flag: the filter is `keywordId`, and the Archive offers 9807 as "Film
       Noir" with the genres. Null is "not fetched", an empty list "TMDB has none", so the
       backfill knows what is left. Every path that fetches a full record now fills it.
     - **The backfill is a script, dry run by default**, at 8 calls a second, touching only
       null rows. Its writes are metadata, as an identification's are, so they are not audited
       one row per film; the run's counts are its record.
     - **A disc TMDB lacks is added by its title and filed as set aside, not a film**, by
       whoever added it, so it never sits on "Still to identify" waiting for a match that does
       not exist. A second copy under the same title finds that row and meets the duplicate
       prompt. Craig can put it back from Identify films as any set-aside title.
     - **With a barcode held, a series or a title-only add skips the barcode confirmation**:
       the barcode cache knows films only, and the copy still carries the barcode, which the
       next scan finds as an owned disc.
     - *Rejected:* IMDb's "Film-Noir" genre (the app has no IMDb source to read it from); the sheet's
       "noir" groupings (48 rows, a shelf grouping, not a film's property); one combined
       film-and-series result list (an old cached app would add a series as a film); a boolean
       `is_noir` column (the next keyword Mark asks for would need another migration).


278. **The 378 open re-check doubts are settled from one agreed plan, 17 Oct.** Mark asked for
     them to be settled "to what you think they are"; Craig agreed the plan Claude proposed
     (`scratchpad/doubts-plan-17-oct.md`) with five answers (Carrie 1976, Crossroads 1986,
     Fright Night 1985, Vice Versa 1948, bin the old Ghostbusters 2 copy) and three exceptions
     of his own (the Pelham and Journey Blu-rays are the 2009 and 2008 films; French
     Connection II's row holds one copy of each film, so one copy moves).

     - **The plan:** 370 kept, 6 corrected (Arsenic and Old Lace 1944, Holiday 1938, X2, A
       Tale of Two Cities 1958, and the Planet Earth II and Last Chance to See series), 1 copy
       moved (to The French Connection), 1 copy binned. A keep needs the identified film to
       be far better known than any namesake (260 by ten times the votes or more) or the
       copy's grouping or shelf to say which; the rest were Craig's.
     - **`src.scripts.settle_doubts` applies it through the app's own actions** (keep,
       correct, a series identification, move one copy, Delete), each audited as Craig and
       undone from Recently identified or the Trash. A dry run checks every entry first; an
       entry overtaken since the plan is skipped, never forced, and a correction that would
       merge is refused.
     - *Rejected:* settling by votes alone (a remake often outvotes the classic this
       collection holds); writing the statuses in SQL (no audit, no undo); asking Mark about
       all 378 (he asked not to be).


279. **A doubt shows only while what it is about is still owned (Batch Y6).** On 17–18 Oct a
     re-check doubt outlived the copy it named, binned by #278's plan: its film had no owned copy,
     so the Archive and the film page never showed it while Identify films counted it, and Craig
     could not find it. He chose this on 18 Oct from two options.

     - **One predicate, read everywhere** (`showing_doubt()`): an open doubt on a live identified
       film whose named copy is still an owned copy of that film, or, naming no copy, whose film
       has one. Identify films' list, overview and the daily check now ask what the Archive and
       the film page already asked.
     - **Nothing is written when a copy goes.** A binned or sold copy's doubt stays `open` in the
       table and hides; restoring or unselling the copy shows it again unchanged. Every path that
       bins, sells or restores is covered by the rule, including ones not yet written.
     - **Counts are films where the Archive's are.** "Identified, in doubt" counts films, equal to
       the Archive's "In doubt (N)"; the daily check counts films with a fortnight-old showing
       doubt. The doubts list stays one card per doubt and says both numbers when they differ.
     - *Rejected:* settling the doubt when its copy is binned and reopening it on restore (B): a
       new status and a migration, hooks in about four bin paths, three restore paths and the
       sell path, and a rule for film-level doubts when the last copy goes; each missed hook brings
       the fault back. Its one gain, that the table's statuses match the screens, is not worth
       that. Hiding only when the film has no owned copy at all (A as first written): a doubt
       naming a binned copy of a film with other copies would still show, about a disc that is
       gone.


280. **X10 is slimmed to what still holds, at Craig's word on 18 Oct ("slim X10 as you
     recommend").** Re-measured read-only before code: the four title rules still disagree on
     7 of R1's 8 pairs; the 5 split films are one row each and only 1 owned film is
     unidentified (from 210 on 11 Oct); no owned copies share a barcode; 9 copy-less rows from
     the 18 Sep refresh remain, plus 3 of the same kind since.

     - **Kept in full:** the one title-key module and its pair-table guard, the dry-run diff,
       and the leftover rows at Craig's word with the count shown first.
     - **Narrowed:** the add form's lookalike check and the barcode warning stay, as cheap
       insurance rather than a fix for live harm: the lookalike reuses Search's check through
       the duplicate check the add form already makes, and the barcode warning names the copy
       the scan's banner already finds.
     - **Two levels, not one key:** `WORDS` keeps order and the article, for a page title read
       as a prefix (AVForums' "Dog Soldiers 4K Blu-ray Review"); `TITLE` is a catalogue
       entry's key, the article dropped, as Letterboxd's rule already dropped it. T9's
       `compare` stays the identification verdict on top of the same `fold`.
     - **Choices made building it:** `TITLE` drops edition words and a bracketed year as the
       catalogue's rule did, and the leading article as Letterboxd's did; Search's lookalike now
       drops the article too (a may, which the year still checks). A barcode on an owned copy is
       refused unconfirmed by the add, as the same film is, while the lookalike is asked only by
       the preflight check: it is a question, not a duplicate. The add form sends the film's
       title and year with the check rather than the API fetching TMDB for them.
     - **The leftover rows are a rule, not a list:** a live row with no TMDB id of either kind, at
       least one copy and every copy binned, and no watch, want or movie-night suggestion.
       `--apply` needs `--expect N`, the count Craig saw, and puts each in the Trash, audited,
       restorable. The dry run on 18 Oct found 12: the review's 8 were 9, and binning has made 3
       more of the kind.
     - *Rejected:* dropping the add-form and barcode criteria (Craig's alternative): both cost
       about an hour once the module exists, and the next import or title-only add can make an
       unidentified twin again; keeping X10 as written (two of its five findings are gone, and
       a criterion that cannot fail proves nothing).

281. **X11: shop prices shown, alerts without a limit, and a weekly ask for refusing shops.
     Amends the ledger's third criterion at Craig's word on 18 Oct (counter on `retailers`,
     half-requests rule, no live seeding; alert only on a stored fresh usual).**

     - **Re-measured first (read-only, 18 Oct):** 1 of 10 wants has a limit; no screen showed a
       shop price; the nightly run took 26-29 minutes on every night from 3 Oct (25-28 refusals,
       each waited 60 s). **No shop refuses every request:** 101 Films, Powerhouse and Second
       Sight each had 5-10 of 10 wants refused twice on each of the last 9 nights and a retry
       get through on some, so "refused every request for a week" matched none. The shops now
       give 1-2 prices a night (5-7 on 11 Oct); Zavvi has priced nothing since 12 Oct.
       `retailers.scrape_frequency` exists but `run_scrape` never reads it, and every live shop
       holds the default `weekly`: honouring it as it stands would have moved Zavvi and Arrow off
       nightly too.
     - **The rule:** a night counts against a shop when it refused, twice each, at least half of
       the requests it was asked (`REFUSING_SHARE`); `retailers.refused_nights` (migration 060)
       counts such scheduled nights in a row and any other night resets it. At seven
       (`WEEKLY_AFTER_NIGHTS`) the scheduled check leaves the shop alone until a week less 12
       hours after it was last asked, then asks it; if it still refuses it stays weekly, if it
       answers it is nightly again. "Run now" and dry runs ask every shop and never touch the
       counter. No stored schedule, no change to `scrape_frequency`.
     - **No live row is written.** Every shop starts at zero, so the first skip is the scheduled
       check after the seventh refusing night: about 26 Oct if the three keep refusing at this
       rate (Second Sight sits at exactly half on some nights and may not hold seven). A seed
       to start sooner would write live rows: Craig's word, count shown first. Until then the
       half-hour night stays.
     - **Alert without a limit:** a shop price strictly under the usual alerts, on the way down
       as a limit's does. The usual is `ebay_price_refs` for the film and the format read off
       the shop's listing (not the want's, 8 of 10 name none), as a New copy's (`yardstick`),
       from a ref fresh within 14 days; a limited or other non-standard edition, a non-GBP
       price, or no fresh ref means no alert. Nothing calls eBay from the shop check. The body
       names the usual and its listing count. A want with a limit is unchanged.
     - **Shown:** `GET /wanted` carries `shopPrices` (each shop's newest check for the want,
       cheapest first: shop, price, date, the listing's title, its link); the card lists them
       with the day, or says none was found. The Retailers screen says "asked weekly".
     - *Rejected:* a circuit breaker that ends a shop's night at its first refused-twice request
       (a night would be minutes at once, but it gives up the one price in four that gets
       through, which Second Sight and Powerhouse still delivered this week); honouring
       `scrape_frequency` (see above); a threshold below the usual such as V8's 30% (the ledger
       says "under", and an alert fires once per drop).


282. **X12 is split into X12a, X12b and X12c, at Craig's word on 18 Oct; X12a is built.**
     Re-measured first (read-only): the review's stale agent summaries and the API's films count
     were already fixed (X5, #269); live copies are 1,923 (1,335 discs, 588 downloads) over 1,899
     films with a copy, not 11 Oct's numbers.

     - **Split:** X12a counts, dates and the movie night; X12b phone polish and speed; X12c terms
       and tidying (two live steps at Craig's word). About three days, so three close-outs.
     - **Home:** "Films owned" (with a copy) and "Copies" with "N discs, M downloads" under it
       (`downloadCopies` on `/collection/stats`); the Formats chart says "Downloads" (copies
       carrying the download format, 588) and both charts say "(copies)", because "Digital" was
       also a shelf section with a different count (454).
     - **Dates:** one module, `lib/utils.ts`: `formatDate` ("11 Oct", "11 Oct 2026" outside the
       current year), `formatDateTime`, `formatMonth`, beside `formatShortDate` (always with the
       year) and `formatDayMonth`. Every `toLocale*String` date was moved onto them, and a test
       fails when a screen formats one by hand again (month headings on Releases and UK clock
       time on Price alerts are named exceptions). *Not done:* `formatShortDate` keeps its year
       in the current year, because its callers (watch dates, price history) want the full date
       and its tests pin that.
     - **Movie night:** the shortlist, the match event, the push and the night page read title,
       year and poster from the film when it is on the shelf (the snapshot only for a film nobody
       owns). **A match is now stored on the session** (`matched_suggestion_id`, migration 061,
       set when announced, with **no foreign key**: a suggestion already points at its session, and
       the second constraint is a cycle the restore drill refuses) and `GET /movie-night/{id}`
       returns it, so a night opened
       from the push shows it. This **departs from the old rule "no matches table: the votes are
       the truth"** (Batch 35): the column only remembers which suggestion the latest
       announcement was about, nothing reads a match from it but the page, and the votes still
       decide whether there is one. No backfill: nights that matched before show none.
     - **A copy's shelf once:** one `placeLabel` (`lib/place.ts`) for the film page, Move discs
       and Loans; it prints the recorded place, else the section and shelf.
     - **Tell Craig:** a line typed on Mark's You page (300 characters, at most 5 waiting) is
       stored in `craig_notes` (migration 062, both read-only roles granted) and appears in
       Craig's "Needs attention" row as "Mark says: …" with a Clear button (`DELETE
       /attention/notes/{id}`, admin). No push: Craig opens Home. Craig is not offered the form.
     - **Expectations that changed, by design, because a response gained a field:**
       `test_home_lists_the_problems…` (attention items carry `noteId: null`) and the shared
       `attentionSchema` test (the parse now returns `noteId: null`). No assertion was loosened.


283. **X12b: the phone's type, targets and speed (UX48-06, UX48-07).** Re-measured first, with R6's
     headless walker (Playwright, axe-core 4.10.2, 375 px, both themes) pointed at the current
     build and a seeded throwaway database, 29 of R6's screens, before and after.

     - **Gone before I started:** the dark primary button is 4.84:1 now (R6 measured 4.17:1; the
       token test pins AA), and axe finds no contrast or target-size *violation* on any measured
       screen (22 "could not decide" results over images and gradients, unchanged).
     - **12 px floor:** every `text-[9-11px]`, `0.5625-0.6875rem` and the two shared classes
       (`.page-kicker`, `.metadata-label`) became `text-xs`; small text on the measured screens
       went from 390 elements to 0. `MobileTabBar.test` pinned 11 px and now pins 12 px (the
       criterion changed it); the bar's side padding and tracking went so "Movie night" fits its
       75 px slot at 12 px. A test (`type-floor.test.ts`) fails when a size under 12 px returns.
     - **44 px targets:** `.list-link` (44 px tall) on Wanted's titles and review links, Trash,
       Identify's three title links, the Home shelf link and the privacy page's way back; the
       activity feed's whole row is the link; the top bar's avatar and assistant buttons are
       44 px; the skip link is. Targets under 44 px on the measured screens went from 142 to 70.
       **Not done, by design:** in-sentence links keep their line; 24 px-tall settings switches
       stay (WCAG 2.5.8's floor is 24); `Button size="sm"` is 36-40 px and is a button, not a
       list link. The ledger's "list links" are met; "every control at 44" is not claimed.
     - **Compression:** `GZipMiddleware` (minimum 1,000 bytes, level 5), innermost. Starlette
       leaves `text/event-stream` out, and a test pins that the app does not override the list, so
       the assistant's and the movie night's streams still flush.
     - **Archive list:** the query selects the 14 columns a card shows (`LIST_COLUMNS`), as
       columns rather than half-loaded `Movie` objects, which would break the next read of
       another column in the same session. On live data, whole rows are 5,462 kB for 1,927 films
       and the list's columns 287 kB (19 times less). **Its first screen renders before the
       rest:** the page asks for 60 films and for all of them together, shows the 60 as soon as
       they arrive and swaps in the full list, saying "Showing the first 60 of N films; loading
       the rest…" meanwhile, and if the rest fails keeps the 60 and says so.
     - **Not measured:** wall-clock times against production. R6's cold-open numbers (2.0 s on 4G,
       7.8 s on a weak link) came from a throttled rig reading production-sized data; mine reads
       a seeded database of three films, so only the bytes are measured here. Check on a phone
       after the deploy.


284. **X12c: terms and tidying (DS44-06, CT46-06, CT46-07, the rest of CR43-08).** Re-measured read-only
     on 18 Oct before code; the live counts are in the ledger. Two data steps stay Craig's word.

     - **TMDB's terms:** Settings ends with a "Film data" panel: TMDB's own logo (the
       `blue_square_2` SVG from themoviedb.org/about/logos-attribution, 2,577 bytes, downloaded at
       Craig's word on 18 Oct and saved unaltered as `apps/web/public/third-party/tmdb.svg` (not `brand/`, whose files a test requires to be byte for byte the design system's), so no CSP or
       hosting change) and "This product uses the TMDB API but is not endorsed or certified by
       TMDB". TMDB's page gives no required wording; this is the standard sentence. **JustWatch** is
       credited under the film page's providers and on the movie night's "Streaming on" line.
     - **TMDB data over six months:** `services/tmdb_refresh.py` refetches a film (or series) whose
       `last_tmdb_sync_utc` is older than 150 days, stalest first, 100 at a time, inside the
       calendar refresh (which a read triggers at most daily). It rewrites TMDB's fields and credit
       rows and nothing a person set. **A film with no sync date is left alone** (17 on 18 Oct): its
       age is unknown, and the first run must not write rows nobody expected. None is 150 days old
       yet (the oldest is 8 Sep; 1,051 films reach it on 5 Feb 2027, so 11 days of runs clear them
       well before 8 Mar). A failure on one film is recorded and the rest go on; a failure of the
       whole step is added to the calendar run's errors and never fails the calendar.
     - **Brave results:** `done` and `skipped` are the settled states (not `accepted`, whose fetch can
       be sent back and then needs the results). A settled lookup keeps only its accepted page, which
       the doubt checks read the title of; the deletion runs after the edition is read off the other
       results. For the 850 `done` lookups already holding results, `src.scripts.prune_spec_results`
       (dry run by default; `--apply --expect N`) deletes what remains: **9,456 results of 15,516
       on 18 Oct.** `test_a_disc_searched_under_a_misspelt_title...` changed its expectation from
       "keeps both new results" to "keeps the accepted page", which is the criterion.
     - **Completion sets:** an actor counts only for films they are top-ten billed in (both when the
       person is chosen and for the set's members; the old member rule was order 15); a credit TMDB
       flags `video` (a compilation: *Cinema 16*) and a film of 40 minutes or less (TMDB's discover
       by runtime, one call per set, `with_runtime.gte=1` so an unknown runtime is not a short) are
       left out. If the shorts call fails the set is left as it was and the run says so. The
       existing 40 sets change only when the refresh runs: **a live step, Craig's word.**
     - **Tidying:** the Supabase-era `migrations/001_profiles.sql` is deleted (nothing read it);
       `*.xlsx` is ignored by pattern (Craig's two catalogue spreadsheets stay, untracked and
       untouched); the duplicate #28 is noted in place, not renumbered (documents cite both);
       `group-start.md` cites #24, not #13.
