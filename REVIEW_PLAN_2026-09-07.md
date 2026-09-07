# MCU App — Alignment Review Plan
**Date:** 2026-09-07 · **Status:** proposed, awaiting go-ahead
**Author:** Claude (Opus 5) with Craig Robinson

## Why this exists

mcu_app was last touched 2026-05-05 (Phase 3.1, CI green). Since then three
further apps were built — `garmin-coach`, `wc_2026_predictor`, `the-coupon` —
and their common baseline was distilled into a clone-and-own template,
`app-starter`. mcu_app therefore runs the **oldest** version of the house
standard, in both code and working method.

This document plans a review of (a) what mcu_app has already built and
(b) its remaining ~80-phase roadmap, against that matured standard.

**It is a plan, not the review.** No findings or verdicts are recorded here.

## Decisions taken

| # | Question | Answer | Date |
|---|---|---|---|
| 1 | Is getting this deployed a goal? | **Yes** | 2026-09-07 |
| 2 | Auth model | **PIN** — name + PIN + JWT. Take **the-coupon's** implementation, not app-starter's (see below) | 2026-09-07 |
| 3 | Rework appetite | **Properly** — full rebase on the table | 2026-09-07 |
| 4 | Roadmap critique scope | **All phases**, 3.2 → 11.3 | 2026-09-07 |
| 5 | **Fork gate** | **Re-scaffold — in this repo, on a branch, bottom-up.** Not a fresh clone, not a big-bang cutover | 2026-09-07 |
| 6 | **API conventions (Tier 2)** | **camelCase JSON + shared-zod response validation. NO `{data, meta, errors}` envelope** | 2026-09-07 |

### Notes on these decisions

**#2 — PIN, but from the right source.** app-starter defines `MAX_FAILED_ATTEMPTS`
and `LOCKOUT_DURATION` and never enforces them, while its `rate_limit.py` justifies
in-process counters by citing that non-existent durable guard. the-coupon fixed it:
enforcement at `routers/auth.py:273-304`, durable Postgres counters
(`018_durable_rate_limit_counters.py`), and a separate `get_limiter_db` session so a
failed attempt is charged even though the handler's transaction rolls back. Also take
its deliberately-short weak-PIN blocklist and the `pin_hash IS NULL` = *no credential*
semantics.

**#5 — re-scaffold, bottom-up, in place.** The deciding factor is deployment, not code
quality: the deploy spine interlocks (Dockerfile → `alembic upgrade head` on boot →
healthcheck exposing the commit SHA → fail-closed config → CI proving the migration
chain reverses) and cannot be retrofitted a piece at a time. Order: config/database/
models → deploy spine + CI → auth → routers (async, domain assets dropped in) → web
shell → feature pages. Every step independently green; no dead window.

*Reversal condition:* if the live Supabase data were irreplaceable this would be wrong.
It isn't — the spreadsheet parser and matching engine **are** the import pipeline, so
the collection is re-runnable.

**#6 — the three usually-bundled conventions have different price tags.**
*camelCase* is free (name the Pydantic DTO fields camelCase, as garmin-coach does — no
alias generator anywhere in any repo) and stops the frontend hand-mapping.
*Shared-zod validation* is the half that earns its keep: fetch as `unknown`, `.parse()`
through `packages/shared`, catching wire drift where deploy skew actually bites — the
web app deploys ahead of the API on every push. It needs real commitment: schemas ship
with the endpoint, or the package rots into `types.ts` again, which is exactly what
mcu_app's has already done.
*The envelope* is skipped: 3 of 4 repos don't have one, and mcu_app's genuine
partial-success cases (bulk import, matching, a future price feed) are batch operations
that deserve their own shapes rather than taxing every read route.

*Revisit if:* Part D keeps the LLM assistant (Phase 9.x) with tool definitions calling
the API. A second API consumer is when `meta`/`errors` starts paying for itself.

### Still open
- Nothing blocking. Parts C, D and E can proceed.

## Grounding facts from recon (2026-09-07)

All five repos share an identical shape — `apps/api` + `apps/web` +
`packages/shared`, FastAPI + async SQLAlchemy + Postgres/Supabase + Alembic /
React 18 + Vite + Tailwind + shadcn. **This is a retrofit problem, not a
rewrite problem.** Divergence is concentrated here:

