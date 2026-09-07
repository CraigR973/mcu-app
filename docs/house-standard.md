# House Standard — extracted from four repos, 2026-09-07

**Part A deliverable of `REVIEW_PLAN_2026-09-07.md`.** Sources: `app-starter`,
`garmin-coach`, `the-coupon`, `wc_2026_predictor`. Read-only extraction against
a fixed 14-point schema, with load-bearing claims re-verified at source.

## The method finding — why this doc exists

**The standard could not be transcribed from the docs.** Every repo states its
conventions in `AGENTS.md`/`CLAUDE.md`, and in three of the four, some of those
statements have no implementation behind them. A standard copied from the prose
would have contained rules the reference implementations do not follow.

So each convention below is graded by **what the code does**, not what the docs
claim, and divergence between the two is recorded rather than resolved silently.

## The correction that matters most

`app-starter` is **not** the newest thinking, despite being the clone-and-own
template. It was distilled from earlier apps and has since been overtaken by
`garmin-coach` (257 batches, the deepest process artefacts of the four).
`SKELETON.md:47-50` says as much itself: "If you need a pattern the skeleton
doesn't show … the original app is the living reference."

Concretely, `app-starter` carries a **broken** version of a mechanism
`the-coupon` later fixed — see Tier 3, account lockout.

**Implication for this review: where app-starter and garmin-coach disagree,
garmin-coach is the standard.**

---

# Tier 1 — Settled: stated *and* implemented everywhere

These are load-bearing and non-negotiable. mcu_app should match them.

| Convention | Evidence |
|---|---|
| **Monorepo shape** `apps/api` + `apps/web` + `packages/shared` | All 5 repos, identical |
| **Async SQLAlchemy 2.0 + asyncpg** | `create_async_engine` + `async_sessionmaker(expire_on_commit=False)` in all 4 |
| **Pool config** `pool_size=10, max_overflow=10, pool_pre_ping=True, pool_recycle=1800` | Identical in all 4 `database.py` |
| **`prepared_statement_cache_size: 0`** | All 4 — required behind Supabase's pooler |
| **`models/` as a package, not `models.py`** | All 4: `base.py` + one module per aggregate + `__all__` re-export |
| **Base mixins** `UUIDPrimaryKeyMixin` (uuid4), `TimestampMixin`, `UpdatedAtMixin` | All 4 `models/base.py` |
| **Naive UTC everywhere** — `DateTime(timezone=False)` + `_utcnow()` = `datetime.now(UTC).replace(tzinfo=None)` | All 4, byte-identical helper |
| **Alembic at repo root**, `script_location = %(here)s/../../migrations` | All 4 |
| **Linear zero-padded migration chain**, every `down_revision` = N-1 | All 4, no branches |
| **CI proves reversibility** — `alembic upgrade head` then `alembic downgrade base` | All 4 |
| **Deploys migrate themselves** — `alembic upgrade head && uvicorn`; container exits on failure so the platform keeps the last healthy release | All 4 |
| **`/api/v1/` prefix** on every router | All 4, universal |
| **Auth via FastAPI dependency aliases**, never middleware — `CurrentUser` / `AdminUser` | All 4 |
| **Tokens stored SHA-256 hashed**, never raw | All 4 |
| **Fail-closed secret validation** — `raise ValueError("Refusing to start with weak/missing secrets: ...")`, dev exempt | All 4 `config.py` |
| **`Environment` as a StrEnum** so unknown values are rejected | All 4 |
| **Docs/OpenAPI disabled in production** | All 4 |
| **Sentry `send_default_pii=False`** + a `before_send` scrubber | All 4 |
| **`.claude/commands/*` are ≤11-line wrappers**; real procedures live in `docs/agent-commands/` | All 4 — "never duplicate the steps into a wrapper" |
| **`CLAUDE.md` symlinked to `AGENTS.md`** (or a 5-line pointer) | app-starter, garmin-coach symlink; the-coupon points |
| **Repo is the single source of truth; agent memory is a cache** | app-starter, garmin-coach, verbatim |
| **Never `cd`** — absolute paths and `git -C` | All 4, with the ENOSPC rationale |
| **Tests ship with every change** | All 4, stated verbatim |
| **Branches `feat/`/`fix/`/`chore/`; Conventional Commits** | All 4 |
| **Stop hook that suggests, never acts** | All 4, `.claude/settings.json` + `.codex/hooks.json` |
| **PWA**: `injectManifest` + hand-written `sw.ts`, `skipWaiting()`+`clientsClaim()`, `NetworkFirst` with `denylist: [/^\/api/]`, GET+200 only | All 4, same iOS-deadlock scar |
| **Theme**: `light\|dark\|system`, dark default, tokens in `theme/tokens.ts` as single source | All 4 |
| **TanStack Query v5**, `retry: 1`, `refetchOnWindowFocus: true`, `installResumeRefetch()` for iOS warm resume | All 4 |
| **Offline**: `useOnlineStatus` → `OfflineBanner` (`role="status" aria-live="polite"`) + `/offline` route | All 4 |
| **`conftest.py` with `db_engine` that skips when `DATABASE_URL` is unset**, autouse rate-limit reset, per-test rollback | All 4 |

