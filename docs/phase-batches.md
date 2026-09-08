# Batch ledger

The single batch source of record. Each batch is a small, shippable unit driven by
`docs/agent-commands/` (`batch-start` → `batch-verify` → `phase-closeout`).
Close-out is **automatic after a green gate** (`DECISIONS.md` #24, superseding #13).

**Tier:** 🟢 Mid · 🟡 Large · 🔴 XL · **Status:** planned · in-progress · shipped
Strike the row through and set status on close-out.

## Model and effort

Named by **what the batch needs**, then mapped to each tool. The need is stable; model
names are not — the roadmap still carries 98 phase annotations naming "Sonnet 4.6", a model
that no longer exists under that name, which is the decay this split exists to avoid.
`docs/house-standard.md` already says model choice belongs in "small external tables"
rather than in the master doc, so this is where it lives.

| Need | When | Claude Code | Codex |
|---|---|---|---|
| **Deep** | Silent failure modes, irreversible actions, credentials, a public surface, or a spec you expect to be wrong | Opus 5 | GPT-5.6 Sol |
| **Standard** | Ordinary feature work against a clear spec, caught by tests when wrong | Sonnet 5 | GPT-5.6 Terra |
| **Light** | Mechanical, well-specified, small blast radius | Haiku 4.5 | GPT-5.6 Luna |

*Lineups current as of 2026-09-08. On Codex, **GPT-5.5** is the legacy fallback if 5.6 is
unavailable — it is built for multi-step agentic work, so treat it as Terra-equivalent and
raise the effort a step to compensate.*

**No batch is Light.** These are all real features on live data; the row is kept for
mechanical follow-ups and for sub-tasks inside a batch, not because anything here qualifies.

### Effort

Both tools run the same five-step ladder. Claude writes the fourth step `xhigh`; Codex
writes it `Extra High`. The tables below use each tool's own spelling, so a cell can be
copied straight into the setting.

| Claude Code | Codex | Used here for |
|---|---|---|
| `medium` | Medium | Doc restructuring, charts over data already collected, small independent UI |
| `high` | High | **The default.** Ordinary feature work — most batches |
| `xhigh` | Extra High | Irreversible actions, credentials, a public surface, or a known-bad spec |
| `max` | Max | Silent wrong data at scale, or net-new security-critical infrastructure — **three batches** |

**`high` is the baseline, not the exception.** Claude's guidance calls it "the standard
default for many models and agentic workflows ... complex coding and multi-step reasoning",
and Codex describes its High the same way. So an ordinary feature batch is `high`; `medium`
is for work genuinely closer to drafting than to engineering.

*Codex additionally offers **Ultra**, which is not a rung on this ladder — it is automated
delegation across parallel subagents. Reach for it **inside** a batch whose work genuinely
splits, once the shape is settled: **19** is six independent retailer scrapers and **34** is
four independent mailbox parsers. Do not start there — both batches are `Max`/`Extra High`
in the table because the framework each one hangs off has to be right first, and delegating
that is how six scrapers end up with six different silent bugs.*

### How the group rows are set

**A group runs at the strictest setting any of its batches asks for.** The values in the
group manifest are *derived from* the batch rows, not typed independently — so Group F
reads `Opus 5 · max` because Batch 19 does, and Group D reads `Opus 5 · xhigh` because
Batch 15 does even though Batch 14 is `Sonnet 5 · high`.

If you change a batch's setting, re-derive its group's. They are two views of one fact and
the batch row is the one that governs.

### Effort tracks risk, not size

The two are routinely different, and this list has already proved it. **Batch 8 was tiered
🟢 Mid — the smallest of the three shipped on 2026-09-08 — and was by far the most
dangerous**: four defects, every one of which passed the build, the types and 46 tests.
Batch 7, tiered 🟡 Large, went almost clean. Size predicted how long they took and nothing
about the care they needed.

What did predict difficulty: **a failure that does not announce itself** (a paused query
looks like a hang, not an error), **a spec that contradicts itself** (13.9's last-write-wins
against Batch 8's own acceptance criterion), and **a third-party default that is reasonable
for other apps and wrong for this one**.

So the column is set from blast radius and silence. Where it disagrees with the tier, the
disagreement is the point:

- **11** 🟢 → Deep · xhigh — VAPID credentials, and a push that never arrives looks like no news
- **15** 🟢 → Deep · xhigh — permanent delete, irreversible, on 1,857 live rows
- **17** 🟡 → Deep · xhigh — a secret-token `.ics` URL is an unauthenticated public surface
- **19** 🔴 → Deep · **max** — the risk note says a layout change *"does not error — it selects
  the wrong node and persists a plausible wrong number"*, and that number then feeds alerts
- **24** 🟡 → Deep · xhigh — a wrong-edition barcode match is wrong data that looks right
- **27** 🟡 → Deep · xhigh — the app's only public surface; the ledger already says it needs
  its own security review
- **31** 🔴 → Deep · **max** — tool definitions calling this API, and the second consumer that
  `DECISIONS.md` #12 says would reopen the envelope question
- **33** 🔴 → Deep · **max** — two people's live mailbox tokens, with encryption at rest that is
  net-new to this repo

**A group runs at the highest model and effort any of its batches asks for**, so the column
lives per batch here and is not repeated in the group manifest.

---

## Build to first deployment

| # | Batch | Tier | Claude Code | Codex | Status | Covers phases from `MCU_Architecture_v2.1_FINAL.md` §16 | Result |
|---|---|---|---|---|---|---|---|
| ~~1~~ | ~~New spine foundations~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~re-lands **0.1, 0.2, 0.3**; carries **0.6**~~ | PR #1 · `0910428`, `15ed148` |
| ~~2~~ | ~~Deploy spine + CI gate~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~re-lands **0.5**; **implements §15, which was never a phase**~~ | `d4190ac` · API live, `/health` serves the SHA |
| ~~3~~ | ~~Auth — PIN + JWT~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~**supersedes 0.4** (Supabase Auth) per `DECISIONS.md` #11~~ | `e89a9c6` · lockout proved on Postgres in CI |
| ~~4~~ | ~~Domain layer + re-import~~ | ~~🔴~~ | — shipped | — shipped | **shipped** | ~~re-lands **1.1, 1.3–1.8**; **fixes the §3.4 location columns 1.2/1.3 omitted**~~ | 1,857 items imported, 1,733 sectioned; 14 trigger tests running in CI |
| ~~5~~ | ~~Read surface **+ identify flow**~~ | ~~🔴~~ | — shipped | — shipped | **shipped** | ~~re-lands **2.1–2.7**; **adds the in-app film picker** (`DECISIONS.md` #33)~~ | `a731b8c` · 1,857 items browsable; search median 20 ms; 757 films identifiable in-app |
| ~~6~~ | ~~Location + facets **+ watch log**~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~**3.6** (re-scoped), **8.1** (re-scoped); delivers §6.2's unkept promise; **adds §3.7's `watch_log`, which no phase owned**~~ | `1067a72` · Front 2nd shelf answers in 20 ms; 1,855 of 1,857 items sectioned |
| ~~7~~ | ~~Write surface~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~re-lands **3.1**; adds **3.2, 3.5, 3.11**~~ | `c808964` · 1,857 items untouched; audit log survives a hard delete of its target; 331 CI tests, zero skips |
| ~~8~~ | ~~PWA + offline~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~**13.8, 6.5, 13.9** pulled forward~~ | `c310d0f` · installable, collection cached, offline edits land on reconnect; **four defects found only by driving it with the network off** |
| ~~9~~ | ~~Onboarding repair~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~repairs **2.8**~~ | `4de32c3` · six honest steps; **the notifications step was dropped, not fixed — it still has nothing behind it** |

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

### ~~Batch 5 — Read surface + identify flow~~ 🔴 **shipped**
**Goal:** Mark can browse the collection on his phone, and every film shows something —
either its metadata or the way to supply it.
List (paginated), detail, copies, tsvector search. **camelCase DTOs and shared zod schemas
that the web app actually `.parse()`s** (`DECISIONS.md` #12) — schemas ship with the
endpoint. Web shell, grid, detail page, search.

**The identify flow** (`DECISIONS.md` #33). Batch 4 left **757 films unidentified, carrying
764 items** — 41% of the catalogue would otherwise render as blank detail pages, which
contradicts this batch's own goal. They need no flag column: they are exactly
`movies.tmdb_id IS NULL`, and their `title` is the spreadsheet title to search with.
- `GET /api/v1/movies/{id}/candidates` — runs the existing `MatchingEngine` against the
  stored title, live, returning the top five **with poster, year and overview**, plus a
  free-text query parameter for "none of these" (which is the only route for the 136 rows
  TMDB returned nothing for).
- `POST /api/v1/movies/{id}/identify` — takes the chosen `tmdb_id`, calls `get_movie_full`,
  fills every §3.2 column and the credits, sets `tmdb_id`. The `search_vector` trigger fires
  on its own from the title/overview update.
- The same picker, reachable from an **already-identified** film, is what fixes the
  wrong-sibling matches (`STATUS.md` gotcha 1b) without a third change to the ranking.
- **Either user can identify a film**, not admins only (#33).

**Acceptance:** the deployed app renders 1,857 items at 60fps and a search returns in <150ms. Every response the web app consumes is parsed through `packages/shared`; zero `as Promise<T>` casts on API responses. **No film renders an empty detail page** — an unidentified one shows the picker. Identifying a film from the UI populates its poster, overview, cast and `search_vector`, and it is then findable by a search term that only appears in the fetched metadata. Correcting an already-identified film works by the same route.

### ~~Batch 6 — Location + facets~~ 🟡 **shipped**
**Goal:** the app answers "where is this disc?"
`section`/`shelf` filter params and UI. Complete the facet set `FilterBar` lacks — decade
range, watched status, rating. (Phase 8.1 re-scoped; the LLM version stays dropped.)
**Acceptance:** "show me everything on the Front 2nd shelf" works end to end — the §6.2 promise, unimplementable since April.

**Tier moved 🟢 → 🟡 before any code was written, because "watched status" had nothing
behind it.** §3.7 designs `watch_log` and §6.5 lists its endpoints, but **no phase in §16
creates it** — checked against all 96 phase headings — while Batch 37 is defined as "inert
until `watch_log` has ~a year of history". The facet was a missing feature, not a facet.
Owner decision to build it here (`DECISIONS.md` #35), which also unblocks Batch 37.

**The 124 unsectioned rows are settled** (`DECISIONS.md` #34). 122 of them are four named
cabinets, now in the section vocabulary and backfilled; the remaining two are
"(In with The Killing)", which names a disc rather than a place, and one row with no
location. 1,855 of 1,857 items now carry a section, up from 1,733.

### ~~Batch 7 — Write surface~~ 🟡 **shipped**
Add / edit / soft-delete collection items, duplicate detection, condition tracking, with
`admin_actions` audit writes.
**Acceptance:** changes persist; deleted items appear in trash; the audit log records actor, action and target and survives deletion of the target row (`DECISIONS.md` #5).

**`admin_actions` did not exist on the new spine** — gotcha 4's speculative-table warning
in reverse. Created by migration `008` with `target_id` as TEXT and no foreign key
(`DECISIONS.md` #5, which supersedes §3.20's UUID column). The criterion is proved by a
test that disables the soft-delete trigger and genuinely destroys the row.

**Three scope calls, all recorded in `DECISIONS.md` #37–39.** Writes are admin-only, as
§3.1's own acceptance criterion requires. Optimistic UI is Batch 8's phase 6.5, not this
batch's — building rollback here would mean building what Batch 8 explicitly rejects. The
trash is one table with no permanent delete; §13.5 keeps the destructive half.

**Two defects found that a green build could not have shown.** The first create-body
validator never ran when the field was absent, so a body naming no film 500'd instead of
422'ing — caught in CI by this batch's own test. And driving the pages in a browser found
every list claiming to be *empty* when its request had merely been paused; that one is
fixed app-wide and matters most for Batch 8.

### ~~Batch 8 — PWA + offline~~ 🟢 **shipped**
Port `sw.ts` (with the iOS deadlock fix), manifest, `useOnlineStatus`, `OfflineBanner`,
`/offline`. Optimistic UI via the-coupon's queued/unconfirmed reconciliation — **not**
naive optimistic-with-rollback. Offline write queue adapted to multiple entity types.
**Acceptance:** the app installs to a phone home screen, browses cached collection data with the network off, and an edit made offline lands once reconnected without overwriting a newer change.

**Phase 13.9's "last-write-wins" contradicted this batch's own acceptance criterion** and
lost. A queued edit flushed on reconnect *is* written last, so last-write-wins is exactly
what "without overwriting a newer change" forbids. Replaced by an optimistic-concurrency
check (`DECISIONS.md` #42). Phase 6.5's acceptance names the wanted list, which is Batch
18 and does not exist; re-scoped to the collection writes Batch 7 built.

**Four defects, none of which a green gate could show.** React Query *pauses* mutations
when it believes the app is offline, so `mutationFn` never ran and the queue — which
lives inside it — was never reached; the same pause stops a query issuing the fetch the
service worker exists to answer. A 5xx on a write was treated as a refusal and the write
discarded. A 5xx on the profile load signed the person out and destroyed the session the
queued writes were made under. And `updated_at` used `NOW()`, which is *transaction*
time, so the new concurrency token never advanced and the guard passed anything. All four
were found by running the built app against a stub API that could be switched off.

### ~~Batch 9 — Onboarding repair~~ 🟢 **shipped**
Prune `StepEmailConnect` (Stage 10 dropped). `StepInstallPWA` and `StepNotifications` now
have real infrastructure behind them.
**Acceptance:** every step of the wizard does what it says. No step reads a property nothing sets.

**Half of that second sentence was wrong.** `StepInstallPWA` does now have infrastructure —
Batch 8's manifest and service worker let `beforeinstallprompt` fire. **`StepNotifications`
does not**: there is no VAPID key, no subscription, no endpoint to store one and no
`push_subscription` column, and push is Batch 11. It also offered toggles for six features
that do not exist yet. Dropped rather than ported, because keeping it would have broken
this batch's own acceptance criterion (`DECISIONS.md` #50).

**A fourth dead step that gotcha 5 never listed:** the catalogue step read `d?.meta?.total`
— the `{data, meta, errors}` envelope `DECISIONS.md` #6 removed — so it rendered a loading
skeleton for ever.

Result: **six steps for an admin, five for a viewer**, every one of them backed. Completion
is `profiles.onboarding_completed_at_utc` (migration `010`), the column Batch 3 removed the
wizard for the lack of.

---

## Post-launch — sequenced, not scheduled

Revised 2026-09-07 by `DECISIONS.md` #16: all of Part D's drops are reinstated except 9.6.

| # | Batch | Tier | Claude Code | Codex | Status | Phases |
|---|---|---|---|---|---|---|
| 10 | Architecture doc split + §17 reconciliation | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | Part C deferred half |
| 11 | Notifications + push | 🟢 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 6.1, 6.2, 5.11 |
| 12 | Box sets + smart collections | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 11.3, 11.4, 11.5 |
| 13 | Completion sets | 🟡 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 11.1, **11.2** |
| 14 | Stats + export | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 13.1, 13.2, 13.3, 13.4 |
| 15 | Trash, audit UI, lending | 🟢 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 13.5, 13.6, 12.5 |
| 16 | Watch providers + recommendations | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 7.1, 7.2 |
| 17 | Release calendar + iCal | 🟡 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 7.3, 7.4 — secret-token `.ics` URL |
| 18 | Wanted list + retailers | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 5.1, 5.2 (full scope) |
| 19 | **Scraper framework** | 🔴 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | planned | **5.3, 5.4** — see risk note below |
| 20 | Price scraping + drop alerts | 🟡 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 5.5, 5.6, 5.8 |
| 21 | Price history charts | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | **5.7** — needs 7 real days of data after B20 |
| 22 | Deals feed | 🟡 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 5.9, 5.10 — RSS **and** scraped sources |
| 23 | Specs — scraper + display | 🟡 | Opus 5 · high | GPT-5.6 Sol · High | planned | 3.7, 3.8, 3.9 |
| 24 | Barcode — scan + lookup | 🟡 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 3.3, **3.4** — confirmation UI mandatory |
| 25 | Photo uploads | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 3.10 — needs the `vercel.json` CSP fix |
| 26 | Shelf QR | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | 12.3, 12.4 |
| 27 | Gift links | 🟡 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 12.1, 12.2 — high-entropy slug, rate limiter, `noindex` |
| 28 | **eBay integration** | 🔴 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | **4.1, 4.3** — active listings, not sold comps |
| 29 | Format upgrade + sale tracking | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 4.2, 4.4 |
| 30 | AI assistant — client + caps | 🟡 | Opus 5 · high | GPT-5.6 Sol · High | planned | 9.1 + **9.7 together** |
| 31 | AI assistant — tools + chat | 🔴 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | planned | 9.2, 9.3, 9.4 |
| 32 | Voice input | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | **9.5** |
| 33 | **Email — accounts + OAuth** | 🔴 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | planned | **10.1, 10.2, 10.3, 10.4** |
| 34 | **Email — parsers + scanning** | 🔴 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | **10.5, 10.6, 10.7, 10.8** |
| 35 | Movie night | 🔴 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | **8.3, 8.4** — needs Supabase Realtime, net new |
| 36 | Command palette + shortcuts | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | **6.3, 6.4** |
| 37 | On-this-day + rewatch | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | **11.6** — `watch_log` now exists (Batch 6); still inert until it has ~a year of history |
| 38 | E2E suite | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 13.10 — written alongside features, formalised here |

## Batch groups

**Grouping rule:** batches share a group when they touch the same files, share a
verification method, or have a dependency between them. Within a group the order is
dependency-derived and **must not be changed**. A group is authorisation to run its
batches back to back — it is **not** permission to merge them together.

Run with `/group-start <id>`. A **checkpoint** is an owner action the agent stops for.

| Group | Ordered batches and checkpoints | Claude Code | Codex | Why it is a group |
|---|---|---|---|---|
| — | 1 · solo | — shipped | — shipped | Foundation; everything downstream depends on it being right |
| — | **checkpoint: provision Neon + Railway + Vercel** → 2 | — shipped | — shipped | Hosting/credential change; first deployment deserves eyes |
| — | 3 · solo | — shipped | — shipped | Auth is security-critical |
| — | ~~4 · solo~~ | — shipped | — shipped | ~~🔴 XL, and a 1,857-row data operation~~ · **shipped** |
| **A** | 5 → 6 | — shipped | — shipped | Same files (`routers/movies.py`, `FilterBar.tsx`, shared schemas); 6 depends on 5 |
| **B** | ~~7~~ → ~~8~~ → ~~9~~ | — shipped | — shipped | Dependency chain: offline queue needs write endpoints; onboarding needs the PWA |
| — | 10 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Large mechanical restructure of a 2,639-line doc |
| — | **checkpoint: generate VAPID keys + set them in Railway** → 11 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | Credential change, so it stops for the owner. Solo: push shares no files with 10 or 12, and everything that *consumes* it (20, 22, 37) is far downstream |
| **C** | 12 → 13 | Sonnet 5 · high | GPT-5.6 Terra · High | Same domain (sets/collections); 13 reuses 12's UI patterns |
| **D** | 14 → 15 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | Both admin-facing read surfaces, same verification shape |
| **E** | 16 → 17 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | Both TMDB-driven, same client, 17 reuses 16's patterns |
| **F** | 18 → 19 → **checkpoint: live scraper acceptance runs** → 20 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | Dependency chain, same files. 5.3's acceptance needs live retailer hits — owner performs those |
| — | 21 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Hard 7-day wall-clock gate after Batch 20 |
| **G** | 22 → 23 | Opus 5 · high | GPT-5.6 Sol · High | Both consume the scraper framework from 19 |
| **H** | 24 → 25 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | **Both blocked on the same two `vercel.json` fixes** — camera Permissions-Policy and CSP `connect-src` |
| — | 26 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Conditional on Batch 6 proving insufficient |
| — | 27 · solo | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | The app's only public surface; needs its own security review |
| **I** | **checkpoint: eBay production API application** → 28 → 29 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | 29 consumes 28; API access gates the group |
| **J** | 30 → 31 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | Strong dependency, same files; caps must exist before tools |
| — | 32 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Small and independent |
| **K** | **checkpoint: Google + Microsoft OAuth app registration** → 33 → 34 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | 34 consumes 33; credential setup gates the group |
| — | 35 · solo | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | 🔴, needs Supabase Realtime — net new integration |
| — | 36 · solo | Sonnet 5 · high | GPT-5.6 Terra · High | Already two phases in one batch |
| — | 37 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Table exists since Batch 6; inert until it has ~a year of history |
| — | 38 · solo | Sonnet 5 · high | GPT-5.6 Terra · High | Formalises work written across earlier batches |
**Net: 38 batches → 25 sessions.** Eleven groups absorb 24 batches; 14 stay solo.

*Batch 11 had no row here at all until 2026-09-08, and the arithmetic hid it: the old
line claimed groups absorbed 25 batches when the rows only ever added to 24, so the
totals reached 38 while one batch was listed nowhere. Found when Batch 9 dropped the
wizard's notifications step and handed 11 an obligation (`DECISIONS.md` #50) — at which
point "when does 11 run?" had no answer.*

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