| | mcu_app | garmin-coach / wc_2026 / the-coupon |
|---|---|---|
| `AGENTS.md` / `STATUS.md` / `DECISIONS.md` | none | all present, maintained |
| Deploy config | **none** | Railway + Vercel (or nixpacks) |
| `.claude/commands` | none | 4–11 batch/ship/closeout commands |
| Checked-in `settings.json` | no (local only) | yes |
| Web tests | 1 file | 57–65 files |
| Backend layout | flat `models.py` | `models/` pkg, `deps.py`, `rate_limit.py`, `scheduler.py`, `services/` |
| Planning docs | one 2,639-line monolith + `session-log.md.txt` | STATUS/DECISIONS + batch commands |

## Immediate hygiene item (independent of this review)

A GitHub PAT is committed in `CLAUDE.md` and is present in git history. It now
returns 401, so it is already dead — but it must be **revoked at GitHub** and
removed from the file, and the CI-polling pattern replaced with `gh` CLI or an
env var. This is a do-now item, not a review finding.

---

# The review

## Part A — Establish the benchmark *(read-only · parallel ×4)*

Codify what "good" now means, from the evidence rather than from memory.

**Sources**
- `app-starter` — `AGENTS.md`, `SKELETON.md`, `ARCHITECTURE.md`, `DECISIONS.md`, full `src` tree. This is Craig's own distillation and carries the most authority.
- `garmin-coach` — deepest process artefacts: `DECISIONS.md` (1,303 lines), `STATUS.md` (3,175), `COACHING_INTEGRITY_AUDIT.md`, `QA_REVIEW_2026-07-11.md`.
- `the-coupon` — the one that actually launched: `launch-log.md`, `launch-*` commands.
- `wc_2026_predictor` — `ship-prod` / `ship-staging` command patterns.

**Method** — extract the standard across: repo conventions, backend structure,
data layer, auth, API envelope, shared-schema usage, frontend shell, testing
bar, CI topology, deploy topology, secret handling, agent workflow.

**Deliverable** — `docs/house-standard.md`.

**Special attention:** where the three mature projects *disagree with each
other*, that is an unsettled question, not a standard. Those get recorded
separately as open choices rather than as requirements.

## Part B — Audit the built code *(read-only · sequential)*

Audit Stages 0 → 3.1 against Part A, dimension by dimension.

| | Area | What gets examined |
|---|---|---|
| B1 | Data layer | sync vs async SQLAlchemy; `models.py` monolith vs `models/` package; health of the 17 Alembic migrations and whether the baseline is safe to keep; the Phase 1.8 derived-field triggers |
| B2 | Auth & security | current Supabase Auth + admin/viewer vs the target standard; role enforcement at the router boundary; config fail-closed validation; absent rate limiting; secret handling |
| B3 | API conventions | `/api/v1/` prefix; `{data, meta, errors}` envelope; error shape; pagination; snake_case DB / camelCase JSON; UTC `*_utc` columns |
| B4 | Frontend | shell coverage vs app-starter's `Layout`/`TopBar`/`TabBar`/`ProtectedRoute`/`ErrorBoundary`/`OfflineBanner`; PWA + service worker; theme tokens; query client; offline behaviour |
| B5 | Shared package | whether web parses API responses through shared zod schemas, or trusts them |
| B6 | Testing | 80 API tests / 1 web test against the house bar; what the API tests actually cover |
| B7 | CI/CD & deploy | 1 workflow vs 2–3; the total absence of deploy config |
| B8 | Domain assets | the genuinely valuable, hard-won parts to preserve regardless of path: TMDB client, matching engine (Phase 1.6), spreadsheet parser, the real imported collection data, derived triggers |

**Deliverables** — a severity-tagged gap register, and a recommendation on the
fork below.

### Decision gate — retrofit or re-scaffold?

`app-starter` was distilled from two *shipped* apps. mcu_app predates it and
never shipped. With rework appetite set to "properly", both paths are live:

- **Retrofit** — evolve mcu_app in place toward the standard.
- **Re-scaffold** — clone `app-starter`, port the B8 domain assets and the
  imported data across, rebuild the feature surface on the newer shell.

Part B ends by recommending one, with evidence and a cost estimate. **Craig
decides before Parts C–E are written**, because the answer changes what they
contain.

## Part C — Process & workflow retrofit *(sequential)*

Bring mcu_app onto the current working method.

- `AGENTS.md` as the canonical cross-tool instruction file, with `CLAUDE.md` as a symlink (per the app-starter convention — so Codex sees it too).
- `STATUS.md` — the "Now" block + log. `DECISIONS.md` — retrospectively seeded with the decisions already made across Stages 0–3, recovered from the session log and git history.
- Convert `MCU_Architecture_v2.1_FINAL.md` (2,639 lines) into `ARCHITECTURE.md` + a roadmap doc; retire `session-log.md.txt` into the STATUS/DECISIONS pattern.
- `.claude/commands/*` — adopt the batch model (`batch-start`, `batch-verify`, `next-batch-prompt`, `phase-closeout`, `ship-staging`, `ship-prod`).
- Checked-in `.claude/settings.json`.
- Replace the 7-step close-out currently embedded in `CLAUDE.md`, and decide whether mcu_app joins garmin-coach and the-coupon in auto-closing-out after a green gate.

