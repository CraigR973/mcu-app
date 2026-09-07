# Part B — mcu_app code audit (Stages 0 → 3.1)

**Date:** 2026-09-07 · Audited against `docs/house-standard.md` · Read-only, no code changed.

Severity: **H** = blocks deployment or is a correctness/security defect ·
**M** = real divergence with a cost · **L** = cosmetic or deferrable.

---

## B1 — Data layer

| # | Sev | Finding |
|---|---|---|
| B1.1 | **H** | **Sync SQLAlchemy.** `src/database.py:3-17` uses `create_engine` + `sessionmaker` + psycopg2. All four reference repos use `create_async_engine` + `async_sessionmaker(expire_on_commit=False)` + asyncpg. This is the single largest code-level divergence — it touches every router. |
| B1.2 | **M** | **No pool configuration.** Only `pool_pre_ping=True`. The house standard is `pool_size=10, max_overflow=10, pool_pre_ping=True, pool_recycle=1800`, identical in all four. |
| B1.3 | **H** | **25 tables created, 3 have ORM models.** Migrations create `admin_actions, box_set_items, box_sets, chat_conversations, chat_messages, collection_items, completion_sets, deals, email_accounts, gift_links, loans, movie_credits, movie_night_sessions, movie_night_votes, movies, notification_preferences, price_checks, price_history_daily, purchase_candidates, release_calendar, retailers, shelf_qr_codes, smart_collections, wanted_list, watch_log`. `src/models.py` (81 lines) defines only `movies`, `movie_credits`, `collection_items`. ~22 tables are speculative schema for roadmap stages 4–11 that Part D may recommend dropping. |
| B1.4 | **M** | **`models.py` is a flat module.** All four use a `models/` package with `base.py` + one module per aggregate + `__all__` re-export, which `migrations/env.py` imports for side effects. |
| B1.5 | **M** | **Two migration systems.** Alembic lives at `apps/api/migrations` (`alembic.ini:2` → `%(here)s/migrations`), while `migrations/001_profiles.sql` at the repo root is raw SQL. All four reference repos keep a single Alembic tree at the repo root. Consequence: `profiles` is outside the chain, so no single command builds the schema from scratch and `alembic downgrade base` does not fully reverse. |
| B1.6 | **M** | **No `*_utc` column suffix, no naive-UTC helper.** The house `_utcnow()` = `datetime.now(UTC).replace(tzinfo=None)` idiom is absent. |
| B1.7 | L | Migration chain is clean — 17 revisions, strictly linear, every `down_revision` = N-1, downgrades implemented throughout. This is the healthiest part of the data layer. |

**Preserved asset:** `0015_derived_field_triggers.py` is substantive and correct in
shape — `movies_update_search_vector()`, `recalculate_movie_derived_fields(p_movie_id)`,
`collection_items_recalc_movie()` + trigger. Phase 1.8 was Opus-tagged and it shows.

---

## B2 — Auth & security

| # | Sev | Finding |
|---|---|---|
| B2.1 | **H** | **Every authenticated request makes a network call to Supabase.** `auth.py:36` calls `supabase.auth.get_user(token)` — a remote HTTP round-trip per request. All four reference repos decode a local JWT or do one indexed DB query. This couples every endpoint's latency and availability to Supabase's auth service. |
| B2.2 | **H** | **Admin endpoints make a second round-trip.** `require_admin` (`auth.py:47`) issues `supabase.table("profiles").select("role")…execute()`. So an admin request is two remote calls before any business logic runs. |
| B2.3 | **H** | **No inbound rate limiting anywhere.** The only `RateLimiter` in the repo is `tmdb/client.py:18`, an *outbound* throttle. All four reference repos run slowapi with per-endpoint limits; the-coupon backs it with durable Postgres counters. |
| B2.4 | **H** | **`config.py` has no fail-closed validation.** Every secret defaults to `""`, there is no `@model_validator`, and `app_env` is a bare `str` rather than a StrEnum. The app will boot in production with an empty `supabase_service_role_key`, empty `database_url` and empty `tmdb_api_key`, failing at first use rather than at startup. All four reference repos raise `ValueError("Refusing to start with weak/missing secrets: …")`. |
| B2.5 | **M** | **`except Exception` → 401.** `auth.py:41-42` maps every failure, including a Supabase outage, to "Invalid or expired token". |
| B2.6 | **M** | **Service-role key bypasses RLS.** All Supabase client access uses `supabase_service_role_key`, so row-level security is not a backstop for anything. |
| B2.7 | **M** | `get_current_user` returns an untyped `dict` with `# type: ignore[type-arg]`; the house pattern is an ORM `Profile` behind `CurrentUser` / `AdminUser` annotated aliases. |
| B2.8 | **H** | **A GitHub PAT is committed in `CLAUDE.md` and present in git history.** Dead (401) but not revoked. |

