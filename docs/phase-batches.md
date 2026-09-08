# Batch ledger

The single batch source of record. Each batch is a small, shippable unit driven by
`docs/agent-commands/` (`batch-start` → `batch-verify` → `phase-closeout`).
Close-out is **automatic after a green gate** (`DECISIONS.md` #24, superseding #13).

**Tier:** 🟢 Mid · 🟡 Large · 🔴 XL · **Status:** planned · in-progress · shipped
Strike the row through and set status on close-out.

---

## Build to first deployment

| # | Batch | Tier | Status | Covers phases from `MCU_Architecture_v2.1_FINAL.md` §16 | Result |
|---|---|---|---|---|---|
| ~~1~~ | ~~New spine foundations~~ | ~~🟡~~ | **shipped** | ~~re-lands **0.1, 0.2, 0.3**; carries **0.6**~~ | PR #1 · `0910428`, `15ed148` |
| ~~2~~ | ~~Deploy spine + CI gate~~ | ~~🟡~~ | **shipped** | ~~re-lands **0.5**; **implements §15, which was never a phase**~~ | `d4190ac` · API live, `/health` serves the SHA |
| ~~3~~ | ~~Auth — PIN + JWT~~ | ~~🟡~~ | **shipped** | ~~**supersedes 0.4** (Supabase Auth) per `DECISIONS.md` #11~~ | `e89a9c6` · lockout proved on Postgres in CI |
| ~~4~~ | ~~Domain layer + re-import~~ | ~~🔴~~ | **shipped** | ~~re-lands **1.1, 1.3–1.8**; **fixes the §3.4 location columns 1.2/1.3 omitted**~~ | 1,857 items imported, 1,733 sectioned; 14 trigger tests running in CI |
| 5 | Read surface | 🟡 | planned | re-lands **2.1–2.7** | |
| 6 | Location + facets | 🟢 | planned | **3.6** (re-scoped), **8.1** (re-scoped); delivers §6.2's unkept promise | |
| 7 | Write surface | 🟡 | planned | re-lands **3.1**; adds **3.2, 3.5, 3.11** | |
| 8 | PWA + offline | 🟢 | planned | **13.8, 6.5, 13.9** pulled forward | |
| 9 | Onboarding repair | 🟢 | planned | repairs **2.8** | |

> **All 23 shipped phases are accounted for above.** Their ✅ marks in §16 now mean
> "specified and shipped on the old spine" — not "present in the running app". Re-tick
> them as each batch re-lands them; do not assume a ✅ phase needs no work.

### Batch 1 — New spine foundations
**Goal:** the new spine exists and is green; nothing user-visible changes.
Clone app-starter's structure onto a branch. Apply **all six corrections** in
`docs/part-e-migration.md` on the way in. `config.py` with fail-closed validation;
async `database.py` + asyncpg with the house pool settings; `models/` package;
`conftest.py` harness.
**Acceptance:** `ruff`, `mypy`, `pytest` and `pnpm -r test` green. `config.py` **refuses to boot** with an empty secret in a non-development environment — asserted by a test. No `create_engine`, no flat `models.py`, no leaked `coach`/`daily-loop` identifiers remain.

### Batch 2 — Deploy spine + CI gate
**Goal:** the app is deployed and provably serving the commit we think it is.
Dockerfile (migrate-on-boot, exit on failure), current Railway IaC
(`.railway/railway.ts`), `vercel.json` **with both header fixes**. New Neon project
(database only; no Neon Auth). New Alembic baseline `001`; schemas land with their owning
batches rather than reviving speculative tables. CI: lint · typecheck · pytest against a Postgres service · **migration check
(`upgrade head` then `downgrade base`)** · web build/test · dependency audit.
**Acceptance:** `/api/v1/health` returns the **expected commit SHA**, not merely 200. `/api/v1/health/ready` returns 503 when the DB is unreachable. CI's migration job proves the baseline reverses. No routes exist beyond health — nothing is publicly reachable yet.

### Batch 3 — Auth — PIN + JWT
**Goal:** Craig and Mark can log in; nobody else can.
the-coupon's implementation: bcrypt PIN, HS256 access/refresh with separate secrets,
SHA-256-hashed refresh rows, **durable Postgres lockout counters with a separate limiter
session**, the short weak-PIN blocklist, `pin_hash IS NULL` = *no credential*. slowapi
limits per endpoint. Seed two profiles. Web `AuthContext` + `ProtectedRoute`.
**Acceptance:** 5 failed PINs lock the account for 15 minutes, and the lock **survives a process restart** — the defect app-starter ships. No public sign-up route exists. Docs/OpenAPI are off in production.

### ~~Batch 4 — Domain layer + re-import~~ 🔴 **shipped**
**Goal:** all 1,857 items are in the new database **with structured location**.
Port `tmdb/`, `matching/`, `spreadsheet/` unchanged. New models — `Movie`, `MovieCredit`,
`CollectionItem` **with `location`, `section`, `shelf`** per roadmap §3.4. Port `0015`'s
12 `op.execute` trigger blocks onto the new baseline, plus the `soft_delete()` trigger.
Re-run the importer.
**Acceptance:** row count = 1,857. `SELECT count(*) WHERE section IS NOT NULL` is non-trivial and `section` values fall in {Front, Back, Lounge, Garage, Digital}. `--dry-run` diffed against `matching_eval.csv` before the live run. The 13 derived-field trigger tests **run in CI** against the Postgres service — not skipped.

### Batch 5 — Read surface
**Goal:** Mark can browse the collection on his phone.
List (paginated), detail, copies, tsvector search. **camelCase DTOs and shared zod schemas
that the web app actually `.parse()`s** (`DECISIONS.md` #12) — schemas ship with the
endpoint. Web shell, grid, detail page, search.
**Acceptance:** the deployed app renders 1,857 items at 60fps and a search returns in <150ms. Every response the web app consumes is parsed through `packages/shared`; zero `as Promise<T>` casts on API responses.

### Batch 6 — Location + facets
**Goal:** the app answers "where is this disc?"
`section`/`shelf` filter params and UI. Complete the facet set `FilterBar` lacks — decade
range, watched status, rating. (Phase 8.1 re-scoped; the LLM version stays dropped.)
**Acceptance:** "show me everything on the Front 2nd shelf" works end to end — the §6.2 promise, unimplementable since April.

### Batch 7 — Write surface
Add / edit / soft-delete collection items, duplicate detection, condition tracking, with
`admin_actions` audit writes.
**Acceptance:** changes persist; deleted items appear in trash; the audit log records actor, action and target and survives deletion of the target row (`DECISIONS.md` #5).

### Batch 8 — PWA + offline
Port `sw.ts` (with the iOS deadlock fix), manifest, `useOnlineStatus`, `OfflineBanner`,
`/offline`. Optimistic UI via the-coupon's queued/unconfirmed reconciliation — **not**
naive optimistic-with-rollback. Offline write queue adapted to multiple entity types.
**Acceptance:** the app installs to a phone home screen, browses cached collection data with the network off, and an edit made offline lands once reconnected without overwriting a newer change.

### Batch 9 — Onboarding repair
Prune `StepEmailConnect` (Stage 10 dropped). `StepInstallPWA` and `StepNotifications` now
have real infrastructure behind them.
**Acceptance:** every step of the wizard does what it says. No step reads a property nothing sets.

---

## Post-launch — sequenced, not scheduled

Revised 2026-09-07 by `DECISIONS.md` #16: all of Part D's drops are reinstated except 9.6.

| # | Batch | Tier | Status | Phases |
|---|---|---|---|---|
| 10 | Architecture doc split + §17 reconciliation | 🟢 | planned | Part C deferred half |
| 11 | Notifications + push | 🟢 | planned | 6.1, 6.2, 5.11 |
| 12 | Box sets + smart collections | 🟢 | planned | 11.3, 11.4, 11.5 |
| 13 | Completion sets | 🟡 | planned | 11.1, **11.2** |
| 14 | Stats + export | 🟢 | planned | 13.1, 13.2, 13.3, 13.4 |
| 15 | Trash, audit UI, lending | 🟢 | planned | 13.5, 13.6, 12.5 |
| 16 | Watch providers + recommendations | 🟢 | planned | 7.1, 7.2 |
| 17 | Release calendar + iCal | 🟡 | planned | 7.3, 7.4 — secret-token `.ics` URL |
| 18 | Wanted list + retailers | 🟢 | planned | 5.1, 5.2 (full scope) |
| 19 | **Scraper framework** | 🔴 | planned | **5.3, 5.4** — see risk note below |
| 20 | Price scraping + drop alerts | 🟡 | planned | 5.5, 5.6, 5.8 |
| 21 | Price history charts | 🟢 | planned | **5.7** — needs 7 real days of data after B20 |
| 22 | Deals feed | 🟡 | planned | 5.9, 5.10 — RSS **and** scraped sources |
| 23 | Specs — scraper + display | 🟡 | planned | 3.7, 3.8, 3.9 |
| 24 | Barcode — scan + lookup | 🟡 | planned | 3.3, **3.4** — confirmation UI mandatory |
| 25 | Photo uploads | 🟢 | planned | 3.10 — needs the `vercel.json` CSP fix |
| 26 | Shelf QR | 🟢 | planned | 12.3, 12.4 |
| 27 | Gift links | 🟡 | planned | 12.1, 12.2 — high-entropy slug, rate limiter, `noindex` |
| 28 | **eBay integration** | 🔴 | planned | **4.1, 4.3** — active listings, not sold comps |
| 29 | Format upgrade + sale tracking | 🟢 | planned | 4.2, 4.4 |
| 30 | AI assistant — client + caps | 🟡 | planned | 9.1 + **9.7 together** |
| 31 | AI assistant — tools + chat | 🔴 | planned | 9.2, 9.3, 9.4 |
| 32 | Voice input | 🟢 | planned | **9.5** |
| 33 | **Email — accounts + OAuth** | 🔴 | planned | **10.1, 10.2, 10.3, 10.4** |
| 34 | **Email — parsers + scanning** | 🔴 | planned | **10.5, 10.6, 10.7, 10.8** |
| 35 | Movie night | 🔴 | planned | **8.3, 8.4** — needs Supabase Realtime, net new |
| 36 | Command palette + shortcuts | 🟢 | planned | **6.3, 6.4** |
| 37 | On-this-day + rewatch | 🟢 | planned | **11.6** — inert until `watch_log` has ~a year of history |
| 38 | E2E suite | 🟢 | planned | 13.10 — written alongside features, formalised here |

## Batch groups

**Grouping rule:** batches share a group when they touch the same files, share a
verification method, or have a dependency between them. Within a group the order is
dependency-derived and **must not be changed**. A group is authorisation to run its
batches back to back — it is **not** permission to merge them together.

Run with `/group-start <id>`. A **checkpoint** is an owner action the agent stops for.

| Group | Ordered batches and checkpoints | Why it is a group |
|---|---|---|
| — | 1 · solo | Foundation; everything downstream depends on it being right |
| — | **checkpoint: provision Neon + Railway + Vercel** → 2 | Hosting/credential change; first deployment deserves eyes |
| — | 3 · solo | Auth is security-critical |
| — | ~~4 · solo~~ | ~~🔴 XL, and a 1,857-row data operation~~ · **shipped** |
| **A** | 5 → 6 | Same files (`routers/movies.py`, `FilterBar.tsx`, shared schemas); 6 depends on 5 |
| **B** | 7 → 8 → 9 | Dependency chain: offline queue needs write endpoints; onboarding needs the PWA |
| — | 10 · solo | Large mechanical restructure of a 2,639-line doc |
| **C** | 12 → 13 | Same domain (sets/collections); 13 reuses 12's UI patterns |
| **D** | 14 → 15 | Both admin-facing read surfaces, same verification shape |
| **E** | 16 → 17 | Both TMDB-driven, same client, 17 reuses 16's patterns |
| **F** | 18 → 19 → **checkpoint: live scraper acceptance runs** → 20 | Dependency chain, same files. 5.3's acceptance needs live retailer hits — owner performs those |
| — | 21 · solo | Hard 7-day wall-clock gate after Batch 20 |
| **G** | 22 → 23 | Both consume the scraper framework from 19 |
| **H** | 24 → 25 | **Both blocked on the same two `vercel.json` fixes** — camera Permissions-Policy and CSP `connect-src` |
| — | 26 · solo | Conditional on Batch 6 proving insufficient |
| — | 27 · solo | The app's only public surface; needs its own security review |
| **I** | **checkpoint: eBay production API application** → 28 → 29 | 29 consumes 28; API access gates the group |
| **J** | 30 → 31 | Strong dependency, same files; caps must exist before tools |
| — | 32 · solo | Small and independent |
| **K** | **checkpoint: Google + Microsoft OAuth app registration** → 33 → 34 | 34 consumes 33; credential setup gates the group |
| — | 35 · solo | 🔴, needs Supabase Realtime — net new integration |
| — | 36 · solo | Already two phases in one batch |
| — | 37 · solo | Inert until `watch_log` has ~a year of history |
| — | 38 · solo | Formalises work written across earlier batches |

**Net: 38 batches → 24 sessions.** Eleven groups absorb 25 batches; 13 stay solo.

## Risk notes carried by owner decision (`DECISIONS.md` #16)

- **Batch 19/20/22 (scraping).** Six retailer scrapers to build and keep working. A layout change does not error — it selects the wrong node and persists a plausible wrong number, which then feeds price-drop alerts and aggregates. Build a per-scraper "last known good shape" assertion, not just a success/fail counter. Phase 5.3's acceptance criterion requires live-retailer runs; keep those out of CI and run them manually.
- **Batch 33 (email credentials).** Stores two people's live mailbox tokens. Must land **after** Batch 3's rate limiting and fail-closed config, never before. Encryption at rest is net-new — app-starter ships no `cryptography` dependency.
- **Batch 28 (eBay).** Sold-comp data is unobtainable; the UI must say "current asking prices". Production API access is an application, not a given — start it early, it gates the batch.
- **Batch 24 (barcode).** Expect a low hit rate on unknown discs and wrong-edition matches. Confirmation UI is mandatory.

## Dropped — not scheduled

**9.6 Voice Output (TTS)** only, per `DECISIONS.md` #16.

13.11 remains folded into every UI batch's definition of done rather than existing as a
phase — the work happens, the phase does not.

**Reinstating a dropped phase is a `DECISIONS.md` entry, not a quiet edit to this file.**