---

# Tier 2 — Real, with one reference implementation

**These are not phantom conventions. `garmin-coach` implements them fully; the
others inherited the sentence without the code.** The direction of travel is
toward them, so mcu_app should adopt them — from garmin-coach, not app-starter.

### 2.1 The `{data, meta, errors}` envelope

| Repo | Stated | Implemented |
|---|---|---|
| **garmin-coach** | yes | **YES** — `DailyLoopEnvelope{data, meta, errors}` at `routers/daily_loop_schemas.py:517-520`; **28** `*EnvelopeSchema` in `packages/shared/src/schemas.ts` |
| app-starter | yes (`AGENTS.md:39`, `ARCHITECTURE.md:40`) | no — 0 occurrences |
| wc_2026 | yes (3 places, with worked examples) | no — 0 occurrences |
| the-coupon | **no** — honestly documents snake_case, no envelope | n/a (consistent) |

Note the exceptions garmin-coach keeps deliberately: `/api/v1/health` returns
bare `{status, sha}`, and transport-level errors stay FastAPI's `{"detail": ...}`.
The envelope is for domain responses, not for everything.

### 2.2 camelCase JSON

Same table. garmin-coach writes camelCase **field names directly in the Pydantic
DTOs** (`generatedAtUtc`, `subjectDate`, `loopState`) — there is no
`alias_generator` anywhere in any of the four repos. the-coupon is explicitly
snake_case and says so. app-starter and wc_2026 claim camelCase and emit
snake_case, so their frontends hand-map every field.

> `wc_2026`'s own extraction names the hazard: an agent following `CLAUDE.md`
> literally "would write endpoints incompatible with the entire existing frontend."

### 2.3 Shared zod schemas as the validation boundary

| Repo | Reality |
|---|---|
| **garmin-coach** | **1,972-line `schemas.ts`, 28 envelope schemas, 43 `.parse()` calls in web.** Responses fetched as `unknown`, then Zod-validated |
| wc_2026 | 9-line `schemas.ts`, one schema nobody imports; package reaches the app through a single scoring import |
| app-starter | type-only import (`import type { Role }`); `profileSchema` is camelCase and could not parse the snake_case API it claims to mirror |
| the-coupon | **package has zero tracked files**; `zod` is an unused dependency |

### 2.4 `*_utc` column suffix

garmin-coach 32 in one model file · the-coupon `kickoff_utc`, `locks_at_utc`,
`picks_open_at_utc` · wc_2026 partial (domain columns yes, mixins no) ·
app-starter **zero**. Real in 3 of 4; absent in the template.

---

# Tier 3 — Where app-starter is actively behind

**Account lockout.** `app-starter/auth.py:32-33` defines `MAX_FAILED_ATTEMPTS = 5`
and `LOCKOUT_DURATION`. Neither is ever referenced; `failed_login_count` and
`locked_until` are only ever *reset*, at `routers/auth.py:442-443`. And
`rate_limit.py:16-18` justifies its in-process counters by pointing at
"the DB lockout (max_attempts) is the durable brute-force guard" — which does
not exist.

`the-coupon` **fixed this**: enforcement at `routers/auth.py:273-304`, durable
counters in Postgres via `018_durable_rate_limit_counters.py`, and a separate
`get_limiter_db` session because "A counter that shares the handler's transaction
is not a counter: login rolls back on a bad PIN and commits on a good one, and an
attempt has to be charged either way."

Anything cloned from app-starter inherits the broken version. Take the-coupon's.

**Two headers in `app-starter/vercel.json` will silently break features in production
while working fine locally.** `vercel.json:27` sets
`Permissions-Policy: camera=(), microphone=(), geolocation=()` on every non-API route —
which disables `getUserMedia`, so any camera feature (barcode scanning, photo capture)
fails **only once deployed**. And `vercel.json:22`'s CSP allows
`connect-src 'self' https://*.sentry.io` only, which blocks the standard signed-URL
browser→Supabase-Storage upload. Note the API's own `SecurityHeadersMiddleware` sets a
similar Permissions-Policy, but that decorates JSON responses and is irrelevant to
browser capability — the Vercel header is the one that bites. Fix both *before* shipping
any camera or upload feature, not after debugging a "works locally" report.

