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