**Open decision.** The house trajectory has moved past PIN auth: garmin-coach
Decision #73 explicitly supersedes it with passwordless device tokens for a
"1–2 private users, no public sign-up" app — mcu_app's exact shape. Whichever way
this goes, `auth.py` and the web auth context are rewritten.

---

## B3 — API conventions

| # | Sev | Finding |
|---|---|---|
| B3.1 | **M** | **No `{data, meta, errors}` envelope**, though the architecture doc claims one at `:575` and `:2621`. garmin-coach implements the envelope; mcu_app inherited only the sentence. |
| B3.2 | **M** | **No camelCase JSON**, though `MCU_Architecture_v2.1_FINAL.md:1751-1753` specifies it. The API emits snake_case. Either implement it (garmin-coach: camelCase directly in the DTOs) or document snake_case honestly (the-coupon) — the current state is neither. |
| B3.3 | **L** | **`collection.py` has no router prefix** (`APIRouter(tags=["collection"])`), so its two routes carry full `/api/v1/...` paths inline while the other three routers use `prefix=`. |
| B3.4 | **L** | Errors are plain `HTTPException(detail="…")` strings — 8 in total, zero machine-readable codes. the-coupon's SCREAMING_SNAKE `detail` codes are the better pattern for a client that needs to branch. |
| B3.5 | L | **Pagination is present and correct** (`movies.py:56`, `page`/`per_page` with offset/limit). Better than garmin-coach, which has none. |

---

## B4 — Frontend

| # | Sev | Finding |
|---|---|---|
| B4.1 | **H** | **Not a PWA.** No `vite-plugin-pwa`, no `sw.ts`, no manifest link in `index.html`, no `beforeinstallprompt` handler. All four reference repos ship an `injectManifest` service worker with a documented iOS-deadlock workaround. |
| B4.2 | **H** | **The onboarding "Install as an app" step is dead code.** `OnboardingPage.tsx:125-161` reads `window.__pwaInstallPrompt` and calls `.prompt()`. Nothing in the codebase ever sets that property, and `beforeinstallprompt` cannot fire without a manifest and service worker. Shipped in Phase 2.8 ✅. |
| B4.3 | **M** | **No offline handling.** No `useOnlineStatus`, no `OfflineBanner`, no `/offline` route. Present in all four. |
| B4.4 | **M** | **Missing shell components**: `UpdateBanner`, `PageHeader`, `EmptyState`. Present: `ErrorBoundary`, `ProtectedRoute`, `layouts/AppLayout`, `layouts/Sidebar`. |
| B4.5 | **M** | **No `theme/tokens.ts`.** There is a `context/theme.tsx`, but not the single-source token module all four use to keep CSS variables, Tailwind utilities and JS consumers in agreement. |
| B4.6 | L | Sentry **is** wired (1 API file, 2 web files, package dependency) — Phase 0.6 is genuine. |

---

## B5 — Shared package

| # | Sev | Finding |
|---|---|---|
| B5.1 | **M** | **`packages/shared` is types-only and unused.** 4 tracked files (`index.ts`, `types.ts`), no zod schemas, **0 imports** from `apps/web`, **0** `.parse()` calls. |