Also stale in app-starter: `docs/runbooks/` holds only `.gitkeep` while
`closeout.md:12` makes reading `docs/runbooks/deploys-ongoing.md` step 1 — so
`/closeout` fails its own first instruction. Playwright is fully configured
against an `e2e/` directory that does not exist. And the distillation leaked:
`@coach/web` package name, `coach_test` CI databases, `daily-loop` query keys,
"Batch 62.1" comments.

---

# Tier 4 — Genuinely open questions

The four repos disagree. These are decisions for mcu_app, not inherited rules.

### 4.1 Auth model — **the trajectory has moved**

| Repo | Model |
|---|---|
| app-starter | name + PIN + JWT + single-use activation links, no public sign-up |
| the-coupon | display name + PIN, **public self-serve signup** (ADR 0008 superseding ADR 0001), killable via `PUBLIC_SIGNUP_ENABLED` without a deploy |
| wc_2026 | name + PIN + JWT; docs say invite-only, **code has a public `/signup`** — two contradictory specs in two files |
| **garmin-coach** | **passwordless opaque device tokens + single-use activation links. Zero PIN references in `auth.py`.** |

garmin-coach's Decision #73 explicitly supersedes #20, "replacing the inherited
display-name + 4-digit-PIN + JWT login". Decision #74 made the cutover phased,
parallel-run and reversible. It also names the better end-state it did *not*
adopt: Cloudflare Access with an HttpOnly cookie, deferred rather than chosen —
device tokens still live in `localStorage`, mitigated by a hash-pinned CSP.

**Relevance to mcu_app:** garmin-coach describes itself as "1–2 private users, no
public sign-up". That is exactly mcu_app's shape (Craig + Mark). The newest
thinking for a private two-person app is passwordless device tokens, **not** the
PIN model in app-starter.

### 4.2 Close-out automation — trajectory toward automatic-with-a-gate

| Repo | Position |
|---|---|
| app-starter | "This is never automatic." |
| wc_2026 | Explicit; defers to the global rule |
| the-coupon | **Build batches automatic** after a green gate (2026-08-27); **launch phases explicit** |
| garmin-coach | **Automatic** (2026-09-03) with a named exclusion list: Mark-facing copy not signed off, destructive/irreversible ops, credential and hosting changes, discretionary Anthropic spend |

Both recent overrides went automatic. Both pair it with a hard gate and a
written exclusion list — the automation is bought by the gate, not instead of it.

the-coupon's rule is the sharpest statement of why:
> "Close-out now deploys, so this gate is the last thing standing between a
> mistake and members; an agent that edits the gate to satisfy the gate has
> removed the only safeguard left."

### 4.3 Deploy topology

| Repo | Model |
|---|---|
| **wc_2026** | **Most mature.** `staging` branch → `main`. Staging frontend gated behind all 9 CI jobs. Promotion gated on staging-green + a SHA check against `/api/v1/health` + a post-deploy CORS synthetic |
| the-coupon | Split: web auto-deploys on close-out push; **API requires explicit `/ship-prod`**. Railway IaC with pinned invariants |
| garmin-coach | `main`-only, no backend staging; a post-merge `deploy-freshness.yml` polls both hosts until they serve the merged SHA |
| app-starter | `main`-only; "Vercel previews are staging" |

Three of four have no backend staging and say so. Only wc_2026 built the
two-environment promotion. Nixpacks (the-coupon) vs Dockerfile (the other three)
is a real split — the-coupon chose nixpacks so local container tooling isn't required.

### 4.4 Where decisions get recorded

| Repo | Mechanism |
|---|---|
| garmin-coach | `DECISIONS.md`, 1,303 lines, 328 numbered entries, append-only, **scoped supersessions** ("only at delivery", "only the Red-cluster half") |
| app-starter | `DECISIONS.md`, same contract, near-empty |
| the-coupon | **No `DECISIONS.md`** — 8 numbered ADRs with `Status:` verdicts, inline `(owner decision, date)` annotations, session-log key facts, and long-form code docstrings |
| wc_2026 | **No `DECISIONS.md`** — a 41-row table in §17 of the architecture doc; `docs/adr/` is an empty promise |

Both `docs/adr/` directories that exist are empty. The two working mechanisms are
garmin-coach's numbered append-only log and the-coupon's ADRs-plus-annotations.

---

# Tier 5 — Practices worth stealing outright

Not conventions so much as hard-won mechanisms. Each exists because something broke.

1. **The gate is one command.** the-coupon's `scripts/ci-local.sh` — 11 checks, its own venv built from pinned requirements, a fresh `pgserver`, `alembic upgrade head` before pytest. The interpreter is deliberately **not** configurable: *"A local PASS on a commit CI fails is worse than no local gate at all."*

