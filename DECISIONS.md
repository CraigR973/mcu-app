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