This is the majority position, not an outlier: the-coupon's shared package has zero
tracked files, wc_2026's has one schema nobody imports, app-starter's reaches the web
app through a single type-only import. **Only garmin-coach made it work** — 1,972 lines,
28 envelope schemas, 43 `.parse()` calls, responses fetched as `unknown` then validated.
Either commit to garmin-coach's pattern or delete the package; the current state is cost
without benefit.

---

## B6 — Testing

**8 files, 123 tests** (async- and class-based tests included; an earlier figure in
this session undercounted).

| File | Tests | Exercises |
|---|---|---|
| `test_matching.py` | 44 | TMDB matching engine — pure logic |
| `test_import_collection.py` | 22 | Import pipeline — pure logic |
| `test_spreadsheet_parser.py` | 17 | Parser — pure logic |
| `test_derived_field_triggers.py` | 13 | **Live Postgres** — skips without `DATABASE_URL` |
| `test_movies_api.py` | 12 | HTTP routes via TestClient |
| `test_tmdb_client.py` | 11 | TMDB client |
| `test_correlation.py` | 3 | Middleware |
| `test_health.py` | 1 | Health route |

| # | Sev | Finding |
|---|---|---|
| B6.1 | **H** | **The 13 DB-backed trigger tests never run in CI.** They skip when `DATABASE_URL` is unset (`test_derived_field_triggers.py:20`), and CI provides no Postgres service and no `DATABASE_URL` — **zero** occurrences in `.github/workflows/ci.yml`. So the most complex component in the app, the Phase 1.8 derived-field triggers, is verified by nothing automated. This is exactly the-coupon's documented hazard: *"A green run in that mode says very little."* |
| B6.2 | **M** | **No `conftest.py`.** All four reference repos have one providing `db_engine` (session-scoped, skip-without-URL), `db_conn` (per-test rollback) and an autouse rate-limit reset. mcu_app's one DB-backed module opens raw `psycopg2` connections itself, bypassing SQLAlchemy. |
| B6.3 | **M** | **1 web test** (`utils.test.ts`) against 57–65 in the other three. No accessibility, contrast, or component tests. |
| B6.4 | **M** | No test exercises `collection.py` — the Phase 3.1 endpoints, the most recent work, are untested. |

---

## B7 — CI / deploy

| # | Sev | Finding |
|---|---|---|
| B7.1 | **H** | **No deploy configuration of any kind.** No `Dockerfile`, no `railway.toml`, no `vercel.json`, no `nixpacks.toml`. The app has never been deployed and currently cannot be. |
| B7.2 | **H** | **No migration check in CI.** All four run `alembic upgrade head` then `alembic downgrade base` against a Postgres service. mcu_app's 17-revision chain and 25 tables have never been proven to apply or reverse. |
| B7.3 | **M** | **2 CI jobs** (`api`, `web`) against 7 (app-starter, garmin-coach), 4 (the-coupon), 10 (wc_2026). Missing: Postgres-backed tests, migration check, dependency/security audit, secret scanning, prod-bundle check. |
| B7.4 | **M** | No `.claude/settings.json` checked in (only `settings.local.json`), and no `.claude/commands/` — so no batch workflow, and nothing is shared across tools or sessions. |

---

## B8 — Domain assets worth preserving

> **Correction (2026-09-07):** an earlier draft of this audit cited ~140 items, read
> from `import_review.csv`. That file is a review queue, not the collection. The
> collection is **1,866 items**. See STATUS gotchas 0 and 0b.

These survive regardless of the path taken. They are framework-independent —
no SQLAlchemy session, no FastAPI internals.