2. **Never weaken the gate to reach green.** the-coupon `AGENTS.md:76-83` — deleting a test, loosening an assertion, changing an expected value, adding `type: ignore`, marking `xfail`, lowering a threshold are all forbidden *as a route to green*, "including when they would technically be defensible. If green genuinely requires changing a test's expectations, that is a decision to report, not to take."

3. **Know what a green run actually proves.** the-coupon: without `DATABASE_URL`, pytest is "509 passed, 151 skipped, and the skipped set is the HTTP pick flow, settlement, the scheduler jobs, slate persistence, seeds and every migration test — that is, the core of the game. A green run in that mode says very little."

4. **Correct time at the wire, once.** the-coupon's `UtcDatetime` annotation plus `tests/test_wire_datetimes.py`, which walks every route and fails if a datetime is unannotated. Born from a real defect: a naive UTC instant serialised without an offset, parsed as local by JS, closed the pick screen an hour early. The frontend test runner is pinned to `TZ: 'America/New_York'` so a UTC-machine assumption can't hide.

5. **Treat the spec as a proposal, not an instruction.** garmin-coach `batch-start.md:73-75` — *"A green test suite cannot tell you the spec was right, only that you built what it said."* Rows decay between authoring and building; Batch 216's row told the build to copy the very path that batch existed to fix.

6. **Verify production, don't assume it.** All four check that `/api/v1/health` reports the *expected commit SHA*, not merely HTTP 200. wc_2026 additionally asserts the CORS header echoes the prod origin.

7. **Report every failure, including ones fixed first try.** the-coupon: with no manual review before the push, the close-out report is the only record of what went wrong on the way to shipping.

8. **Self-audit against named adversarial failure modes.** garmin-coach's `COACHING_INTEGRITY_AUDIT.md` drives the *real* production functions with crafted inputs — "no logic was re-implemented" — grades itself (B+, down from A−), and separates diagnosis from remediation: *"This audit diagnoses only. No code was changed."*

9. **The large-doc organising scheme** (from wc_2026, directly applicable to mcu_app's 2,639-line monolith): numbered reference sections that never change during a batch, one plan section, one decision ledger. Every phase is a single greppable line — `**Phase 0.4: Title** 🟢 Sonnet 4.6 ✅ 2026-05-09` — where **status is the presence of the ✅ suffix**, not a separate field. Everything volatile (which phases group into a session, model, what's next) lives in small external tables. *The doc changes one character sequence per phase and nothing else.* That is what let a 1,840-line file survive 133 sessions without a restructure.

---

# mcu_app's position against this standard

Recorded here as input to Part B, not as the Part B audit.

| Dimension | Standard | mcu_app |
|---|---|---|
| Data layer | async SQLAlchemy + asyncpg (4/4) | **sync** `create_engine` / `sessionmaker` |
| Models | `models/` package (4/4) | flat `models.py` |
| API envelope | garmin-coach implements | **claimed** in the architecture doc (`:575`, `:2621`), 0 occurrences in code |
| JSON casing | camelCase (garmin-coach) or honest snake_case (the-coupon) | **claimed** camelCase (`:1751-1753`), not implemented |
| `*_utc` columns | 3/4 | **0** |
| Test harness | `conftest.py` with DB-skip discipline (4/4) | **no `conftest.py`** |
| Tests | 121 files / 1,750 CI (garmin-coach) · 59 / 230 (the-coupon) | **8 files / 90 tests · 1 web test** |
| Deploy config | Dockerfile + railway.toml + vercel.json (or nixpacks) | **none** |
| `AGENTS.md` / `STATUS.md` / `DECISIONS.md` | 3/4 have all three | **none** |
| `.claude/commands` | 4–11 wrappers (4/4) | **none** |
| Secret handling | fail-closed validation; nothing credential-bearing tracked | **live PAT committed in `CLAUDE.md`, in git history** |

The corrected test figure supersedes an earlier count in this session that
mistakenly included `.venv` contents.

---

## Cross-repo hygiene items noticed in passing

Not part of the standard; flagged because they are live.

- **the-coupon** `.claude/settings.local.json` (untracked) grants `Bash(*)`, `Edit`, `Write` plus ~13 entries scoped to **a different repository** (`wc_2026_predictor`), including `rm -rf ~/Library/Caches/*` and `pkill -f postgres` — inside a project whose ship workflows are otherwise fastidious about never acting on an unrecorded target.
- **the-coupon** production has **no database backup** by owner decision; `picks` has no second copy and migrations apply automatically on boot, so rollback must never assume a recoverable database.
- **garmin-coach** `README.md` is still the World Cup project's README, including wrong setup commands.
- Both `docs/adr/` directories (garmin-coach, wc_2026) are empty while being advertised in the README.