**Deliverable** — the docs and commands themselves, not a description of them.

## Part D — Roadmap critique, all remaining phases *(parallel ×7 by cluster)*

Every phase from 3.2 to 11.3 gets a verdict: **keep / re-scope / defer / drop**,
a re-estimate against current models (the `🟢 Sonnet 4.6` / `🔴 Opus` tags date
from April and are stale), and a sequencing position.

**Cross-cutting themes to resolve rather than decide phase-by-phase:**

- **The scraping cluster** (3.7 Blu-ray.com, 5.3–5.9 price scraping, 5.9 deals) — ~8 phases of fragile, ToS-exposed work concentrated in one dependency. Is scraping still the right mechanism?
- **The LLM cluster** (8.1 Smart Search, 9.1–9.7 assistant + voice, 10.6 LLM fallback parser) — mostly tagged 🔴 Opus on April assumptions. Much of this is likely now far cheaper to build; some of it may be obsolete as designed.
- **The email cluster** (10.1–10.8) — OAuth for Gmail *and* Outlook, credential encryption, scheduled scanning. Heavy. Does the value justify it?
- **The eBay cluster** (4.1–4.4) — external API dependency and listing-creation risk.
- **Time-to-deployable** — now that shipping is a goal, the current plan puts 11 phases in Stage 3 before anything is live. What is the shortest credible path to a deployed, genuinely useful app?

**Deliverable** — a revised roadmap replacing the v2.1 monolith, in the current
house format.

## Part E — Synthesis & migration plan *(sequential)*

A sequenced, batched work plan in the house format, covering: the chosen fork
path, deploy bring-up (Supabase + Railway + Vercel), the auth migration if
confirmed, the testing catch-up, and an ordering that reaches production
earliest without stranding completed work.

---

## Execution model — parallel vs sequential

Governing principle: **parallelise evidence-gathering, centralise judgement.**
The deliverable is a *coherent* standard and a *consistent* set of verdicts.
Independent agents produce independent opinions; synthesis has to be done once,
by one mind, or the review contradicts itself.

| Part | Mode | Rationale |
|---|---|---|
| **A** | **Parallel ×4** — one agent per source repo | Genuinely independent reads, ~10,000 lines of markdown. Fixed extraction schema so outputs are comparable. Cross-repo synthesis is done centrally. |
| **B** | **Sequential** | This is where judgement about *Craig's own code* happens, and where he rebuilds his mental model after four months away. Kept visible and steerable. The fork decision needs the whole picture. |
| **C** | **Sequential** | Authorship. `AGENTS.md` / `STATUS.md` / `DECISIONS.md` must read as one hand. |
| **D** | **Parallel ×7 — by cluster, never by phase number** | Arbitrary splits would cut the scraping and LLM clusters in half and yield contradictory verdicts. Clusters: scraping · LLM · email · eBay · core collection · discovery/calendar · UX polish. Arbitrated centrally. |
| **E** | **Sequential** | Synthesis. |

### Constraints on parallel work
- Agents are spawned **read-only** (no write tools), enforcing the guardrail below by construction rather than by instruction.
- Every agent works to an **identical output schema**, with file:line citations and verbatim quotes rather than prose summaries — a summarised convention is a lost convention.
- Load-bearing findings are **spot-checked at source** before entering the gap register or the standard. An unverified finding is worse than no finding in an audit.
- **Nothing downstream of the fork gate is parallelised in advance.** If the decision is re-scaffold, retrofit-flavoured analysis is wasted — parallelism would only buy wasted work faster.

## Sequencing

| Session | Contents | Gate |
|---|---|---|
| 1 | Part A (parallel ×4) → synthesise → Part B (sequential) | **ends at the fork decision — Craig's call** |
| 2 | Part C (sequential) + Part D (parallel ×7) → arbitrate → Part E | |

Part D remains the long pole — 80 phases at genuine depth — but parallelising
by cluster compresses the original three sessions to roughly two.

## Guardrails

- Parts A, B and D are **read-only**. No code changes.
- Part C writes docs and commands only.
- No execution of the migration until Part E is agreed.
- The dead PAT is revoked and removed immediately, outside this sequence.