| Asset | Lines | Note |
|---|---|---|
| `src/matching/` — TMDB matching engine | 247 | Phase 1.6, Opus-tagged. 44 tests. The hardest-won code in the repo |
| `src/spreadsheet/` — parser | 275 | Phase 1.5. 17 tests |
| `src/tmdb/` — API client with outbound rate limiting | 317 | Phase 1.4. 11 tests |
| `0015_derived_field_triggers.py` — the SQL itself | ~180 | Phase 1.8, Opus-tagged. Portable as SQL |
| The real imported collection — **1,866 items** | — | Re-runnable: the parser and matching engine are the import pipeline |
| `MCU_Architecture_v2.1_FINAL.md` | 2,639 | The plan. Part D's input |

**839 lines of domain logic — 51% of all API source — carries across untouched.**

---

# The gate: retrofit or re-scaffold?

## Sizing

| | Lines |
|---|---|
| API source (routers 430 · schemas 82 · top-level 306) | **818** |
| API domain assets (tmdb · matching · spreadsheet) | **839** |
| Migrations | 2,106 (~22 of 25 tables speculative) |
| Tests | 1,907 |
| Web source (35 files) | **3,319** |

**This is a small codebase.** Excluding migrations and tests, there are ~1,657
lines of API source and 3,319 of web.

## The argument

**What mcu_app is missing is precisely what `app-starter` ships working:** PWA and
service worker, offline handling, deploy configuration for all three hosts,
fail-closed config validation, rate limiting, an auth implementation that doesn't
call out per request, a `conftest.py` test harness, a CI matrix with a migration
check, and the agent command workflow. Under a retrofit, **the list of things to add
is longer than the list of things that exist**.

Four things settle it:

1. **The domain assets port cleanly either way.** 839 lines with no framework coupling.
2. **Sync → async rewrites every router regardless.** If the routers are being rewritten, they may as well be written into a shell that already works.
3. **The auth change is forced either way.** Moving off per-request Supabase calls means rewriting `auth.py` and the web auth context whatever the path. Doing it inside a working implementation is strictly cheaper than building it fresh.
4. **The migration chain is a liability under retrofit and an asset under re-scaffold.** Retrofit keeps 2,106 lines and 25 tables, ~22 of them speculative and none CI-verified, plus a `profiles` table outside the chain. Re-scaffold starts from app-starter's proven `001_baseline` (profiles, refresh_tokens, push_subscriptions, notification_preferences, audit_log — CI-verified reversible) and adds only the tables the revised roadmap actually needs.

## Recommendation — **re-scaffold**

Not a rewrite from scratch. Specifically:

**Base:** clone `app-starter`, **then immediately apply the corrections Part A identified**, because the template is behind its own source apps:
- the-coupon's **durable account lockout** (app-starter's is defined but never enforced, and `rate_limit.py` justifies its weakness by pointing at it)
- garmin-coach's **envelope + shared-zod-validation** pattern, if Tier 2 is adopted
- garmin-coach's **passwordless device-token auth**, if that's the chosen model
- the-coupon's **`ci-local.sh` one-command gate** and its `UtcDatetime` wire mechanism
- strip app-starter's leaked identity (`@coach/web`, `coach_test`, `daily-loop` query keys) and its dangling references (`docs/runbooks/`, the `e2e/` directory that doesn't exist)

**Port:** the four B8 assets, the derived-field SQL rewritten against the new baseline,
the four routers converted to async, and the web feature pages onto app-starter's shell.

**Discard:** ~818 lines of sync API source, ~22 speculative tables, and a frontend
shell that a retrofit would have replaced anyway.

**What this is not:** throwing away the work. Everything genuinely hard — the matching
engine, the parser, the TMDB client, the trigger SQL, the imported data, and the
2,639-line plan — survives.

## Before Part C/D can proceed

1. **The gate decision** — this recommendation accepted, or retrofit chosen.
2. **The auth model** — still open from the plan's question 2. Evidence now favours garmin-coach's passwordless device tokens over app-starter's PIN.
3. **The Tier 2 question** — adopt garmin-coach's envelope + camelCase + shared-zod validation, or follow the-coupon and document honest snake_case with no envelope? This decides a lot of Part E's shape.
