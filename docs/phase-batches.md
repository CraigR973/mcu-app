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

### Batch 10 — Architecture doc split + §17 reconciliation
**Goal:** `MCU_Architecture_v2.1_FINAL.md` stops being the place anyone has to go to find
out what's actually true. It is the deferred half of `REVIEW_PLAN_2026-09-07.md` Part C,
which specifies: *"Convert `MCU_Architecture_v2.1_FINAL.md` (2,639 lines) into
`ARCHITECTURE.md` + a roadmap doc; retire `session-log.md.txt` into the STATUS/DECISIONS
pattern."* No acceptance criteria were ever written for this batch when the ledger row was
added; this section supplies them before work starts.

- **Split.** Extract the durable design/reference material (stack choices, schema
  rationale, non-batch-specific spec) out of `MCU_Architecture_v2.1_FINAL.md` into a new
  `ARCHITECTURE.md`. `docs/phase-batches.md` already *is* the roadmap doc the review plan
  asked for — this batch confirms that rather than authoring a second one.
- **§17 reconciliation.** The "Resolved Decisions" table (50 rows, April) gets a verdict
  per row: still current as designed / superseded (cite the `DECISIONS.md` # or batch that
  overrode it) / not yet built. No row is deleted outright — the table becomes a dated
  record with each entry's current status attached, the same treatment gotcha 0 already
  gives `docs/part-b-audit.md` and `docs/part-d-roadmap.md`.
- **Retire `session-log.md.txt`.** `DECISIONS.md` already says entries 1–8 were
  reconstructed from it on 2026-09-07. Confirm nothing else in it is un-migrated, then
  remove it from the working tree (git history keeps it).
- **Fix cross-references.** `AGENTS.md`/`CLAUDE.md` currently point at
  `MCU_Architecture_v2.1_FINAL.md` as one of the "read these first" docs and instruct
  "never read it whole." Update those pointers to the new split.

**Acceptance:**
1. `ARCHITECTURE.md` exists and holds the durable design content; `MCU_Architecture_v2.1_FINAL.md` is either removed or reduced to a superseded stub pointing at its replacement.
2. Every one of §17's 50 rows carries an explicit current-status verdict, not just its original April resolution.
3. `session-log.md.txt` no longer exists in the working tree, and nothing it uniquely held is lost — verified by confirming its content is covered by `DECISIONS.md`/`STATUS.md` before deletion.
4. `AGENTS.md` and `CLAUDE.md`'s "Source of truth" table point at the new doc(s), not the retired one.
5. No code changes; the standard CI gate (lint/typecheck/test/build) stays green because nothing it exercises changed.

This batch touches no hosting/credentials and performs no destructive data operation, so
automatic close-out applies once the gate is green.

### ~~Batch 12 — Box sets + smart collections~~ 🟢 **shipped**
**Covers phases 11.3, 11.4, 11.5.** Their goals and acceptance criteria, recovered
**verbatim** from `MCU_Architecture_v2.1_FINAL.md` §16 at `d94a6b8~1` — Batch 10 removed
§16 and the ledger did not carry the criteria forward, so `batch-start.md` step 2's
"restate them verbatim" had nothing to read (`DECISIONS.md` #54).

> **Phase 11.3: Box Set CRUD**
> - Admin creates a box set, adds collection_items
> - Series linking
> - **Acceptance:** Admin creates "Columbia Noir Vol 4" with 4 items
>
> **Phase 11.4: Box Set Display & Completion**
> - Box set grid view
> - Per-set completion ("3 of 4")
> - **Acceptance:** Browsing box sets shows all with status
>
> **Phase 11.5: Smart Collections**
> - Create/edit/delete smart collections
> - Dynamic filter evaluation
> - Pin to dashboard
> - **Acceptance:** Creating "Unwatched 4Ks from 2010s" lists correct films and updates live

Schema per §3.23 (`smart_collections`), §3.24 (`box_sets`) and §3.25 (`box_set_items`);
endpoints per §6.5's own table. Two shapes differ from the tables as drawn and both are
recorded in migration `011`'s docstring: `box_sets` gains `deleted_at` (house convention;
the row groups real discs), and both new parents gain `updated_at` with `009`'s trigger.

**`sub_category` is neither read nor rewritten.** 627 live items carry one across 106
distinct values, and it is tempting to seed box sets from the ~30 matching /box|vol|set/.
It would be wrong: the same column holds "Clint Eastwood" (64 items) and "Hitchcock" (30),
which are groupings of a person's work rather than boxes. §11.3's acceptance is
*"Admin creates …"* precisely because the judgement is a person's.

This batch touches no hosting/credentials and performs no destructive data operation, so
automatic close-out applies once the gate is green.

### ~~Batch 13 — Completion sets~~ 🟡 **shipped**
**Covers phases 11.1 and 11.2**, verbatim from `MCU_Architecture_v2.1_FINAL.md` §16 at
`d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 11.1: Completion Sets Data & Refresh**
> - Seed director, franchise, award sets
> - Weekly refresh job from TMDB collections
> - **Acceptance:** Refresh job runs live against TMDB and populates `completion_sets` with ≥ 20 sets (directors, franchises, awards); Hitchcock set lists every Hitchcock film TMDB returns; re-running after a TMDB change updates the affected rows.
>
> **Phase 11.2: Completion Insights UI**
> - Progress bars per set
> - Missing films list with posters
> - Bulk "add missing to wanted list"
> - **Acceptance:** Opening Insights shows ≥ 20 sets with owned/missing counts

**Three things in that spec do not hold, all recorded rather than worked around.**

1. **"Bulk add missing to wanted list" was dropped.** The wanted list does not exist —
   §3.5 designs `wanted_list`, **Batch 18** builds it, and `/watchlist` is a "coming soon"
   stub. Shipping the button would ship a control that does nothing (`DECISIONS.md` #50,
   `STATUS.md` gotcha 5). 11.2's acceptance criterion does not mention it. **Batch 18 owns
   adding it.**
2. **"awards" has no source.** TMDB has no awards API, so a Best Picture set has to be
   typed by hand — which is what §3.15's `curated_list` type is for. Not built here.
3. **"franchises" needs a column this app does not have.** TMDB's `belongs_to_collection`
   is returned by `get_movie_full` and never stored, so learning it for the 1,086
   identified films is a schema change plus a 1,086-call backfill — its own piece of work.

**What the sets are built from instead: the collection's own credits.** `movie_credits`
already holds real TMDB person ids, so the top 20 directors and top 20 actors by owned
count give 40 sets with no name-matching step to get wrong — which matters, because
gotcha 1b is the record of what fuzzy TMDB matching did to this app once already.

**"Weekly" is not scheduled by this batch.** A Railway cron is a hosting change and stays
explicit. `src/scripts/refresh_completion_sets.py` and `POST /insights/completion/refresh`
are what a schedule would call; wiring one is an owner action.

### ~~Batch 14 — Stats + export~~ 🟢 **shipped**
**Covers phases 13.1, 13.2, 13.3, 13.4**, verbatim from §16 at `d94a6b8~1`
(`DECISIONS.md` #54):

> **Phase 13.1: Stats Dashboard** — Format breakdown pie · Genre bar chart · Decade distribution · Most-watched · Collection value over time. **Acceptance:** Stats page loads in < 1s with all charts populated
>
> **Phase 13.2: Activity Feed** — Timeline of recent additions, watches, price drops, loans. **Acceptance:** Home dashboard shows last 20 events across all users
>
> **Phase 13.3: Collection Export (CSV, JSON)** — Full collection export endpoints · Download links. **Acceptance:** CSV opens cleanly in Excel; JSON is valid
>
> **Phase 13.4: Collection Export (PDF, HTML)** — Printable PDF with posters · "Coffee table" HTML style. **Acceptance:** PDF looks presentation-ready; HTML prints well

**"All charts populated" cannot be literally true, and the page says so rather than
drawing zeros.** Measured against live Neon before any code was written: `watch_log` holds
**0 rows** and `purchase_price`/`purchase_date` are NULL on **all 1,857** items, because
the spreadsheet never carried a price. So "most watched" and "collection value over time"
have no data — while formats, genres, decades and sections all do. Both empty charts state
what they are waiting for, and the response carries `itemsWithPrice` so an empty series can
distinguish "nothing recorded" from "nothing bought". An empty chart reads as a broken
chart; that is gotcha 19's lesson applied to a dashboard.

**Two of §13.2's four feed sources do not exist yet** — price drops are Batch 20, loans are
Batch 15. Both write into the same endpoint when they land.

**There is no server-side PDF renderer, by decision** (`DECISIONS.md` #62). Every option
needs system libraries in an image **Railway builds and CI does not**, so a missing shared
object fails a deploy rather than a pull request. `/export/collection.html` is laid out for
print and the browser's own "Save as PDF" produces the file — one artifact for both halves
of §13.4, with no dependency the gate cannot prove.

### ~~Batch 15 — Trash, audit UI, lending~~ 🟢 **shipped**
**Covers phases 13.5, 13.6, 12.5**, verbatim from §16 at `d94a6b8~1`
(`DECISIONS.md` #54):

> **Phase 13.5: Trash & Restore UI** — List soft-deleted items per table · Restore / permanently delete actions. **Acceptance:** Deleted item in Trash; restoring brings it back with full state
>
> **Phase 13.6: Admin Audit Log UI** — Filterable log of all admin actions. **Acceptance:** Making 5 test changes shows 5 entries with correct diffs
>
> **Phase 12.5: Lending Tracker** — Mark as lent / returned · Loans page · Reminder notifications for overdue. **Acceptance:** Lending a disc shows it in Loans; overdue triggers a push

**12.5's second acceptance clause cannot be met and no substitute was shipped.** "Overdue
triggers a push" needs push, and there is no VAPID key, no subscription store and no
endpoint — that is **Batch 11**, which stops for an owner credential checkpoint. An overdue
loan is shown in red and counted; `loans.reminder_sent` exists for Batch 11 to write and
nothing reads it. A toggle promising a notification that never arrives is the defect Batch
9 refused to ship (`DECISIONS.md` #50).

**The permanent delete is the first irreversible operation in this app**, and the mechanism
matters more than the endpoint (`DECISIONS.md` #64). `003`'s `soft_delete` trigger rewrites
every DELETE, so the destroy path has to get past it — and **not** with
`ALTER TABLE ... DISABLE TRIGGER`, which is persistent and *global*: a process death
between disabling and re-enabling would make every delete in the app permanent while the
trash kept showing an empty page. Migration `013` makes the trigger skip on a
transaction-scoped `SET LOCAL`, turned off again immediately so it covers one statement.

**`wanted_list` is absent from the trash, not empty.** §6.30 names it; Batch 18 builds it.
The API refuses the table name rather than answering "nothing here".

### ~~Batch 16 — Watch providers + recommendations~~ 🟢 **shipped**
**Covers phases 7.1 and 7.2**, verbatim from §16 at `d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 7.1: TMDB Watch Providers Integration** — `GET /api/v1/movies/{id}/streaming` · Region-aware (user's streaming_region) · Display on detail page. **Acceptance:** For a popular film, UK streaming options shown correctly
>
> **Phase 7.2: Recommendations & New Releases** — TMDB `/recommendations` on detail page · Flag as owned / wanted / unowned · New releases feed filtered by collected genres. **Acceptance:** Detail page shows 10+ recommendations with correct ownership flags

**`profiles.streaming_region` did not exist.** §7.1 says "user's streaming_region"; the only
region column in the schema was `collection_items.region_code`, which is a disc's Blu-ray
region — a different thing entirely. Migration `014` adds it, defaulting to `GB`, with a
CHECK on the two-letter shape because TMDB answers an unrecognised key with an **empty map
rather than an error**: a lower-cased "gb" would make every film appear to stream nowhere.

**"Wanted" was dropped from the ownership flags.** §7.2 lists "owned / wanted / unowned";
the wanted list is §3.5 and **Batch 18** builds it. Two states are what the app can
distinguish today, and the zod enum has exactly two so a third cannot be rendered by
accident.

**Nothing is cached.** Streaming rights move constantly, so a stale answer is a wrong
answer with a confident face. Contrast `completion_sets`, which caches precisely because a
filmography barely changes.

### ~~Batch 17 — Release calendar + iCal~~ 🟡 **shipped**
**Covers phases 7.3 and 7.4**, verbatim from §16 at `d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 7.3: Release Calendar Data Source** — Populate release_calendar from TMDB upcoming + curated sources · Filter by genres of interest. **Acceptance:** Live ingestion run populates `release_calendar` with ≥ 30 rows spanning the next 3 months (not seeded data); Calendar page renders them.
>
> **Phase 7.4: Calendar UI & iCal Feed** — Monthly calendar view · `/api/v1/calendar.ics` endpoint · Subscribe button with copy-link. **Acceptance:** Subscribing in Apple Calendar successfully displays events

**7.4's acceptance cannot be verified from here** — it needs a real calendar app on a real
device. What *was* verified: the feed serves 200 with no `Authorization` header, 32 events,
correct escaping and 75-octet folding, and the document is well-formed RFC 5545. **Owner
action: subscribe in Apple Calendar and confirm the events appear.**

**"Curated sources" is two things, not four.** §6.33 names Criterion and boutique-label
announcements, award ceremonies and sale events. Only the last has a source this app can
reach without a scraper, so sale events are a small dated list in `services/calendar.py`
and **boutique-label announcements are left to Batch 19's scraper framework** — not
half-built here.

**The `.ics` URL is the app's first unauthenticated surface**, and is treated as a
credential: 256 bits of entropy, stored SHA-256-hashed like a refresh token, one live token
per person enforced by a partial unique index, rotated on every subscribe, `noindex` and
`no-store`, and a revoked token answering identically to a never-existent one. The feed
carries no personal data at all — a test asserts it.

**A security review of this batch found a real content-injection hole in the serialiser**
(`DECISIONS.md` #73). Nothing writes `release_calendar.url` yet; **Batch 19's scrapers are
what would have armed it.**

### ~~Batch 18 — Wanted list + retailers~~ 🟢 **shipped**
**Covers phases 5.1 and 5.2**, verbatim from §16 at `d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 5.1: Wanted List CRUD** — Add, edit, remove endpoints · Wanted list page UI with cards · Preferred format, max price, currency. **Acceptance:** Adding to wanted list from detail page and listing it works both ways
>
> **Phase 5.2: Retailer Management** — `retailers` CRUD UI · Admin adds retailer with base URL, deals URL, selectors · Seeded default retailers. **Acceptance:** Admin adds a new retailer; it's saved and enabled

**This batch pays four debts.** Every one of them was deferred here because §3.5 had no
table, and each was recorded rather than fudged at the time:

| Batch | What it deferred | Now |
|---|---|---|
| 13 | §11.2's "bulk add missing to wanted list" — dropped | the button exists on a completion set |
| 15 | the `wanted_list` trash tab — the API **refused** the name | a real tab, with `retailers` beside it |
| 16 | §7.2's third ownership state — a two-value enum | `owned` / `wanted` / `unowned`, with a badge |
| 17 | `release_calendar.is_wishlist_match` — created, never written | still unwritten; left to whichever batch next touches ingestion |

**Seeded retailers arrive with no selectors, and the UI says so.** §5.2 asks for "seeded
default retailers" and §3.16 names six; a seeded row is a name and a URL, not a working
scraper. Inventing CSS nobody has run against a live page would be worse than none — the
ledger's own risk note for Batch 19 is that a wrong selector *"does not error — it selects
the wrong node and persists a plausible wrong number"*. `configuredCount` is 0 and the page
says why.

**Seeding is an endpoint, not a migration**, so it is idempotent, re-runnable and
inspectable — a migration that inserts rows makes `downgrade` ambiguous and CI cannot prove
either direction.

### ~~Batch 19 — Scraper framework~~ 🔴 **shipped; acceptance met 2026-09-09 (`DECISIONS.md` #111)**
**Covers phases 5.3 and 5.4**, verbatim from §16 at `d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 5.3: Scraper Framework** — Generic CSS scraper that uses retailer config · Built-in scrapers for HMV, Amazon UK, Blu-ray.com, Zavvi, Arrow, CEX · Error handling with retry and auto-disable after 3 fails. **Acceptance:** Each built-in scraper runs against the **live** retailer and persists ≥ 1 `price_checks` row per scraper for a real wanted item; total `price_checks` rows after the run verified > 0.
>
> **Phase 5.4: Test Scraper Tool** — "Test scraper" button in retailer UI · Runs selectors against live page, displays sample results. **Acceptance:** Admin validates a new retailer before enabling

**Neither acceptance criterion is met by this batch, by design.** Both require live
requests to real shops, which `group-start.md` makes a hard stop:

> "A batch whose acceptance requires **live third-party requests** (scraper runs against
> real retailers, live eBay or mailbox calls) stops before those runs. The owner performs
> them. Fixture-backed tests may run unattended; live ones may not."

That is Group F's own **checkpoint: live scraper acceptance runs**, which sits between this
batch and Batch 20. The framework is built and fixture-tested; the runs are the owner's.

**The whole batch is shaped by one sentence in its risk note** — *"a layout change does not
error — it selects the wrong node and persists a plausible wrong number, which then feeds
price-drop alerts and aggregates. Build a per-scraper 'last known good shape' assertion, not
just a success/fail counter."* `services/scraping/extract.py:check_shape` is that
assertion, and a result failing it is a **failure**, never data (`DECISIONS.md` #79).

**A built-in reports `verified: false` until a live page-shape check passes**, and the UI
says so. A selector nobody has run against a live page is a guess, and the honest state of a
guess is unverified (#80). Those checks ran on 2026-09-09: **five shops passed** — Zavvi,
Arrow (on its UK domain), 101 Films, Second Sight and Powerhouse — and **four are
permanently unverified**, because HMV and CEX disallow the search routes, Amazon blocks
automated access, and Blu-ray.com is a catalogue rather than a shop (#91). They stay listed
with the reason rather than being deleted. eBay takes the general-market role on approval.

**The framework fetches URLs a person typed, which is a new kind of surface for this app.**
`services/scraping/fetcher.py` resolves the host and refuses anything not publicly
routable — re-checked at **every redirect hop**, because httpx would otherwise follow a 302
into an internal address (#81).

### ~~Batch 27 — Gift links~~ 🟡 **shipped**
**Covers phases 12.1 and 12.2**, verbatim from §16 at `d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 12.1: Gift Link Creation** — CRUD for gift_links · Filter configuration · Slug-based public URL. **Acceptance:** Admin creates a link; visiting the slug renders public list
>
> **Phase 12.2: Public Gift Page** — Read-only rendering with posters and retailer links · No auth required · Basic filters visible to viewer. **Acceptance:** Non-logged-in visitor can browse Dad's wanted list

**§3.21's slug design was not followed, deliberately.** It says *"id | UUID (PK) | Public
slug used in the URL"*, and §6.26's worked example is `/gift/a8f3b2c1` — **eight hex
characters, 32 bits**. That is enumerable, and what would be enumerated is a named person's
wish list. The slug is its own column holding 128 bits (`DECISIONS.md` #83).

**The public response model is deliberately unrelated to the admin one** (#85). It could
share a base and must not: the risk of this feature is one admin field reaching the public
page because a model was reused. In particular the page never says **what the recipient
already owns** — a film can be wanted *and* owned (a DVD-to-4K upgrade), Batch 18 shows that
to the admin, and it has no business on a page shown to family.

**Every reason a link does not work answers identically** — missing, expired, deactivated
and revoked are one 404 with one body, so a visitor cannot learn whether a guessed slug was
ever real (#86).

**The slug is stored in plaintext, unlike Batch 17's feed token** (#84). That is a reasoned
difference, not an inconsistency: a gift link exists to be re-shared and re-shown, which
hashing would make impossible.

**Security review: run, and it found four things.** The ledger's own note says this batch
"needs its own security review", and the owner asked for it before close-out. An independent
pass verified all six intended properties with file-and-line evidence and reported **no
security findings at its confidence bar**. What it did surface were real defects, all fixed
here:

| Found | Severity | Fixed by |
|---|---|---|
| `_retailer_links` ran **inside** the per-film loop, re-reading the whole `retailers` table per film — 50 identical queries for a 50-film page, on the unauthenticated endpoint | performance | hoisted; a test asserts exactly one `FROM retailers` per page |
| **The service worker cached `no-store` responses.** `sw.ts` matched any GET under `/api/v1/` by pathname alone, so a gift page a family member opened was stored for 24h in *their* browser against the API's explicit instruction — and the route's own comment claiming "the API sets no `Cache-Control`" had become false | correctness / privacy | the route now matches same-origin only and excludes both capability URLs; the stale comment is corrected |
| `Decimal("NaN")` **parses**, so the `<= 0` guard raised `InvalidOperation` rather than the `try` catching it — a 500 on an admin-only field in **Batch 18's already-merged code** | bug | `is_finite()` check; a test covers NaN, Infinity and sNaN |
| `view_count += 1` was a read-modify-write in Python | correctness | atomic `SET view_count = view_count + 1`; a test asserts the SQL |

Two things the review named as conscious trade-offs rather than defects: the slug is stored
in plaintext (`DECISIONS.md` #84 — a gift link must be re-shareable, unlike Batch 17's feed
token), and it transits request logs the way any path parameter does.

### ~~Batch 36 — Command palette + shortcuts~~ 🟢 **shipped**
**Covers phases 6.3 and 6.4**, verbatim from §16 at `d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 6.3: Command Palette (⌘K)** — Modal with fuzzy search · Indexes films, pages,
> actions, recent items · Keyboard navigation. **Acceptance:** ⌘K opens instantly; typing
> "blade" surfaces Blade Runner films; Enter navigates
>
> **Phase 6.4: Keyboard Shortcuts** — Global shortcuts (g+h, g+c, /, n, ., ?) · Help modal
> listing all shortcuts (triggered with ?). **Acceptance:** All documented shortcuts work;
> help modal shows all

`1425f91` — a Cmd/Ctrl+K palette indexing every page, the admin-only write action, and
films (reusing Batch 5's `/search`, not a re-implementation), plus recently-viewed films
tracked in localStorage. All ten `g`-chord/`/`/`n`/`?`/Esc shortcuts and the help modal
are centralized in one `useKeyboardShortcuts` hook; `SearchBar`'s pre-existing `/`
handler now defers to it (`mcu:focus-search`) instead of the two owning the same key.

**One fact in §7.5's fuller shortcut table had decayed, so it was dropped rather than
built wrong**: `.` is specified to open AI-assistant chat, and the palette's "recent
conversations with the AI assistant" index depends on the same feature — both depend on
Batch 31, which is still planned, not shipped. Same treatment Batches 8/9 gave dead
onboarding steps that outlived their backing feature.

**Verified live in a browser** (Ctrl+K open, empty-state page index, fuzzy filter
narrowing "wanted" to one result, Enter navigating and closing, Escape closing, a `g s`
chord landing on `/stats`) against the dev server with `VITE_SKIP_AUTH`, since the local
API wasn't running. **Not independently browser-verified**: `?` and `/` — the browser
automation tool cannot synthesize a real `key: '?'`/`key: '/'` keydown (confirmed via a
raw listener: `shift+/` and `/` both arrive as `key: ''` through it) — and "typing
'blade' surfaces Blade Runner", since no local API/Postgres was running to search
against. Both rest on the 27 new unit/integration tests, which dispatch real
`KeyboardEvent`s and mock the search endpoint directly.

### Batch 37 — On-this-day + rewatch 🟢
**Covers Phase 11.6**, recovered verbatim from §16 at `d94a6b8~1`
(`DECISIONS.md` #54):

> **Phase 11.6: On-This-Day & Rewatch Memories** 🟢 Sonnet 4.6
> - On-this-day query from watch_log
> - Rewatch suggestions (highly-rated, not recently watched)
> - Optional daily push
> - **Acceptance:** If a watch was logged a year ago, today's dashboard surfaces it

`watch_log` was built early in Batch 6 (`DECISIONS.md` #35), but the feature remains
inert until it has enough history to produce a real anniversary. The acceptance criterion
must therefore be proved with a date-controlled test fixture, not by waiting a calendar
year. The optional daily push depends on Batch 11's VAPID-key checkpoint; it is deferred
to that batch and is not part of Batch 37's acceptance criterion.

This batch touches no hosting/credentials and performs no destructive data operation, so
automatic close-out applies once the gate is green.

---

## Criteria recovered for the 2026-09-09 overnight run

`DECISIONS.md` #54 requires a planned batch's criteria to be written here **before** any code
is written. Six were recovered verbatim from §16 at `d94a6b8~1` on 2026-09-09; **Batch 20's and
Batch 35's were missed and were recovered the same way on 2026-09-10**, when the run reached
them and `STATUS.md`'s claim that all eight were present turned out to be wrong.

### Batch 11 — Notifications + push 🟢
**Covers Phases 6.1, 6.2 and 5.11:**

> **Phase 6.1: Notification Preferences** 🟢
> - Per-category toggles
> - Digest mode and quiet hours
> - **Acceptance:** Disabling "deals" stops deal pushes; quiet hours suppress evening alerts
>
> **Phase 6.2: Multi-Device Push Subscriptions** 🟢
> - Per-device subscription records
> - Test notification button
> - **Acceptance:** Admin connects phone + laptop; both receive pushes; removing one doesn't silence the other
>
> **Phase 5.11: Sale Season Calendar Events** 🟢
> - Seeded data for Prime Day, Black Friday, Boxing Day, Criterion Flash Sale, etc.
> - Pre-sale push notifications
> - **Acceptance:** Test date set 2 weeks before a seeded event triggers a reminder

**The credential landed on 2026-09-09 and its names are now fixed by what is in Railway:**
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`. The key pair was verified to match.
`VITE_VAPID_PUBLIC_KEY` is deliberately **not** yet set on Vercel — it is a build-time Vite
variable, so it does nothing until this batch ships code that reads it. Setting it is a
hosting change and therefore an owner action at the end of this batch, not during it.

**6.2's acceptance cannot be met by an agent.** "Admin connects phone + laptop; both receive
pushes" needs two real devices holding real subscriptions. Build the per-device subscription
records and the test-notification button, prove the send path against a stub push service,
and **defer the criterion to the owner** — the same shape as Batch 19. Say so plainly in the
close-out rather than implying it passed.

**6.1 and 5.11 are provable tonight** with a date-controlled fixture, which is Batch 37's
pattern: quiet hours and "two weeks before a seeded event" are both clock questions.

**This batch owes two debts.** Batch 15 shipped §12.5's "overdue loan triggers a push"
without the push, and Batch 19 deferred price-drop notifications here. Both land now.

### Batch 30 — AI assistant, client + caps 🟡
**Covers Phases 9.1 and 9.7:**

> **Phase 9.1: Claude API Client** 🟢
> - Anthropic SDK integration
> - System prompt scaffolding
> - Token + cost logging per message
> - **Acceptance:** Simple text prompt returns a response; tokens logged
>
> **Phase 9.7: Usage Caps** 🟢
> - Per-user daily message / cost cap
> - Graceful "limit reached" message
> - **Acceptance:** Sending over the cap blocks with clear messaging; resets next day

`ANTHROPIC_API_KEY` was set in Railway on 2026-09-09. **The default cap is 50 messages per
person per day** (owner, 2026-09-09), editable in the app afterwards — a starting value, not
a commitment.

**Do not guess a model id.** The April spec predates the current lineup by two generations.
The Claude 5 family is current: `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5-1`, plus
`claude-haiku-4-5-20251001`. Sonnet 5 is the sensible default for an assistant answering
questions about a film collection; the id belongs in config, not scattered through the code.

**9.1's acceptance spends real money on the owner's key.** One live call is enough to satisfy
it — do not loop.

### Batch 31 — AI assistant, tools + chat 🔴
**Covers Phases 9.2, 9.3 and 9.4:**

> **Phase 9.2: Tool Definitions** 🔴
> - Tool schemas for major endpoints (search, add_wanted, log_watch, etc.)
> - Role-aware tool filtering (admin vs viewer)
> - **Acceptance:** Tool list differs correctly between admin and viewer
>
> **Phase 9.3: Chat UI** 🟢
> - Conversation list and detail
> - Streaming response display
> - Floating chat button on every page
> - **Acceptance:** User sends message, streamed response renders progressively
>
> **Phase 9.4: Tool Execution with Confirmation** 🟢
> - When Claude calls a write tool, UI confirms before executing
> - **Acceptance:** "Add X to wanted list" prompts confirmation; cancelling aborts

**This is the batch `DECISIONS.md` #12 warned about** — the second consumer that would reopen
the response-envelope question. It does not: tools call the same endpoints the web app calls,
through the same schemas. If a tool wants a shape no endpoint returns, that is a finding to
report, not a reason to add an envelope.

**9.4's confirmation is a safety boundary, not a nicety.** A write tool must not execute
before the user confirms, and cancelling must leave nothing behind. Batch 36's command
palette already dropped its AI-conversations index waiting for this batch.

### Batch 32 — Voice input 🟢
**Covers Phase 9.5:**

> **Phase 9.5: Voice Input** 🟢
> - Web Speech API integration
> - Mic button, transcribes to text input
> - **Acceptance:** Tapping mic, speaking a query, sends correct transcription

**Depends on Batch 31 existing** — the transcription is sent to the chat input, so building it
first is a microphone button wired to nothing. `microphone=(self)` has been live in
`vercel.json` since Batch 2, so no hosting change is needed.

**Its acceptance needs a human speaking into a microphone** and is therefore **deferred to the
owner**, like 6.2.

### Batch 25 — Photo uploads 🟢
**Covers Phase 3.10:**

> **Phase 3.10: Photo Uploads** 🟢
> - Upload to Supabase Storage (max 5 per item, 5MB each)
> - Camera capture or file picker on mobile
> - Gallery display on detail page
> - **Acceptance:** Upload succeeds; photos appear in gallery; deletion works

**The storage line in that phase is dead.** There is no Supabase project (`DECISIONS.md` #17)
and the owner settled storage as **Neon** on 2026-09-09 — photo bytes in Postgres, served
through the API. That makes three changes to the phase as written:

- **A new `item_photos` table**, not §3.4's `photo_urls` JSONB array of external URLs.
- **A ~300 KB per-photo cap after server-side resize** (owner, 2026-09-09). The spec's raw
  5 MB × 5 × 1,857 ≈ 46 GB is not sensible in a database that is 35 MB today; at 300 KB the
  worst case is ≈ 2.8 GB and the realistic case under 200 MB.
- **No CSP change is needed.** Images come from the API origin, which `connect-src` already
  allows — so the second half of Group H's `vercel.json` note is retired. Serve them with a
  strong `ETag`/`Cache-Control` so Batch 8's service worker caches them; there is no CDN in
  front of Postgres.

### Batch 20 — Price scraping + drop alerts 🟡
**Covers Phases 5.5, 5.6 and 5.8:**

> **Phase 5.5: Daily Price Scraping Job** 🟢
> - APScheduler job running daily
> - Iterates through active wanted items × enabled retailers
> - Inserts price_checks rows
> - **Acceptance:** First overnight run completes; same-day `price_checks` row count ≈ (active wanted items × enabled retailers) within ≤ 10% failure margin; failures logged with retailer + reason.
>
> **Phase 5.6: Price Drop Trigger & Push Notification** 🔴
> - Postgres trigger after price_check insert: if price ≤ max_price and not notified, queue push
> - Web Push via pywebpush with VAPID
> - Service worker shows notification
> - **Acceptance:** Setting max_price above current price and running scrape triggers a push on test device
>
> **Phase 5.8: Daily Aggregation Job** 🟢
> - Nightly job rolls price_checks > 90 days old into price_history_daily
> - **Acceptance:** After backdating test data, rows > 90 days are aggregated and raw rows removed

**Recovered late.** `STATUS.md` claimed all eight of the overnight batches had their criteria
here; only six did. These are verbatim from §16 at `d94a6b8~1`, like the others.

**Four things the April spec no longer knows.**

- **5.5's acceptance is superseded by `DECISIONS.md` #112**, decided before this batch was
  built and on the evidence of #111's live run. It now reads: *the same-day row count is ≈
  (attempted pairs − not-stocked pairs) within a ≤ 10% failure margin, with every failure
  logged with its retailer and reason.* As originally written it assumed every shop stocks
  every film, which no shop does — 7 wants × 5 shops predicted 35 rows and the correct
  answer was 6.
- **"APScheduler job running daily" is dead.** `DECISIONS.md` #60 rules out an in-process
  scheduler: it runs once per container, so a second instance silently doubles every scrape.
  The schedule is a Railway cron and therefore an owner action. This batch ships the endpoint
  and leaves the cron on `OWNER-ACTIONS.md` — which is also why *"first overnight run
  completes"* cannot be met by an agent.
- **5.6's "Postgres trigger" cannot work as described.** A trigger runs inside the
  transaction and cannot make an HTTP request to a push service; at most it could write a
  queue row. Batch 11 already built that queue — the `notifications` outbox — so the drop
  detection belongs in the scrape path, writing a `deals`-category notification. "Web Push
  via pywebpush" is likewise superseded: #115 implements RFC 8291 on `cryptography`, and the
  service worker already shows the notification.
- **5.6's acceptance needs a real device** and is **deferred to the owner**, like 6.2. What
  can be proved here is that a price at or below `max_price` queues exactly one notification,
  that a second scrape at the same price queues none, and that the payload reaches the send
  path.

**One category question this batch settles.** §3.19 designs `price_drops` and `deals` as
*separate* toggles — the first for the wanted list, the second for Batch 22's deals feed.
Batch 11 shipped a single `deals` category, matching §6.1's own acceptance wording
("disabling deals stops deal pushes"), and this batch is its sender. **Batch 22 owns adding a
second category for the feed** if it wants one; it must not quietly reuse this one.

**5.8 needs a table that does not exist.** §3.18 designs `price_history_daily` — `wanted_id`,
`retailer_id`, `date`, `min_price`, `max_price`, `avg_price`, `check_count` — and nothing has
created it. Its acceptance ("after backdating test data") is fully provable in CI, unlike the
other two.

### Batch 20b — Shops that answer 429 🟡 — **shipped: first half 2026-10-01 (`548160f`, [#19](https://github.com/CraigR973/mcu-app/pull/19)), second half 2026-10-02 (`abc17d6`, [#25](https://github.com/CraigR973/mcu-app/pull/25)); read back 3 Oct: a minute's wait does not get past the limit**
**As shipped (second half), live 2 Oct 23:51 UTC with migration 045:** a refused request waits for the shop's
`Retry-After` (up to 90 s, never less than the usual 2 s; a missing, unreadable or longer value
keeps 2 s and says so) before its one retry; the sale-page check follows the same rule;
`scrape_runs.refusals` records each refusal's ask, wait and whether the retry got through, and
the job's summary counts them; the nightly run commits before each request and checks a pooled
connection before reuse; "Run now" keeps 2 s. Local gate and CI green first time (1,750 API
tests, warnings unchanged at 178; web 464, shared 123).

**The first night under the second half, 3 Oct 03:03–03:31 UTC (read back the same morning;
the second half's last criterion).** No shop switched off. 40 asked, 6 priced, 25 refused.
**27 refused requests waited the 60 seconds asked; 2 got through** (Powerhouse's Romper
Stomper, Second Sight's Bad Lieutenant) **and 25 were refused again**: 101 Films 9 of 9,
Powerhouse 8 of 9, Second Sight 8 of 9. On 2 Oct the 2-second retry got 4 of 29 through, so
waiting is no better. Every one of the 52 refused requests said `retry-after 60; server
cloudflare; title "Too many requests"`, none `cf-mitigated`. Each Shopify shop refused its first
request (Powerhouse 03:03:23, 101 Films 03:12:36, Second Sight 03:22:26), 101 Films after nine
minutes in which the app asked it nothing. The run took 28 minutes, against 2.
- **So the limit is not this app's to wait out: most refusals survive a minute.** The one option
  left is a fixed outbound address for `cron-scrape`, a Railway setting and so a hosting
  change: Craig's call (`OWNER-ACTIONS.md` 28). Whether a fixed address cures it is not proved.
- **22c waits on that call:** a sale's further pages at Second Sight would meet the same limit.
- 101 Films and Second Sight are `blocked` (Second Sight's count still 1); Powerhouse priced one
  want and is `success`. Batch 21 is unchanged.

**As shipped (first half):** the fetcher raises a refusal for a `429`, carrying `Retry-After`,
`cf-mitigated`, `server` and the page's title; the runner logs each refused request
(`scrape_refused`), keeps refusals out of the auto-disable count, and records a shop that only
refused as `blocked`, its count left alone. A genuine failure beside refusals still counts.
No migration: Batch 16's CHECK already allowed `blocked`. Local gate and CI green first time
(1,719 API tests, warnings unchanged at 178; web 458, shared 119). ~~**Open:** the 2 Oct
03:00 UTC check read back~~ **read back 2 Oct: no shop switched off; every refusal a 60 s
`Retry-After`** (below). **The second half is built from that one night**, at Craig's word on
2 Oct 23:28 UTC, so the 3 Oct check is its first night (#240). 101 Films and Powerhouse went
back to 0 failures on 2 Oct.

**Written 30 Sep at Craig's word ("yes, write a batch for this"); builds at his go, after the
1 Oct 03:00 UTC shop check, which is its first evidence.** Opus 5 · high / GPT-5.6 Sol ·
High: request pacing against live shops. Criteria authored 30 Sep, before any code (#54).

**Found 30 Sep** (Batch 21's session): the 03:00 UTC shop check got `429 Too Many Requests` on
21 of 33 checks, from Second Sight, 101 Films and Powerhouse, the three Shopify shops. Zavvi
and Arrow answered normally, and the six nights before had no `429` at all. 101 Films and
Powerhouse each took a consecutive failure, and **three such nights would switch a working
shop off**. The run asked 33 questions against 22 on earlier nights, with one second between
requests to the same shop; two wants added on 30 Sep (Batch 21's) take 1 Oct's to about 50.

**Diagnosis, 1 Oct (read-only: `scrape_runs`, `retailers`, the `cron-scrape` logs of both
nights, and the fetcher).** This is the first criterion below, written before any code.

| Night | Refused | 101 Films | Powerhouse | Second Sight | Zavvi, Arrow |
|---|---|---|---|---|---|
| 30 Sep, 8 wants | 21 of 33 | 8 of 8 | 7 of 8 | 6 of 8 | none |
| 1 Oct, 10 wants | 29 of 42 | 10 of 10 | 10 of 10 | 9 of 10 | none |

- **Which shops:** the three Shopify shops, every failure a `429`. No other reason appeared.
- **After how many requests: none.** The run goes shop by shop, so a shop's first request of
  the night comes after a quiet day, and both nights each Shopify shop refused that first
  request and its retry two seconds later. The few that got through came mid-list (1 Oct:
  only Second Sight's Romper Stomper). So **this run's own pace is not what trips the limit**,
  and a longer pause alone is unlikely to cure it. Something changed between the 29 and 30
  Sep checks: perhaps Railway's shared outbound address, perhaps the shops' platform now
  refusing a client that names itself a price checker (`USER_AGENT`). The logs cannot say.
- **How quickly:** 1 Oct's run took 125 s. Powerhouse 03:02:43–03:03:15, Zavvi to 03:03:31,
  101 Films to 03:04:03, Arrow to 03:04:16, Second Sight to 03:04:48. A refused want costs
  two requests two seconds apart, then the one-second pause: about 3 s a want, ~30 s a shop.
- **`Retry-After`: unknown.** The fetcher raises on any status from 400 with the code alone
  (`fetcher.py`, "The page answered 429") and keeps no headers, and the job logs only its
  summary, never a request. The batch has to record it.
- **Auto-disable is one night away:** 101 Films and Powerhouse stand at 2 consecutive
  failures and Second Sight at 1, so a third refused night (2 Oct, 03:00 UTC) switches 101
  Films and Powerhouse off.
- **It also holds up Batch 21**, whose third want needs a Shopify shop's price.

**The first night under the first half, 2 Oct 03:04 UTC (read back the same night; the
first half's last criterion).** No shop was switched off: 101 Films and Powerhouse each got a
price and went back to 0 failures, and Second Sight was recorded `blocked` with its count
held at 1. 42 asked, 7 priced, 25 refused (Powerhouse 9, Second Sight 9, 101 Films 7), Zavvi
and Arrow none. **Every refusal said the same: `retry-after 60; server cloudflare; title "Too
many requests"`**, and none carried `cf-mitigated`. So it is a rate limit asking for a
minute, not a challenge page or a block.

- **Still refused from the first request.** Each Shopify shop's first request of the night
  (Powerhouse 03:04:10, 101 Films 03:04:41, Second Sight 03:05:50) was refused, after a day
  in which the app asked them nothing. Whatever fills the limit is not this run's pace:
  most likely traffic sharing Railway's outbound address.
- **The limit leaks.** 54 refused requests in all; 4 of the 29 retries two seconds later got
  an answer (Powerhouse's Romper Stomper, priced; 101 Films' Castle Freak, priced, and two
  more), and Second Sight answered Romper Stomper first time.
- **What it suggests for the second half:** honour `Retry-After` (60 s, bounded) before the
  one retry, instead of the 2 s pause. A refused night would take up to about 30 minutes
  (29 refused wants × 60 s), unattended at 03:00. If refusals survive a minute's wait, the
  limit is the shared address's, and only a different outbound address would cure it, a
  Railway setting and Craig's call. 22c's extra pages would meet the same limit, so it
  waits for that answer.
- **Batch 21 is unchanged:** still 2 of the 3 wants (Dog Soldiers has Zavvi only).

**Split in two at Craig's word, 1 Oct ("2) yes"), after that diagnosis.** The first half
ships before the 2 Oct check, so no shop is switched off by refusals; the pacing half, and
22c after it, wait for two nights of the evidence the first half records.

**First half — acceptance:**
- A `429` is a refusal, not a broken scraper: it never counts towards auto-disable. A shop
  whose requests were all refused or answered "not here" is recorded as `blocked` (a status
  Batch 16 declared and nothing used), its failure count left as it was.
- Each refusal records what the shop sent back: `Retry-After`, `cf-mitigated`, `server` and
  the page's title, in the run's failure record and in a log line per refused request.
- The run's record still names every shop and want refused, and the job's summary counts
  them.
- Tests. Gate green.
- The first scheduled check after the merge is read back from `scrape_runs` and the job's
  log: no shop switched off by `429`s, and what the refusals carried.

**Second half — acceptance, rewritten 2 Oct 23:40 UTC from the 2 Oct night, before any code
(#54).** The proposal Craig said go to on 2 Oct, built from one night rather than two at his
word, so the 3 Oct check is its first night (#240). It replaces the 30 Sep draft, whose
per-shop pause the diagnosis ruled out: the shops refuse the first request of the night, so
spacing this run's own requests cannot be the cure.
- A refused request waits for the shop's `Retry-After` before its one retry, instead of two
  seconds, bounded at 90 seconds; a missing or larger value keeps today's pause and says so
  in the refusal's record. Still one retry, still sequential per shop.
- The sale-page check (22b) follows the same rule.
- The run's record says, for each refusal, whether the retry after the wait got through.
- **The nightly run holds no database transaction while it waits, and checks a connection
  before reusing it.** A refused night can leave the database untouched for ten minutes at a
  time (one shop's ten wants), longer than a network path reliably keeps an idle connection;
  a dropped connection would lose the whole night. *(Added from reading the runner: the
  proposal did not cover it.)*
- **"Run now" on /retailers keeps today's two-second pause**, and its record says it did: a
  run from the phone cannot hold a request open for half an hour. Only the scheduled check
  and the sale-page check wait.
- The first scheduled check after the merge is read back: refusals that survive a minute's
  wait are named. If most do, tell Craig, with the remaining option: a fixed outbound address
  for Railway, a hosting change and his call.
- Tests (a refused request's wait is bounded, honoured and reported). Gate green.

*Its cost, as stated on 2 Oct:* a refused night may take up to about 30 minutes at 03:00,
unattended (3 shops × 10 wants × a minute). 22c still waits for this half's read-back.

### Batch 35 — Movie night 🔴
**Covers Phases 8.3 and 8.4:**

> **Phase 8.3: Movie Night Session Start** 🟢
> - Session creation with filters
> - Invite URL for second user
> - **Acceptance:** Session created; second user joins via URL
>
> **Phase 8.4: Movie Night Swipe & Match** 🔴
> - Swipe-like UI (cards, left/right gestures)
> - Real-time sync via Supabase Realtime
> - Match detection, notification to both
> - **Acceptance:** Both users swiping on the same film triggers a match notification

**Recovered late**, with Batch 20's, for the same reason.

**Three things the April spec no longer knows.**

- **"Real-time sync via Supabase Realtime" is superseded by `DECISIONS.md` #113.** There is
  no Supabase project — #17 moved the database to Neon — and the owner settled this as
  Postgres `LISTEN`/`NOTIFY` with SSE to the browser. No new service, no new credential, no
  hosting step. **#113's constraint is the one to respect:** `LISTEN` occupies a connection,
  so the listener must not borrow from the request pool for the life of a session, or the
  pool exhausts and the whole app appears to hang.
- **"Notification to both" now has a transport.** Batch 11 shipped Web Push and a
  `movie_night` category, so a match can genuinely notify. Whether the *acceptance* is met by
  an agent depends on how the match is signalled: an in-app match rendered over SSE is
  provable here; a **push received on a device** is not, and is deferred like 6.2 and 5.6.
- **"Invite URL for second user" has a second user.** Mark's PIN was set on 2026-09-09, so
  both profiles can sign in — which is what a two-person acceptance criterion needs.

### Batch 23 — Specs scraper + display 🟡
**Covers Phases 3.7, 3.8 and 3.9:**

> **Phase 3.7: Blu-ray.com Specs Scraper** 🔴
> - Scrape video_specs, audio_specs, special_features, region_code, release_label
> - Handle multiple editions (prompt admin to pick)
> - Cache URL for future re-syncs
> - Unit tests with mocked Blu-ray.com HTML
> - **Acceptance:** Scraper run against 10 known **live** Blu-ray.com URLs persists correct specs to the matching `collection_items` rows; row counts verified — not just unit tests against fixture HTML.
>
> **Phase 3.8: Spec Display & Quality Badges** 🟢
> - Badge components for resolution, HDR, audio
> - Displayed on collection cards and detail page
> - Hover/tap shows full spec list
> - **Acceptance:** A 4K disc with Dolby Vision + Atmos shows three distinct coloured badges
>
> **Phase 3.9: Spec-Based Filtering** 🟢
> - Filter panel: "Dolby Atmos only", "Dolby Vision 4K only", "Arrow Video", "Region-free"
> - URL-encoded so filters are bookmarkable
> - **Acceptance:** Applying "Dolby Vision" filter reduces list to only DV-capable discs

**Read `DECISIONS.md` #108 and #110 together before writing a line.** #110 is the governing
one: this is an **owner-accepted risk, not a permitted access**. #108's closing claim that it
"stays inside what the site allows" was wrong — absence from `robots.txt` is not permission,
and the site's Legal Notices prohibit automated reuse.

**#110's bounds are the specification here.** Exact release URLs only; never the disallowed
search routes; no authentication, no images/scripts/advertising, no prices, reviews, ratings
or member content; no republished dataset, no IP rotation, no CAPTCHA solving, no evasion of
an access control. Requests sequential and conservatively rate-limited. Successful results
cached indefinitely rather than refreshed automatically. **Every derived row records its
source URL and fetch time** so the data can be identified and removed. A `403`, a `429`, an
explicit objection or a hosting complaint **halts the whole integration**, and resuming needs
a new owner decision.

**Three extraction facts, measured against a real page on 2026-09-09** (`#108`):

- The page **also carries prices** — a list price and an Amazon price, in the same document.
  #91 ruled those out as third-party numbers nobody can pay, and #110 forbids extracting
  them. The temptation is unusually close to hand.
- **Audio and subtitles appear twice** in the flattened text, behind `(more)`/`(less)`
  toggles. Extraction must target the DOM node, not the page text.
- **`Special Features` was absent** from that page despite being one of 3.7's five fields, so
  it is nullable rather than assumed.

**The ten URLs come from browse pages** (owner, 2026-09-09), which `robots.txt` does not
disallow — only `/search/` and `/movies/search.php` are. List every URL fetched in the
close-out report.

### Batch 28 — eBay integration 🔴
**Covers phases 4.1 and 4.3**, verbatim from §16 at `d94a6b8~1` (`DECISIONS.md` #54):

> **Phase 4.1: eBay API Integration** — eBay Browse API client (OAuth app credentials) ·
> Search sold listings endpoint · Median price calculation for title + format + UK.
> **Acceptance:** Querying "Blade Runner 2049 Blu-ray" returns a reasonable UK median price
>
> **Phase 4.3: eBay Listing Creation** — Option A (preferred): eBay Sell API draft listing
> creation · Option B (fallback): pre-filled eBay listing URL · Admin publishes from eBay.
> **Acceptance:** A draft listing appears in admin's eBay account (or URL opens with
> prefilled fields)

**Three things about those criteria are already known to be wrong, and are recorded here so
the batch does not rediscover them.**

**"Search sold listings endpoint" cannot be built.** `DECISIONS.md` #16 settled this in
April and #126 re-confirmed it: Marketplace Insights is closed to new applicants, and since
late August 2026 sold listings need a login. Built against **active listings**, labelled
**"current asking prices"**.

**Phase 4.3's Option A describes something eBay does not do.** There is no API to create a
Seller Hub *draft*: an Inventory API offer is invisible until it is **published**, at which
point it is a live listing with a buyer on the other end, not a draft for review. Option A
would also require storing a refreshing eBay **user** token for a real selling account and
opting that account into business policies — the same class of secret Batch 33 is
deliberately sequenced late for. **Option B is the primary path, not the fallback**, and
inverting §5.6's stated preference is a decision the batch must record. ⚠️ **Nobody has yet
confirmed the pre-filled URL still accepts prefill parameters** — `ebay.co.uk/sl/prelist/suggest`
is the current entry point, and an attempt to check it from an agent was served an error
page rather than the form. **Check that in a browser before starting the batch**: if prefill
is gone, 4.3 has no remaining path and Batch 28 is 4.1 alone.

**"A reasonable UK median price" is not one number.** See #129 — segment by format and
`conditionId`, report the sample size, and treat a result failing the match assertion as a
failure rather than data. Sandbox cannot prove this criterion (its GB catalogue is empty),
so **4.1's acceptance is a live production call** — an owner-run acceptance in the same
shape as Batch 19's, not something an unattended agent signs off.

**What is already built and proven**, ahead of the batch: a production keyset, the
client-credentials token mint (`expires_in` 7200 — token caching is net-new versus
`src/tmdb/`, whose token is static), and `POST|GET /api/v1/ebay/account-deletion`
(`DECISIONS.md` #127). The client belongs in a new `src/ebay/` package modelled on
`src/tmdb/`, **not** as a retailer in Batch 19's scraper framework: eBay is a fixed host
with a typed API, `check_shape` exists for HTML drift, and #16's accepted ToS exposure
covers retailers rather than eBay.

## Criteria recovered for the seven remaining batches *(2026-09-11)*

`DECISIONS.md` #54 says a planned batch's criteria are recovered verbatim from §16 at
`d94a6b8~1` and written here **before** any code is written, and that whoever runs a batch
does this first. Batch 28's were recovered on 2026-09-10 and are above. These are the other
seven — **21, 22, 24, 29, 33, 34 and 38** — recovered together on 2026-09-11 so that no
remaining batch starts without something to verify against.

**One deliberate deviation from verbatim, following Batch 11's precedent:** the tier emoji
is kept and the `Sonnet 4.6` / `Opus` annotation is dropped. Those names are the decay this
ledger exists to stop; the model each batch actually needs is in the table above.

**Nothing here was re-authored.** Where the repo or the live system already contradicts a
criterion, that is recorded *underneath* the quote, never folded into it.

### Batch 21 — Price history charts 🟢
**Wave 1 review, 12 Oct:** still two wants qualify (Castle Freak; Dead Man's Shoes), and Dog
Soldiers stays one Second Sight day short while the Shopify shops refuse. **Dead Man's Shoes'
want sits on the 1940 film while its shop prices are the 2004 film's** (R4, R5): settle it with
the film page's Correct match before charting it.

**Status 26 Sep (Group U, step 6): the clock started on 24 Sep.** The scheduled scrape first
ran at 03:04 UTC that day, after the jobs fix (#204), and had three days by 26 Sep; the
seventh is the 30 Sep run. The check below still applies: count `trigger=cron` days in
`scrape_runs` before starting, not the calendar.

**Checked 1 Oct (`live_sql`): the days hold, the breadth does not.** Eight `trigger=cron` days
(24 Sep–1 Oct), none errored. **Two** wants have prices from two shops on two days or more:
Castle Freak (101 Films 8 days, Zavvi 8) and Dead Man's Shoes (Second Sight 9, Zavvi 8). Dog
Soldiers has Zavvi on one day and Bad Lieutenant nothing; Zavvi and Arrow found no more of
them, so the shops left to price them are the Shopify ones, refusing since 30 Sep (20b). So
21 does not start on 2 Oct unless those shops answer.

**Checked 4 Oct (`live_sql`): still two.** Eleven `trigger=cron` days (24 Sep–4 Oct). Castle
Freak (Zavvi 11, 101 Films 9) and Dead Man's Shoes (Zavvi 11, Second Sight 9) qualify; Dog
Soldiers has Zavvi on 4 days and Second Sight on 1, one Second Sight day short. Craig left the
fixed outbound address for now (`OWNER-ACTIONS.md` 28, #247), so the Shopify shops stay
mostly refused; **the route to a third is a want that both Zavvi and Arrow sell**, Craig's to
add, which qualifies two nights later.

**Covers Phase 5.7:**

> **Phase 5.7: Price History Charts** 🟢
> - Chart per wanted item showing price over time across retailers
> - Recharts line chart
> - **Acceptance:** After 7+ days of **real scheduled scrapes** (not back-dated fixtures), chart renders multi-retailer time-series for ≥ 3 wanted items.

**The clock has not started, and the criterion is a wall-clock gate.** Measured against live
Neon on 2026-09-11: `scrape_runs` holds **one** row and its trigger is `manual`;
`price_checks` holds **14** rows across **two** days — 2026-09-09 (8) and 2026-09-10 (6) —
both hand-run. `cron-scrape` was applied on 2026-09-10 at `0 3 * * *` and **has produced no
row**, 19 hours past its first scheduled fire. So §5.5 is not merely pending, and 5.7 cannot
begin until seven days of `trigger=cron` runs exist. **Check `scrape_runs` before starting,
not the calendar.**

**"Not back-dated fixtures" is in the criterion for a reason** — do not seed the table to
reach green. That is the guardrail in `AGENTS.md`, stated inside the acceptance text itself.

**The other half of the criterion is already satisfied.** `price_checks` covers **8 distinct
wanted items** across **5 retailers**, against a floor of 3 — so when the days exist, the
breadth will too.

**"Recharts line chart" conflicts with a shipped decision, and the batch must resolve it
out loud.** Batch 14 drew §13.1's charts in CSS and wrote down why, in `StatsPage.tsx`:
*"No chart library"* — three of its four populated charts are "a label and a proportion",
which a flex row expresses exactly. A multi-retailer time-series is **not** that shape. So
this batch either adds the charting dependency Batch 14 declined or hand-rolls SVG;
`apps/web/package.json` carries neither Recharts nor any other charting library today.
Whichever way it goes is a `DECISIONS.md` entry, not a silent `pnpm add`.

### Batch 22 — Deals feed 🟡
**Covers Phases 5.9 and 5.10:**

> **Phase 5.9: Deals Scraper & Feed** 🔴
> - Scrape retailer deals pages (not just wanted items)
> - Match to TMDB, store in `deals` table
> - Skip already-owned
> - **Acceptance:** Deals scraper run against live retailer pages populates the `deals` table with ≥ 20 rows from ≥ 3 retailers; UI renders them with posters; "skip already-owned" verified against the real `collection_items` table.
>
> **Phase 5.10: Deal Filtering & Actions** 🟢
> - Filters: genre, discount %, retailer, format
> - One-tap dismiss / add to wanted list
> - **Acceptance:** Admin can curate the deals feed; dismissed items don't reappear

**5.9's acceptance is a live third-party run, so it is an owner action** — the same shape as
Batch 19's checkpoint and Batch 23's §3.7, and `docs/agent-commands/group-start.md` puts
live retailer runs in the owner's hands. The ToS exposure itself is already accepted for
retailers (`DECISIONS.md` #16); what stays the owner's is pressing the button.

**The `deals` table does not exist** — verified against live Neon on 2026-09-11. It is a
net-new migration, not an existing table to fill.

**"≥ 3 retailers" is reachable and the ceiling is known.** 10 retailers are seeded, **5 are
enabled and verified**, and 4 were ruled out permanently by page-shape checks on 2026-09-09
(`DECISIONS.md` #91). Amazon is among the four that are out.

**The risk note above applies in full.** A deals page that changes layout does not error —
it selects the wrong node and stores a plausible wrong discount, which then feeds the feed.
Batch 19's `check_shape` is the pattern; extend it rather than adding a bare success counter.

### ~~Batch 22b — Retailer sale pages that work~~ 🟡 **shipped 2026-09-30 (`eb51568`)**
**Acceptance: eight of eight met; §5.9's own acceptance stays Craig's run** (`OWNER-ACTIONS.md`
1e). Zavvi reads its "2 for £30 4K" listing, at Craig's pick (the criterion below is
amended to say so), and Second Sight its sale collection's compare-at price, both proved
against three trimmed captures of the real pages (#224). `check_page_shape` is unchanged,
line for line. Arrow's, Powerhouse's and 101 Films' configs are unchanged and pinned by a
test. "Check sale pages" and "Save deals" are on /retailers, admin-only, the response
parsed by `dealsRunSchema`; browser check at 375 and 1,280 px from a captured real dry run.
Production's retailer rows carry the new configuration (apply-built-ins, 13:44 UTC: three
values changed, none set by hand). Local gate and CI green, after a pre-existing red
(PyJWT's advisories) was fixed on its own branch first (`6a8197b`).

**Found on the way, fixed where they live (#225, #226):** the deals runner handed the
same-site guard a URL, which failed every one of Second Sight's and 101 Films' own
listings; a card at a single price was kept as a deal; the film matcher missed titles with
a shop's word ("includes", "download") or a remake's year ("The Mummy (2017)"); and
#153's "Zavvi's title is a heading" came from a test helper. **What a check should show
today**, from the captures against the real collection: 5 deals from 2 shops, 7 already
owned. §5.9's ≥ 20 from ≥ 3 is out of reach from the first page of two shops.

**Proposed and started 28 Sep at Craig's word, for `OWNER-ACTIONS.md` 1e. Group U, step 3b.**
Opus 5 · high / GPT-5.6 Sol · High: scraper selectors against live markup, where Batches 19
and 22 each found real defects. Criteria authored 28 Sep, before any code, so `DECISIONS.md`
#54 is met rather than waived.

**Found 13 Sep** (`STATUS.md` Log): Batch 22's sale-page scrape has never written a row.
Zavvi's deals URL (`/sale.list`) 404s; its real page is `/c/offers/flash-deals/film/`, with
Current price / RRP pairs. Second Sight's sale collection has real Regular/Sale pairs (Dog
Soldiers £24.99 → £17.99), but the selector does not match that theme, so `check_page_shape`
rightly refused the whole page. Arrow and Powerhouse offer only bundles ("2 for £40", "3 for
20% off"). 101 Films had nothing on sale. And nothing on screen runs the scrape:
`runDealsScrape` is in the web client, but no page calls it.

**Craig's choice (28 Sep):** fix Zavvi and Second Sight, and add a button so he can run the
scrape from his phone. Arrow and Powerhouse stay as they are: the feed holds one disc's
was/now price, and a bundle has none, so no bundle extraction is built. 101 Films stays as it
is: correct, with nothing on sale.

**Acceptance:**
- ~~Zavvi's deals URL is its live flash-deals film page~~ Zavvi's deals URL is its "2 for
  £30 4K" listing, and its selectors read that page's price pair. *Amended at Craig's word,
  30 Sep:* on 28-30 Sep the flash-deals page was a landing page of two carousels, six discs,
  five of them already owned. He chose to read the two listings its carousels lead to and
  take the larger: "2 for £30 4K", 169 discs with each disc's own price and RRP (the other,
  "Awards Winners", held two).
- Second Sight's selectors read its sale collection's Regular/Sale pair.
- Both are proven by tests against trimmed copies of the real pages, saved as fixtures
  beside `zavvi_search_two_price_shapes.html`.
- `check_page_shape` is not weakened.
- Arrow, Powerhouse and 101 Films are unchanged.
- An admin-only "Check sale pages" on the Retailers page previews (a dry run, which writes
  nothing) and shows the three numbers and each shop's found, kept and reasons. "Save deals"
  appears only after a preview. The response parses through a zod schema in
  `packages/shared`.
- Production's retailer rows carry the new configuration after the deploy.
- Tests. Gate green.

**The live requests, and their bounds** (Craig's go, 28 Sep): read-only fetches of Zavvi's
flash-deals film page and Second Sight's sale collection, and their second pages only if the
fix needs pagination. A handful, at least 5 seconds apart, with the scraper's own
User-Agent; stop at a 403, a 429, a bot wall or a CAPTCHA. Everything else runs against the
fixtures. **§5.9's live acceptance (≥ 20 deals from ≥ 3 retailers) stays Craig's run**, from
the new button.

### Batch 22c — Every page of a sale 🟡
**Wave 1 review, 12 Oct:** with no job running it, the one manual run's six Zavvi deals of
30 Sep stayed on the Deals page, undated, for 11 days. X1 expires a shop's deal two days
after it was last seen, so a reopened 22c should schedule the check, not rely on the button.

**Parked 4 Oct, with `OWNER-ACTIONS.md` 28, at Craig's word ("yes lets leave it for now",
#247).** A sale's further pages at Second Sight meet the same refusals as the nightly check,
and the one hosting fix Railway offers needs its Pro plan without being sure to work. It
builds again only if Craig reopens 28.

**Written 30 Sep at Craig's word ("2) yes"); builds at his go, after 20b, whose pacing it
uses.** Opus 5 · high / GPT-5.6 Sol · High: selectors against live markup again. Criteria
authored 30 Sep, before any code (#54).

**Found 30 Sep** (22b): the sale-page check reads the first page of each shop's sale.
Zavvi's "2 for £30 4K" listing runs to 169 discs over seven pages, twelve served on each,
and Second Sight's sale collection to 80 over five. From the first pages a check finds about
5 new deals, against §5.9's 20.

**Acceptance:**
- The check follows each shop's next-page link until the last page, a page with no cards,
  or 10 pages a shop, whichever comes first. The link is a per-shop selector in the built-in
  sale config; both pages captured for 22b carry it as `a[aria-label='Next page']`.
- Requests to one shop keep 20b's pacing, at least 5 seconds apart. A `403` or `429` stops
  that shop, keeps what its earlier pages found, and says so on its line.
- `check_page_shape` judges each page; a page it refuses stops that shop there and is
  reported. It is not weakened.
- Each shop's line says how many pages were read. The new field parses through the zod
  schema, defaulted for an API a deploy behind.
- Arrow, Powerhouse and 101 Films are unchanged: no next-page selector, so one page.
- Proven by tests against trimmed captures of real later pages, each shop's last page among
  them. The live requests are bounded as 22b's were: a handful, at least 5 seconds apart,
  the scraper's own User-Agent, stopping at a `403`, a `429`, a bot wall or a CAPTCHA.
- A check still finishes within two minutes.
- Production's retailer rows carry the new configuration after the deploy.
- Tests. Gate green.

### Batch 24 — Barcode scan + lookup 🟡
**Covers Phases 3.3 and 3.4:**

> **Phase 3.3: Barcode Scanner UI** 🟢
> - Camera access via `getUserMedia`
> - quagga2 or zxing-js barcode reading
> - Display scanned UPC, ready for lookup
> - **Acceptance:** Scanning a real Blu-ray barcode on mobile returns a valid EAN in < 2 seconds
>
> **Phase 3.4: Barcode → TMDB Lookup** 🔴
> - `POST /api/v1/barcode/lookup` endpoint
> - UPC-to-title resolution (try cached mapping, then eBay/Amazon UPC search, then TMDB)
> - Confirmation UI before adding
> - **Acceptance:** Scanning a common Blu-ray returns the correct movie; unknown UPCs prompt manual search

**3.3's acceptance is an owner action.** "Scanning a real Blu-ray barcode on mobile … in
< 2 seconds" needs a phone, a real disc and a stopwatch. An agent can build the decode path
and prove it against fixture images; it cannot sign off the live timing. Say so in the
close-out rather than letting a green gate imply it.

**No hosting change is needed.** `camera=(self)` has been in the `Permissions-Policy` header
since Batch 2 — verified in `vercel.json` on 2026-09-11. This supersedes the group table's
older note that Batch 24 was blocked on a `vercel.json` fix; it never was.

**3.4's lookup chain shipped with one extra certain leg and the unavailable half named
correctly.** It is **confirmed cache → exact collection barcode → eBay Browse → TMDB**:
an already-owned product is a free exact answer before a seller-title search spends quota.
**Amazon does not work** — it is one of the four shops #91 ruled out permanently — so eBay
is the recorded replacement (`DECISIONS.md` #148).

**The confirmation UI is mandatory, not a nicety.** The risk note above expects a low hit
rate on unknown discs and wrong-edition matches; the criterion's own second half — "unknown
UPCs prompt manual search" — is the same requirement stated from the other side.

**`collection_items.barcode` was the scanned value's existing home.** The scanner uses
ZXing `^0.21.3`, pinned below its Node-24 release and loaded only after the camera action.
The real-phone timing and common/unknown-product observations remain owner acceptance in
`OWNER-ACTIONS.md` 1d; shipment on 2026-09-12 deferred those observations, not the criteria.

### Batch 29 — Format upgrade + sale tracking 🟢
**Covers Phases 4.2 and 4.4:**

> **Phase 4.2: Format Upgrade Flow** 🟢
> - After duplicate detection "it's an upgrade" path
> - Flag old format as superseded
> - Show suggested sell price from 4.1
> - Admin adjusts or accepts
> - **Acceptance:** Upgrade path completes in ≤ 3 taps; old item marked `listed_for_sale`
>
> **Phase 4.4: Listing Status Management** 🟢
> - "Mark as sold" action on listed items
> - Auto-archive from active collection
> - **Acceptance:** Marking sold removes from active views, remains in audit/trash

**4.2 depends on Batch 28 and the group order must not be inverted.** "Show suggested sell
price from 4.1" is the eBay median; without Batch 28 there is nothing to show. That
dependency *is* Group I's ordering.

**The schema is already there — this is the rare criterion that needs no migration.**
`collection_items` carries `listing_status`, `ebay_listing_url` and `listing_price`, and a
CHECK constrains the status to `in_collection` / `listed_for_sale` / `sold` / `donated`.
Verified live on 2026-09-11: all **1,857** rows are `in_collection`, so every transition
this batch writes will be the first of its kind. `listed_for_sale`, the exact string the
criterion names, is already a legal value.

**4.4's second half is already served.** Batch 15 shipped trash and the audit UI and proved
an audit trail outliving its subject through a permanent delete, so "remains in audit/trash"
is a wiring job against existing machinery rather than new infrastructure.

**Duplicate detection, which 4.2 hangs off, shipped in Batch 7** as §3.5.

### Batch 33 — Email accounts + OAuth 🔴
**Covers Phases 10.1, 10.2, 10.3 and 10.4:**

> **Phase 10.1: Email Account Model & Encryption** 🔴
> - Supabase Vault or encryption-at-rest for credentials
> - email_accounts CRUD endpoints
> - **Acceptance:** Credentials round-trip through encryption; DB never stores plaintext
>
> **Phase 10.2: Gmail OAuth Flow** 🔴
> - Consent screen, read-only scope
> - Token storage, refresh handling
> - **Acceptance:** Admin connects Gmail; token refreshes automatically
>
> **Phase 10.3: Outlook OAuth Flow** 🔴
> - Microsoft Graph integration
> - **Acceptance:** Admin connects Outlook successfully
>
> **Phase 10.4: Generic IMAP Connector** 🟢
> - IMAP client for iCloud, Yahoo, custom
> - App-specific password input form
> - Instructions linked per provider
> - **Acceptance:** Admin connects an iCloud account using an app password

**This group is deprioritised, not ready.** `OWNER-ACTIONS.md` #7 took Group K off the queue
on 2026-09-09 pending Google and Microsoft OAuth app registrations. Nothing here starts
until the owner says so.

**"Supabase Vault" names a product this app does not use.** There is no Supabase project —
the re-scaffold removed it (`DECISIONS.md` #5, #11) and #113 settled the last thing that
still named it. Encryption at rest is the app's own to build, and every remaining `supabase`
string in the source is a comment explaining its absence.

**The risk note above is stale on one point and it matters.** It says *"Encryption at rest
is net-new — app-starter ships no `cryptography` dependency"*. That was true when written
and is not now: **`cryptography>=50.0.0` has been a direct dependency since Batch 11**, which
needs ECDH and AES-GCM for RFC 8291 Web Push (`apps/api/src/services/webpush.py`). The
library is present and pinned in both locks. **Key management is still net-new** — where the
key lives, how it rotates, and what happens on a key the app cannot read — and that, not the
dependency, is why this batch is `max` effort.

**The sequencing rule holds and its precondition is met.** #16 requires this to land after
Batch 3's rate limiting and fail-closed config, which shipped.

**`email_accounts` does not exist** — verified live on 2026-09-11.

### Batch 34 — Email parsers + scanning 🔴
**Covers Phases 10.5, 10.6, 10.7 and 10.8:**

> **Phase 10.5: Retailer Email Parsers** 🟢
> - Templates for eBay, Amazon, HMV, Zavvi order confirmations
> - Extract title, price, date
> - **Acceptance:** Each parser passes against (a) a fixture sample email in unit tests AND (b) at least one **real received email** from the admin's connected mailbox, both producing correct structured output.
>
> **Phase 10.6: LLM Fallback Parser** 🔴
> - Claude API call to extract order fields from unfamiliar email templates
> - **Acceptance:** A novel retailer's email is parsed into structured data
>
> **Phase 10.7: Scheduled Scan Job** 🟢
> - Per-account scheduled scan
> - Fuzzy match to wanted_list
> - purchase_candidate creation
> - **Acceptance:** Scanning a mailbox with a known wanted item creates a candidate
>
> **Phase 10.8: Candidate Review UI** 🟢
> - Review queue with confirm/dismiss actions
> - Confirm creates collection_item and removes wanted entry
> - **Acceptance:** Admin reviews and processes candidates; state updates correctly

**10.5's acceptance has two halves and only one is an agent's.** The fixture unit tests are;
*"at least one real received email from the admin's connected mailbox"* needs a connected
mailbox, which needs Batch 33, which needs the deprioritised registrations. **This is the
same trap Batch 23 fell into** — `test_specs.py`'s fixture was invented to match the parser,
so eleven tests passed against markup the site has never served (`DECISIONS.md` #122).
Capture real emails as fixtures; do not write fixtures to match the parser.

**10.6 must route through Batch 30's client, not call Anthropic directly.** That client
validates the model id against a priced list at load, checks both the message and dollar
ceilings *before* the call, and logs every call including failures. A second call path
bypasses all three — and an email scan is exactly the unattended loop those ceilings exist
for.

**10.7's schedule is a Railway cron, not an in-process timer** — `DECISIONS.md` #60, and
#119's correction that an admin-authed endpoint is not callable by a cron. It needs to be a
command, as `daily_scrape` and `run_reminders` are.

**`purchase_candidates` does not exist** — verified live on 2026-09-11.

### ~~Batch 38 — E2E suite~~ 🟢 **built 2026-10-19 ([#94](https://github.com/CraigR973/mcu-app/pull/94)); the last batch of Group X**
**Acceptance: met on Chromium and Firefox locally and on CI, and on WebKit on CI only (Playwright
has no WebKit for macOS 13, so it cannot run on Craig's Mac). Four things cannot run, and a
case is skipped on WebKit for each of two reasons; all are listed below, none dropped.** Choices,
findings and the incident are in `DECISIONS.md` #285; how to run it is `apps/e2e/README.md`.

**What was built.** `apps/e2e` boots the production web build against the real API on a throwaway
Postgres with every outside service faked (`apps/api/tests/outside_world`), in three browsers,
plus the five cron jobs run as `python -m src.scripts.<job>`. A seventh CI job, `e2e`, runs on
pull requests, `main` and by hand (not on feature-branch pushes).

**The flows, as the criteria list them (29 cases per browser, 5 job cases):**

| Flow | Case | Notes |
|---|---|---|
| login (both people) | 4 | form, Mark's first-run wizard, wrong PIN, Mark turned away from Craig's screens, sign-out |
| import | 2 | **Amended: there is no import screen or endpoint.** The case runs the real import CLI on the throwaway database (fake TMDB) and checks the screens |
| search | 2 | the top bar, and a film not owned found on TMDB |
| add via scan | 2 | typed digits take the camera's road; **the camera itself cannot run** (real-device check, `OWNER-ACTIONS.md` 1d) |
| price alert | 3 | a shop price under the limit reaches the Wanted card (X11) and the phone; **the eighth flow, T8a's eBay alert**, through the `ebay_watch` job; a listing watched by address |
| chat session | 4 | two messages on a recorded model (AI45-01, held to the wire), the Yes/No card, the cap, dictation (**skipped visibly on Firefox**) |
| movie night match | 2 | push read off the fake service, Mark opens the night by its address, the match is stored (X12a); **the tap on the notification cannot run**; the live update on an open page is **skipped visibly on WebKit** |
| CR43-05 offline replay | 1 + 3 unit | the browser case is **skipped visibly on WebKit** (the replayed POST cannot be intercepted there); three vitest cases hold it on all |
| UX48-01 cross-origin worker | 1 | cache kept under the API's origin; API stopped, a film read online opens |
| UX48-03 drift and chunk | 2 | **found: Safari's wording of a removed chunk was not recognised** (fixed) |
| never-used screens | 4 | photos, box sets, smart collections, eBay accounts (connect, return, disconnect) |
| Group X | 2 | Tell Craig reaches Craig's Needs attention row; the Archive's first 60 before the rest |
| CR43-07 the five jobs | 5 | **wider than the review said** (the shop check and reminders had not run either); in the `jobs` project |

**Skips, all visible in the report with their reason:** dictation on Firefox (no Web Speech API); on
WebKit, the lost-answer replay and the live match on an open page (Playwright's WebKit; unproven
for Safari). **Cannot run anywhere:** a real camera decode, the notification tap, speech, a real
phone.

**Guards proved to bite** (the fix reverted, the case fails): the replay's unconfirmed step
(vitest and browser), the cross-origin cache rule, the reload-once guard, the chat block filter,
a job's `main()`, the first-read race, the single flush.

**The suite also found, and Batch 38 fixed:** a person's first assistant message could 500 (two
first reads of their caps at once); `flushQueue` could run twice at once and replay a write twice;
Safari's chunk-failure wording. **Found, not fixed, `DECISIONS.md` #285:** the new-conversation
card race, a TMDB-id add whose answer is lost never settling, the raw `blu_ray` on the barcode
screen.

---

---

## Owner snag batches — from the 2026-09-14 triage

**These eight are not from the April spec, and there is no `**Phase X.Y:` heading to recover.**
They come from Craig's 11 snags (`docs/owner-snags-2026-09-14.md`), triaged against the code
and live data in `docs/owner-snags-triage-2026-09-14.md`. **The acceptance criteria below were
authored on 2026-09-15, not recovered** — `DECISIONS.md` #54 governs recovery from §16 and does
not apply. Do not go looking for a phase row; this section is the ledger entry.

The four shaping decisions are `DECISIONS.md` **#154–#157**; the Letterboxd findings are
**#158–#161**.

**Order is dependency-derived and must not be rearranged:** S4 needs S3's navigation shape, S6
needs somewhere to put the merged screen, S5 reuses S8's matcher, S7 needs S8's watch history.

---

### ~~Batch S1 — Remove Gift links~~ 🟢 **shipped 2026-09-15 (`43d1ecf`)**
**Covers snag 4.** Model: **Sonnet 5 · medium** / GPT-5.6 Terra · Medium.

~~`gift_links` holds **0 rows** and 0 views, measured against live Neon 2026-09-14. Dropping the
table therefore destroys no data and **does not trip the close-out's destructive-operation
stop**, which `AGENTS.md` scopes to "tables holding real rows". Say the row count at close-out.~~
**Re-measured immediately before the merge, 2026-09-15: still 0 rows, still 0 views.** The drop
destroyed nothing.

**Acceptance — all eight met:**
- ~~`/gift-links` and the public `/gift/:slug` route are gone, with the nav item and every client
  function in `lib/api.ts`.~~ ✅ Both 404 in the running built bundle; eight client functions gone.
- ~~`routers/gift.py`, `schemas/gift.py` and `models/gift_link.py` are removed and the router is
  deregistered from `main.py`.~~ ✅
- ~~`services/trash.py` no longer registers `gift_links`, and a test proves restore still works
  for every remaining table.~~ ✅ `test_every_remaining_table_can_still_be_restored` walks
  `TRASH_TABLES` itself rather than a hand-written list, so it cannot fall behind the registry.
- ~~The `/api/v1/gift/` cache exclusion is out of `sw.ts` without reopening the bug its comment
  records.~~ ✅ The same-origin guard and the `.ics` exclusion both stay.
- ~~The gift zod schemas and their tests are gone from `packages/shared`.~~ ✅
- ~~A migration drops the table, and CI's `upgrade head` → `downgrade base` reverses cleanly.~~
  ✅ Migration `030`; its downgrade recreates the table in full, because `018.downgrade` drops a
  table that must exist by the time the reversal reaches it.
- ~~`grep -ri gift apps/ packages/` returns only historical mentions in docs and comments.~~ ✅
  Plus migrations `018` and `030` themselves, which are the record of the table and its removal.
- ~~Gate green.~~ ✅ **One CI failure on the way:** the new test's retailer fixture said
  `scraper_type="generic"`, which `ck_retailers_scraper_type` refuses — a bug that can only
  appear against real Postgres (`STATUS.md` gotcha 3). Fixed in `43d1ecf`; green on the re-run.

### ~~Batch S2 — App-feel fixes~~ 🟢 **shipped 2026-09-15 (`baef542`)**
**Covers snags 3 and 9.** Model: **Sonnet 5 · medium** / GPT-5.6 Terra · Medium.

Both causes were measured on the deployed app at 375×812, not inferred (`triage` §3, §9).

**Acceptance — five of five met in code; two real-device checks remain open below.**
- ~~Form controls compute **≥ 16px** at touch widths — verified by reading the computed style in
  a browser, not only by asserting the class.~~ ✅ **16px measured at 375×812** against the
  shipped stylesheet, across ten real class combinations — `.form-control`, `.select-control`,
  `FilterBar`'s `CONTROL_CLS`, `CommandPalette`, `SearchBar`, a bare input, and one deliberately
  styled `text-xs` to prove the floor wins the cascade. Desktop is unchanged at 14px.
- ~~`html` and `body` compute `touch-action: manipulation`.~~ ✅ Both, read from the browser.
- ~~**Pinch-zoom still works.** The viewport meta gains no `user-scalable=no` and no
  `maximum-scale`; a test or a recorded check proves it.~~ ✅ Meta is byte-identical; four tests
  in `viewport-meta.test.ts` read the real `index.html` and fail on either shortcut.
- ~~The Letterboxd link resolves to `letterboxd.com/imdb/<imdbId>` when `imdbId` is present and
  to search only when it is null. Both branches tested.~~ ✅ Six tests in `external-links.test.ts`.
- ~~Gate green.~~ ✅ First time, no CI failures.

> **⚠️ Two checks remain open and are Craig's, exactly as this row warned.** An agent cannot
> observe either, and **the green gate above does not stand in for them**:
>
> 1. **On the phone: does tapping a field still zoom, and does double-tapping still zoom?**
>    The causes are fixed and measured in a desktop browser at phone width; the *behaviour* is
>    iOS Safari's and only a real iPhone shows it. Also worth confirming the thing this batch
>    protected: **pinch-zoom should still work**.
> 2. **Does a Letterboxd link now open the Letterboxd app?** That is universal-link handling on
>    the device, controlled by nothing in this codebase. The prerequisite is done — the link is
>    a *film* link now instead of a search — so the check is finally meaningful.
>
> **Coverage to expect on check 2:** 1,091 of 1,854 films carry an IMDb id, so ~59% open the
> film's own page and the rest still land on a search until they are identified. A film that
> searches is not a bug in this batch.

### ~~Batch S3 — Navigation shape~~ 🟡 **shipped 2026-09-15 (`a3409f1`)**
**Covers snags 5, 11 and 1.** Model: **Opus 5 · high** / GPT-5.6 Sol · High. `DECISIONS.md` #154.

**Acceptance — ten of ten met.**
- ~~Home, Stats and Insights are one reading page at `/dashboard`; `/stats` and `/insights`
  redirect to it rather than 404.~~ ✅ Both redirects confirmed in the browser.
- ~~Box sets, Collections, Deals and Loans are **hidden from the menu while their table is
  empty** and appear once it is not. **Both states tested**~~ ✅ Tested at three levels and
  **seen in a browser in both states**: `8` destinations with all four counts at 0, `12` with
  all four non-zero. Nine API tests cover each table's empty and non-empty case, including the
  three that would be wrong in a subtler way — a soft-deleted box set must not count, a
  dismissed deal must not, a *returned* loan must.
- ~~Notifications and AI settings are one `/settings` page, and AI settings is in the menu.~~
  ✅ Two tabs; the three old paths redirect, each onto its own tab.
- ~~A signed-in non-admin sees **8** sidebar destinations.~~ ✅ Counted in the DOM at 375×812:
  Movies · Wanted · Movie night · Coming soon · Calendar · Home · Assistant · Settings.
- ~~Search is gone from the shell header's mobile second row and reachable from the bottom bar
  on every screen.~~ ✅ No visible search input in the header at 375px; the bottom bar reads
  Archive · **Search** · Home · Movie night · More, and opens a sheet with the field focused.
- ~~`FilterBar` collapses to a single button below `sm`.~~ ✅ **One control** in the bar at
  375px, measured; all nine reappear when expanded.
- ~~`/` opens the merged Home.~~ ✅
- ~~Empty sections inside the merged page hide rather than render empty.~~ ✅ On this day,
  Worth a rewatch and Pinned collections render nothing at all today. **The two empty charts
  are hidden too**, with their reasons collected into one line beneath — see the note below.
- ~~Export moves to Admin.~~ ✅ `/export`, admin-only.
- ~~Gate green, **plus a real browser pass at 375×812**~~ ✅ Green first time. The browser pass
  drove the real bundle against a scratch stub of the API, using the repo's own DEV-only
  `VITE_SKIP_AUTH` (compiled out of production builds), because a signed-in view needs Craig's
  PIN. Nothing from that harness is in the tree.

> **One judgement call worth flagging.** "Empty sections hide" and Batch 14's *"an empty chart
> reads as a broken chart, so say what it is waiting for"* pull in opposite directions for
> Most watched and Spend over time. Both are honoured: the panels are **hidden**, and their
> explanations — *"nothing logged yet"*, *"the imported spreadsheet never carried a price"* —
> are collected into a single muted line under the charts. Two empty frames on a page whose
> complaint was emptiness would have been the complaint.

> **Three test expectations changed.** The command palette no longer indexes 'Stats', and
> `g s` — "go to stats" — now goes to `/settings`, because stats is a section of `/dashboard`
> that `g h` already reaches. Each is the batch's own point rather than a concession, and the
> palette assertion was **strengthened**: it now also proves 'Stats' and 'Insights' are gone
> from the index rather than merely renamed.

### ~~Batch S4 — Quick add within reach~~ 🟡 **shipped 2026-09-15 (`45ec4fa`)**
**Covers snags 7 and 8.** Model: **Opus 5 · high** / GPT-5.6 Sol · High. `DECISIONS.md` #155.

The eBay sell-offer already exists (Batch 29). **This batch is reach, not capability.**

**Acceptance — six of six met.**
- ~~A quick-add entry point on Home and in the bottom bar, **visible below 640px**.~~ ✅ Both
  seen at 375×812: a button on Home (where `/` lands since S3) and an accented **Add** slot in
  the bottom bar. The header's own button keeps `hidden sm:inline-flex` on purpose — two add
  controls in the scarcest space the app has would be one too many.
- ~~`/collection/add` is reachable by a `viewer` — the route guard **and** the API.~~ ✅ The
  route is `AppShell` now, and the page was **opened as a viewer in a browser**: heading, scan
  button and search field all render, no access denial. **Five endpoints moved for the page to
  work, not one** — `/tmdb/search`, `/collection/duplicate-check`, `POST /collection`,
  `/barcode/lookup`, `/barcode/confirm`.
- ~~`POST /api/v1/ebay/price-estimate` and `/ebay/listing-url` accept a `viewer`; tests assert
  **200, not 403**.~~ ✅ Two tests, both asserting 200 with a body.
- ~~Trash, Audit log, Retailers and Admin still refuse a viewer; tests assert **403**.~~ ✅ —
  **with one correction to the criterion, in the code's favour.** `GET /api/v1/retailers` is
  **200** for a viewer and has been since Batch 18, deliberately: *"reads are open to both
  people — Mark can reasonably want to see what is being looked for"*. "Retailers refuses a
  viewer" is true of the **page** (`/retailers` is `AdminShell`), not of the read endpoint.
  Every retailer *write* is admin-only, and that is what the test asserts.
- ~~The upgrade → "List for sale" flow is reachable from the add flow, not only from the film
  page afterwards.~~ ✅ — **and this criterion found the defect the others would have missed.**
  The flow already ran add → "this is an upgrade" → film page with a one-tap button. But that
  button calls `PUT /collection/{id}/listing`, which the criterion does not name and which was
  still `AdminUser`: Mark would have seen the prompt, fetched the price, pressed the button and
  got a 403. **Found by following the button rather than the criterion.**
- ~~Gate green, plus a browser pass at 375×812.~~ ✅ Browser pass driven **as a viewer**, by the
  method `DECISIONS.md` #169 records.

**Two test expectations flipped**, both required by the criteria: a viewer posting to
`/collection` is a **201**, and a viewer listing a superseded disc for sale is a **200**. The
old test name *"a viewer cannot sell a disc"* was doing too much work — that endpoint covers
both "I have listed this" and "this is gone", and the first is half the flow snag 7 is about.

**One CI failure, in this batch's own new tests.** The add test built a disc for the film it
then tried to add, so `POST /collection` answered **409 duplicate** before the role check ever
ran — it would have passed for the wrong reason the day the widening was reverted. Fixed in
`45ec4fa`. Both failures were invisible locally, where the 49 Postgres-backed tests in that
file skip.

**The API moves with the UI, never after it.** A button that appears while its endpoint still
403s is worse than no change. Eight endpoints moved in the same commit as the route guard.

### ~~Batch S8 — Watch history, the backfill~~ 🔴 **shipped 2026-09-15 (`0a8c813`)** · ⏸ **live import waits for Craig**
**Covers snag 10b.** Model: **Opus 5 · xhigh** / GPT-5.6 Sol · Extra High. `DECISIONS.md` #160, #161.

Both diaries are already retrieved and sit in `.letterboxd-export/` (gitignored — personal
data, never commit them): **Craig 1,173 entries, Mark 1,149, 2,322 total.**

**Acceptance — seven of seven met.**
- ~~An importer reads a Letterboxd `diary.csv`-shaped file and writes `watch_log` rows.~~ ✅
  `services/letterboxd/` — reader, matcher and importer, split so S5 reuses all but the reader.
- ~~**Idempotent on `ViewingId`** — a second run of the same file writes zero new rows.
  Tested.~~ ✅ Migration `031` adds `watch_log.letterboxd_viewing_id`, unique per person and
  partial on NOT NULL. **One column serves both sources**: the feed's
  `letterboxd-watch-<id>` guid wraps the same number, so **S5's no-double-count criterion is
  met here** — tested — rather than discovered after 2,322 rows are in.
- ~~Matching is exact on `tmdb_id` where present, else normalised title + year.~~ ✅ And **the
  year is a tie-breaker, never a filter** — filtering is the artifact #158 records.
- ~~**Ambiguous matches are offered, never guessed** — tested against a `Death on the Nile`
  fixture~~ ✅ — **and the count is 28, not 6. See the correction below.**
- ~~A film matching an **unidentified** row is identified: `tmdb_id`, year, poster, runtime and
  cast filled, and each identification reported.~~ ✅ Reuses `services/identification.py`,
  extracted from `routers/movies.py` so an imported identification and a hand-made one cannot
  drift. A TMDB match the engine calls ambiguous is **refused and reported**, and the watch is
  still written.
- ~~A **dry-run** mode reports every count without writing.~~ ✅ `dry_run=True` is the
  *default*, and a dry run never touches TMDB.
- ~~Gate green against fixtures.~~ ✅ **One CI failure**, in this batch's own new test — it
  constructed a tie the engine can legitimately break (the diary's year settles it), so the
  assertion was wrong and the code was right. Fixed in `0a8c813`, with a second test pinning
  the behaviour CI demonstrated.

> **⚠️ Correction to `DECISIONS.md` #160: ambiguities are 28, not 6** — see #174. Measured by
> running *this* matcher over both real diaries against live Neon:
>
> | | measured | #160 said |
> |---|---|---|
> | Links straight to an owned film | 969 | 950 |
> | Owned but unidentified → identify | 586 | 580 |
> | **Ambiguous** | **28** | **6** |
> | Not in the collection | 739 | 786 |
> | Watches of owned films | **1,555 (66%)** | 1,530 (66%) |
> | Distinct films identified | **397** | 396 |
>
> **This matcher is the stricter of the two.** #160's pass did not collapse parenthetical
> disambiguators or rotate trailing articles, so `Mummy, The (Brendan Fraser)`, `(Original)`
> and `(Tom Cruise)` looked like three unrelated titles and a diary entry for *The Mummy*
> matched **none** — counted as "not in the collection" rather than as a question. That is the
> whole 47-row difference: **22 silent misses became 22 explicit questions.** All 15 distinct
> ambiguities are genuine; the collection really holds two *Dunkirk*s, two *Titanic*s, two
> *Lion King*s and three *Mummy*s. 66% is unchanged, which is the check that it scales.

> **⏸ The live import is Craig's and was not run.** `OWNER-ACTIONS.md` **1i** has the two
> commands. It writes **~1,555 watch rows** and, with `--identify`, **overwrites ~397 existing
> `movies` rows**. `--identify` is a separate flag from `--write` on purpose: writing watches
> is additive and reversible, identification rewrites rows that already exist and merges two
> into one where the collection holds both.

### ~~Batch S5 — Watch history, ongoing~~ 🟡 **shipped 2026-09-15 (`834c3f1`)** · ⏸ **first live fetch waits for Craig**
**Covers snag 10a.** Model: **Opus 5 · high** / GPT-5.6 Sol · High. `DECISIONS.md` #156, #158, #159.

**Acceptance — seven of seven met.**
- ~~Reads `letterboxd.com/<user>/rss` and parses `letterboxd:watchedDate`, `letterboxd:rewatch`,
  `letterboxd:memberRating`, `tmdb:movieId` and `guid`.~~ ✅ 18 parser tests. **It matches on
  local names and ignores namespace prefixes** — see the caveat below.
- ~~**Reuses S8's matcher and writer.** No second matching implementation~~ ✅ S5 added
  `feed.py` and `sync.py` and **nothing else**. The feed reader's only job is to produce the
  same `DiaryEntry` the file reader produces.
- ~~**Cannot double-count across sources**~~ ✅ Tested end to end: import the viewing from the
  *file*, then sync the *feed*, and the second writes zero. The guid wraps the same number
  `watch_log.letterboxd_viewing_id` already stores (#176).
- ~~A **null rating is valid**~~ ✅ The fixture's *Collector* entry carries no `memberRating`
  at all — an ordinary entry, and Mark's look exactly like it.
- ~~A manual "sync now" works with no cron~~ ✅ `letterboxd_syncs.trigger` already accepts
  `cron`, so adding one when the Railway crons are fixed needs no migration.
- ~~The UI states **when the sync last ran**.~~ ✅ **Seen in a browser at 375×812**: *"Last
  synced 3 days ago · 4 new"*, with the watch count beside it. A **failed** run keeps its row
  and reads *"— and it failed"* with the reason; a feed that comes back full at 50 is surfaced
  as a **cadence warning**, not a success.
- ~~Gate green against fixtures.~~ ✅ **One CI failure**, in the lint job alone: CI's mypy
  resolves `db.scalar(...)` as `Any` where this machine's does not (`STATUS.md` gotcha 21).
  pytest against real Postgres was green on the first run.

> **⏸ The first live fetch is Craig's** — `OWNER-ACTIONS.md` **1j**. It is one button press,
> and it is also what settles the caveat below.
>
> **The fixture is constructed from a measurement, not captured from the wire.** The element
> names come from `OWNER-ACTIONS.md` 1f's reading of both real feeds across 100 entries; the
> exact namespace URIs and nesting were never captured, because capturing them needs a live
> request. `AGENTS.md` says to work from real payloads — where that is not available
> unattended, the honest substitute is **a parser with no opinions about the parts that were
> not measured**: it matches local names, ignores prefixes, and falls back to RSS's own
> `<title>`. A test renames every prefix and points the namespaces at nonsense URIs to prove
> it does not care.

**Identification is deliberately not attempted**, though every feed entry carries a TMDB id.
That rewrites `movies` rows — the operation S8 put in the owner's hands — and doing it from a
button, repeatedly, would take that decision back without asking.

### ~~Batch S6 — Physical release dates~~ 🟡 **shipped 2026-09-15 (`b5b3796`)**
**Covers snag 2.** Model: **Opus 5 · high** / GPT-5.6 Sol · High.

`RELEASE_TYPES` has carried `4k_uhd_release` and `blu_ray_release` since Batch 17 and
**nothing has ever written either** — `services/calendar.py` hardcoded `"theatrical"`.
*(The row said "all 32 live rows are cinema dates"; measured, it is **30 theatrical plus 2
`sale_event`** from Batch 11's seeding. The point stands: no physical row had ever existed.)*

**Acceptance — six of six met.**
- ~~`tmdb/client.py` gains a `release_dates` method; GB **type 5 (Physical)** is ingested as
  `blu_ray_release` / `4k_uhd_release`.~~ ✅ Ingested **beside** the cinema date, not instead
  — one film, two rows. **TMDB type 5 says "Physical" and no more**, so `classify_physical`
  reads the free-text note; every string it matches was read off live TMDB.
- ~~Calendar and Coming soon are one screen; `/calendar` and `/discover` both resolve to
  it.~~ ✅ `/discover` redirects; confirmed in a browser.
- ~~Physical releases lead; cinema dates are kept and visibly distinct.~~ ✅ Seen at 375×812:
  a **Coming to disc** section above the month, and an accented **4K UHD** badge against a
  muted **In cinemas** one.
- ~~**A film with no physical date is still visible, not silently dropped.** Tested.~~ ✅ —
  **and it is not an edge case, it is almost every film.**
- ~~Ingestion stays idempotent on `(tmdb_id, release_type, region)`.~~ ✅ `candidates` is
  rekeyed on `(tmdb_id, release_type)` because one film now yields up to three rows. Two
  type-5 entries of one format collapse to one row and **the earliest date wins**.
- ~~Gate green, plus a browser pass.~~ ✅

> **📉 The real coverage number, as this row demanded: 1%.** Measured against live TMDB on
> 2026-09-15 over three pages of `/movie/upcoming` GB — **1 of 58 forthcoming films had a GB
> physical date at all**, and that one's note said 'DVD'. Across a 60-film sample of the
> collection itself it is **11%** (7 of 60), against 68% for cinema dates.
>
> **So the disc section leads and will usually be empty.** When it is, the page states the
> number rather than rendering an empty frame or implying no discs are coming — which is
> precisely the failure mode this row named. The feature is correct and thin, and it fills in
> as TMDB's contributors add dates.

**One CI failure, and it was a staging mistake rather than a code one.** The first commit
carried *only* the two page deletions: `git add` was handed the already-removed paths along
with everything else, and it aborts the whole invocation on a pathspec that matches nothing —
with `2>/dev/null` hiding the error. **The same trap S1 hit.** Fixed in `b5b3796`.

**A signed-in non-admin now sees 7 sidebar destinations, not S3's 8** — merging two more is
this batch's own criterion. Fourteen → eight → seven.

### ~~Batch S7 — Movie night rebuild~~ 🔴 **shipped 2026-09-15 (`804744f`)**
**Covers snag 6.** Model: **Opus 5 · xhigh** / GPT-5.6 Sol · Extra High. `DECISIONS.md` #157.

What existed was a random swipe deck over the collection. Two of Craig's five points were met;
the other three needed the input side replaced.

**Acceptance — six of six met.**
- ~~Anyone in a session can **suggest** a film, and everyone can vote on anyone's suggestion.~~
  ✅ New `movie_night_suggestions`, and **a vote is cast on a suggestion rather than on a
  film** — which is what makes both halves true. Tested with the *viewer* suggesting and both
  people voting.
- ~~**Films outside the Archive can be suggested**, with streaming availability.~~ ✅ Seen at
  375×812: *The Matrix*, "Streaming on Netflix", "Not in the collection — this one would be a
  rental." `Match.movie_id` is nullable, because there is nothing on the shelf to point at.
- ~~Opening a card shows the film's full details — cast, runtime, genres, and a link to its
  page.~~ ✅ Seen: *"2h 50m · Crime · Drama"*, *"Starring Al Pacino, Robert De Niro"*,
  *"Suggested by Mark"*, *"Open its full details"*.
- ~~A card shows **whether the other participants have watched it, and when**.~~ ✅ Seen:
  *"Mark saw this on 2026-03-04"*. **Everyone except the person asking** — "have I seen it" is
  on the film's own page. **Reads empty until S8's import runs**, which is why #157 put S7
  after S8.
- ~~Sessions still work for 3+ people, and a match still requires **everyone**.~~ ✅ Unchanged:
  `issubset` was already right, and is one of the two points Batch 35 met.
- ~~`candidate_movies`'s unseeded `func.random()` no longer contradicts its docstring.~~ ✅
  **Seeded rather than the claim deleted.** Ordering on `md5(session_id ‖ movie_id)` is stable
  per session, different between sessions and identical for everyone in one — without
  `setseed()`, which is connection state that would leak into whatever ran next on that
  connection. Two tests: same session twice, and two sessions differing. *(No standalone
  `fix/` branch had landed; `git log --all` was checked.)*
- ~~Gate green, plus a browser pass.~~ ✅ **Green first time**, migration reversal included.

> **The migration is additive, because the tables hold real rows.** 13 votes across **2
> sessions that were still open**, measured against live Neon. Nothing is dropped and no
> column is rewritten: `movie_id` is *relaxed* to nullable, and a backfill gives each existing
> vote a suggestion so those two sessions keep working rather than becoming history. The CHECK
> is "one of `movie_id` or `suggestion_id`", not "`suggestion_id NOT NULL`" — a constraint
> that only holds where a backfill happened to succeed fails on the one database where it did
> not.

**One expectation changed on purpose: a card no longer vanishes when you swipe it.** Batch 35
removed it because the deck was private; a shortlist everyone is adding to is a list you
re-read. **The privacy property it protected is kept** — `myVote` is built from the caller's
own votes alone, and a test asserts the other person's vote is still invisible.

---

## Go live — the collection refresh *(2026-09-16)*

**Not from the April spec and not from the 2026-09-14 snag triage.** This comes from
`DECISIONS.md` #192, found on 2026-09-15 when Craig proposed a fresher import of his dad's
spreadsheet before go live. The acceptance criteria below were **authored 2026-09-16, not
recovered** — there is no `**Phase X.Y:` heading behind them and `DECISIONS.md` #54 does
not apply.

---

### ~~Batch 39 — Collection refresh~~ 🟡 **shipped 2026-09-16 (`b1db470`)**
**Covers `OWNER-ACTIONS.md` 1k, option A.** Model: **Opus 5 · xhigh** / GPT-5.6 Sol · Extra High.
`DECISIONS.md` #192, #193.

**🟡 by size, `xhigh` by blast radius and silence** — the same disagreement Batches 15, 17,
24 and 27 carry, and for Batch 15's exact reason: this operates on all **1,857 live
collection rows**. Two of its failure modes announce nothing at all.

**The problem.** Re-running `import_collection.py` over live data refreshes nothing. Items
deduplicate on `import_source_row` — the spreadsheet **line number** — and the 1,857 discs
occupy lines 2–1867 with exactly 9 gaps, which are the 9 blank rows `STATUS.md` gotcha 0
records. Every non-blank line is claimed, so every disc is skipped however much its row
changed. Meanwhile the *film* upsert runs independently of that check and is
`ON CONFLICT (tmdb_id) DO NOTHING` — and a NULL `tmdb_id` does not conflict — so a title
TMDB can now match gets a brand-new `movies` row **with no discs on it**.

**Why rebuilding the discs is safe**, re-measured 2026-09-16: `collection_items` holds no
app-created data **apart from 10 Blu-ray.com spec records**. 0 photos, 0 notes, 0 purchase
prices, 0 loans, 0 barcodes, and `listing_status` is `in_collection` on all 1,857.
**Nothing references a `collection_items.id` either** — `box_set_items`, `loans` and
`item_photos` are all empty, and the audit log has zero rows targeting an item. The
valuable data hangs off `movies`: 1,555 watches, 11 wanted-list rows, 40 completion sets,
45,600 credits. A replace that never touches `movies` keeps all of it.

**Craig accepted losing those 10 specs from the active collection on 2026-09-16** (#195).
The old rows and their specs still land in Trash for 90 days, but the new items start
without them. The importer does not transfer specs by `import_source_row`: spreadsheet
position is the unstable identity this batch exists to replace, so doing that would risk
attaching edition-specific specs to the wrong new disc.

**Acceptance — nine of nine met.**
- ~~Live source rows block re-import and Trash rows do not.~~ ✅ Query and both states
  tested. Migration 034 replaces the all-history unique index with a live lookup index so
  full-state restore remains possible even when a replacement reused the sheet line.
- ~~`--replace-items` soft-deletes every live item in the import transaction and reports
  the count; no flag leaves the old path unchanged.~~ ✅ One locked transaction for the
  replace, one transaction per item for the unchanged path, both tested.
- ~~`--replace-items --dry-run` reports its count and removes nothing.~~ ✅ Tested.
- ~~A replaced row lands in Trash and `restore-row` brings it back.~~ ✅ Postgres CI restores
  the complete old row even while a replacement has the same `import_source_row`.
- ~~Watch history survives and existing movie metadata is not overwritten.~~ ✅ Tested in
  Postgres with both identified and unidentified watched films.
- ~~An identified replacement deduplicates onto the existing movie.~~ ✅ One TMDB id, one
  movie row, replacement item attached to it.
- ~~Derived fields and copy counts ignore the soft-deleted rows.~~ ✅ Postgres CI sees the
  replacement Blu-ray as the sole live copy and recalculates `best_format_owned`.
- ~~Unidentified watched films block replacement with counts and `--identify` guidance;
  `--accept-split` is explicit override.~~ ✅ Refusal and override both tested; the final
  transaction locks items, movies and watches before repeating the guard.
- ~~Gate green.~~ ✅ Feature branch and `main` CI green; migration 034 upgraded and reversed.

> **⏸ The live run is the owner's, and it needs a spreadsheet that does not exist yet.**
> Ship the mechanism and the dry run, then stop — the same shape as S8. The real run
> soft-deletes 1,857 rows, which `docs/agent-commands/group-start.md` puts squarely in the
> owner's hands.

> **⚠️ Ordering constraint: `--identify` must run first — and this batch is what enforces
> it.** `OWNER-ACTIONS.md` 1i step 2. 397 unidentified films currently carry **586 watch
> rows**, and they are exactly the messy-titled ones — `African Queen, The`, `39 Steps The
> (Robert Donat)` — that exact-title dedup will miss the moment the new sheet tidies them.
> Give them a real `tmdb_id` first and the reload deduplicates on the id instead.
>
> **Running the replace before the identification is the one sequence that silently splits
> history from discs**, which is why the guard above is an acceptance criterion rather than
> a note. Until this batch ships, **nothing stops that sequence at all** — the constraint
> lives only in prose, in this entry and in `OWNER-ACTIONS.md` 1k.

---

### Batch 42 — The guard counts discs lost 🟢
**Sharpens Batch 41's guard.** Model: **Opus 5 · high** / GPT-5.6 Sol · High.
`DECISIONS.md` #199.

**The problem.** Batch 41's `orphan_risk` asked which watched films end without a disc.
Against production that named five, and two were not at risk: *Project Hail Mary* (watched,
never owned on disc) and *Misery* (already split between two rows today). A guard whose
override is one flag must not name films nothing is happening to.

**Acceptance.**
- A watched film that holds no live disc today is not reported as losing one.
- A watched film that does hold one still is — the narrowing cannot silently disable it.
- A film whose only disc is already in Trash does not count.
- Gate green with the Postgres tests running.

---

### Batch 41 — An unsettled row reuses the film we hold 🟡
**Unblocks the refresh in `OWNER-ACTIONS.md` 1k.** Model: **Opus 5 · xhigh** /
GPT-5.6 Sol · Extra High. `DECISIONS.md` #198.

**🟡 by size, `xhigh` by what it stands in front of** — the 1,857-row replacement.

**The problem, measured rather than predicted.** The 2026-09-18 dry run of the fresh
spreadsheet would have duplicated **401 films and stranded 587 watch rows**, silently.
`upsert_unmatched_movie` reused an existing film only via `title = %s AND tmdb_id IS NULL`,
and Batch 40's identification run had just given 395 films a `tmdb_id`. Batch 39's guard
passed it, because that guard counts *unidentified* films holding watches — which was 1.

**Acceptance.**
- A row TMDB cannot settle attaches to the live film of that title, identified or not.
- A title identification tidied (`Thing, The` → `The Thing`) still resolves, through the
  same `normalise_title` the diary matcher uses.
- A title naming two live films mints a new row and is reported — offered, never guessed.
- An exact title beats a normalised collision.
- `orphan_risk` refuses the replacement when any watched film would end without a disc,
  names the films, and is overridden only by `--accept-split`.
- Its resolution mirrors the write path — `tmdb_id` for a matched row, the index for an
  unsettled one — so it is a check rather than a second opinion.
- A dry run reports the same refusal and the same reuse counts a real run would.
- Gate green with the Postgres tests running rather than skipping.

> **⏸ The live replacement stays the owner's.** This batch only makes it safe to consider.

---

### Batch 40 — Identification on a re-run 🟢
**Unblocks `OWNER-ACTIONS.md` 1i step 2, which unblocks 1k.** Model: **Opus 5 · xhigh** /
GPT-5.6 Sol · Extra High. `DECISIONS.md` #197.

**🟢 by size, `xhigh` by consequence.** The change is one hoisted branch in
`run_import`. What it re-enables is not small: a run that rewrites title, year, poster,
runtime and cast on ~396 live `movies` rows carrying **582 watch rows between them**, and
deletes a row wherever the collection turns out to hold the same film twice.

**The problem.** `--identify` cannot reach anything. The already-imported check sits
*above* the match, so once step 1 wrote the 1,555 watches on 2026-09-15 every entry
short-circuits on its `letterboxd_viewing_id` before the matcher runs. Measured against
live Neon on 2026-09-17: **Craig 593 already imported, films identified 0; Mark 962
already imported, films identified 0.** The flag reports a clean run and does nothing.

**Why no test caught it.** Every S8 identification test identifies on a *first* run — the
one case where writing watches and identifying films are separable. The sequence that
breaks it is the sequence the live database is actually in: watches first, identification
second.

**Acceptance.**
- Identification reaches a film whose watches are already imported, and that run writes
  **zero** watch rows.
- `would_write` still means "rows a real run would insert" — already-imported entries do
  not inflate it.
- A dry run reports how many films it would identify, and their local titles, while
  spending **no** TMDB calls. It cannot say what each becomes; that stays true.
- A film whose identification **fails** reports one failure line, not one per watch.
- A later entry for a film that identification merged away follows the surviving row
  rather than fetching and re-merging it.
- Gate green, with the Postgres-backed tests running rather than skipping.

> **⏸ The live run is the owner's.** Shipping this batch does not identify anything. The
> run rewrites ~396 rows and makes ~800 live TMDB calls, which
> `docs/agent-commands/group-start.md` puts in Craig's hands — and it is the ordering
> constraint Batch 39's guard enforces, so it must precede the collection refresh.

---

## Owner snag batches — from the 2026-09-23 reconciliation

**Not from the April spec, and there is no `**Phase X.Y:` heading to recover.** They come
from Craig's 14 snags of 23 Sep, reconciled against the code and live data in
`docs/owner-snags-2026-09-23.md`. **The criteria below were authored on 2026-09-23**, so
`DECISIONS.md` #54 does not apply. The shaping decisions are **#200–#203**.

**Status: approved by Craig on 2026-09-23** ("2) yes"). T1 and the scheduled-jobs fix have
shipped. The batches run in order and close out one at a time.

**Order is dependency-derived:** T2 → T3 → T4 → T5 → T6 → T7 → T8. T4 needs T2's search and
T3's top bar. T6 and T8 share the eBay client. T6, T7 and T8 each end in a scheduled job, so
they want the scheduled-jobs fix below first.

---

### ~~T1 — Session renewal~~ **shipped 2026-09-23 (`aa112bd`) as a fix, not a batch**
Covers snag 5. `DECISIONS.md` #200. CI green, with 1,175 passed and the four new Postgres
tests among them. Production serves `aa112bd` with `db: ok`.

**Live check owed:** a renewal row in `refresh_tokens` the next time either person's
24-hour access token lapses (Craig's lapses at 18:46 UTC on 23 Sep). A renewal's row is
created in the same instant its predecessor is revoked.

### ~~Scheduled jobs never start~~ **fixed 2026-09-23 (`aeb87aa`) at Craig's go** — `DECISIONS.md` #204
**One CI failure on the way:** a new test left the session secrets to the environment, so it
raised locally, where there are none, and not in CI, which sets them. Fixed in `aeb87aa`,
after reproducing CI's variables locally. **Still owed:** the first real runs, at 03:00 and
08:00 UTC on 24 Sep. A `scrape_runs` row with `trigger=cron` is the proof.

Found on 23 Sep from read-only Railway logs. Both crons fire on time (03:00 and 08:00 UTC)
and crash on import. `Settings()` refuses to start in production without
`JWT_ACCESS_SECRET`, `JWT_REFRESH_SECRET` and a non-localhost `FRONTEND_ORIGIN`.
`.railway/railway.ts` passes none of them to the job services, and no job uses them: only
`auth.py` and the CORS set-up in `main.py` read them. Every scheduled run has crashed.
`scrape_runs` holds a single manual row, from 10 Sep.

**Proposed:** a job profile. The job scripts declare themselves before importing settings,
and the fail-closed check skips the web-only secrets for a job while still refusing an empty
database URL. Tests prove the API still refuses to boot without them. Code only, no hosting
change. **Switching it on starts the nightly shop price checks and the 08:00 reminder
pushes for the first time.** Opus 5 · xhigh / GPT-5.6 Sol · Extra High, because it edits the
fail-closed configuration.

### ~~T2 — One search~~ 🟡 **shipped 2026-09-23 (`fe409f3`)**
**Acceptance: eight of eight met.** Browser check at 375×812 used the dev-only
`VITE_SKIP_AUTH` and a scratch API stub, as #169 did; nothing from it is in the tree.
There were no CI failures. Along the way: a zod/API mismatch that failed the page of any
film with no disc left, and a duplicate native clear button on every search box (#205).

**Covers snags 4, 6, 14 and 10d.** Opus 5 · high / GPT-5.6 Sol · High. It merges two sources,
and a missed or mislabelled owned film is wrong data that looks right.

**Acceptance:**
- Picking a result in the phone search sheet closes the sheet and shows the film. Tested.
- Each owned result shows the signed-in person's own "Seen <date>" (their latest watch) or
  "Not seen". `lastWatchedAt` ships in the API response and its zod schema together, and is
  tested for two people with different histories.
- Films not in the collection follow the owned ones, labelled "Not in the collection". They
  never duplicate an owned film.
- Unowned results show UK subscription streaming services where TMDB has them. Lookups are
  limited to the first few results and cached. A failed lookup loses the provider line,
  never the result.
- Tapping an unowned film opens a film card with the overview, where to watch (stream, rent
  or buy), "Add to Wanted", and "Suggest for movie night" when a night is open.
- Movie night's "Suggest a film" uses the same live search.
- Offline, owned results still come from the cache, and the TMDB half says it needs a
  connection.
- Gate green, and checked in a browser at 375×812.

### ~~T3 — Navigation and the Archive row~~ 🟡 **shipped 2026-09-23 (`90d6994`)**
**Acceptance: nine of nine met.** Measured in a browser: at 375px the row is 343px
wide in a 343px space with no overflow, and all five bar labels are 11px with none
truncated. At 768, 1024 and 1280px there is no overflow either. The browser pass used
the dev-only `VITE_SKIP_AUTH` and a scratch API stub (#169). **One CI failure:** a
Postgres-backed test pins every key a saved collection sends, and needed the two new
runtime keys. Fixed in `90d6994`. Decisions in #206.

**Covers snags 1, 2, 12, 13 and 10a.** Opus 5 · high / GPT-5.6 Sol · High. `DECISIONS.md` #201.

**Acceptance:**
- Below 1024px the bottom bar has five slots: Home · Archive · (+) Add · Movie night · Search.
  Labels are at least 11px and none truncates at 375px, measured.
- Below 1024px there's no slide-out menu: the top-left menu button and "More" are gone.
  Desktop keeps its sidebar.
- The phone top bar shows the page's title, a back arrow on sub-pages, and the person's
  initial, which opens a "You" page.
- The "You" page lists every destination not in the bar, and honours hide-when-empty (#154)
  and admin-only items. A test proves every destination is reachable from the bar or the
  "You" page.
- On phones the kicker, title and description block isn't rendered, because the title is in
  the top bar. Desktop keeps its page headers.
- The Archive's controls are one row at every width: Filters with its active count, Sort,
  the film count (once) and the layout switch.
- Runtime filter: from and to minutes in the Filters panel, `runtimeMin` and `runtimeMax` in
  the API and in smart collections, shown as a chip. Films with no runtime are excluded when
  either bound is set, as the rating filter already does. Tested.
- The command palette and keyboard shortcuts still reach every destination.
- Gate green, and checked in a browser at 375×812 and at desktop width.

### ~~T4 — Movie night~~ 🔴 **shipped 2026-09-23 (`99b04c0`)** · ⏸ **two-phone check waits for Craig**
**Acceptance: six of seven met; the seventh is the owner's**, as written. CI was green
first time, with all 8 new Postgres tests. The browser pass at 375×812 (dev-only
`VITE_SKIP_AUTH` and a scratch stub) found two things, both fixed before the commit:
the floating assistant button covered the deck's Add button, and Chrome wrote "Sept".
**Found on the way:** movie-night notifications were only ever queued, so no match
had ever reached a phone (#207).

**Covers snags 10b, 10e and 11.** Opus 5 · xhigh / GPT-5.6 Sol · Extra High, because a push
that never arrives looks like no news (Batch 11's reason). Needs T2 and T3.

**Acceptance:**
- Opening a night shows the shortlist: every suggestion with its poster, title, who suggested
  it and your own vote. "Start swiping" opens the deck at your first undecided film. Other
  people's votes stay hidden until a match (#157).
- The deck's buttons read "Skip" and "Add", with icons. Swiping and arrow keys are unchanged.
- "Send to <other person>" adds them to the night and queues a push that opens
  `/movie-night/<id>`. It honours notification preferences and quiet hours, and is
  deduplicated per night.
- "Share link" uses the phone's share sheet, with copying as the fallback. After sign-in, the
  link lands on that night (tested: login returns to it).
- The invited person sees the night in their list before opening anything.
- **Owner check, not an agent's:** the push arrives on both phones and opens the night, on
  Craig's iPhone and Mark's Android. This also closes Batch 11's open 6.2.
- Gate green, and a browser pass.

### ~~T5 — Releases~~ 🟡 **shipped 2026-09-23 (`1e08f40`)**
**Acceptance: seven of seven met.** **Live run, recorded:** 140 created, 1 updated, 19
unchanged, 44 skipped (cinema outside the genres), 28 of 28 disc films found, and no
errors. That matches the 28 TMDB listed that morning. **One CI failure:** the background
refresh, started by a calendar read in an unrelated test, committed rows into the shared
test database. It was fixed with a test guard in `1e08f40` (#208).

**Covers snag 9.** Opus 5 · high / GPT-5.6 Sol · High.

**Acceptance:**
- Ingestion asks TMDB's discover endpoint by release type for GB: physical (type 5) and
  cinema (types 2 and 3), six months ahead. It reads each physical film's own GB type-5 date
  and classifies 4K against Blu-ray as today. On 23 Sep TMDB listed **28** GB disc releases
  to 31 Dec, where the current lookup finds none.
- Disc releases aren't genre-filtered. Cinema dates keep §7.3's genres of interest.
- "Coming to disc" lists the next releases from today, whichever month is on screen.
- Home opens with the next few disc releases, hidden when there are none.
- The calendar stays fresh without a schedule. When it's read (the page or the `.ics` feed)
  and the last refresh is more than 24 hours old, a refresh runs in the background, one at a
  time. This doesn't breach #60: nothing is scheduled in-process, and a read triggers
  idempotent work.
- A live run is recorded with its counts. A run that writes far fewer than TMDB lists is a
  failure to investigate, not a coverage figure.
- Gate green, and a browser pass.

### ~~T6 — Collection value~~ 🟡 **shipped 2026-09-23 (`9acd0ee`)**
**Acceptance: all met, and the first live run waits for Craig, as the criterion says**
(`OWNER-ACTIONS.md` 19). One search per film and format (1,454 for 1,457 discs), each
stored with price, sample size, basis and date; migration 036 reversed in CI. Runs spend
at most 750 calls per UTC day, carry on next time and record their counts. Fewer than
three listings is "not priced". Home shows the total; each copy shows its stored value
beside the live check. Gate: 1,271 API tests in CI, none skipped, and a browser pass at
375px. **CI failed once:** strict mypy, which the documented local command never ran
(#209). **First live run, 24 Sep, at Craig's word:** 748 calls, 639 films and formats priced,
108 not priced, 707 due on 25 Sep; 641 of 1,457 discs priced, £11,844.31. A dropped
connection stopped the first of the day's two runs at call 574, fixed in `e256d65` (#211).

**Covers snag 7.** Opus 5 · high / GPT-5.6 Sol · High.

**Acceptance:**
- A valuation run prices every live physical disc with the existing estimator, leaving out
  downloads. It makes one eBay call per film and format, and stores each disc's price, sample
  size, basis and date. The migration is reversible.
- Runs are resumable and budgeted. Each stops at a set share of the 5,000-a-day allowance,
  carries on next time, and records its counts.
- A disc with too few matched listings is marked "not priced", never guessed.
- Home shows the total "at current eBay asking prices", how many discs are priced, and the
  date. A film's page shows its stored estimate beside the on-demand check.
- **The first full live run is Craig's to authorise**, because it spends about 1,460 eBay
  calls. Monthly refreshes need the scheduled jobs, plus eBay keys on the job service, which
  is a hosting change and his.
- Gate green.

### ~~T7 — Blu-ray.com backfill~~ 🔴 **shipped 2026-09-24 (`160f842`; sharper matching `bfc28e7`)**
**Acceptance: met, with the nightly job waiting on Craig's hosting step** (`OWNER-ACTIONS.md`
17). Three batches were run by hand and checked on 24 Sep: 314 Brave searches (about $1.57,
inside the month's free credit), 188 pages fetched five seconds apart, **178 discs with
specs**, and no halts or failures. **The 10 Sep records were all checked against their pages
and none was a UK edition**, so none was copied; 9 of those 10 discs got UK specs fetched
fresh, and Fight Club waits for Craig. The year check caught 10 pages for remakes and 2
doubtful identifications. **136 discs wait for Craig**, 43% of those searched (#213). CI
failed once, on the shared package's type-check, which the local gate lacked (#212).

**Covers snag 3.** Opus 5 · xhigh / GPT-5.6 Sol · Extra High. A wrong-edition match is wrong
data that looks right (Batch 24's reason), and the work runs under a risk acceptance (#110).
`DECISIONS.md` #202.

**Acceptance:**
- The 10 old spec records are restored onto the matching new discs, each one checked by its
  source URL.
- For each Blu-ray and 4K disc without specs, the outside search API proposes exact
  Blu-ray.com release pages, and only URLs that pass #110's release-page predicate count. A
  single strong match on title, year, format and UK edition is accepted. Anything else waits
  in a confirm queue in the app.
- Nothing is fetched until a page is accepted. Fetching runs in bounded nightly batches under
  #110's pacing and halt rules, with provenance on every row.
- Search spend is capped per run and counted.
- The Dolby Vision, Atmos and Region-free filters stay hidden while no disc has specs
  (#154's rule).
- Coverage is reported against the ~1,250 Blu-ray and 4K discs.
- **Owner steps first:** a Brave Search API account and key (a credential), and the job
  service's environment.

### ~~T9 — Identify the unmatched films~~ 🔴 **shipped 2026-09-25 (`4d16723`)**
**Acceptance: nine of nine met.** Craig read the dry run and said go on 25 Sep. The live run
applied his approved plan once: **156 identified, 166 for Craig, 35 set aside** (34 TV, 1
test row), 0 left alone and 0 failed. 80 Brave searches were recorded: the plan's 26 and the
54 of two unapplied dry runs. Films with a disc and no TMDB match went from 357 to 201.
Nothing merged; the 10 would-be merges wait on the Identify films page, which was checked in
a browser against the live data. **Knock-ons:** T7's second look settled 9 discs of
identified films, all now with specs. The Disc specs queue went from 136 to 197, because the
same batch searched 148 new discs. 133 valuations fell due, 41 were re-priced with the day's
last eBay calls, and 92 stay due. Local gate and CI green on the branch and on `main`; there
were no failures at close-out. Choices: #214. Live results: #215.

**Craig's request, 25 Sep**, after T7 showed these films are 41% of the Disc specs queue.
Opus 5 · xhigh / GPT-5.6 Sol · Extra High. It rewrites the film identities that discs and
watches hang off, and #194, #198 and #199 are the silent failures this area has already
produced.

**Today (25 Sep):** 366 live films have no TMDB match. 357 own a disc, 244 of them Blu-ray
or 4K; 1 has watch history; none has a year. The titles fall into kinds:
- typos: "Peepiing Tom", "Beaue Geste (1939)";
- remakes with nothing to choose between them: "Lolita", "Emma", "Mutiny on The Bounty";
- notes the search cannot use: "Kingdom of the Crystal Skull, The - Indiana Jones",
  "Enforcer, The (Humphrey Bogart}";
- a year outside brackets: "Murder by Decree 1979";
- TV series: "Steptoe & Son - Complete Series", "Dynasties";
- at least one test row: "Test 15.04.26".

**Acceptance:**
- A **dry run** classifies every unidentified film with a live disc and writes nothing:
  identify (with the evidence), ask Craig (with the candidates and why), or set aside (a TV
  series or not a film).
- The matcher uses what a title carries: a year in or out of brackets; a person named in
  brackets, checked against each candidate's TMDB credits; a series name after a dash; and
  brackets that do not close.
- A title TMDB cannot find gets **one** Brave web search for its TMDB page. The page's id is
  then confirmed through TMDB's own API. These searches count against Brave's monthly
  ceiling.
- **Automatic only when one TMDB film is a strong match**, and a year or a person agrees
  whenever TMDB holds another film of the same title. A match that would merge into a film
  the collection already has is never automatic: it waits for Craig with both films shown.
- Everything else waits on an **Identify films** page. Craig can pick a candidate, search
  again with a corrected title, mark the row as a TV series or not a film, or skip it. Each
  is one tap.
- Every identification is audited with the title it replaced, so it can be undone. Watch
  history moves with the film, as `apply_identification` already does, and #194/#198's
  guards hold.
- **The live run is Craig's to authorise** after he has read the dry run.
- Afterwards, T7's second look re-decides the discs whose film now has a year, and
  valuations that failed on a messy title are due again. Report films identified, and the
  Disc specs queue before and after.
- Gate green.

### ~~T10 — Search again for discs whose film was identified~~ 🟢 **shipped 2026-09-26 (`db75229`)**
**Acceptance: five of five met.** A batch run by hand on 26 Sep searched the 5 qualifying
discs first; 2 settled (The Fellowship of the Ring got specs; Dr. Strangelove's page is
accepted, its fetch answered 301). The run recorded both numbers. Local gate and CI green
first time; migration 039 applied. Only 5 discs qualified, not ~70: most cleaned titles
already read as TMDB's (#217).

**Proposed 26 Sep at Craig's word (#216), who said go the same day.** Opus 5 · high /
GPT-5.6 Sol · High. Small, but it spends Brave searches and moves discs in Craig's queue.
**Criteria authored 2026-09-26**, so `DECISIONS.md` #54 does not apply.

**Why:** T9's live run identified 156 films. T7's second look settled 9 of the 18 queued
discs of those films. The other 9 still wait, because their saved search results came from
the old, misspelt titles and the second look never searches again (#213, #215). The 61
queued discs of films still waiting on Identify films will be in the same position once
Craig identifies them.

**Acceptance:**
- A spec batch searches again, once, each queued disc (waiting for Craig, without specs,
  and not decided by him) whose film was identified after the disc was searched. The search
  uses the film's corrected title, and the matcher judges the new results as for any disc.
- "Once": a disc searched after its film's latest identification is not searched again.
  A page that failed its year check for a disc is never accepted for it again.
- These searches count in the batch's 150 and the month's 1,500, and go before discs never
  searched. The batch report says how many discs were searched again and how many settled.
- A disc Craig has decided on, or one with specs, is never searched again.
- Tests ship with it. Gate green.

### ~~T8 — Mark's eBay~~ **split on 2026-09-26 into T8a and T8b at Craig's word** (#216)
*Kept as the record of what was split. T8a and T8b below carry every criterion.*

**Covers snag 8.** Opus 5 · max / GPT-5.6 Sol · Max. It's the first personal third-party
account token this app holds (#142), and it spends money. `DECISIONS.md` #203.

**Acceptance:**
- "Connect eBay" in settings uses eBay's authorization-code consent with the fewest scopes.
  The token is encrypted at rest with a key from the environment, and disconnecting deletes
  it. Only the account's owner sees their eBay data.
- The app shows his watch list (Trading API `GetMyeBayBuying`) and his selling list
  (`GetMyeBaySelling`, active and sold).
- Price targets can be set on any watched item or saved search and are checked on a
  schedule. When one is met, a push arrives with a one-tap link. For auctions, the alert
  offers to set the target as a maximum bid on eBay, and eBay's own bidding takes over.
- Deal scan: new GB 4K and Blu-ray listings well below the film's usual asking price. Films
  on his Wanted list come first, and owned films are skipped unless the listing would be an
  upgrade. Finds go to the Deals page and arrive as a push, within a set share of the eBay
  allowance.
- The app never stores his eBay password or drives eBay's website. Automatic purchase stays
  off unless eBay grants Buy API access, which would be a separate decision.
- **Owner steps first:** OAuth settings in eBay's developer portal (redirect URL and RuName),
  the encryption key in Railway, and eBay keys on the job service.

### ~~T8a — eBay price alerts and the deal scan~~ 🟡 **shipped 2026-09-26 (`e2142b7`)**
**Acceptance: met, with the schedule waiting on Craig's config apply** (`OWNER-ACTIONS.md` 23).
Targets on a listing or on a film and format; a deal scan of eBay's newest UK Blu-ray and 4K
listings; no password or sign-in; Craig's OK given on 26 Sep. A read-only dry pass against live
eBay found 2 deals in the previous six hours for 25 calls. The film-page clause of the first
criterion was wrong and is amended below. CI failed once, on three new database tests that
read objects a refused request had expired (T9's lesson), then passed. The browser check found
and fixed an older Deals bug. Choices: #218.

**Proposed 26 Sep: Craig chose to split T8 (#216), and said go the same day.** Opus 5 ·
xhigh / GPT-5.6 Sol · Extra High. It spends a daily share of the eBay allowance on its own
and pushes to both phones. It signs nobody in and holds no personal token, which is why it is
not T8's max. **Criteria authored 2026-09-26 from T8's.** Covers the half of snag 8 that
needs no sign-in. `DECISIONS.md` #203.

**Acceptance:**
- A price target can be set on any eBay listing (a pasted link; ~~or a listing from the
  film page's eBay check~~, which shows medians and not listings, so the film page sets a
  saved search instead, #218) or on a saved search (a film and a format). Targets are checked on a
  schedule with the app's own eBay access. When one is met, a push arrives with a one-tap
  link. For an auction, the alert offers the target as a maximum bid to set on eBay, and
  eBay's own bidding takes over (#203).
- Deal scan: new GB 4K and Blu-ray listings well below the film's usual asking price. Films
  on the Wanted list come first, and owned films are skipped unless the listing would be an
  upgrade. Finds go to the Deals page and arrive as a push. The scan keeps to a set daily
  share of the eBay allowance that leaves the valuation's 750 calls and the film page's
  checks untouched.
- The app never asks for an eBay password or drives eBay's website. Automatic purchase
  stays off (#204).
- **Owner step:** the schedule is a job declared in `.railway/railway.ts` with the eBay keys
  by reference. Craig applies it, because that is a hosting change, so the merge waits for
  his OK, as T7's did. If `OWNER-ACTIONS.md` 17's apply has not happened by then, one apply
  starts both.
- Gate green.

### ~~T8b — Connect eBay: Mark's watch and selling lists~~ 🟡 **shipped 2026-10-04 (`2995b26`, [#33](https://github.com/CraigR973/mcu-app/pull/33))**
**Acceptance: met, with the first live sign-in Craig's** (`OWNER-ACTIONS.md` 29): it is what
proves the base scope is enough for eBay's two list calls, which were built and tested against
eBay's documented answers. Built at Craig's go of 4 Oct (#245); merged at his OK the same day,
because it changes `.railway/railway.ts`; no config apply is needed. Verified in production at
10:28 UTC: the merge SHA, `db: ok`, migration 047 at head, and the read-only role refused both
new tables. Each person connects their own eBay; their watch list, saved searches and selling
list are read live; a watched item or a saved search becomes a T8a alert, the saved search's
film found on Wanted or in the collection. The browser check and review found five faults,
fixed before the merge. Choices: #246.

**Proposed 26 Sep (#216). The eBay checkpoint passed on 3 Oct (`OWNER-ACTIONS.md` 18); at
Craig's word it starts after V9 merges, because both add a migration (#243). Group U, step 5. U4 was applied on its own on 28 Sep, so T8b's Railway change gets its own
apply.** Opus 5 · max / GPT-5.6 Sol ·
Max. It's the first personal third-party account token this app holds (#142). **Criteria
authored 2026-09-26 from T8's.**

**Acceptance:**
- "Connect eBay" in settings uses eBay's authorization-code consent with the fewest scopes.
  The token is encrypted at rest with a key from the environment, and disconnecting deletes
  it. Only the account's owner sees their eBay data.
- The app shows his watch list (Trading API `GetMyeBayBuying`) and his selling list
  (`GetMyeBaySelling`, active and sold).
- T8a's price targets can also be set on his watched items and his eBay saved searches.
- The app never stores his eBay password or drives eBay's website.
- **Owner steps first** (`OWNER-ACTIONS.md` 18): OAuth settings in eBay's developer portal
  (redirect URL and RuName) and the encryption key in Railway.
- **The owner steps' values, fixed 30 Sep** so Craig could set them before T8b is built
  (#227). T8b uses these rather than choosing its own:
  - the RuName's Auth accepted URL `https://mcu-app-fawn.vercel.app/settings/ebay/connected`
    and Auth declined URL `https://mcu-app-fawn.vercel.app/settings/ebay/declined`: web
    routes, so the page that receives eBay's code already holds the person's session and
    hands the code to the API with it;
  - the Privacy policy URL `https://mcu-app-fawn.vercel.app/privacy`, a public page T8b adds;
  - `EBAY_RUNAME` on `api`, the RuName eBay generates, sent as the `redirect_uri`;
  - `EBAY_TOKEN_KEY` on `api`, 32 random bytes in base64 (`openssl rand -base64 32`), from
    which T8b derives the key that encrypts the stored token.
- **Both variables are declared with `preserve()` in `.railway/railway.ts`.** Set in the
  console but undeclared, the next `config apply` would delete them (#124).
- Gate green.

## What is left — Group U, planned 26 Sep

**Proposed 2026-09-26 at Craig's request ("batch up all the remaining work"), and regrouped at
his word the same day. He said go on U1 → U2 the same day, with his yes to U2's column; the
rest still waits on the gates below.** Criteria authored 2026-09-26, so
`DECISIONS.md` #54 does not apply. This section is the whole remaining sequence: the new U
batches, the three older batches still open (21, T8b, 38), the two parked ones (33, 34), and
one item to close. **Since 30 Sep, Group V's table is the whole remaining sequence**; it keeps
every gate below and moves 38 to the very end. **Since 5 Oct, Group W runs before 38** (#249).

**The order, and what gates each:**

| Step | Batch | Gate |
|---|---|---|
| 1 | ~~U1 → U2~~ — moved Blu-ray.com pages, then editions | **go given 26 Sep**, U2's column included. **Both shipped:** U1 `cb1111f`, U2 `52fcced` |
| 2 | ~~U3 — three small calls: the assistant button, `/debug`, the brand assets~~ | **picks given 26 Sep; shipped** `e116ef2` |
| 3 | ~~U4 — re-price the collection on its own~~ | **shipped 28 Sep** `3974733`, fortnightly (#222, #223); applied the same evening |
| 3b | ~~22b — retailer sale pages that work (Zavvi, Second Sight, a "Check sale pages" button)~~ | **shipped 30 Sep** `eb51568` (#224–#226); the live check and save are Craig's, `OWNER-ACTIONS.md` 1e |
| 3c | ~~20b — shops that answer 429~~ | **shipped:** first half 1 Oct (`548160f`, [#19](https://github.com/CraigR973/mcu-app/pull/19)), at his "2) yes": a `429` no longer counts towards auto-disable, and each refusal records what the shop sent; second half 2 Oct (`abc17d6`, [#25](https://github.com/CraigR973/mcu-app/pull/25)), from one night's evidence at his word (#240): a refusal waits for `Retry-After` before its retry. **Read back 3 Oct: 2 of 27 got through after a minute; the remaining option, a fixed outbound address, is Craig's** (`OWNER-ACTIONS.md` 28). Criteria under Batch 20b |
| 3d | 22c — every page of a sale | **parked 4 Oct with `OWNER-ACTIONS.md` 28, at Craig's word** (#247); written 30 Sep. Criteria under Batch 22 |
| 4 | 21 — price history charts | **go given 28 Sep**; its 30 Sep session found only 2 wanted items priced by more than one shop, against 3. **Craig chose to add wants (30 Sep):** Bad Lieutenant and Dog Soldiers, both 4K, added that evening (#227). Starts once 3 wants have prices from two shops on two days or more, 2 Oct at the earliest. **1 Oct: 2 of 3**; the third needs a Shopify shop, refusing since 30 Sep (20b). **4 Oct: still 2 of 3** (Castle Freak, Dead Man's Shoes); Dog Soldiers is one Second Sight day short. With 28 left for now, the route is a want both Zavvi and Arrow sell, Craig's to add (#247) |
| 5 | ~~T8b — Connect eBay~~ | **shipped 4 Oct** `2995b26`; the first live sign-in is Craig's (`OWNER-ACTIONS.md` 29) |
| 6 | 38 — the end-to-end suite | last, so it pins the flows as they end up |
| — | 33 → 34 — Email | parked with `OWNER-ACTIONS.md` 7 |

**How they are grouped, and why** (Craig's word, 26 Sep):

- **U1 then U2, back to back on one go.** Both work from the Blu-ray.com page each disc settled
  on. U1 first means U2 fills editions from pages already corrected, and one live spec batch
  checks both. They stay two batches with two close-outs.
- **U3 carries three small calls in one batch.** The brand assets were U5; they joined the
  assistant button and `/debug` because all three are small, all wait on a pick Craig can make
  in one sitting, and one browser check verifies them. One close-out instead of two. This is a
  merge, which the grouping rule below does not grant on its own; Craig chose it.
- **U4 and T8b share a Railway config apply when the timing allows.** Both need one. If Craig's
  eBay set-up (item 18) happens before prices fall due on 24 Oct, one apply covers both; if not,
  U4 ships alone before 24 Oct.
- **21, T8b and 38 stay alone.** 21 waits only on the calendar, T8b is the one at max effort
  with a personal token, and 38 must be last.

~~**To close rather than build:** `OWNER-ACTIONS.md` 14, the before/after screenshots of the
10 Sep redesign.~~ **Closed at Craig's word, 28 Sep (#222).** Batch T3 had replaced that
navigation (#201), so the pair would have recorded a design that is gone.

**Craig's own work is not batched here**; it is in `OWNER-ACTIONS.md`, grouped there by
sitting: accounts (22, 18, 9), a phone session (16b, 3, 1d, 1h, 1j, 1c), the two queues
(Identify films, Disc specs), and one live run (1e).

### ~~U1 — Blu-ray.com pages that have moved~~ 🟢 **shipped 2026-09-26 (`cb1111f`)**
**Acceptance: six of six met.** A redirect is followed once, only to the same release number,
five seconds after the first request, and a `403` or `429` to it halts everything; anywhere
else, or a second redirect, sends the disc straight back to Craig with the address (#219).
Local gate and CI green first time (1,547 API tests against Postgres). **Live, 26 Sep:** a
batch run by hand at 14:35 UTC settled Dr. Strangelove's disc at 14:37: its page answered
`301` to a new name for release 117642, the fetcher followed it, and the disc's page and its
specs' source are now the new address. The batch: 148 Brave searches, 88 accepted, 89 pages
fetched, 83 with specs, 6 sent back (all the year check), no failures. 430 of 1,250 discs have
specs; 323 wait for Craig.

**Proposed 26 Sep.** Opus 5 · xhigh / GPT-5.6 Sol · Extra High: small, but it is #110's
ground, what the fetcher may request. Replaces the separate task offered on 26 Sep.

**Found 26 Sep (#217):** the fetcher treats a `301` from Blu-ray.com as a failed load. A page
whose address moved (Dr. Strangelove's, accepted that day) is retried in three batches and
then sent back to Craig.

**Acceptance:**
- A fetch answered with a redirect follows it once, and only when the new address passes
  #110's release-page predicate for the **same release number**. The redirect counts as a
  request under #110's spacing, and a `403` or `429` still halts everything.
- The disc's accepted page and its specs' source become the new address.
- A redirect anywhere else sends the disc straight back to Craig with the reason, rather than
  after three nights.
- Dr. Strangelove's disc settles on the first batch after the merge, checked live.
- A `DECISIONS.md` entry says why this stays inside #110.
- Tests ship with it. Gate green.

### ~~U2 — Record and show each copy's edition~~ 🟡 **shipped 2026-09-26 (`52fcced`)**
**Acceptance: four of four met.** Migration 041 adds a free-text edition to each copy, set and
corrected on the copy form. It is filled only where the settled page is certainly the copy
(#220); the backfill wrote **83 editions, all from pages that were the one UK edition the
search found** (none yet from pages Craig chose or pasted), matching the dry run exactly. The
archive list carries each film's editions in one grouped query (6 queries for all 1,866 films,
as for 20), with zod defaults for cached responses. "Collector edition" is relabelled
"Sub-category", since it holds the spreadsheet's groupings. Browser check at 375 and 1,280 px;
local gate and CI green first time (1,593 API tests against Postgres).

**Proposed 26 Sep; needs Craig's yes, because it adds a column.** Opus 5 · high / GPT-5.6
Sol · High. Replaces `OWNER-ACTIONS.md` 12.

**Found 26 Sep:** item 12 assumed an edition to show; **no copy records one**. What exists:
the Blu-ray.com page each of the 347 specced discs settled on names its edition in brackets
(258 plain; Masters of Cinema 11, Indicator 11, HMV Exclusive 11, and so on), and 346 carry
the studio as their label. The page is not always the copy: when several UK editions matched,
the matcher took the plain one (#212).

**Acceptance:**
- Each copy can hold an edition (free text, like the Wanted list's `preferred_edition`),
  set and corrected on the copy form.
- It is filled from the settled Blu-ray.com page only where that page is certainly the copy:
  Craig chose or pasted it, or it was the one UK edition the search found. Nothing is guessed.
- Browsing shows it on a film that has one: an additive list field, all a film's editions
  in one query and not one per film, with its zod schema; a cached response without it still
  parses.
- Tests ship with it. Gate green.

### ~~U3 — Three small calls: the assistant button, `/debug`, the brand assets~~ 🟢 **shipped 2026-09-26 (`e116ef2`)**
**Acceptance: four of four met.** Craig's picks, built (#221): no floating assistant button,
a top-bar icon beside the person's initial instead (and a top-bar link on a desktop), the five
bottom tabs still five; `/debug` in development builds only, proved by a test that builds the
production bundle, which proves the `VITE_SKIP_AUTH` bypass compiled out too; and pick B for
the brand files, 25 third-party images untracked and ignored, still on disk, with tests that
fail if one is tracked again. At 375 px nothing on Settings, Price alerts, Identify films, the
Archive (grid, list, compact) or a film page (four tabs) sits under anything, hit-tested
control by control; the check found and fixed two older faults (Settings' switch knobs, the
film page's tab counts). The shipped icons rebuild from a clean clone: every SVG byte for byte,
38 of 42 PNGs pixel for pixel, four within 2 of 255 levels. **Left for Craig, not blocking:**
36 tracked images built from stills or posters, four of which the live site serves (#221).
Local gate and CI green first time (1,593 API tests against Postgres, 408 web tests).

**Proposed 26 Sep; waits for Craig's three picks. Carries what was U5.** Sonnet 5 · medium /
GPT-5.6 Terra · Medium.

- **The floating assistant button still covers controls on a phone** (`OWNER-ACTIONS.md`
  11; seen again on 26 Sep over the Price alerts page). The item's three ways out predate the
  top bar: a sixth tab now conflicts with Craig's five (#201). **Proposed instead: an
  assistant icon in the top bar, beside the person's initial, and no floating button.**
- **`/debug` is public in production** (`OWNER-ACTIONS.md` 13). Its one button throws an
  error to test error reporting. **Proposed: development builds only**, the way
  `VITE_SKIP_AUTH` is compiled out.
- **The brand assets are in the repo after all** (`OWNER-ACTIONS.md` 15, corrected 26 Sep):
  all 195 files, 56 MB, since `fb6ecbd` on 10 Sep, third-party stills and posters included;
  the repository is private. **Proposed: stop tracking the third-party images and ignore
  their folders (B).** Rewriting history to remove them (C) is Craig's to run.

**Acceptance:**
- Craig's three choices, built.
- At 375 px no control on Settings, Price alerts, Identify films or a film page sits under
  anything.
- The third-party images are handled as Craig picks. With B: they are no longer tracked,
  their folders are ignored, they stay on disk, no new still or photograph can be committed,
  and the shipped icons still regenerate from a clean clone as far as the concept masters
  allow. *(Corrected 26 Sep: this line said "no film still or photograph enters history",
  which has not been possible since 10 Sep.)*
- Tests. Gate green.

### ~~U4 — Re-price the collection on its own~~ 🟢 **shipped 2026-09-28 (`3974733`)**
**Acceptance: three of three met** (#223). `cron-values` runs the Home button's valuation at 04:00
UTC on the 1st, 2nd, 15th and 16th, fortnightly at Craig's word (#222), with the eBay keys by
reference; it spends nothing when nothing is due and stays inside the day's 750 calls. The
merge waited for Craig's OK; the agent then ran the pinned plan (1 to add, 1 known change,
0 to destroy) and applied it at his word. Local gate and CI green first time (1,595 API tests
against Postgres). First run 1 Oct with nothing due; first with work 1 Nov.

**Proposed 26 Sep; needs Craig's yes, and his config apply starts it.** Sonnet 5 · medium /
GPT-5.6 Terra · Medium. `OWNER-ACTIONS.md` 19's optional cron.

**Built 28 Sep on `feat/u4-fortnightly-revaluation` (#223); the merge waits for Craig's OK
(`OWNER-ACTIONS.md` 24).** **Craig's yes, 28 Sep, with a change (#222): fortnightly, not daily.** "Repricing bi weekly is
enough." The first criterion below is amended to match: the job runs at 04:00 UTC on the 1st,
2nd, 15th and 16th, two mornings a fortnight, because a day's share prices about half the
collection and the whole of it falls due together.

Prices fall due 30 days after they were taken, the first on 24 Oct. Today only the Home button
re-prices them. **If T8b is ready before 24 Oct, its Railway change and this one go in one
apply;** otherwise this ships alone before 24 Oct.

**Acceptance:**
- A `cron-values` job in `.railway/railway.ts` runs `python -m src.scripts.value_collection`
  ~~daily at 04:00 UTC~~ at 04:00 UTC on the 1st, 2nd, 15th and 16th (#222), with the eBay keys
  by reference. On a day with nothing due it spends nothing, and it stays inside the day's 750
  calls.
- The merge waits for Craig's OK, as T8a's did; the plan should add one service and destroy
  nothing.
- Gate green.

## Group V — the 30 Sep snags, planned 30 Sep

**Planned 2026-09-30 from Craig's nine snags of that day**, reconciled against the code in
`docs/owner-snags-2026-09-30.md`, with his answers of the same evening (#228) and his shape
for the plan (#229). **Criteria authored 2026-09-30**, so `DECISIONS.md` #54 does not apply.
**Status: written into the plan at Craig's word ("just write into the plan"); go given 30 Sep
for an overnight run of V1 → V3 → V4 → V5 → V6, one pull request per batch (#230).** Its
prompt is `docs/group-v-overnight.md`. `main`'s red (`urllib3`) was fixed and this plan merged
the same evening, before the run ([#4](https://github.com/CraigR973/mcu-app/pull/4)). V7 onwards
wait as the table says.

**Model tiers.** This section names models by the tiers this ledger already uses: **top tier**
is the two models on Group U's row in "Batch groups" (Claude Code's and Codex's), **mid tier**
the two on Batch 21's row. Only the models are taken from those rows; each batch sets its own
effort, written as each tool spells it: Claude Code `medium`, `high`, `xhigh`, `max`; Codex
Medium, High, Extra High, Max.

**Two merges, Craig's choice (#229):** V2 is merged into V1, and V10 into V9, as U5 was into U3.
V2 and V10 are retired as batch names; their criteria are carried in V1 and V9 below.

**This table is now the whole remaining sequence**, in six sittings plus 21. A sitting runs
its batches back to back, and each batch keeps its own gate and close-out. Group U's open
batches keep their gates unchanged.

| Sitting | Batches, in order | Gate | Claude Code | Codex |
|---|---|---|---|---|
| 1 | V1 top bar, tints, back arrows, Loans → V3 movie night → V4 Craig's house → V5 Highlights | **Go given 30 Sep** for the overnight run, with V6 after it (#230); the production host allowed first (`OWNER-ACTIONS.md` 25) | top tier · high (from V4) | top tier · High |
| 2 | ~~V6 bid trial~~ → **Craig ran it and picked neither (1 Oct, #237)** → ~~V7 value from bids~~ (shelved) → ~~V8 Deals "usual" price~~ (shipped 2 Oct, `37e7c0a`) | **Done** | top tier · xhigh (from V6, V7) | top tier · Extra High |
| 3 | ~~V9 reviews: links, lines and scores~~ | **Shipped 3 Oct (`d1c3bf7`, [#30](https://github.com/CraigR973/mcu-app/pull/30))**, on Craig's Mac; AVForums links only and owned films followed to the reviewed edition, at his word (#241) | top tier · max | top tier · Max |
| 4 | ~~20b shops that answer 429~~ (first half `548160f`, 1 Oct) → ~~20b's second half~~ (`abc17d6`, 2 Oct) → 22c every page of a sale | **20b done; 22c parked:** the 3 Oct read-back showed a minute's wait gets 2 of 27 past the limit, and on 4 Oct Craig left the fixed outbound address for now (`OWNER-ACTIONS.md` 28, #247) | top tier · high | top tier · High |
| — | 21 price history charts | Starts itself once 3 wants have two shops' prices on two days (Group U); **2 of 3 on 4 Oct**, the third waiting on a want Zavvi and Arrow both sell, since 28 is left for now (#247) | mid tier · medium | mid tier · Medium |
| 5 | ~~T8b Connect eBay~~ | **Shipped 4 Oct (`2995b26`, [#33](https://github.com/CraigR973/mcu-app/pull/33))** at Craig's go and OK; the first live sign-in is his (`OWNER-ACTIONS.md` 29) | top tier · max | top tier · Max |
| 6 | 38 the end-to-end suite | Last, after every V batch and Group W (#249) | mid tier · high | mid tier · High |
| — | 33 → 34 Email | Parked (`OWNER-ACTIONS.md` 7) | top tier · max | top tier · Max |

**Each batch on its own** (what a batch needs if it is run outside its sitting):

| Batch | Covers | Size | Claude Code | Codex |
|---|---|---|---|---|
| V1 | Snags 7, 5 and 3: the top bar's background and the tints, back arrows, Loans always shown | 🟡 | mid tier · high | mid tier · High |
| V3 | Snag 4: movie night on one screen | 🟡 | mid tier · high | mid tier · High |
| V4 | Snag 6: Craig's house | 🟡 | top tier · high | top tier · High |
| V5 | Snag 9: Highlights on Home | 🟡 | mid tier · high | mid tier · High |
| V6 | Snag 2, step one: the bid trial | 🟡 | top tier · xhigh | top tier · Extra High |
| ~~V7~~ | ~~Snag 2: value from live bids~~ **shelved 1 Oct, #237** | 🔴 | top tier · xhigh | top tier · Extra High |
| ~~V8~~ | ~~Snag 1: the Deals "usual" price~~ **shipped 2 Oct (`37e7c0a`)** | 🟡 | top tier · high | top tier · High |
| ~~V9~~ | ~~Snag 8, and V5's fourth row: reviews~~ **shipped 3 Oct (`d1c3bf7`)** | 🔴 | top tier · max | top tier · Max |

*Why those efforts.* V4 writes a migration against a live table's CHECK, and migrations are
where this repo's green local gates have hidden faults (gotchas 15 and 18). V6 and V7 change
what the collection's value means for 1,457 discs and spend live eBay calls. V9 opens a new
scraping surface under a widened risk acceptance (#110, #228), the kind of work Group F's
scrapers did at `max`. The rest is interface work with clear criteria.

**Craig's steps, inside the batches** (#229), not before them:

- **Sitting 2:** once V6 is live, the sitting stops and asks Craig to tap "Try bid prices" on
  Home, then to choose a blend or bids only from its report. It carries on to V7 with his pick.
- **Sitting 3:** V9 starts by asking Craig to allow blu-ray.com and avforums.com in the
  environment's network settings (the 30 Sep session could reach neither). It asks him to
  raise Brave's monthly limit only if the month's credit has run out when it gets there.
- **Sitting 1:** the two-phone match check for V3 is still Craig's, as T4's was.

**Running a sitting from a cloud session** (checked 30 Sep, #230):

- **Each batch lands through a pull request.** Its own `feat/` (or `fix/`) branch from `main`,
  a pull request, CI green, then the session merges it with a merge commit, verifies
  production, and lands the close-out's docs through a second pull request. Craig said yes on
  30 Sep. CI runs on pushes to `main`, `feat/**`, `fix/**` and `chore/**`, and on pull
  requests.
- **The whole gate runs in the container.** `/usr/bin/python3.12 -m venv apps/api/.venv`, then
  `pip install --require-hashes -r apps/api/requirements-dev.lock`; `pnpm install
  --frozen-lockfile` on the container's Node 22. A throwaway local Postgres 16
  (`/usr/lib/postgresql/16/bin`, run as the `postgres` user) takes the API suite from 583
  skipped to none: 1,634 passed on 30 Sep. CI's Postgres 17 stays the authority.
- **The close-out's health check needs `api-production-a8fe.up.railway.app`**, which the
  30 Sep session's network policy refused. Craig allows it before a run
  (`OWNER-ACTIONS.md` 25); without it a run stops before its first merge.

**Why this order.** Sitting 1 needs nothing from anyone and is what Craig sees every day; V1
comes first because it fixes a fault visible on every page, and V1's back arrows change the
same top bar. Sitting 2's trial is quick to build, so the pick can be made early. V8 averages
V7's eBay figure, so it follows V7 rather than being built twice. *(V7 was shelved on 1 Oct,
#237, so V8 averages today's eBay figure, the asking prices.)* Sitting 3 waits on nothing,
but its first step is Craig's. Group U's 20b and 22c keep their gate and slot in when it
clears. 38 moves from after T8b to the very end, so it pins the flows sittings 1 and 2 change.

### ~~V1 — Top bar, tints, back arrows and Loans~~ 🟡 **shipped 2026-09-30 (`13791c2`, [#6](https://github.com/CraigR973/mcu-app/pull/6))**
**Acceptance: all met.** The five steps (12, 14, 88, 94, 96) are in the theme and all 20
classes in the built stylesheet; `theme/opacity-steps.test.ts` fails on any step the theme
lacks, naming file and line, and with the theme change reverted it lists exactly the 20. On a
phone only the four bottom tabs and You are top-level; every other page has the arrow, which
falls back to You for a page You lists and to the parent otherwise. The film page's Back
returns to where it was opened from (the Archive with no history) and hides below 1024 px.
Loans is always listed, for both; the navigation test moved from eight to nine. Browser check
at 375 and 1280 px, light and dark, against the real API on a throwaway local Postgres (#231).
Local gate and CI green first time (1,634 API tests, web 428, shared 114). **Nothing is left
open.** The bars are 94% and 96% opaque as the redesign asked, so a faint shadow of the page
shows through the bottom bar in the light theme; fully solid is a one-class change if Craig
wants it.

**Covers snags 7, 5 and 3. Carries what was V2 (#229).** Mid tier · high / mid tier · High.
Sitting 1, first. **The top bar has had no background since 10 Sep (`9afc173`):**
`bg-background/94` names an opacity step Tailwind 3 does not have, so the class is never built,
and only the blur is left. 20 classes in 10 files share the fault: the bottom tab bar (`/96`),
every tinted badge and notice (`/12`), the format badges (`/14`) and the filled buttons' hover
(`/88`). The back arrows change the same top bar, which is why V2 joined it.

**Acceptance:**
- The missing steps (12, 14, 88, 94, 96) are added to the Tailwind theme, so all 20 classes
  are built as written. Proved by the built stylesheet containing them.
- A test fails when any class in `apps/web/src` names an opacity step the theme lacks, so a
  dropped class cannot recur silently.
- On a phone the top-level pages are the four bottom-tab pages (Home, Archive, Add, Movie
  night) and You. Every other page shows the top bar's back arrow. It goes back through
  history; with none (a notification, a link) it goes to You for a page listed there, and to
  the page's parent otherwise.
- The film page's back button returns to where the person came from, and to the Archive when
  there is no history. Below 1024 px it is hidden, since the top bar's arrow does that job.
- **Loans is always listed, for Mark and Craig** (#228), in the sidebar and on the You page.
  Box sets, Collections and Deals keep hiding while empty (#154). The navigation test's count
  moves, with the reason beside it. Lending and "Mark returned" stay admin-only.
- Browser check at 375 px, light and dark: the top and bottom bars are opaque with content
  scrolled under them; the Deals discount badge, a movie-night vote chip and a format badge
  show their tint; Wanted, Deals and Settings opened from You show the arrow and return to You;
  a film opened from Deals returns to Deals, at 375 px and at 1280 px.
- Gate green.

### ~~V2 — Back arrows, and Loans always shown~~ **merged into V1 at Craig's word, 30 Sep (#229)**
Its criteria are V1's now. The name is retired, as U5's was.

### ~~V3 — Movie night on one screen~~ 🟡 **shipped 2026-09-30 (`0b29e58`, [#8](https://github.com/CraigR973/mcu-app/pull/8))**
**Acceptance: all met but the two-phone check, which is Craig's** (`OWNER-ACTIONS.md` 16b, as
T4's was). A night is the shortlist alone: each film has one Add / Added control, and Added takes
the vote back as a vote of `false` (#232). The deck, its gestures, its arrow keys and its "N of
M" count are gone; "Start swiping" is "Start movie night". Tapping a film opens its synopsis,
runtime, genres, cast, who else in the night has seen it and when, where it streams, and a link
to its page, in the row. The API's vote and match logic is unchanged; the one server string that
still said swipe, the push that sends a night, now names the shortlist. **Tests removed, and
why:** "says 'Skip' and 'Add' in the deck" (the deck and Skip are gone), "leaves arrow keys with
an editable field and votes only from the deck" (the arrow keys went with the deck), and "opens
on the shortlist, with your own vote on each film" (rewritten for the list); nine list tests,
one page test and two API tests replace them. Browser check at 375 and 1280 px on the rig (#231),
with a two-person match across two browser contexts: announced to both, 2 pushes queued, and not
announced again after a take-back and re-add. Local gate and CI green first time (1,636 API
tests, web 435).

**Covers snag 4.** Mid tier · high / mid tier · High. Sitting 1, second. Craig chose the list
over the swipe deck (#228), which retires Phase 8.4's "swipe-like UI" and #207's arrow-key rule.

**Acceptance:**
- A night is one screen, the shortlist. Each film has one Add / Added control; tapping Added
  takes the vote back. The swipe deck, its gestures, its arrow keys and its "N of M" count are
  removed, and "Start swiping" is renamed where it starts a night.
- Tapping a film opens its details in the row: synopsis, runtime, genres, cast, who else has
  seen it and when, where it streams, and a link to its page.
- A match is still everyone adding the same film, announced once, with its push. The other
  person's votes stay hidden (#157). The API does not change: `record_vote` already replaces
  a vote.
- The deck's tests are replaced by tests of voting on the list, and the close-out names each
  test removed and why: a feature removed, not a test weakened.
- Browser check at 375 px and 1280 px. The two-phone match check is Craig's, as T4's was.
- Gate green.

### ~~V4 — Craig's house~~ 🟡 **shipped 2026-09-30 (`f7a66f8`, [#10](https://github.com/CraigR973/mcu-app/pull/10))**
**Acceptance: all met.** "Craig's house" is in `SECTIONS` (no shelves), in the parser (with the
apostrophe, without it, or an iPhone's curly one), and in `ck_collection_items_section` through
migration 042, which doubles the apostrophe where 007's pasting would have ended the SQL string;
it writes no rows, and its downgrade clears `section` on those rows before narrowing the CHECK
and leaves `location` alone. `test_craigs_house.py` proves the clause, the constraint Postgres
holds, and a real downgrade and upgrade with a disc there, inside a rolled-back transaction: the
round trip CI's empty schema cannot make (#233). The copy form offers every section through the
facets' new `allSections`; the Archive's filter still lists only places that hold a disc.
Browser check at 375 px on the rig: Local Hero moved to Craig's house, then found alone by the
section filter. Also: the assistant's browse tool names every section (it had missed the
cabinets since Batch 6). Local gate and CI green first time (1,655 API tests, web 439).
**Nothing is left open.** No disc is in Craig's house yet: the first move is Craig's.

**Covers snag 6.** Top tier · high / top tier · High. Sitting 1, third. "Craig's house is
fine" (#228): that name, one place with no shelves, counted like any other disc.

**Acceptance:**
- "Craig's house" is a section: in `SECTIONS`, in the location parser (typing "Craig's house"
  or "Craigs house" lands there), and in the `ck_collection_items_section` CHECK through a
  reversible migration. The apostrophe is escaped in the SQL, with a test: migration 007's
  `_check_clause` pastes names inside quotes and would break on it.
- The copy form's Section picker offers every section, including one with no discs yet. The
  Archive's section filter still lists only sections that hold a disc.
- The migration writes no rows. Its downgrade clears `section` on rows using the new name
  before narrowing the CHECK, and leaves `location` alone, as 007's does.
- Browser check at 375 px: a disc moved to Craig's house, then found by the section filter.
- Gate green.

### ~~V5 — Highlights on Home~~ 🟡 **shipped 2026-10-01 (`f1b497c`, [#12](https://github.com/CraigR973/mcu-app/pull/12))**
**Acceptance: met; the open check closed on 1 Oct.** The four statements, captured from
`highlights()` as #234 did, ran under `EXPLAIN (ANALYZE, BUFFERS)` on production's own rows
through `live_sql`, four times each: medians **3.5, 0.8, 2.9 and 10.3 ms** (planning 1.7, 0.2,
0.7 and 2.9 ms more), against the scratch run's 3.1, 0.8, 1.9 and 8.4. **The same shapes:**
sequential scans at ~2,000 rows, index scans on the joins, every page a shared-buffer hit.
Most rewatched's extra millisecond is mostly its sequential scan of production's `movies`,
13 MB for 1,888 rows (1.4 ms); most valuable joins 1,303 priced discs to `movies` twice by
index, against a planner estimate of 7. About 23 ms of database time for the endpoint, so
still no cache (§17 row 33).

**As shipped:** Home has a Highlights panel after "Worth a
rewatch": up to 12 posters a row, each opening its film, from one request,
`GET /api/v1/highlights`. **Top rated** is films on the shelf (`owned_copy()`) at 4½ or 5 stars
by each person's highest rating, each poster naming whose; the row says "Rated 4½ or 5 stars by
Craig. Mark has not rated any films.", built from who has rated anything, so it stays true when
Mark starts. **Most rewatched** counts viewings in both diaries, twice or more, and says whose
("Craig 3 · Mark 1"). **Most valuable discs** are owned physical discs at their stored
film-and-format value, through the `owned_valued_discs()` the collection's total now shares,
with the basis, listings and date. A row with nothing in it is not shown, nor the panel when all
three are empty. **The query plans were read at production's counts, not on its rows:**
`EXPLAIN (ANALYZE, BUFFERS)` on the endpoint's own SQL against a scratch Postgres seeded to
`STATUS.md`'s figures gave 3.1, 0.8, 1.9 and 8.4 ms, the endpoint 22 ms median (#234). Browser
check at 375 px, light and dark, on the rig. Local gate and CI green first time (1,662 API
tests, web 448, shared 117). ~~Open: the same plans against production's own rows~~ — read on
1 Oct, above. "Best reviewed" stays V9's.

**Covers snag 9.** Mid tier · high / mid tier · High. Sitting 1, last. "A mix of all" (#228).

**Acceptance:**
- Home gains a Highlights panel of short poster rows, each film opening its page:
  - **Top rated:** films on the shelf rated 4½ or 5 stars, with whose rating it is. Craig rates
    on Letterboxd and Mark does not (#159), so the row says so rather than implying both.
  - **Most rewatched**, across both diaries.
  - **Most valuable discs**, at their stored value, with its basis.
  - **Best reviewed** is V9's to add, once review scores exist.
- A row with nothing in it is not shown.
- One request for the panel, its query plan read against the real row counts.
- Browser check at 375 px.
- Gate green.

### ~~V6 — Trial: pricing from live bids~~ 🟡 **shipped 2026-10-01 (`153d45b`, [#14](https://github.com/CraigR973/mcu-app/pull/14))**
**Acceptance: met; the run and the pick are Craig's.** Home has an admin-only "Try bid prices"
after "What it's worth": up to 100 priced, owned films and formats, a third each on 4K, Blu-ray
and DVD, one search each with `buyingOptions:{FIXED_PRICE|AUCTION}`. It claims a
`valuation_runs` row (trigger `trial`, migration 043), so its calls come out of the day's 750
and it never overlaps a valuation run; **it saves no prices** (a test snapshots
`disc_valuations`). An auction counts only with a bid and past the valuation's own matcher
(`ebay/bids.py` makes the current bid the listing's price); three make a bid price. The report
answers each question below, by format and overall, compares bids with the asking price from
the same search, and is kept on the run row (`valuation_runs.report`) and served by
`GET /collection/value/bid-trial` (#235). **No live eBay request was made:** the tests and the
375 px rig check used payloads built from the captured Blade Runner 2049 search, its one
auction edited to carry bids. Local gate and CI green first time (1,683 API tests, web 458,
shared 119). **Open, Craig's:** tap "Try bid prices" (about 100 of the day's 750 lookups), read
the report, and pick a blend or bids only, which starts V7 (`OWNER-ACTIONS.md` 26).

**Covers snag 2, first step.** Top tier · xhigh / top tier · Extra High. Sitting 2, first.
"Lets trial first" (#228). Sold prices stay out of reach, signed in or not (#16, #126, #228).
**The sitting stops here** once V6 is live: Craig taps "Try bid prices" on Home and picks a
blend or bids only from its report (#229).

**Acceptance:**
- An admin-only "Try bid prices" on Home searches eBay once per film and format for a sample
  of up to 100 priced films across 4K, Blu-ray and DVD, asking for Buy It Now and auctions
  together (`buyingOptions:{FIXED_PRICE|AUCTION}`). Its calls count against the day's
  valuation share (#209). **It saves no prices.**
- An auction counts only with at least one bid, and passes the same matcher: standard edition,
  the right film and format, a UK seller.
- The report says, by format: how many films had three or more auctions with bids; for those,
  the bid median against the asking median; how many of those auctions end within 24 hours;
  whether sharing the 200 results with auctions cost Buy It Now listings; and what the sampled
  discs total on each basis.
- The report is kept where a later session can read it, not only shown once.
- Gate green. The run is Craig's, and his pick of blend or bids only follows it.

### ~~V7 — Value from live bids~~ 🔴 **shelved 2026-10-01 at Craig's word ("1) neither", #237)**
**Shelved:** V6's trial (below) found no film with a bid price, so a blend would equal
today's asking prices and bids only would value nothing. Values stay on asking prices. The
criteria stay below, unbuilt, in case bids are ever thick enough to be worth a second look.

**Covers snag 2.** Top tier · xhigh / top tier · Extra High. Sitting 2, after Craig's pick.
Written for a blend; a pick of bids only changes the second point.

**V6's trial, run by Craig on 1 Oct at 14:14 UTC** (read with `live_sql` from
`valuation_runs.report`, run `6edadb88`). eBay answered all 100 searches. **No film has a bid
price:** 12 films had any matching auction with a bid, the most on one film was 2 (The Da
Vinci Code, 4K), and a price needs 3.

| | 4K | Blu-ray | DVD | All |
|---|---|---|---|---|
| Films searched | 34 | 33 | 33 | 100 |
| With a bid price | 0 | 0 | 0 | 0 |
| Matching auctions with a bid | 10 | 3 | 0 | 13 |
| … ending within 24 hours | 0 | 1 | 0 | 1 |
| Matching auctions, no bid | 8 | 31 | 71 | 110 |
| Auctions the matcher turned away | 47 | 86 | 65 | 198 |
| Searches cut at 200 | 5 | 8 | 13 | 26 |
| Places auction-only listings took in them | 29 | 81 | 88 | 198 |
| Films that lost their asking price | 0 | 0 | 0 | 0 |
| Stored (asking, last run) | £1,054.73 | £527.19 | £285.40 | £1,867.32 |
| Today's asking | £1,057.60 | £546.12 | £299.62 | £1,903.34 |
| Bids only | £0, 0 discs | £0 | £0 | £0 |
| Blend | all asking | all asking | all asking | £1,903.34 |

**Bids against asking** cannot be compared: no film has both. **What it means for the pick:**
today a blend values every disc exactly as asking prices do, and bids only values none.
Sharing the 200 places cost no film its asking price.

**Acceptance:**
- The valuation's one search per film and format reads Buy It Now and auctions together.
  Auctions count only with a bid, and only within the time-to-end window V6's report supports.
- A disc is valued on current bids when three or more auctions with bids stand behind it, and
  on asking prices otherwise. Each stored value records its basis and sample size; the
  migration is reversible.
- Home shows the total split by basis ("£X from bids on N discs, £Y from asking prices on M
  discs"), and each disc's value says which.
- The Deals "usual" figure (`ebay_price_refs`) follows the same rule, so the two cannot
  disagree.
- Every disc is re-priced on the new basis within two of the fortnightly mornings, at 750
  calls a day (#223), or sooner from Home's Update values.
- Gate green.

### ~~V8 — The Deals "usual" price~~ 🟡 **shipped 2026-10-02 (`37e7c0a`, [#22](https://github.com/CraigR973/mcu-app/pull/22))**
**Acceptance: met.** An eBay find's "usually" is the average of eBay's figure (asking
prices) and each watched shop's latest price for the film on the format from the nightly
check's last seven days, like for like: the same format, read off the listing priced, and
a standard edition by the eBay matcher's own rule (#239). eBay's figure alone where no shop
has one, which is most finds. The scan judges the 70% rule against that figure and keeps
its parts in `deals.usual_sources` (migration 044, applied in production). The card reads
"£4.75 with postage · usually £18.00" with "eBay £16.00 before postage · Zavvi £20.00"
beneath; a find stored before V8 reads as eBay alone. "Sold on eBay" on the eBay card and
"Sold listings on eBay" under each disc's stored value on the film page open eBay's sold
listings in a new tab, searched with the same words as the asking prices. Browser check at
375 px, light and dark, against the real API on the throwaway test database (#169). Local
gate and CI green first time (1,724 API tests, warnings 177; web 463, shared 123).
Production reported the merge SHA at 03:36 UTC with `db: ok`. The like-for-like rule (#239)
kept at Craig's word, 2 Oct ("yes keep").

**Covers snag 1.** Top tier · high / top tier · High. Sitting 2, last. **V7 is shelved (#237),
so eBay's figure is today's: the asking-price median in `ebay_price_refs`.**

**Acceptance:**
- An eBay find's "usually" is the average of eBay's figure for the film and format (asking
  prices, V7 being shelved) and
  the latest price from each watched shop that stocks it, from the nightly check within the
  last 7 days. With no shop price, eBay's figure alone. Sold prices are not part of it (#228).
- The card says what the figure is: "£P with postage · usually £U", and beneath it where £U
  comes from ("eBay £A before postage · Zavvi £B").
- The 70% rule (`DEAL_RATIO`) compares with the new figure.
- The eBay deal card and the film page's value each link to eBay's own sold listings for the
  film and format. They open in the person's browser, where eBay asks for a sign-in.
- Shop prices exist only for Wanted films, because the nightly check reads only the Wanted
  list. Asking the shops about every eBay find is left out: it multiplies requests to shops
  already answering 429 (20b).
- Gate green.

### ~~V9 — Reviews: links, lines and scores~~ 🔴 — **shipped 2026-10-03 (`d1c3bf7`, [#30](https://github.com/CraigR973/mcu-app/pull/30))**
**As shipped, live 22:47 UTC on 3 Oct with migration 046:** `film_reviews` holds each
site's review of a film and format (its page, Brave's title and line, and for Blu-ray.com
the review's scores under its own headings with when they were read); `review_runs` counts
every Brave search into the month's total (#202). Adding a want searches both sites once
the response has gone; the nightly `cron-specs` job, after the spec batch, searches the
wants still without a review, seeds a row for each owned film and format from its spec
page, and reads up to 150 Blu-ray.com pages five seconds apart, following a page's link to
the edition that carries the review (#241). AVForums is links only, and the app says why.
Wanted items and the film page show "Reviews: Blu-ray.com · AVForums" with Brave's line and
the scores once read; Home's Highlights has its fourth row, "Best reviewed": owned films by
Blu-ray.com's Overall, for a format on the shelf. Browser check at 375 px, light and dark
(#169's method); it found Brave's line unclamped, fixed before the merge. **First nightly
run, 4 Oct 02:01–02:16 UTC, read back at 02:40:** finished, no halt; 20 Brave searches
found 16 reviews (Blu-ray.com 10 of 10 wants, AVForums 6), and 150 Blu-ray.com requests
scored 81 reviews (8 wanted films', 73 owned), with 3 showing none and 1 another year's
film (Dead Man's Shoes, catalogued as the 1940 film). 651 owned films and formats wait,
about five more nights. **Open:** AVForums' scores (forbidden; Craig chose links only) and
AVForums for owned films (a higher Brave budget, Craig's call).

**Runs on Craig's Mac, at his word on 2 Oct** (`docs/next-mac-session.md`, after 20b's second
half): the Mac reaches blu-ray.com and avforums.com, so the network step below is not needed.

**Covers snag 8 (all three options) and V5's fourth row. Carries what was V10 (#229).** Top
tier · max / top tier · Max. Sitting 3, alone. It opens a new scraping surface under #110 as
widened by #228, which is why it runs at Group F's effort.

**Before any code, 3 Oct 00:00–00:20 UTC, on the Mac (#241).** Two Brave searches for Dog
Soldiers (4K) and two Blu-ray.com pages, one request each, saved as fixtures; AVForums'
`robots.txt` (one request) and its terms (read in a browser after the app's client got a
`403`).
- **AVForums forbids automated access.** Its terms, §3.6: "You may not access these Services
  through automated or programmatic means (such as through a content scraper) without prior
  permission from us"; its `robots.txt` says the same of scraping; and it answers the app's
  client with Cloudflare's "Just a moment…" challenge, an access control #110 forbids
  evading. **Links only, at Craig's word ("Links only"), and the app says why.** Brave
  finds its reviews directly: "Dog Soldiers 4K Blu-ray Review | AVForums" at
  `/reviews/<slug>.<id>/`, its line a quote from the review.
- **Blu-ray.com's review lives on one edition's page, and Brave cannot say which.** Brave
  returns release pages, every one with the same boilerplate line. The UK 4K release's page
  (315545) has no review: every score `0.0`, and "No review exists for this particular
  release" above links to the editions that have one. The US 4K page (314666), Brave's first
  hit, carries it: "Blu-ray review" scores Movie 3.5, Video 4K 4.0, Video 2K 4.5, Audio 3.5,
  Extras 5.0, Overall 4.0, out of 5, beside a members' rating that is never read.
- **So "for owned films … if the capture shows the review lives there" is false for the
  page found for specs**, which is the UK release. At Craig's word ("Yes, follow the link"),
  owned films follow that page's link to the reviewed edition of the same format: up to two
  paced requests per film and format, about 1,060 in all, 150 a night, no searches. Wanted
  films do the same from the page Brave proposes.

**Acceptance:**
- **Craig's steps come first, inside the batch (#229).** The session asks Craig to allow
  blu-ray.com and avforums.com in the environment's network settings (the 30 Sep session could
  reach neither). It asks him to raise Brave's monthly limit only if the month's credit has run
  out when it gets there.
- **Before any code:** a Blu-ray.com review page and an AVForums review page are captured as
  real fixtures, and AVForums' terms and robots.txt are read. If AVForums forbids automated
  access, it stays links-only and the app says so; its scores would then need another decision.
- **Finding:** when a film is added to Wanted, and once for those already there, Brave is
  searched for its review on Blu-ray.com and on AVForums. A result is kept only if it is that
  site's review of that film, and of that format on Blu-ray.com. Finding a review sends no
  request to either site. Searches count towards the month's Brave total (#202) under a cap of
  their own, and a failed search leaves the want as it was, to try again.
- **Showing:** each Wanted item and film page shows "Reviews: Blu-ray.com · AVForums" as links,
  with Brave's one-line description of each and, once read, the review's scores.
- **Scores:** Blu-ray.com's out of 5 and AVForums' out of 10, each under the site's own
  headings, read once per review and stored with the page address and the time.
- **#110's other bounds hold unchanged:** exact page addresses only, no search routes,
  sequential and paced, a 403 or 429 halts the integration, and every stored row names its
  source so it can be removed.
- **For owned films,** Blu-ray.com's scores come from the release pages already found for
  specs, if the capture shows the review lives there, paced like the spec batch and needing no
  searches. AVForums' for owned films only if Craig raises Brave's budget.
- V5's Highlights gains its "Best reviewed" row.
- Gate green.

### ~~V10 — Review scores~~ **merged into V9 at Craig's word, 30 Sep (#229)**
Its criteria are V9's now. The name is retired.

## Group W — the 5 Oct snags, planned 5 Oct

**Planned 2026-10-05 from Craig's seven snags of that day**, reconciled against the code in
`docs/owner-snags-2026-10-05.md`, with his answers the same day (#249). **Criteria authored
2026-10-05**, so `DECISIONS.md` #54 does not apply. **Go given 5 Oct for W1 → W2 → W3, a pull
request per batch**, run on Craig's Mac. Model tiers are Group V's: top tier is the two models
on Group U's row in "Batch groups", mid tier the two on Batch 21's row.

| Sitting | Batches, in order | Gate | Claude Code | Codex |
|---|---|---|---|---|
| 1 | ~~W1 search and top bar~~ (`9dd6805`) → ~~W2 Home~~ (`0a87625`) → ~~W3 lend and borrow~~ (`3ad71eb`) | **Go given 5 Oct** (#249) | top tier · high (from W3) | top tier · High |

**Each batch on its own:**

| Batch | Covers | Size | Claude Code | Codex |
|---|---|---|---|---|
| W1 | Snags 1 and 5: the search keyboard, the top bar | 🟢 | mid tier · high | mid tier · High |
| W2 | Snags 3, 4, 6 and 7: Home as rows, the collection first | 🟡 | mid tier · high | mid tier · High |
| W3 | Snag 2: lend and borrow, from Loans with the scanner | 🟡 | top tier · high | top tier · High |

*Why those efforts.* W3 writes a migration (one nullable column on `loans`, which held 0 rows
on 5 Oct), widens who may write loans, and changes the reminder job; V4 ran its migration at
top tier · high. W1 and W2 are interface work with clear criteria.

**How each lands, on Craig's Mac:** its own `feat/` branch from `main`, a pull request, CI
green, then a merge commit; production `/api/v1/health` must report the merge SHA and
`/health/ready` `db: ok`; the close-out's docs land through a second pull request (#230's
method). **Browser checks use #169's method:** the DEV-only auth bypass and a scratch stub of
the API, both kept out of the tree, since the Mac has no local Postgres. **The iPhone is
Craig's:** W1's keyboard and top bar go into `OWNER-ACTIONS.md` when W1 ships.

### ~~W1 — The search keyboard and the top bar~~ 🟢 **shipped 2026-10-05 (`9dd6805`, [#38](https://github.com/CraigR973/mcu-app/pull/38))**
**Acceptance: met; the iPhone checks are Craig's (`OWNER-ACTIONS.md` 30).** Search's sheet is
built and its box focused inside the tap (`flushSync`); a test listening on `window` at the
end of the same click finds the box focused, and failed against the old code. The top bar
takes the bottom bar's surface and shadow, its back arrow and assistant icon at full
strength: at 375 px dark `33,28,23` against the page's `18,15,13`, light `254,253,251`
against `246,244,238`. 1,280 px checked in both themes. Browser check by #169's method with
the stub's data read from production, read-only (#250). Local gate green (API 1,188 passed,
644 skipped without Postgres; web 502, shared 131); CI green first time; production reported
the merge SHA at 15:08 UTC with `db: ok`, 25 minutes after the merge: Railway's builds from GitHub were
queuing (its incident that afternoon). cron-scrape's deployment failed at Railway's image push in
the same incident; its previous one, with the same API code, stayed live, and the next merge
redeploys it. **Open:** the keyboard and the bar's look on an
iPhone, and Craig's screenshot if the bar still looks faded (the light theme's status bar).
**Follow-up, 5 Oct** ([#44](https://github.com/CraigR973/mcu-app/pull/44)): Craig, dark theme, "still faded when i hit search". The search
sheet covers the top bar while open and had kept the page's colour; it takes the bar's surface
now, measured `33,28,23` for both at 375 px.


**Covers snags 1 and 5.** Mid tier · high / mid tier · High. Sitting 1, first.

**Snag 1.** The bottom bar's Search builds its sheet after the tap and focuses the box one
animation frame later. iOS raises the keyboard only for a focus made while the tap is being
handled, so Craig's iPhone needs a second tap on the box.

**Snag 5.** V1's background is built, but the top bar sits above the page's scrolling region,
not over it, so it shows the page's own colour either way: 94% of the page's colour over the
page's colour is the page's colour. Measured at 375 px on 5 Oct in both themes. The bar reads
as part of the page, its back arrow and assistant icon in the muted colour, while the bottom
bar is a lighter panel with a shadow. Whether Craig's "faded" is that, or iOS drawing the clock
and battery in white over the light theme's cream bar (`black-translucent`), waits on his
screenshot (`docs/owner-snags-2026-10-05.md`, snag 5).

**Acceptance:**
- Tapping Search opens the sheet with its box focused **before the tap's handler returns**: a
  test clicks Search and finds the box focused without running an animation frame. The
  `mcu:focus-search` event stays the way in, as the `/` shortcut already uses it.
- The phone's top bar is a raised panel, distinct from the page in both themes: the bottom
  bar's surface (`popover`) and a shadow. Its back arrow and assistant icon are drawn at full
  strength. Measured at 375 px, light and dark: the bar's colour differs from the page's.
- At 1,280 px the top bar still sits correctly beside the sidebar (checked, not redesigned).
- `OWNER-ACTIONS.md` gains Craig's iPhone check: Search opens with the keyboard up, and the top
  bar no longer looks faded. If it still does, his screenshot settles the status-bar question.
- Browser check at 375 and 1,280 px, light and dark.
- Gate green.

### ~~W2 — Home: every section a row, the collection first~~ 🟡 **shipped 2026-10-05 (`0a87625`, [#39](https://github.com/CraigR973/mcu-app/pull/39))**
**Acceptance: met.** Home runs The collection (number cards, then chart cards) → Coming to disc →
Top rated → Most rewatched → Most valuable discs → Best reviewed → On this day → Worth a rewatch →
Completion → Pinned collections → Recent activity, every section but the last a row that scrolls
sideways (one `Shelf` component), each hidden while empty and showing its own error. Most watched,
Home's own Add a disc, and the bid trial with "Update values" are gone from Home; the last two
are Admin's **Collection value** (`/valuation`, admin-only), and Home keeps the total as the Worth
card. Completion's cards run fewest-missing first and "All 40" opens `/insights`, the full view
again. **Found and fixed on the way:** tapping a set on Home showed the whole list instead of that
set (Home swapped in a second copy of the list, which started with nothing open). Browser check at
375 and 1,280 px, light and dark, as Craig and as Mark, with every row filled from production's
data read read-only (#250) and then every row empty. Local gate green (API 1,188 passed, 644
skipped without Postgres; web 515, shared 131); CI green first time; production reported the merge
SHA at 16:41 UTC with `db: ok`. **Nothing is left open.**


**Covers snags 3, 4, 6 and 7.** Mid tier · high / mid tier · High. Sitting 1, second. Craig's
answers (#249): the collection first, and the bid trial to Admin with "Update values".

**Today (5 Oct):** eleven sections, top to bottom: Add a disc, Coming to disc, On this day,
Worth a rewatch, Highlights (four poster rows), What it's worth, the bid trial (Craig only), The
collection (tiles, charts and Most watched), Completion (all 40 sets), Recent activity (20) and
Pinned collections. Only Highlights' rows scroll sideways. Most watched repeats Most rewatched:
8 of its 10 films were in both on 5 Oct.

**Acceptance:**
- Home's order: **The collection** (number cards for films, discs, worth, watched and
  identified, then chart cards for formats, where they live, genres, decades, and spend over
  time when it has data) → Coming to disc → Top rated → Most rewatched → Most valuable discs →
  Best reviewed → On this day → Worth a rewatch → Completion → Pinned collections → Recent
  activity. **This replaces T5's "Home opens with the next few disc releases".**
- Every section but Recent activity is a titled row that scrolls sideways and snaps, as
  Highlights' rows do. Recent activity stays a short list at the foot.
- Each row still hides while it has nothing in it (#154), and an error still shows its own
  panel.
- Coming to disc's cards are posters with the date and the format; a film on the shelf opens
  its page; "All releases" stays.
- Completion's cards run closest to complete first, and a link carrying the count opens
  today's full view, filters included.
- **Most watched is gone from Home**, with its "Not shown yet" line. The stats API is
  unchanged, so an older web build still parses it.
- **Home has no "Add a disc" at any width.** The bottom bar keeps its Add below 1,024 px and the
  top bar its button from 1,024 px.
- **The bid trial and "Update values" leave Home** for an admin-only Admin tool, "Collection
  value", which carries both, the trial's report as today. Home's worth card shows the total to
  both people and hides from a viewer until there is one, as today. #237's "the trial stays on
  Home" is superseded; the trial can still be run again.
- Browser check at 375 and 1,280 px, light and dark, with every row filled and with none.
- Gate green.

### ~~W3 — Lend and borrow, from Loans with the scanner~~ 🟡 **shipped 2026-10-05 (`3ad71eb`, [#42](https://github.com/CraigR973/mcu-app/pull/42))**
**Acceptance: met; a live camera scan and the first real loans are Craig's (`OWNER-ACTIONS.md`
30).** Either person lends, borrows and marks returned, in the API and on screen. Migration 048
adds `loans.borrower_profile_id` (nullable, on delete set null), and a borrow names the person
by it, the name read from the profile; exactly one way of naming a borrower, an unknown profile
refused. Overdue reminders go to both people, the borrower in their own words. Loans' "Lend or
borrow" finds the disc by a search of your own films or a barcode (camera or typed) that
resolves to a film, then lists its discs; choosing the film remembers the code, and nothing
writes a barcode onto a disc. "Mark returned" became "Returned"; loan dates read "5 Oct
2026". Browser check at 375 and 1,280 px, light and dark, as Mark and as Craig, with a film's
real data read read-only (#250). Local gate green (API 1,188 passed, 650 skipped without
Postgres; web 524, shared 131); **CI ran the six new database tests for the first time, green**,
and reversed migration 048; production reported the merge SHA at 16:53 UTC with `db: ok`.


**Covers snag 2.** Top tier · high / top tier · High. Sitting 1, last. Craig's answer (#249):
both lend and borrow.

**Today (5 Oct):** a loan is one disc with a free-text borrower. Lending and "Mark returned" are
admin-only in the API and on screen; Mark reads Loans and nothing more; there is no borrow, and
Loans cannot start a loan. Overdue reminders go to the admin only. **0 loans have ever been
recorded.** The scanner lives on Add a disc. **0 of 1,880 owned discs store a barcode** and 1
code is remembered, so a disc's first scan resolves through eBay (one of the shared 5,000 calls
a day, at most 60 an hour a person) to a film.

**Acceptance:**
- **Both people lend, borrow and mark returned.** `POST /loans` and `PUT /loans/{id}/return`
  accept either signed-in person, and tests prove a viewer can do both. The API moves with the
  screens, as #155 did.
- **Borrow records the borrower as the person.** Migration 048 adds
  `loans.borrower_profile_id`, nullable, a foreign key to `profiles`; `borrower_name` keeps the
  name as text. A loan to anyone else leaves it null. Upgrade and downgrade are proved in CI;
  `mcu_readonly`'s table-level grant already covers a new column.
- `LoanResponse` gains `borrowerProfileId`. The shared schema defaults it to null, so a web
  build ahead of the API still parses.
- **Loans gets "Lend or borrow":** scan (camera or a typed code) or search your own films →
  that film's discs on the shelf → pick one → "I'm borrowing it", or "Lend to …" with a name; a
  due date is optional either way. A disc already out offers "Returned" instead. A scan that
  matches nothing on the shelf says so. Choosing the film a scan found remembers the code
  through the existing confirm step; **no loan writes a barcode onto a disc.**
- The film page offers Lend and Borrow on each disc, and Returned on one that is out, to both
  people.
- **Overdue reminders go to both people**, each worded for them: a borrower who is one of them
  reads "You've had *Heat* since 2 October; it was due back 3 days ago", and everyone else
  reads today's wording, "Craig has had *Heat* since 2 October; …". Still once per loan
  (`reminder_sent`).
- "Mark returned" becomes "Returned", since Mark is a person here.
- The model's comment that neither person borrows from the other is corrected.
- Browser check at 375 px, light and dark: lend, borrow and return from Loans by typed code and
  by search, and from the film page, as each person. A live camera scan is Craig's.
- Gate green.

## Group X — the wave 1 review, planned 12 Oct

**Planned 2026-10-12 from the wave 1 full review** (Batches 43–48: six passes at `527522d`,
`docs/reviews/BATCH_43-48_ROADMAP.md` and its packages X1–X12; each finding id points into
its pass report in `docs/reviews/`). **Criteria authored 2026-10-12** from the roadmap, so
`DECISIONS.md` #54 does not apply. **Written into the plan at Craig's word ("do rows and
merge", 12 Oct, #253); each sitting starts at his go, and he starts X1 himself.** **Regrouped
the same day at his word (#255): five sittings, X4 inside the late-October one, and the first
run as one group. eBay's licence (MK47-04) is an accepted risk (#254).** Numbers are
as re-checked on 12 Oct: re-verify them, per `batch-start.md` step 3. Model tiers are Group
V's: top tier is the two models on Group U's row in "Batch groups", mid tier the two on Batch
21's row. **The cases X1, X5 and X9 test against are in `docs/reviews/BATCH_43-48_EVIDENCE.md`.**
The review's other working files (`scratchpad/wave-1/`, gitignored) exist only on Craig's Mac,
so X7 (R3's probe) and Batch 38 (R6's rig) run there or rebuild what they need.

| Sitting | Batches, in order | Gate | Claude Code | Codex |
|---|---|---|---|---|
| 1 | ~~X1 eBay scan~~ (`7979e19`) → ~~X2 failures reach Craig~~ (`857ee8f`) → ~~X3 push heals itself~~ (`adcae0d`) — **done 12 Oct** | Craig's go, as one group (`/group-start X · 1`); **X1 before 21 Oct 16:35 UTC**. MK47-04 is settled (#254), so X1's close-out does not stop | top tier · high | top tier · High |
| 2 | ~~X7 assistant repair~~ (`aa6946d`) → ~~X8 offline, drift and failure words~~ (`e991281`) — **done 13 Oct** | Craig's go | top tier · high | top tier · High |
| 3 | ~~X6 value as used copies~~ (`51c81ff`, 14 Oct) → ~~X4 weekly dump and restore drill~~ (`87a734b`, 14 Oct) → ~~X5 watch history~~ (`19c9aad`, 14 Oct; its live data steps at Craig's word) | X6: used-copy values (#256), before 1 Nov 04:00 — **shipped 14 Oct**. X4: Actions artifacts (#257); stops for Craig's credential steps. X5: after X4, by 31 Oct; its live data steps at his word | top tier · xhigh (from X4 and X5) | top tier · Extra High |
| 4 | ~~X9 catalogue truth~~ → ~~X10 one title rule, owned twins~~ (`f8de7ab`, 18 Oct) — **done** | Craig's go; their data steps at his word | top tier · xhigh (from X9) | top tier · Extra High |
| 5 | ~~X11 Wanted shop prices~~ (18 Oct) → ~~X12 polish and terms~~ (X12a–c, 18 Oct) | Craig's go | mid tier · high | mid tier · High |
| — | ~~38 the end-to-end suite~~ — **built 19 Oct** (#285) | Craig's go, last; six cases added by the review | mid tier · high | mid tier · High |

**Each batch on its own:**

| Batch | Covers | Size | Claude Code | Codex |
|---|---|---|---|---|
| ~~X1~~ | ~~CR43-01 ≡ MK47-02, MK47-01, MK47-06, MK47-07, CR43-06; MK47-04's steps~~ | ~~🟡~~ | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~X2~~ | ~~DS44-01, DS44-05, UX48-02 (the screens)~~ | ~~🟡~~ | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~X3~~ | ~~DS44-02, UX48-02 (Settings)~~ | ~~🟢~~ | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~X4~~ | ~~DS44-03~~ | ~~🟢~~ | ~~top tier · xhigh~~ | ~~top tier · Extra High~~ |
| ~~X5~~ | ~~Craig's 11 Oct watch-history choice, CT46-02, UX48-04, CT46-01's diary share~~ | ~~🔴~~ | ~~top tier · xhigh~~ | ~~top tier · Extra High~~ |
| ~~X6~~ | ~~MK47-03~~ | ~~🟡~~ | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~X7~~ | ~~AI45-01 to AI45-08~~ | ~~🟡~~ | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~X8~~ | ~~UX48-01, UX48-03, CR43-04, DS44-04, DS44-07~~ | ~~🟡~~ | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~X9~~ | ~~CT46-01, CT46-03, CT46-05, CR43-02~~ | ~~🔴~~ | ~~top tier · xhigh~~ | ~~top tier · Extra High~~ |
| ~~X10~~ | ~~CR43-03, CT46-04~~ | ~~🟢~~ | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~X11~~ | ~~MK47-05~~ (#281) | ~~🟡~~ | ~~mid tier · high~~ | ~~mid tier · High~~ |
| ~~X12~~ | ~~UX48-05, UX48-06, UX48-07, CT46-06, CT46-07, DS44-06, the rest of CR43-08~~ (#282, #283, #284) | ~~🟡~~ | ~~mid tier · high~~ | ~~mid tier · High~~ |

*Why those efforts.* `xhigh` where a batch writes live data or holds a credential: X4 (a dump
role and a secret), X5 (a backfill of 756 diary entries and film records with no copies, as
Batch 40 ran), X9 (identification on live rows, as 39–41 ran). X7 is top tier although R3
proposed mid: it changes the write confirmation and the money caps. X11 and X12 are interface
work with clear criteria.

**How each lands:** as Group W did: its own `feat/` or `fix/` branch from `main`, a pull
request, CI green, a merge commit, then production `/api/v1/health` reporting the merge SHA
with `db: ok`. **Each batch ships its own guards** (the roadmap's section e lists all twenty).
**Live data steps** (X5's backfill and re-pointing, X9's settling, X10's leftover rows) stop
for Craig's word with the row count, as `group-start.md` requires.

### ~~X1 — eBay: unblind the scan, name the right disc, say how fresh~~ 🟡 **shipped 2026-10-12 (`7979e19`, [#48](https://github.com/CraigR973/mcu-app/pull/48))**
**Acceptance: met, every criterion; **seen in production:** the first scheduled pass after the deploy (20:23 UTC) read 2,709 listings, 10 pages plus the one-off search of the 10 Wanted films, found 21 deals (each the right film on a read-only check) and pushed 5, its mark set 10 minutes before its start. 9 of the 21 are *Romper Stomper* against a £19.00 usual, which looks like a high usual rather than nine bargains; noted for X6/X11, not changed here.** The mark is the pass's start less 10
minutes, never a listing's date, and reading it ignores any mark later than the reading pass's
start, so production's 21 Oct row stopped counting on the deploy with no data write. The
matcher refuses another year after the title (±1, past format words), incomplete items, a
Blu-ray that names 4K, Region A/1 Blu-rays and television; crafted titles for all 25 wrong
products go through the scan's path (22 refused, the 3 no rule can see pushed under their own
title). A used listing meets only used listings; a shop price is a ceiling on a New listing's
usual (#239 amended). One item call re-checks a find before its push. The push and the card
name the listing's title and condition and "asking prices, n listings"; every card says
"Seen 30 Sep"; a shop's deal leaves two days after it was last seen (the six Zavvi deals of
30 Sep left on the deploy: 0 live shop deals at 19:05 UTC); an expired eBay find keeps its
price and film and loses the listing's title, image and condition. TMDB's 429 follows the
scraper's bounded rule and a last-try refusal answers 503. Migration 049 (three nullable
columns), live at 049, the read-only role reading them with no grant of its own. Choices in
#258; MK47-04 stands accepted (#254). Local gate green (API 1,237 passed, 657 skipped without
Postgres, and the full suite against a local Postgres 16, 1,884 passed with one collection test
that fails there on unchanged `main` too; web 527, shared 132); CI green; production reported
the merge SHA at 19:03 UTC with `db: ok`. The Deals card was checked in a browser at 375 px
against a local API, which moved eBay titles from one line to three.

**Covers CR43-01 ≡ MK47-02 (High), MK47-01 (High), MK47-06, MK47-07 and CR43-06 (Low), and
MK47-04's freshness and deletion steps.** Top tier · high. Sitting 1, first. **Must land before
21 Oct 16:35 UTC**, when the stored mark stops blinding the scan by itself and the gap since
9 Oct can no longer be read.

**Found 11 Oct, re-checked 12 Oct (`live_sql`):** every scan run from 9 Oct 02:21 to 12 Oct
06:24 (39 of 39) read one page and 0 listings. The stored "newest listing" is 21 Oct 16:35:01,
taken from one listing dated 12 days ahead by the 9 Oct 00:22 run: the scan keeps the newest
listing date it sees with no ceiling, and reads from the maximum over every run ever.
Separately, 25 of the 265 finds of 26 Sep–9 Oct were another product (14 another film, 7 a disc
with no case, 2 a Blu-ray scored as 4K, 2 Region A), 14 of the 60 pushes delivered to Craig
were among them, and 227 of the 265 were judged against the New median whatever the listing's
condition (`BATCH_43_CODE_REVIEW.md`, `BATCH_47_PRICES_VALUE_DEALS_REVIEW.md`).

**Acceptance:**
- A run never stores a mark later than its own start: the mark is the run's start less a
  margin (about 10 minutes, for eBay's indexing), never a listing's date. A listing dated in
  the future is still read and judged; it cannot move the mark.
- Reading the mark ignores any stored value later than the current run's start, so
  production's 21 Oct row stops blinding the scan with no data write; the first run after the
  deploy reads back as far as its page cap allows.
- A four-digit year after the film's title, with nothing but brackets and format words
  between, must be the film's year ±1: "Halloween (2018)", "Road House 1989", "Wonder Woman
  1984" and "IF Blu-ray (2024)" are refused for the 1978, 1948, 2017 and 1968 films.
- Incomplete items are refused ("disc only", "no case", "case only", "no disc", "empty"). A
  Blu-ray titled "not a 4K", "not 4K" or "remastered in 4K" is not a 4K; a Region A or Region 1
  Blu-ray is refused (Region B and region-free pass); a TV "complete series" or "season" is not
  the film.
- A used listing (Like new, Very good, Good, Acceptable) is judged only against used listings:
  its own condition group when it has 3 or more, else the pooled used groups when they have 3
  or more, else it is not a deal. Never against the New median, and never against a group whose
  median is above New's (#239 amended).
- A shop's price never raises a usual: it can lower a New listing's usual, as a ceiling, and
  never enters a used listing's (MK47-06; #239 amended).
- A deal push names the listing's own title and condition and says "asking prices, n
  listings"; the Deals card shows the same. A find is re-checked with one item call before its
  push; a find that has ended or sold out is not pushed and leaves the page.
- Every deal card says when its price was last seen ("Seen 30 Sep"). A shop's deal expires two
  days after it was last seen, so the six Zavvi deals of 30 Sep leave the page on the deploy.
  An expired eBay deal keeps its price, dates and film and loses the listing's title and image
  (eBay API licence §8.1.2, §3.1(b)).
- The first fixed run also searches each wanted film once (about 10 calls), through the same
  matcher and checks, to recover what the gap hid for the films that matter most.
- The TMDB client's wait on a 429 follows the scraper's bounded rule (#238): `Retry-After`
  honoured up to 90 seconds, dates parsed; a refusal on the last try is a 503 with the "TMDB
  didn't answer" wording, not a 500.
- MK47-04 is settled: an accepted risk, at Craig's word on 12 Oct (#254). The re-check, the
  age line and the deletion steps above are what bound it; X1's close-out cites #254 and
  needs no decision.
- **Guards (CI):** a listing dated in the future never moves the mark, on write or on read;
  titles crafted from the 25 wrong-product finds (`docs/reviews/BATCH_43-48_EVIDENCE.md`,
  section 1) never match, except the three no title rule can tell apart (*Maggie* and the two
  *Titanic* 3D sets), whose push and card must name the listing's own title and condition; a
  used listing never meets the New median. Each fails when its fix is reverted.
- **Seen in production:** the first scheduled run after the deploy reads listings
  (`listings_seen > 0`), read with `live_sql`.
- Tests. Gate green.

### ~~X2 — Failures reach Craig~~ 🟡 **shipped 2026-10-12 (`857ee8f`, [#50](https://github.com/CraigR973/mcu-app/pull/50))**
**Acceptance: met; the first scheduled check runs at 08:00 UTC on 13 Oct, and until then
Home's row says "The daily check hasn't run yet".** A check inside the 08:00 reminders job
reads only tables the app writes and records each result in `health_checks`: each job's
heartbeat or last run within its cadence (daily jobs 26 hours, eBay 5, the valuation 17 days),
the eBay scan reading listings in one of its last six runs, each person's live device and last
three days not all undelivered, readiness (written by the API at boot), the spec integration,
the database under half its 1 GB, a PIN lock in the last day, Identify proposals older than a
fortnight and identified films a disc page or review puts in another year, and deals older
than their source's freshness. A new problem appears in a "Needs attention" row at the top of
Home (admin) and is pushed once, in an `attention` category with no toggle; the row also says
when the check itself has not run for a day. Every job writes a heartbeat each run, "nothing
due" and "budget spent" included; `cron-scrape` exits 0 when shops only refused; Price alerts
says "read 0 new listings, 33 checks in a row"; Deals stays in the menu and its empty page says
when eBay and each shop last answered; repeated PIN locks in a day escalate (15 minutes, 1
hour, 4 hours, 24 hours). Migration 050: `job_heartbeats` and `health_checks`, granted to the
read-only role, guarded, and two profile columns. Choices in #259. Local gate green (API 1,241
passed, 676 skipped without Postgres, and 1,902 passed against a local Postgres 16, its five
failures also failing on unchanged `main`; web 531, shared 135); CI green; production reported the merge SHA at 22:30 UTC with `db: ok`; alembic at 050, the API's boot heartbeat written with push, the assistant and eBay configured, and the read-only role reading both tables and both columns while `pin_hash` stays withheld. Home's row,
Deals' empty page and Price alerts' line were checked in a browser at 375 px against a local
API, which removed a doubled "since".

**Covers DS44-01 (High), UX48-02's screens (High) and DS44-05 (Low).** Top tier · high.
Sitting 1, after X1.

**Found 11 Oct:** none of the seven failures since 9 Sep reached anyone. Error reporting runs
only with a DSN, and none is set; `cron-scrape` exits non-zero whenever a shop refuses, so
Railway shows it Crashed every night; the spec, valuation and eBay jobs write no row when
nothing is due, so idle and stopped look alike; Price alerts reported the blind scan as "Last
check 19:20"; Deals leaves the menu when its source fails (`BATCH_44_…`, `BATCH_48_…`).

**Acceptance:**
- A daily check runs inside the 08:00 reminders job (no new Railway service), reads only tables
  the app already writes, and records each result. Its checks: each job's last run or heartbeat
  within its cadence; the eBay scan read listings in at least one of its last six runs; each
  person holds a live device and their last three days of notifications are not all suppressed;
  the spec integration is not halted; readiness reports every field configured; the database is
  under half its cap; any profile locked in the last day; Identify proposals older than a
  fortnight and identified films whose disc page or review names another year (CT46-03); no
  deal older than its source's freshness (eBay 3 days, shops 2). X7 adds the assistant's
  failure count.
- A new problem reaches Craig two ways: a "Needs attention" row at the top of Home (admin),
  naming it in words (R6's wording, UX48-02), and one push when it first appears, not every
  morning it persists. The row works when push is what broke.
- The spec, valuation and eBay jobs write a heartbeat row when nothing is due or no budget is
  left.
- `cron-scrape` exits 0 when every failure is a shop's refusal (#240: refusals are not
  failures), and non-zero for anything else.
- Price alerts shows how many listings the last checks read ("read 0 new listings, 33 checks
  in a row"); the scan's run answer carries the count, through `packages/shared`.
- Deals stays in the menu when empty, its empty state saying when each source last answered
  (#154 and #165 amended for Deals alone; box sets and collections keep hide-when-empty).
- Repeated PIN lockouts in a day escalate (15 minutes, 1 hour, 4 hours, 24 hours), and a
  lockout appears in the attention row.
- Any new table is granted to `mcu_readonly`, guarded, per `AGENTS.md`.
- **Guards:** every check above has a test with crafted rows that trip it and rows that pass;
  `cron-scrape`'s exit code on refusals alone.
- Tests. Gate green.

### ~~X3 — Push that heals itself~~ 🟢 **shipped 2026-10-12 (`adcae0d`, [#52](https://github.com/CraigR973/mcu-app/pull/52))**
**Acceptance: met; a real phone re-subscribing after a refusal is Craig's to see (an
agent's browser cannot hold a push subscription).** A 404 or 410 now keeps the device as
revoked, `revoked_reason` "refused" (migration 051; a person's removal is "removed"), and
registering the same endpoint revives it. On every open, and on the worker's subscription
change, the app shell asks `POST /notifications/subscriptions/status` what the server holds
for this browser and registers the phone again when the server lacks it or holds it as
refused, with a fresh subscription for a refused endpoint; a removed device is left alone, and
no permission prompt is ever raised. Settings says "Notifications are on for this device" only
when the server holds it live, otherwise "This phone stopped getting notifications on 8 Oct.
Turn them on again." with Turn on; a banner stays on every page while a person's last device
was refused and none is live; the worker's comment is now true. The eBay run records finds
delivered, not queued. Choices in #260. Local gate green (API 1,241 passed, 681 skipped without
Postgres, and 1,907 against a local Postgres 16 with the same five environment failures as
unchanged `main`; web 542, shared 137); CI green; production reported the merge SHA at 23:06
UTC with `db: ok`, alembic at 051, both live devices untouched. The banner was checked in a
browser at 375 px against a local API.

**Covers DS44-02 (High) and UX48-02's Settings line.** Top tier · high. Sitting 1, after X2.

**Found 11 Oct:** Mark's phone was dropped on its first push (24 Sep) and Craig's on 8 Oct. A
404 or 410 deletes the device with an info log; Settings reads the browser's own subscription,
so it showed "Notifications are on for this device" above "No devices are registered yet";
nothing registers a device again (the worker's comment says the page does; the hook only reads
local state); the eBay run counts queued pushes as pushed. Both phones were re-registered by
hand on 11 Oct.

**Acceptance:**
- On app open, and when the worker reports a subscription change, the page compares this
  browser's subscription with the server's devices for the signed-in person. When the server
  lacks it, or holds it as refused, the page registers this phone again, with a fresh
  subscription when the old endpoint was refused. The worker's comment becomes true.
- Settings says "Notifications are on for this device" only when the server holds this device
  live; otherwise it says when they stopped ("This phone stopped getting notifications on
  8 Oct. Turn them on again.") and offers Turn on.
- A device the push service refuses is kept as revoked (`revoked_at_utc`), not deleted, and
  registering the same endpoint again revives it. When a person's last device goes, they see a
  banner in the app until they turn notifications on, and X2's row names it for Craig.
- The eBay run records pushes delivered, not queued.
- **Guards:** tests for re-registration when the server lacks the device or holds it as
  refused, both Settings states, the refused-device path and the count.
- Tests. Gate green.

### ~~X4 — Weekly dump and restore drill~~ 🟢 **shipped 2026-10-14 (`87a734b`, [#67](https://github.com/CraigR973/mcu-app/pull/67))**
**Acceptance: met, every criterion, and seen in production.** The credential steps were done by
a session at Craig's word ("option 2", #268): the `mcu_backup` role with a generated password,
the `BACKUP_DATABASE_URL` secret, and an age key pair whose private half is on the Mac (a copy
off the Mac is his, `OWNER-ACTIONS.md`). Every Sunday 03:30 UTC `.github/workflows/backup.yml`
copies every table through the role, one CSV per table plus a manifest in one read-only
snapshot, encrypts it to `.github/backup-age-recipient.txt`, keeps it 90 days and the newest
8. The role reads no credential: migration 053 grants 48 of 56 tables whole and `profiles` and
`movie_night_sessions` without `pin_hash` and `invite_token`, and the copy refuses to run if the
catalogue says otherwise or a table is ungranted. The drill (the 1st, and every manual run)
restores the copy into a throwaway Postgres before encryption, checks it is at the code's head,
and compares every table's rows; a failure fails the run, which GitHub emails. **First run, by
hand after the deploy:** 49 tables, 99,822 rows, 26 MB (about 0.11 GB a month of egress),
drill passed, 7.7 MB encrypted; downloaded and decrypted on the Mac with the private key, no PIN
hash in it. Runbook `docs/restore-runbook.md`. Choices in #268. Local gate green (API 1,316
passed, 718 skipped without Postgres; against a local Postgres 16, 2,023 passed and the same 2
collection tests that fail there on unchanged `main`; web 571, shared 141); CI green, the two
end-to-end backup tests among 2,034 passed on Postgres 17; production reported the merge SHA,
web and API, with `db: ok` and every field configured; live at 053.

**Covers DS44-03 (High).** Top tier · xhigh. Sitting 3, after X6 (#255). **Storage: encrypted
GitHub Actions artifacts, at Craig's word on 12 Oct (#257); lands before X5.** Its credential
steps are Craig's, and the sitting stops for them.

**Found 11 Oct:** Neon's free plan (1 GB cap) restores within 6 hours, keeps one manual
snapshot and offers no scheduled backups; no dump, export or restore runbook exists
(ARCHITECTURE §9.9's weekly dump never came across the re-scaffold). Craig left the manual
snapshot for now on 12 Oct, which is why X4 precedes X5.

**Acceptance (with Actions artifacts):**
- A weekly GitHub Actions schedule dumps the database through a dedicated role that never
  reads a credential (PIN hashes, refresh tokens, eBay tokens, push devices, invite tokens),
  encrypts the dump to a public key in the repo (the private key stays with Craig), uploads it
  as an artifact kept 90 days, and keeps the newest 8.
- A monthly drill restores the newest dump into a throwaway Postgres in the runner, checks
  Alembic is at head, and compares row counts per table with the dump's manifest; a failure
  fails the workflow, which GitHub emails to Craig.
- A restore runbook in `docs/` (restore into a Neon branch, check, switch) says a restore signs
  both people out, asks for push again, and how sign-in is restored.
- Craig's steps are listed and not done by an agent: the role's password, the repository
  secret, the key pair. The role's grants land in a guarded migration, as `mcu_readonly`'s did.
- Egress stays near 0.4 GB a month of Neon's free 5 GB.
- **Guard:** the monthly drill.
- Tests for any code (the manifest comparison). Gate green.

### ~~X5 — Watch history: films not owned, the backfill, the year rule~~ 🔴 **shipped 2026-10-14 (`19c9aad`, [#69](https://github.com/CraigR973/mcu-app/pull/69)); its live data steps wait for Craig's word**
**Acceptance: met in code, in CI and on production's read-only role; three live data steps are
Craig's** (`OWNER-ACTIONS.md`). The feed attaches by TMDB id only and a film not in the
catalogue gets a row with no copies, kept out of Home's counts, the movie night deck and the
completion counts (`owned_film`, #269); each watch keeps the feed's TMDB id (054, live, both
roles reading it). A known year more than one apart excludes a title candidate (#158 amended;
guarded in CI). The diary import no longer uses `MatchingEngine`. The weekly sync runs in the
08:00 job (`trigger = cron`), and the Watch history tab says the feed holds 50 entries and the
app syncs weekly. **Dry runs on 14 Oct (read-only):** backfill Craig 493 watches (436 on 397
films to add) and 86 doubtful, Mark 158 (101 on 95) and 19 doubtful; the 15: 7 to move, 8
doubtful. **Waiting for Craig's word:** the two backfill applies (651 watches), the 7 moves, and
storing Mark's username (`markr973`, #253); then both press Sync now. Local gate green (API
1,319 passed, 721 skipped without Postgres; against a local Postgres 16, 2,029 passed and the
same 2 collection tests that fail there on `main`; web 572, shared 141); CI green; production
reported the merge SHA, web and API, with `db: ok`.

**Covers Craig's decision of 11 Oct (`docs/reviews/BATCH_43-48_REVIEW_SCOPE.md`, "Decisions
during the passes"), CT46-02 (Medium), UX48-04 (Medium) and CT46-01's diary share.** Top tier ·
xhigh. Sitting 3, last. **After X4; by 31 Oct**, so a sync then still reaches back past
14 Sep for Mark (his 50-entry feed stops reaching back around 10–19 Nov).

**Found 11 Oct:** 15 imported watches sit on a different film of the same name (a 2013 film on
the 1995 one; `docs/reviews/BATCH_43-48_EVIDENCE.md`, section 3); the diary matcher drops the leading
article, and "the year breaks a tie, never excludes" (#158, #160) holds even when both years
are known; the RSS sync falls back to titles when the feed's TMDB id is not owned; films not
owned are skipped by design, and 756 dated diary entries were never recorded. Mark has no
Letterboxd username stored; Craig synced once on 11 Oct (4 written, all right).

**Acceptance:**
- The sync attaches each feed entry by its TMDB id. A film not in the catalogue gets a film
  record with no copies, kept out of collection counts and value as wanted films are, and the
  watch goes on it. The feed never falls back to a title.
- Wherever a title is matched (the diary file import, the backfill), a candidate whose year is
  known and differs from the entry's by more than one is excluded; a row with no year keeps
  #158's "never excludes" (#158 amended).
- Each watch row keeps the feed's TMDB id (a new nullable column, granted to `mcu_readonly`).
- The backfill imports every dated diary entry not yet recorded, from the two diary files on
  the Mac (756 entries: Craig 579, Mark 177; about 680 films), matched with T9's care; doubtful
  matches go to Craig, not into the table. **Dry run first; the live run at Craig's word, with
  the row count.** Undated "watched" films and watchlists are out of scope (Craig's choice).
- The 15 misattributed watches are re-pointed to their real films at Craig's word, from a
  dry-run list.
- The diary import no longer uses `MatchingEngine` (CT46-01's share).
- Mark's Letterboxd username is stored (Craig gave it on 12 Oct; `OWNER-ACTIONS.md` 1j names
  it). The app lets only each person set their own, so this is a one-row data step at Craig's
  word (#253).
- A weekly sync for each person with a username runs inside the 08:00 reminders job (no new
  Railway service), recorded with `trigger=cron`.
- The Watch history tab says "Letterboxd's feed holds your last 50 diary entries. The app syncs
  weekly; last synced …".
- **Guards:** a known, different year excludes a candidate (CI); the weekly sync.
- Tests. Gate green. Then both people press Sync now, or the first weekly run does it.

### ~~X6 — Value the shelf as used copies~~ 🟡 **shipped 2026-10-14 (`51c81ff`, [#65](https://github.com/CraigR973/mcu-app/pull/65))**
**Acceptance: met, every criterion, in code, in CI and in a browser; the live values arrive with
the runs of 15 and 16 Oct 04:00 UTC.** A disc's value is its used listings' median with three
or more, else New's median times the used-to-New factor, measured per format from the stored
values (median ratio over films with three or more of each, capped at 1.00; 0.60 until 20
films) and re-applied to every New-based value at each run's end. Every value from before X6
(all 1,454 live rows at the deploy) is due at once and counts nowhere until re-priced, so Home
has no total, then a partial one, until 16 Oct. The matcher now refuses another film's word
before the title everywhere (the deal scan's rule, shared, its window 4 → 6 and its seller
words widened with labels), Staffel and mini-series as television unless the title is a TV
series, "Not 4K UHD" on a 4K search, and reads "Steelbooks" as a collector edition; the 12 crafted
wrong products of R5 never price a film, and reverting any rule fails that guard. Home, Admin
and Most valuable say "as used copies"; Most valuable shows each value's listings and range;
the film page says how its value was reached; the sale panel and upgrade prompt pre-fill from
the used value. Migration 052 (eight nullable columns, two checks), live at 052, the read-only
role reading them with no grant of its own. #256 amends #209; choices in #267. Local gate green
(API 1,302 passed, 716 skipped without Postgres; the full suite against a local Postgres 16,
2,007 passed and 2 collection tests that fail there on unchanged `main` too; web 571, shared
141); CI green; production reported the merge SHA, web and API, with `db: ok` and every field
configured. Checked in a browser at 375 px against a local API with seeded values: Home's
total and Most valuable, Admin, and the film page's four states (used, New-based, not priced,
before X6) with the sale panel's pre-fill. Not live-tested: the film page's "What is it worth?"
against real eBay (it spends a lookup; the tests use captured searches).

**Covers MK47-03 (Medium).** Top tier · high. Sitting 3, first. **Value basis: used copies, at
Craig's word on 12 Oct (#256, amending #209; #237's asking prices stand); lands before 1 Nov
04:00**, the first re-pricing with work since 26 Sep, or the new-copy values stand
until about 1 Dec.

**Found 11 Oct, re-checked 12 Oct:** 965 of the 1,300 priced discs, £21,843 of £23,604 (92.5%),
are medians of New listings; where both exist, a used copy asks 0.48–0.71 of New; valued as
used, the total is roughly £12,800–£17,200. 7 of 20 live re-searches mixed in another product
(TV box sets, a sequel, "Spider Labyrinth" for *Labyrinth*), four of the six highest values
among them.

**Acceptance:**
- An owned disc's value is the median of used listings when there are 3 or more; otherwise
  New's median times the measured used-to-New factor for its format. Home and the film page
  say "as used copies".
- The estimator refuses a content word before the title (the deal scan's "title opens the
  listing" rule), TV words (series, season, staffel) unless the film is a series, and a listing
  titled "not 4K" on a 4K search; "Steelbooks" is not a standard edition.
- Most valuable shows each value's listing count and range; the sale panel pre-fills from the
  used value.
- #256 amends #209 (12 Oct); X6's close-out cites it and needs no decision.
- **Guard (CI):** R5's crafted titles never price a film.
- Tests. Gate green.

### ~~X7 — The assistant answers more than once~~ 🟡 **shipped 2026-10-13 (`aa6946d`, [#54](https://github.com/CraigR973/mcu-app/pull/54))**
**Acceptance: met in code and in a browser; a real follow-up to the real model is Craig's to
send (`OWNER-ACTIONS.md` 2), because it spends his money and needs his sign-in.** Stored and
replayed blocks keep only the SDK's request fields for their type (`chat.request_block`), on
write and on read, so the six stored conversations continue with no data write; a test drives
real SDK blocks (thinking, a streamed text block, a tool call) through the real client over a
stubbed transport and checks the second request. The write tools and the prompt say the app
shows a Yes/No card; the prompt names the person and their London date and no disc count. The
film a write is about is settled before the card (an id from a result, an exact title and
year, or the one TMDB film with that title), so a shared title or an unknown film comes back
as a question, and the card names "Halloween (2018)" and the date. A message sent while a card
waits closes it as declined first; the web locks the box meanwhile. Tool results are a compact
view (title, year, formats, place, watched), totals first, 25 a page; releases take a window
and a kind; a cut counts what it left out. Every failed call leaves a usage row with status and
type; 400, 401, 402, 403, 404, 413 and a 429 without `retry-after` read "The assistant isn't
working right now; Craig has been told."; the daily check names failures in the last day. The
allowance is checked before every model call under a per-person advisory lock, the fifth round
is sent with `tool_choice: none`, four tools run per round, caps stop at 200 messages and $10,
and a zero cost cap is refused (a stored zero reads as $2). One confirmation claims its row in
one guarded update; a failed write is `failed`. Cost is priced by the configured id; the 5.5
family is allowed and Fable 5.1's cache read corrected. #261 records the write tools behind a
card; #262 the rest. R3's probe is kept as `src/scripts/assistant_canary.py`, at Craig's word
at each delta review. Local gate green (API 1,261 passed, 705 skipped without Postgres, and
1,956 against a local Postgres 16 with one collection test that fails there on unchanged
`main` too; web 545, shared 137); CI green (1,966 passed, none skipped); production reported
the merge SHA `4b38214` with `db: ok`. Seen at 375 px against a local API: the card naming the
2018 film and its date, the locked box, one watch row written on Yes, the box unlocked. **Not
seen:** a live follow-up (no read-only role on this Mac, and no sign-in).

**Covers AI45-01 (High), AI45-02 and AI45-03 (Med-High), AI45-04 (Medium) and AI45-05 to
AI45-08 (Low).** Top tier · high (R3 proposed mid; raised for the write confirmation and the
money caps). Sitting 2, first.

**Found 11 Oct, re-checked 12 Oct:** every follow-up fails with a 400, because each answer is
stored as the SDK's full block dump, whose text blocks carry the SDK-only `parsed_output`, and
is replayed (all 5 stored answers carry it; proved by R3's paid probe and by SDK 1.4.0's own
dump). The write tools cannot be completed from ordinary words; lists are cut at 6,000
characters before their totals (the app's example question saw 13 of 162 films); a failed chat
call leaves no usage row and tells the person to rephrase.

**Acceptance:**
- Stored and replayed assistant content carries only the API's request fields for each block
  type, on write and on read, so the six stored conversations continue.
- The write tools' descriptions and the system prompt say the app shows a Yes/No card, so the
  model calls the tool directly; the prompt gives today's date (Europe/London) and who is
  asking, and no stale disc count.
- The input is disabled while a card waits; the server refuses a new message while a call is
  pending, or closes the call as declined first.
- Tool results are a compact view (title, year, formats, place, watched), totals first, with a
  page argument; releases take a date window and a type filter; a cut-off says how many were
  left out.
- Every failed call is logged with its status and error type. 400, 402, 403, 404, 413 and a 429
  with no retry-after read "The assistant isn't working right now; Craig has been told."; a
  daily count feeds X2's check.
- Caps are checked and reserved before every model call, resumes included; a blank or 0 cost
  cap means "off" or is refused, and both caps have upper bounds; the last round is forced to
  answer (`tool_choice: none`); tool calls per round are capped.
- One confirmation writes once: the pending row is claimed in one guarded update before the
  write, and a failed write is marked `failed`.
- Decades are described as decades; add-to-wanted accepts a TMDB match as the web does; a
  shared title passes the film id the model saw, or asks.
- Cost is priced by the configured id; the 5.5 family is on the allow-list.
- A decision records Part D 9.4's change: the model holds two write tools, behind a card.
- **Guards:** real SDK blocks through store and replay, keys checked against the SDK's request
  types (CI); each tool's visible text carries its total (CI); R3's probe
  (`scratchpad/wave-1/r3/probes/`) kept as a monthly five-question canary, about $0.08, run at
  Craig's word at each monthly delta review.
- Tests. Gate green.

### ~~X8 — Offline, version drift and failure words~~ 🟡 **shipped 2026-10-13 (`e991281`, [#56](https://github.com/CraigR973/mcu-app/pull/56))**
**Acceptance: met, every criterion; a phone in a garage with no signal is Craig's to see.** The
worker keeps API reads from the configured API origin as well as the page's (the rule is
`lib/api-cache-route.ts`, guarded by its test and by the production-build test reading the
built worker), each person's in their own partition, and sign-out deletes the cache. Seen in a
browser: the bundle built with `VITE_API_URL=http://127.0.0.1:8000` and served on
`localhost:4173` cached 20 answers, all from the API's origin; with the API stopped, a film read
online opened from the cache. One describer (`lib/describe-error.ts`, behind
`queryErrorMessage`, and the seven places that showed `error.message` directly) says "No signal
— showing what's saved.", "The archive had a problem. Try again in a minute." or "This screen
needs the newest version." with a Reload banner; a failed chunk reloads once a minute at most.
`UnhandledErrorMiddleware` answers a crash with a 500 inside CORS. Readiness reports `tmdb` and
`brave`; `phase-closeout.md` step 8 now checks every field and the web's `/version.json`
(emitted by the build). The contract test (`apps/web/src/contract.test.ts`) walks all 140-odd
parsing functions in `api.ts` against `packages/shared/openapi.json`, held fresh by
`test_openapi_snapshot.py`; the API now declares the 158 lower bounds the web assumed and the
audit log's five actions; a planted enum value fails it. The CSP names
`api-production-a8fe.up.railway.app` and drops Supabase and Sentry: **a `vercel.json` header
change**, live after the merge. Choices in #263. Local gate green (API 1,268 passed, 705 skipped
without Postgres; 1,962 against a local Postgres 16, one collection test excluded that fails
there on unchanged `main`; web 561, shared 137); CI green (1,973 passed, none skipped);
production: API and web both at `92273e3`, `db: ok`, all five services `configured`, the live
worker carrying the API host, CORS answering the web's origin. Two expectations changed with the
criteria and are recorded here: the CSP test and `test_deployment_config.py` had pinned the
wildcard Railway host and Supabase this batch removes.

**Covers UX48-01 (High), UX48-03 and DS44-04 (Medium), CR43-04 and DS44-07 (Low).** Top tier ·
high. Sitting 2, after X7.

**Found 11 Oct:** the worker caches API reads only when the request's origin is the page's
own; production's API is on Railway and the page on Vercel, so it has never kept an answer,
and offline the app shows "You can still browse" above "Failed to fetch" (Batch 8 was verified
through the dev proxy, where they share an origin). A 500 arrives without CORS headers and
reads as no signal; a newer API's enum value turns a page into raw JSON; a chunk missing after a
deploy fails until a full reload; readiness omits TMDB and Brave; nothing compares the web
build's commit with the API's; the CSP allows any Railway app and Supabase.

**Acceptance:**
- The worker caches API reads from the configured API origin, keeping each person's cache
  apart and clearing it at sign-out; proved in a browser with the built bundle against a
  cross-origin API (offline, a film read online opens from cache).
- One error describer replaces raw error text: no signal ("No signal — showing what's saved"),
  a server fault ("The archive had a problem. Try again in a minute."), out of date ("This
  screen needs the newest version", with Reload).
- A failed chunk load reloads the page once.
- Error answers carry CORS headers, so a 500 is not read as no signal.
- Readiness reports TMDB and Brave (presence only); the close-out procedure checks every
  readiness field is configured and that the served web bundle's release is the merged commit.
- A CI contract test compares the API's OpenAPI with the compiled shared schemas: enums,
  nullability, minimums.
- The CSP names the one API host and drops Supabase, and Sentry until it is on. It is a
  `vercel.json` header change: say so in the close-out.
- **Guards:** the cross-origin worker rule (CI, and a case in Batch 38); the contract test
  (CI); the gate's two checks.
- Tests. Gate green.

### ~~X9 — Catalogue truth~~ 🔴 **shipped 2026-10-16 ([#79](https://github.com/CraigR973/mcu-app/pull/79)); the re-check's live run is Craig's (`OWNER-ACTIONS.md` 32)**
**Acceptance: met in code, criterion by criterion; the live re-check and the queue are Craig's.**
Choices in `DECISIONS.md` #275.
**The live re-check ran 16 Oct on Craig's Mac (item 32):** 1,486 copies, 384 disagreements,
all raised as doubts at his word. **Of the 30 known wrong copies, 19 were already corrected
(14 by Mark that afternoon), 10 appear, 0 are missed, and King Kong [1976] was not
re-checked:** its film was identified on 15 Oct, so a wrong copy beside a right one on that
film is outside the re-check. The morning's run, before Mark's fixes, missed Holy Grail and
House on the River (an obscure film's exact title; a grouping never counts against a film).
- **The identify run** takes its id before the loop and reloads by it after a rollback;
  `test_the_live_run_records_a_tmdb_failure_and_carries_on` injects a `ConnectError` and the run
  finishes with it recorded. Identify, specs, reviews, valuation and eBay each have a
  failure-injection test (the reviews one is new).
- **The dry run over the old paths' films** is `scripts/recheck_identifications`: every owned
  copy the import or the diary identified that neither T9 nor a person has since, its own sheet
  row asked of T9 (no Brave), a verdict each, and a report that names each of the 30 known wrong
  copies as appearing, already corrected (Y3's pass corrected the series among them), or missed
  and why. `--apply` puts every disagreement into Identify as a doubt with its evidence, at
  Craig's word. **Built and tested in CI, not yet run on live data:** no cloud session reaches
  TMDB or the live database, so the run is item 32.
- **A copy moves to another film** on its own (`POST /identify/copies/{id}/move`), made from
  TMDB's record if the collection lacks it, audited on the copy and undone from the recent
  list; Craig's copy cards and a doubt naming one copy of a film with others offer it.
- **A disc page or review** for the copy's own title (by T9's rule) in another year raises a
  doubt instead of only "pick the right page" (migration 057, `identify_doubts`); the film page
  shows "Identification in doubt" while one is open.
- **Editions** the spec job inferred read "Probably …" with their source until either person
  confirms or retypes them (migration 058, `edition_source`); release names are compared with
  T9's rule too ("Vol." is "Volume", numerals agree). Of the review's three examples, Kill Bill
  and Mission: Impossible now match; *Star Wars: Episode IX* against *The Rise of Skywalker*
  does not, since T9 requires the numbers to agree.
- **`MatchingEngine`** no longer decides or ranks in the refresh, Correct match or Identify's
  search; `test_the_engine_decides_nothing_in_the_app_any_more` holds it to that. The class
  stays for its evaluation script and X10's title work.
- **Craig settles the queue**: nothing is re-identified by the batch; the apply only raises
  doubts, and it waits for his word.
- **Guards:** the failure-injection tests; the namesake and article cases through the refresh
  and Correct match; the daily check counts doubts a fortnight old beside year conflicts.
- Local gate green (API 2,148 passed, none skipped; shared 146; web 602); CI and production in
  the close-out.
**Covers CT46-01 (High), CT46-03 and CR43-02 (Medium) and CT46-05 (Low).** Top tier · xhigh.
Sitting 4, first. Before any future sheet import or refresh, which would match with the old
engine.

**Found 11 Oct, re-checked 12 Oct:** 30 copies are confidently the wrong film (27 of 1,115
matched by the 8 Sep import, 3 of 404 by the diary import, 0 of 156 by T9; all 29 film rows
unchanged on 12 Oct; `docs/reviews/BATCH_43-48_EVIDENCE.md`, section 2). The old engine keeps a
leading article, scores an exact namesake above the real film, floors any containing title at
0.9 and reads one results page, so #31's tie never fires. 36 spec lookups carry "the page is
for a 1957 film … pick the right page", 8 of them on these films. The identify run's error
handler reads the run after a rollback and crashes on its first failure (`MissingGreenlet`).

**Acceptance:**
- The identify run takes its id before the loop and reloads by it after a rollback; a test
  injects a TMDB error, and the run continues and records it. Each run loop (identify, specs,
  reviews, valuation, eBay) has a failure-injection test.
- A dry run of T9's `Identifier` over the films the old paths decided (1,109 import-matched,
  397 diary-identified; no Brave; free TMDB calls, spread over nights if needed) puts every
  disagreement into Identify with its evidence. All 30 of R4's known wrong copies appear, or
  the batch says why one does not.
- A copy can be moved to another film ("this copy is another film"), undoable and audited;
  3 of the 30 share their film row with a right copy.
- A disc page or review naming the copy's own sheet title in another year adds an Identify
  proposal instead of "pick the right page", and the film page shows "identification in
  doubt" while one is open.
- An edition inferred by the spec job reads "probably …" with its source until a person
  confirms it; release names are compared with T9's title rule (Vol./Volume, numerals).
- `MatchingEngine` no longer decides or ranks in the collection refresh, the film page's
  Correct match list or Identify's search (the diary import's use goes in X5).
- Craig settles the queue with his taps; the batch stops before any bulk change for his word.
- **Guards:** the failure-injection tests (CI); the engine's namesake and article cases (CI);
  X2's daily counts of year conflicts and old proposals.
- Tests. Gate green.

### ~~X10 — One title rule, and owned twins found~~ 🟢 **shipped 18 Oct (`f8de7ab`, [#86](https://github.com/CraigR973/mcu-app/pull/86), #280); the 12 leftover rows trashed at Craig's word the same day**
**Acceptance: met, criterion by criterion, as amended 18 Oct.** (1) `services/title_key.py` holds
T9's `fold`, moved unchanged, and two levels, `WORDS` and `TITLE`; Search's and the add form's
lookalike (`services/lookalike.py`), the spec page check, the diary and refresh index and review
finding use it, and `canonical_title`, Letterboxd's `normalise_title`, reviews' `normalise` and
the "&" patch are gone. `tests/test_title_key.py` runs 21 pairs, R1's eight among them, through
every site. Review finding now splits a page title into the film's words and its format words
before folding, so *Rocky IV 4K Blu-ray* still finds *Rocky IV*. (2) **The dry-run diff**, old
against new keys over all 1,939 live films: identification's fold is identical for every title
(0 moves); the diary and refresh index and the spec check change on 0 pairs; Search's lookalike
gains 3 pairs (*Steptoe & Son* 1972 ~ 1962, *The Batman* ~ *Batman*, and the leftover *Outlaw
Josey Wales* row ~ the 1976 film), none of them an owned unidentified film, so nothing it shows
changes today; review finding loses 1 (*Alien³* no longer takes *Alien*'s pages). (3) The add
form asks the duplicate check with the film's title and year, and shows "You may already own
this" with Open it. (4) The duplicate check and the add carry `barcodeCopy`; an unconfirmed add
under a barcode on an owned copy is refused 409, and the prompt names the copy, says a box of two
formats is one copy and links to it. (5) `src.scripts.remove_leftover_films`, dry run by default,
`--apply --expect N`; the live dry run found 12, and at Craig's word `--apply --expect 12` put all 12 in the Trash (item 34). Local gate green (API 1,571 passed, 789
skipped without Postgres; the full suite on a throwaway Postgres bar the two known stale-edit
tests; web 629, shared 154); checked at 375 px against a seeded local API. CI green (14 checks);
production API and web reported `f8de7ab` with `db: ok`.

**Covers CR43-03 and CT46-04 (Medium).** Top tier · high. Sitting 4, after X9.

**Re-measured 18 Oct, read-only, before code; slimmed at Craig's word the same day (#280).**
At `7584d8d` and on live data: (1) the four title rules still disagree on 7 of R1's 8 pairs
(R1's probe re-run unchanged) — **holds**. (2) The 5 split films are each one row now, merged
by Mark's identifying; unidentified owned films fell from 210 to 1 (set aside, not a film) —
**gone**, so the lookalike check stays only as cheap insurance for the next import or
title-only add. (3) 0 owned copies share a barcode (6 carry one at all); the scan already says
"This exact barcode is already in the collection" but names no copy — **mostly gone**. (4) 9
copy-less rows from the 18 Sep refresh remain, each unidentified and holding only a copy binned
on 18 Sep, plus 3 of the same kind since — **holds**, and shows nowhere in the app.

**Acceptance, as amended 18 Oct (#280).** Each original criterion is kept or narrowed; none
dropped:
- One title-key module (`services/title_key.py`) with named strictness levels — `WORDS` (a
  page's words: "&" and "and", accents, apostrophes, numerals; order and article kept) and
  `TITLE` (a catalogue entry: brackets, a trailing year, edition words and library order
  removed, then folded and its leading article dropped) — built from T9's `fold`, which moves
  there unchanged. Used by the catalogue's lookalike check (Search, and now the add form), the
  spec page check, the Letterboxd and refresh index, and review finding; T9's `compare` reads
  the same `fold`. `canonical_title`, Letterboxd's `normalise_title` and reviews' `normalise`
  are gone, and the spec check's "&" patch with them. R1's pair table, with namesake and
  article cases, is the test.
- A dry-run diff of old against new keys over every live title lists, per site, each pair of
  live films whose sameness changes; identification's own comparison is unchanged by
  construction, so 0 identifications move, or the diff lists each for Craig.
- The add form, whether the film came from the search or a barcode, says "you may already
  own this" when an unidentified owned title has the same `TITLE` key and no other year:
  Search's check, shared.
- A barcode already on an owned copy is named before another copy is added: which copy (film,
  formats, place), that a box holding two formats is one copy (#101), and a link to it.
- The leftover rows are listed with their count after the merge and removed only at Craig's
  word, never in the merge.
- **Guard (CI):** the pair table, and a test that each site gives the table's answer.
- Tests. Gate green.

**The criteria as written on 12 Oct:**

**Found 11 Oct:** four title rules (the catalogue matcher, T9, the Letterboxd matcher, review
finding) disagree on 7 of 8 pairs and are patched per site; 5 films are split across two rows
(*Sorcerer* wanted while owned as a download); the add form and the barcode flow mark "in
collection" by TMDB id only, so an unidentified twin is invisible; two copies of one film were
added under one barcode; 8 film rows with no copies were left by the 18 Sep refresh.

**Acceptance (12 Oct, superseded by the amended list above):**
- One title-key module with named strictness levels, built from T9's comparison (numerals,
  both sides of a colon, "&" and "and", accents, leading articles), used by all four sites; the
  per-site patches are gone; R1's pair table is its test.
- An identify dry-run diff shows no identification moves, or lists each move for Craig.
- The add form and the barcode flow use Search's lookalike check (unidentified owned titles)
  for "you may already own this".
- A barcode already on a copy warns before another copy is added (#101's combo).
- The 8 leftover rows are removed at Craig's word, with the count shown first.
- **Guard (CI):** the pair table.
- Tests. Gate green.

### ~~X11~~ — Wanted: shop prices shown, alerts without a limit 🟡 — **shipped 18 Oct (#281)**
**Covers MK47-05 (Medium).** Mid tier · high. Sitting 5, first.

**Found 11 Oct:** 1 of 10 wants has a price limit, and a shop alert needs one; shop prices are
stored nightly and shown nowhere; the three Shopify shops answer Cloudflare 429s to every
request, costing 28–31 minutes a night.

**Acceptance:**
- The Wanted page shows each want's latest price per shop, with its date.
- A want with no price limit alerts on a shop price under the film's usual (V8's).
- A shop that refused every request for a week is asked weekly, not nightly, until
  `OWNER-ACTIONS.md` 28; a nightly run takes minutes, not half an hour.
- Tests. Gate green.

**Re-measured 18 Oct, read-only against live (nothing built yet; waits for Craig's go).** What
still holds, and what changed since 11 Oct:
- *Holds:* 1 of 10 active wants has a limit (Cross of Iron, £14); 8 of 10 name no format. No
  API or screen shows a stored shop price. The nightly run took 26–29 minutes on every night
  from 3 to 18 Oct (2 minutes before 3 Oct); 25–28 refusals a night, each waited 60 s.
- *Changed:* no shop refuses **every** request. On each of the last 9 nights 101 Films,
  Powerhouse and Second Sight each had 5–10 of 10 wants refused twice, but each also had a
  retry get through on some nights (Second Sight priced a want on 18 Oct, Powerhouse on 15 Oct,
  101 Films on 13 Oct). Read literally the weekly criterion matches no shop today.
- *Changed:* the shops now give 1–2 prices a night, not 5–7. Zavvi has priced nothing since 12
  Oct (`no_results` on every want since; 74 checks before). Not X11's to fix; noted for Craig.
- *Changed:* `retailers.scrape_frequency` already exists and the admin screen edits it, but
  `run_scrape` never reads it, and every live shop holds the default `weekly`. Making the
  runner honour it as it stands would move Zavvi and Arrow to weekly too.
- *Changed:* V8's "usual" exists as `ebay_price_refs` per film and format (fresh for 14 days;
  all 10 wants' films were last priced 12 Oct, so they go stale on 26 Oct unless the scan
  refreshes them). A want with no format has no usual to compare against until the format is
  read off the shop's own listing, as `ebay_watch/usual.py` does.

**Amended criteria (the original wording kept above; each change stated):**
- The Wanted page shows each want's latest price per shop, with its date. *(unchanged; adds the
  listing's title and link, so a "Limited Edition" price is not read as the standard disc.)*
- A want with no price limit alerts on a shop price under the film's usual (V8's). *(Amended:
  "usual" is the stored usual for the format and standard edition of the listing the shop
  priced; no stored fresh usual means no alert, and nothing calls eBay from the shop check.
  An alert still fires only on the way down, as a limit's does. A want with a limit is as
  before.)*
- A shop that refused every request for a week is asked weekly... *(Amended, pending Craig's
  choice: "refused every request" becomes "refused at least half of a night's requests, twice
  each, on each of its last seven asked nights", which the three shops meet today. Weekly means
  the scheduled check skips it for six nights; "Run now" still asks every shop. The mechanism
  (a counter column on `retailers`, or the runner honouring `scrape_frequency`) is Craig's
  choice at the go: either way the shops start nightly and the first weekly skip comes after
  seven refused nights, unless he says to seed it, which writes live rows.)* A scheduled run
  without those shops takes about 3 minutes.
- Tests. Gate green. *(unchanged)*

**Acceptance: met in code, criterion by criterion (18 Oct, #281).** Shop prices with dates and
links on the Wanted card (web and API tests; seen at 375 px against a seeded throwaway
database). No-limit alert under the stored usual: eight cases (under, at and over, no ref,
stale ref, other format, limited edition, once per drop) plus a limit's unchanged. Weekly ask:
the rule, the counter, the skip without a request, "Run now" asking every shop, and a night
that answers resetting it. **Not yet seen live:** every shop's counter starts at 0, so the
half-hour night ends only after the seventh scheduled refusing check (about 26 Oct), unless
Craig says to seed it. Migration 060 adds `retailers.refused_nights`; both read-only roles
already read the table, and the grant is repeated for the column. Gate: ruff, mypy, API pytest
(2,372 passed, the two known stale-edit tests failing on a throwaway pgserver as on `main`, 9
skipped), `pnpm -r test` (631 web), shared typecheck and build, web lint (10 warnings, none
added), typecheck and build. OpenAPI snapshot regenerated.

### X12 — Polish and terms 🟡
**Covers UX48-05 (Medium), UX48-06, UX48-07, CT46-06, CT46-07, DS44-06 and the rest of CR43-08
(Low).** Mid tier · high. Sitting 5, after X11.

**Acceptance:**
- Home's "Films owned" counts films with a copy (1,869 on 11 Oct, not 1,891); copies read
  "1,889: 1,466 discs, 422 downloads"; the two "Digital" figures say what each counts.
- One date helper ("11 Oct", "11 Oct 2026") across screens; the movie-night shortlist reads
  title, year and poster from the film; a match is stored on the session and shown on the night
  page; a copy's shelf is printed once.
- Labels and badges at least 12 px; list links padded to 44 px; the dark primary button at
  least 4.5:1; axe-core passes on the screens R6 measured.
- JSON answers compressed; the Archive list selects only the columns it shows, and its first
  screen renders before the rest.
- TMDB's logo and "not endorsed" notice in Settings; the JustWatch credit under watch
  providers.
- A spec lookup's Brave results are deleted once it is decided (the accepted address kept);
  TMDB fields older than 150 days are refreshed inside the calendar refresh, before 8 Mar 2027.
- Completion sets count the top ten billed and drop shorts and compilations; the refresh is
  re-run.
- The dead Supabase-era `/migrations/001_profiles.sql` is deleted; `*.xlsx` is ignored by git;
  `DECISIONS.md`'s duplicate #28 is noted; `group-start.md`'s "close-out is explicit (#13)"
  is corrected to #24.
- A "Tell Craig" line on Mark's You page lands in X2's attention row.
- Tests. Gate green.

**Re-measured 18 Oct, read-only against live and the code (nothing built; waits for Craig's
go on the split below).** What holds, what has moved, what has gone:
- *Gone:* `AGENTS.md`'s stale summaries and `docs/agent-commands/README.md`'s "never automatic"
  (CR43-08's first half): both already read correctly. The API's "Films" count already counts
  films with an owned copy (X5, #269); only the labels remain.
- *Moved:* live counts are 1,923 copies (1,335 discs, 588 downloads) over 1,899 films with a
  copy, not 1,889 / 1,466 / 422 / 1,869. "Digital" is 588 in Formats (copies carrying the
  download format) and 454 in Where they live (copies kept in the Digital section).
  Criterion 1 is written as "copies N: discs, downloads" with the live numbers, not those of
  11 Oct.
- *Holds:* no JSON compression; 80 date-formatting sites across the web (several forms); 18
  `text-[9-11px]` sites; no TMDB logo or "not endorsed" notice and no JustWatch credit; root
  `/migrations/001_profiles.sql` exists and nothing reads it; `*.xlsx` is not ignored (the two
  untracked spreadsheets are the proof); `group-start.md` still says "(#13)"; `DECISIONS.md` has
  two #28s; no match is stored on a movie-night session; nothing tells Craig from Mark's You
  page (X2's `/attention` reads the daily check only).
- *Holds, live data:* Brave results kept on decided lookups: 10,306 on 851 done lookups, 850 of
  them the accepted address, so **9,456 would be deleted** (the 5,210 on the 422 lookups
  still needing a person stay); TMDB fields: none older than 150 days yet (oldest 8 Sep,
  1,051 films that day; first crosses 150 days on 5 Feb 2027), 17 films with a TMDB id and
  no sync date; completion sets: 40 (20 and 20), all last refreshed 8 Sep (Bess Flowers 353
  members, Christopher Nolan 19), `candidate_people` still counts any billing position.

**X12 is more than a day (about three), so it is split into three batches, each closed out on
its own, in this order** (proposed 18 Oct; amended here, not dropped, criterion by criterion):
- **X12a, counts, dates and the movie night** (UX48-05, the "Tell Craig" line) — **shipped 18
  Oct (#282)**: Home's labels
  and the two Digital figures; one date helper across the 80 sites; the shortlist reading title,
  year and poster from the film; a match stored on the session (migration) and shown on the
  night page; a copy's shelf once; the "Tell Craig" line into X2's attention row. About a day.
- **X12b, phone polish and speed** (UX48-06, UX48-07) — **shipped 18 Oct (#283)**: 12 px floor, 44 px list links, the dark
  primary button at 4.5:1, axe-core on R6's screens (the rig is on this Mac), JSON compression,
  the Archive list's columns and first screen first. About a day.
- **X12c, terms and tidying** (CT46-06, CT46-07, DS44-06, CR43-08's rest) — **shipped 18 Oct (#284; fix
  `e109b98`); both live steps ran at Craig's word the same day**: TMDB's logo and
  notice, the JustWatch credit, Brave results deleted once decided, the 150-day TMDB refresh,
  completion sets by top ten billed without shorts, the dead file, `*.xlsx`, #28, group-start.
  About a day; **two live steps at Craig's word, count first:** deleting 9,456 Brave results,
  and re-running the completion-set refresh (40 sets).

## Group Y — Mark's requests, planned 13 Oct

**Planned 2026-10-13 from Mark's request, relayed by Craig:** edit discs after adding them, and
move them between shelves. Craig's answers the same day (#264): Mark edits and moves copies,
Mark deletes them too, and moving several discs at once is its own batch. **Criteria authored
2026-10-13**, so `DECISIONS.md` #54 does not apply. Model tiers are Group V's. Lands as Group W
did: a `feat/` branch, a pull request, CI green, a merge commit, production `/api/v1/health`
reporting the merge SHA with `db: ok`.

| Batch | Covers | Size | Gate | Claude Code | Codex |
|---|---|---|---|---|---|
| ~~Y1~~ | ~~Mark edits, moves and deletes copies~~ (`4840711`) | ~~🟢~~ | **shipped 13 Oct** | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~Y2~~ | ~~Move several discs at once, from anywhere~~ (`e0b5bad`) | ~~🟡~~ | **shipped 13 Oct** | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~Y3~~ | ~~TV series identified from TMDB, and the ones matched as films found~~ (`ef62257`) | ~~🟡~~ | **shipped 15 Oct** | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~Y4~~ | ~~Mark settles the doubts from the film page~~ ([#81](https://github.com/CraigR973/mcu-app/pull/81), #276) | ~~🟡~~ | **shipped 16 Oct** | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~Y5~~ | ~~Mark's 16 Oct points: series discs added and moved, Film Noir, a disc added by its title~~ (#277) | ~~🟡~~ | **shipped 17 Oct** | ~~top tier · high~~ | ~~top tier · High~~ |
| ~~Y6~~ | ~~Doubts on a film with no copy~~ (#279) | ~~🟢~~ | **shipped 18 Oct** | ~~top tier · high~~ | ~~top tier · High~~ |

*Why those efforts.* Both change who may write the collection. Y2 adds a write endpoint with
partial success and one audit row per copy, and its stale-edit handling is #42's rule applied
to many rows.

### ~~Y1 — Mark edits, moves and deletes copies~~ 🟢 **shipped 2026-10-13 (`4840711`, [#59](https://github.com/CraigR973/mcu-app/pull/59))**
**Acceptance: met.** `PUT` and `DELETE /collection/{id}` take either person; a test has Mark
move a disc to Craig's house and delete it, with both audit rows naming him, and a second has
him refused a restore (403) that Craig's succeeds. The film page shows him Edit copy, Mark
damaged, Add a copy and the upgrade prompt, and still hides the eBay check, the sale panel,
photo uploads and the item history. Move to trash asks first. Browser check at 375 px as Mark
by #169's method (stub API in the scratchpad, `.env.local` deleted after): moved Front 2nd →
Back Top, the `PUT` carrying `baseUpdatedAt`; two-tap delete. Local gate green (API 1,268
passed, 706 skipped without Postgres; web 564; shared 137); CI green first time, pytest 1,974
passed against Postgres with none skipped. The OpenAPI snapshot changed in two descriptions
only. Production reported `4840711` with `db: ok` and every field `configured`, and the web's
`/version.json` the same commit. **Open:** Mark trying it on his phone; asking him whether he
moves whole shelves decides Y2.


**Covers Mark's request.** Since #155 Mark can add a disc but not correct it, and a disc's
location is its section and shelf on the same edit form, so he could not move one either.

**Acceptance:**
- `PUT /collection/{id}` and `DELETE /collection/{id}` take either person (`CurrentUser`).
  Each change writes an audit row naming the person who made it.
- Still Craig's, and still refused to Mark with 403: listing the Trash, restoring from it,
  the audit log, retailers. A test proves Mark deletes a disc and cannot restore it, and
  Craig can.
- The film page shows Mark Edit copy, Mark damaged, Add a copy and the upgrade prompt. It
  still hides from him the live eBay check, the sale panel, photo uploads and the item
  history.
- Move to trash asks before it deletes, for both people. Mark's confirmation says only Craig
  can bring the disc back.
- Mark's edit goes through the same offline-aware path as Craig's, `baseUpdatedAt` included.
- Tests, API and web. Gate green. Browser check at 375 px as Mark: edit a copy, move it, ask
  to delete it.

### Y1 follow-up — Mark's first feedback, fixed 2026-10-13 (`2ef3b8a`, [#63](https://github.com/CraigR973/mcu-app/pull/63))
Both on 12 Angry Men (`DECISIONS.md` #266). **A shelf-only edit kept the old text**, so the film
page showed two places: the copy form now clears the text for a new shelf as it did for a new
section, and the API recomposes text that names a different place from the pickers. Read-only
check: 1 of 1,885 live discs disagreed, this one. **The delete question hid its own Yes** below
a phone's fold with Save in its place, and nothing was deleted: the footer is now only the
question, "Yes, move to trash" and "Keep it". Two API tests, a CopyForm interaction test, the
film page's delete test extended. CI green first time; production reported `2ef3b8a`.

### ~~Y2 — Move several discs at once, from anywhere~~ 🟡 **shipped 2026-10-13 (`e0b5bad`, [#61](https://github.com/CraigR973/mcu-app/pull/61))**
**Acceptance: met.** A Move discs page in The archive's menu for both people; W3's finder
extracted to `FilmFinder` and shared with Loans (its 4 tests unchanged and green). A film with
one disc goes straight into the tray, one with several asks which. The tray lives in
`localStorage` on the phone. `POST /collection/move` takes up to 200 discs with a required
`baseUpdatedAt` and a place each, answers `moved` / `unchanged` / `stale` / `not_found`,
resolves every place before writing, and writes one `update` audit row per disc moved; five
Postgres tests cover the viewer's move with audit rows, partial success, an exact undo
including free text, a bad section writing nothing, and the duplicate and ceiling refusals.
Browser check at 375 px as Mark by #169's method: Heat added by search, Alien by a typed
barcode with its two discs to choose from; three moved (two moved, one already there); "Move
them back" sent each disc's own previous place with its new version. The check found two
wording faults, fixed before the merge: the report now names the disc ("Alien (DVD)"), and the
empty button reads "Move discs". The route pin (`test_health.py`) and the nav list's tests
gained the new route and destination. Local gate green (API 1,268 passed, 711 skipped without
Postgres; web 568; shared 139); CI green first time, pytest 1,979 passed with none skipped.
**Open:** Mark using it on his phone, the camera scan included (the browser check typed the
barcode; the camera path is W3's, unchanged).


**Covers the rest of Mark's request.** Rewritten 13 Oct at Craig's word (#265): the discs come
from anywhere, not from one shelf, so the first draft's "filter to a shelf, then select" is
replaced by a tray. **Scanning included**, at Craig's choice, knowing a scan names the film,
not the copy, for discs with no barcode stored.

**Acceptance:**
- **A Move discs page**, in the archive's menu for both people. Find a disc by searching your
  films or scanning its barcode, with the finder Loans' "Lend or borrow" uses (W3), shared
  rather than copied.
- **Copies, not films.** A film with one disc on the shelf goes straight into the tray and the
  finder is ready for the next. A film with several asks which, each shown with its format,
  edition and place.
- **The tray** lists each disc with where it is now, keeps its picks across searches and
  visits on that phone, and takes a disc out or clears.
- **One place for all of them.** Section from the whole vocabulary (V4), then a shelf where the
  section has any. One request.
- **Partial success.** `POST /collection/move` takes up to 200 discs, each with the `updatedAt`
  it was picked at and its own place. It answers per disc: moved, unchanged (already there,
  nothing written), stale (changed elsewhere since it was picked, left alone, #42), or not
  found (deleted, sold or unknown). A stale or missing disc does not stop the others. Every
  place is resolved before anything is written, so an unknown section refuses the whole
  request. Its own response shape, as #6 allows.
- **Audited per disc.** One `update` audit row per disc moved, naming the actor, with the
  edit's own diff.
- **Either person**, as Y1 made editing.
- **The report** says how many moved and where, which were already there, which changed on
  the other phone (and where they are now; they stay in the tray at their new version), and
  which are no longer in the collection.
- **Move them back** returns each moved disc to its own previous place, free-text location
  included, through the same endpoint.
- **Online only.** Offline the button is off and says why; the tray waits on the phone.
- The Archive, the facet counts and each film's copies refresh after a move.
- Tests: the endpoint's cases against Postgres (partial success, undo exact, a bad section
  writes nothing, one disc named once, the ceiling); the page's one-disc, several-disc, report,
  undo and offline cases. Gate green. Browser check at 375 px as Mark: find two discs, move
  them, see the report, move them back.

### ~~Y3 — TV series identified from TMDB, and the ones matched as films found~~ 🟡 **shipped 2026-10-15 (`ef62257`, [#75](https://github.com/CraigR973/mcu-app/pull/75))**
**Acceptance: met, but for the one check only production can make.** Migration 056 adds
`movies.tmdb_tv_id` and `identify_lookups.media_type`; it went up, down to base and up again
locally and in CI. Nine Postgres tests in `test_tv_series.py`: Mark identifies a set-aside series
from its page (series offered, its own id, cast, creators, genres filed under War, the alias,
the audit's `tmdbTvId`, gone from "Still to identify"); a film corrected to a series and back; a
second copy merged into the row holding the series; Craig undoes one from the Identify films page,
and the undo refuses a series identified again since; a series leaves Craig's queue and cannot be
set aside; streaming from the series providers; TMDB's 404 changes nothing; a card says `tv`.
Seven in `test_series_check.py`: the rule (Band of Brothers named, Fargo left alone, a "TV"
grouping or a series spreadsheet title enough alone), failures noted, the report escaped, and the
HTTPS path's compiled SQL the same rows as the session's. Web: the panel's series group first and
a series chosen by its own kind, the not-a-film note, no Letterboxd link for a series, the card's
tag; shared: an answer from before Y3 still parses. Browser check at Pixel 7 as Mark against a
seeded database and a stand-in TMDB: Broadchurch identified from "Still to identify", Band of
Brothers corrected from the 1998 film to the 2001 series, both cards "TV series", the count 2 → 1.
Local gate green (API 2,101 passed with Postgres, none skipped; web 592; shared 143); CI green
first time on the PR and on `main`. Shipped with #272's two fixes, the same feedback's points 3
and 4. **Production:** Craig read `/api/v1/health` reporting `ef62257` and `/health/ready` with
`db: ok` and every field `configured`, and `version.json` the same commit; this session's network
policy refused both hosts. **Open:** the first live series identification, the check of TMDB's
real `/tv/{id}` answer (no TMDB key here); Mark working through the series; Craig's read-only
`find_series_as_films` run (`OWNER-ACTIONS.md` item 31).


**Covers Mark's feedback of 15 Oct, points 1 and 2** (`OWNER-ACTIONS.md` item 31, built at
Craig's word the same day). The 12 titles left under "Still to identify" are series; T9 set 34
more aside as TV (#214) because the app matched films only; and some series were matched to a
film of the same name (Band of Brothers, 11.22.63). Lands on `claude/brave-tesla-4y6zvv` with
#272's two fixes, through a pull request, as Group Y does. **Criteria authored 2026-10-15.**

**Acceptance:**
- **A series has its own TMDB id.** Migration 056 adds `movies.tmdb_tv_id` (unique) and
  `identify_lookups.media_type` (`film` or `tv`). `tmdb_id` stays a film's only: TMDB numbers
  films and series separately, and about 40 modules read `tmdb_id` as a film's. Both tables are
  granted to `mcu_readonly` and `mcu_backup` whole, so the new columns need no grant, and
  neither holds a credential.
- **Identify a series from its page**, either person. `GET /movies/{id}/candidates` returns
  TMDB's series beside its films (`seriesCandidates`, up to 5, each with its first-air year);
  `POST /movies/{id}/identify` takes `mediaType: "tv"`. A series fills in title, first-air year,
  overview, poster, backdrop, rating, genres (TV genres also filed under the film genre they
  match, so the genre filter finds them), IMDb id, trailer, cast and creators, with `is_tv`
  true, so values keep pricing it by the series rules. It is audited, keeps the title it
  replaced as an alias, merges into a row that already holds the series, and undoes from the
  Identify films page as a film's identification does.
- **A film corrected to a series, and back.** "Correct match" offers series too. Identifying a
  film row as a series clears its film id, and the reverse clears the series id; undo restores
  either.
- **"Still to identify" and the badge** count a film identified when it has either id, and
  list the 34 set aside as TV, since they can now be identified. A title set aside as not a
  film stays out. Craig's Identify films queue and its counts leave out a series identified.
  The identify panel shows series first for a title set aside as TV or already a series.
- **A series' page:** "TV series" on its card and list row; streaming offers from TMDB's series
  providers; no Letterboxd link and no price alert, which are films' (unchanged, as before Y3).
- **Finding the series matched as films:** `src.scripts.find_series_as_films`, read-only (a
  `READ ONLY` transaction, closed before TMDB is asked), checks every identified owned film
  against TMDB's series index and reports the suspects with a link to each film's page: a series
  of the same title (`titles.compare`, `same_title`) that has at least five times the film's
  votes and at least 50, or a disc grouped "TV", or a replaced spreadsheet title in T9's series
  words. It changes nothing; Mark or Craig correct each from its page.
- Tests: the migration up and down; identify a series, merge into one, undo, correct a film to
  a series and back, against Postgres; the candidates' series; the filter, badge and queue
  counts; the detection rule on stand-in TMDB answers; the panel's series group and the card's
  tag. Gate green. Browser check at Pixel 7 size as Mark: identify a set-aside series from its
  page against a stand-in TMDB.
- **The TMDB series payload is not checked against a real answer here:** the cloud session has
  no TMDB key. The model follows TMDB's published `/tv/{id}` shape with every field optional,
  and the first live identification (Broadchurch) is the check.

### Y3 follow-up — the series pass, built 2026-10-15 at Craig's word
`DECISIONS.md` #274. Craig asked for #273's two steps to be done for him; this session could reach
neither TMDB nor the live database, and he chose a pass he runs at the Mac. `src.scripts.
identify_series`: a read-only dry run proposes a TMDB series for each title "Still to identify"
(the Archive's rule, moved to `services/identify/waiting.py`) where TMDB leaves no doubt, and
writes a plan and a report; `--apply` identifies exactly that plan, re-checking each title, audited
`auto`, undoable, never merging. Eight tests in `test_series_pass.py`, two against Postgres; they
caught a would-merge title reading its holder's name after the rollback had expired it. Local gate
green (API 2,109 passed with Postgres; web 592; shared 143). **Open:** Craig's sitting at the Mac,
`OWNER-ACTIONS.md` item 31.

### ~~Y4 — Mark settles the doubts from the film page~~ 🟡 **shipped 2026-10-16 ([#81](https://github.com/CraigR973/mcu-app/pull/81))**
**Acceptance: met, criterion by criterion; production in the close-out.** Five Postgres tests in
`test_mark_settles_doubts.py` (the filter, flag and facet; every doubt on the film page with its
copy and proposal; Mark keeps, audited as him, and Craig sees and undoes it; the undo refused
once the film changed; Mark searches and moves one copy, and is still refused the queue, the
doubts list, the overview, the recent list, undo and correcting a doubt). Web: the filter's
option and chip, the card's flag, the film page's rows and actions for Mark, a kept row with
Mark's name. Two X9/Y1 web assertions changed with #276, flagged in the PR. Local gate green
(API 1,388 passed, Postgres tests skipped on the Mac; shared 149; web 611); the identification
and health tests (63) also ran against a throwaway local Postgres. Browser check at 375px against
seeded local data: Mark filtered "In doubt (2)", kept one, opened Move only this copy; Craig saw
"kept as right · Mark" and undid it ("In doubt" 2 → 3); no console or server errors.

**Asked by Craig, 16 Oct, after item 32 raised 384 doubts:** "can we add them for Mark to
verify in the app?" He chose the full version and said go the same evening (#276). Mark has
worked through the unidentified films from their pages (#271–#273); the doubts were Craig's
alone, on Identify films. Top tier · high: it opens three Craig-only routes to Mark. **Criteria
authored 2026-10-16.**

**Acceptance:**
- **Mark finds them.** The Archive's identification filter offers "In doubt (N)" beside "Still
  to identify": identified films with an open doubt. `GET /movies?inDoubt=true` and the facets'
  `inDoubtMovieCount`; each list item carries `inDoubt`, and a card or row says "In doubt".
- **The film page lists every open doubt**, one row each, with its note, the copy it names and
  T9's proposal where it has one, where it showed only the oldest.
- **Either person settles one there:** **It's right** (keep), **Correct match** (already both,
  #273; settles every doubt), and **Move only this copy** where the doubt names one copy of a
  film with others. Keep, move and the TMDB search the move uses open to any signed-in person;
  each audit row carries who. The rest of Identify (queue, doubts list, recent, undo, set
  aside) stays Craig's.
- **Craig can see and undo Mark's decisions:** a kept doubt is listed under Recently identified
  ("kept as right") with who, and its undo opens the doubt again, refused once the film has
  changed since. Every recent row shows who.
- **Guards:** Postgres tests that Mark keeps and moves, audited as him; that he is still refused
  the rest of Identify; the filter, facet and flag; the film page's list; a keep undone and the
  refusal. Web tests for the filter, the flag, the film page's actions for Mark and a kept row.
- Tests. Gate green; production `/api/v1/health` on the merge SHA with `db: ok`.

### ~~Y5 — Mark's 16 Oct points~~ 🟡 **shipped 2026-10-17**
**Acceptance: met, criterion by criterion; production in the close-out; the backfill waits for
Craig (item 33).** Nine Postgres tests in `test_y5_series_noir_title.py` (series apart on the
add form, page two read; a series made once then found, the duplicate prompt, a trashed one
restored; two references refused; a copy moved to a series as Mark, the doubt settled, the
repeat refused, Craig's undo removing the series; a move to a held series, and a move with no
media type a film's; keywords stored on an add; `keywordId` on `/movies` and a saved
collection; the backfill's dry run, apply, 404 and changed row; a title-only add set aside as
Mark, off "Still to identify", found again) and twelve unit tests in `test_y5_units.py`.
Migration 059 up, down and up on a throwaway pgserver with both roles present: both granted
`SELECT` on the column, neither `UPDATE`. Web: the add form's series, title-only and barcode
cases and a pre-Y5 answer; the move panel's series and opened search; Identify films' series
move; Film Noir's option, place, chip and clearing; the saved filter and its words. One API
assertion gained the new key (`test_smart_collections_api.py`, the wire carries every filter,
as T3's runtime did); the two TMDB fakes gained `search_tv`. Local gate green (API 1,400
passed without Postgres; 2,163 passed against pgserver, bar the two stale-edit tests that fail
there on `main` too; shared 152; web 622). TMDB checked live for the three: *Life* → tv 16946
first of five, *Tinker Tailor* → 35430, *Name of the Rose* → 86343. Browser check at 375px
against seeded local data and live TMDB: Mark filtered Film Noir (3 of 8); opened each
doubt's move already searched; moved Tinker Tailor's Blu-ray to the 1979 series (made with its
keywords); added Band of Brothers as a series and *A Day in the Life* by its title; Craig saw
"one copy moved · Mark" and undid it (series gone, both copies back, doubt open); Identify
films offered BBC's *Life* to move. No server errors. Found and fixed on the way: overviews
were never clamped on the add form (`block` overrode `line-clamp`), and the series sat below
twenty films, so a "N TV series, below ↓" link jumps to them.


**Asked by Mark through Craig, 16 Oct; Craig approved all three parts the same day (#277).**
Mark found three series discs catalogued on the same-named film beside a right copy (BBC's
*Life* Blu-ray on *Life* (2017), the 1979 *Tinker Tailor* Blu-ray on the 2011 film, the 2019
*Name of the Rose* Blu-ray on the 1986 film), each with an open re-check doubt naming the copy,
and "Move only this copy" and the add form offer films only. He asked for a Film Noir filter;
Craig chose TMDB's keyword 9807 "film noir" over IMDb's genre and the sheet's groupings (224 of
the 1,850 identified owned films carry it; 35 of the 48 sheet "noir" groupings). And John
Krish's *A Day in the Life* (BFI Blu-ray) is not on TMDB as one title, so it cannot be added.
Top tier · high: it adds a migration, a live backfill and a third and fourth way to name a
film on the add form. **Criteria authored 2026-10-16.**

**Acceptance:**
- **Series on the add form.** `GET /tmdb/search` answers TMDB's series in their own list
  (`series`, up to 5, ranked by T9's series rule, each saying whether the collection holds it);
  `results` stays films, so an app cached before Y5 never offers a series as a film.
  `POST /collection` and `GET /collection/duplicate-check` take `tmdbTvId`: the copy goes on
  the collection's row for that series, or one made from TMDB's record (metadata and credits as
  Correct match writes them), restored from the Trash as a film's is. The duplicate prompt
  holds for a series as for a film.
- **Series for "Move only this copy".** `GET /identify/films/{id}/search` answers
  `seriesCandidates` beside `candidates`; `POST /identify/copies/{id}/move` takes
  `mediaType: "tv"`, moving the copy to the collection's row for that series or one made from
  TMDB's record. The audit row names both ends, the doubt about the copy is settled, and the
  undo on Recently identified puts it back and removes a series row nothing else points at.
- **One tap from the doubt.** A doubt's "Move only this copy" opens already searched, on the
  title the doubt was raised from (the sheet's, carried as `searchHint`), and lists series
  marked "TV series" beside films, so moving the copy is the next tap. Identify films' doubt
  card offers the same series moves from its search. Checked against TMDB for
  the three: *Life* → tv 16946, *Tinker Tailor* → tv 35430, *Name of the Rose* → tv 86343, each
  offered. The three moves themselves are Craig's, in the app.
- **Film Noir.** Migration 059 adds `movies.tmdb_keyword_ids integer[]`, null meaning not
  fetched, granted to `mcu_readonly` and `mcu_backup` in the guarded block. `get_movie_full`
  and `get_tv_full` append `keywords`; `movie_metadata_values` and `tv_metadata_values` set the
  ids (null when the record carries no keywords block, an empty list when TMDB has none), so
  every add, identification and move fills it. `GET /movies?keywordId=` filters by it, and a
  saved collection's filters carry `keywordId`. The Archive's genre filter offers "Film Noir"
  (keyword 9807), with its chip, beside the genres.
- **The backfill.** `src.scripts.fill_keywords` fills the column for live identified films and
  series whose ids are null, one `/movie/{id}/keywords` (or `/tv/{id}/keywords`) call each, at
  8 a second; a dry run by default (it reads TMDB and reports how many would fill and how many
  are noir, writing nothing), `--apply` at Craig's word. Rerunnable: it touches only null rows,
  and a film TMDB no longer has is counted and left null.
- **Add by title.** The add form's search offers "Add “…” by its title" for a disc TMDB does not
  have. `POST /collection` (and the duplicate check) take `title` as a fourth reference: the
  copy goes on a new title-only film, set aside as not a film (audited, by whoever added it),
  or on the live title-only film already set aside under that title, so a second copy meets
  the duplicate prompt. Such a film is not on "Still to identify" and is not flagged
  "Identify". With a scanned barcode held, a series or a title-only add skips the barcode
  confirmation (the barcode still goes on the copy, which the next scan finds).
- **Guards:** Postgres tests for adding a series (new and existing), the duplicate prompt for
  one, moving a copy to a series and undoing it, the series search answers, the keyword filter,
  the backfill's dry run and apply, adding by title (new, reused, kept off "Still to
  identify"), and the migration's grants; unit tests for the metadata translation. Web tests
  for the add form's series and title-only adds, the move panel's series and opened search,
  the genre filter's Film Noir and its chip. Browser check at 375px against seeded local data.
- Tests. Gate green; production `/api/v1/health` and `version.json` on the merge SHA with
  `db: ok`. Then the backfill waits for Craig's word.


### ~~Y6 — Doubts on a film with no copy~~ 🟢 **shipped 2026-10-18**
**Acceptance: met, criterion by criterion; production in the close-out.** Six Postgres tests in
`test_y6_doubts_without_copy.py` (the only copy binned, then restored, with the daily check;
the named copy binned beside another; sold and unsold; a doubt naming no copy as each copy
goes; a named copy on another film; two doubts on one film counted once, the three counts
agreeing). One existing test changed its setup, not its assertion: the daily check's doubt in
`test_identify_doubts.py` was on a film with no copy, exactly what #279 hides, so it gained a
DVD. Shared and web tests for `films` and the header's words; the OpenAPI snapshot regenerated.
Local gate green (API 1,401 passed without Postgres; 2,174 passed against a throwaway pgserver,
bar the two stale-edit tests that fail there on `main` too; shared 153; web 624). Browser check
at 375px against seeded local data: Identify films read "Identified, in doubt 3" and "In doubt
(3 films, 4 doubts)", the Archive "In doubt (3)"; binning the documentary's only disc made it
2 and "2 films, 3 doubts"; restoring it from the Trash brought back 3 and the film page's
doubt with its copy. No console or server errors.


**The fault, 17–18 Oct.** A re-check doubt named a copy that #278's plan then binned (the old
Ghostbusters 2 disc, catalogued on *Time Is But a Window: Ghostbusters 2 and Beyond*). The film
had no owned copy left, so the Archive's "In doubt" filter, its search and the film page never
showed it, while Identify films' overview still counted it and its doubts list could only show
it with 0 copies. Craig could not find it anywhere; it was cleared by hand on 18 Oct
(`settle_doubts`), so live data has no open doubts. The cause: Identify films and the daily check
read "open, on a live identified film", while the Archive and the film page also need an owned
copy. **Craig chose option A, widened (#279), 18 Oct**, over settling the doubt when its copy is
binned (B). Top tier · high: it changes what five surfaces count. **Criteria authored
2026-10-18.**

**Acceptance:**
- **One rule for a doubt that shows** (`showing_doubt()` in `services/identify/doubts.py`): open,
  on a live identified film, and still about something owned. A doubt naming a copy shows while
  that copy is an owned copy of the film (not binned, not sold, still on that film); a doubt
  naming no copy shows while the film has an owned copy.
- **Every surface uses it:** Identify films' doubts list and its total, the overview's
  "Identified, in doubt", the daily check's fortnight-old count, the Archive's "In doubt" filter
  and count, the card and row flag, and the film page's list and flag.
- **Nothing is written when a copy goes.** Binning or selling the copy hides its doubt, by any
  path (the copy's Delete, the tray, `settle_doubts`, a merge, marking sold); restoring it from
  the Trash or unselling it shows the doubt again, as it was.
- **The counts agree.** The overview counts films, so it equals the Archive's "In doubt (N)";
  the daily check counts films whose showing doubt is a fortnight old, so it is never more. The
  doubts list says how many films and how many doubts when they differ
  (`IdentifyDoubtsResponse.films`, optional in the shared schema, so the web still parses an
  API from before Y6 while the two deploy).
- **Guards:** Postgres tests for a doubt whose copy is binned (film has no copy, and film has
  another copy), sold, restored from the Trash, and a film-level doubt whose last copy goes;
  the overview, the Archive count and the daily check agreeing; two doubts on one film counted
  once. Shared and web tests for the films count and its words. Browser check at 375px against
  seeded local data.
- Tests. Gate green (pytest without Postgres, and against a throwaway pgserver bar the two
  stale-edit tests that fail there on `main` too); production `/api/v1/health` and
  `version.json` on the merge SHA with `db: ok`. No live data step.

## Post-launch — sequenced, not scheduled

Revised 2026-09-07 by `DECISIONS.md` #16: all of Part D's drops are reinstated except 9.6.

| # | Batch | Tier | Claude Code | Codex | Status | Phases |
|---|---|---|---|---|---|---|
| ~~10~~ | ~~Architecture doc split + §17 reconciliation~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~Part C deferred half~~ | `d94a6b8` · `ARCHITECTURE.md` split off with §16 replaced by a pointer to this ledger; all 50 §17 rows carry a reconciled status; `session-log.md.txt` retired |
| ~~11~~ | ~~Notifications + push~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~6.1, 6.2, 5.11~~ | `36d3efa` + `69d263e` · Web Push on RFC 8291/8292 over one new dependency; three tables and an outbox that makes §6.1 observable — a disabled category leaves a `suppressed` row naming itself, quiet hours leave one due next morning. **Two debts paid**: §12.5's overdue-loan push (unmet since Batch 15) and Batch 9's dropped onboarding step. `VITE_VAPID_PUBLIC_KEY` is **no longer needed** — the API serves the key, derived from the private half (#114). Live: `push: configured` on `/health/ready`. **6.2 not met — needs two real devices** |
| ~~12~~ | ~~Box sets + smart collections~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~11.3, 11.4, 11.5~~ | `881f444` · 3 tables, 7 endpoints; a saved collection and the filter bar evaluate through one function; "Unwatched 4Ks from the 2010s" listed 40 real films in the browser |
| ~~13~~ | ~~Completion sets~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~11.1, **11.2**~~ | 40 sets built live from TMDB, 0 errors; Hitchcock 12 of 61 (TMDB returns 65 director credits, 4 are screen tests); **"add to wanted list" dropped — Batch 18 owns it** |
| ~~14~~ | ~~Stats + export~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~13.1, 13.2, 13.3, 13.4~~ | stats **344 ms median** against live Neon (criterion: <1s); CSV/JSON/HTML export all 1,857 discs; **2 of 5 charts have no data and say so** |
| ~~15~~ | ~~Trash, audit UI, lending~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~13.5, 13.6, 12.5~~ | permanent delete proved on live data — row gone, cascade fired, **audit trail outlived its subject**, 1,857 discs untouched; **"overdue triggers a push" not met — Batch 11 owns push** |
| ~~16~~ | ~~Watch providers + recommendations~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~7.1, 7.2~~ | live: *North by Northwest* shows HBO Max + 6 rent + 6 buy in GB; **20 recommendations, 7 already on the shelf**; **"wanted" dropped — Batch 18 owns it** |
| ~~17~~ | ~~Release calendar + iCal~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~7.3, 7.4 — secret-token `.ics` URL~~ | live ingestion put **32 rows** in `release_calendar`, re-run idempotent; feed serves unauthenticated with hashed rotating tokens. **A security review found and closed a URL content-injection hole.** Apple Calendar check is an owner action |
| ~~18~~ | ~~Wanted list + retailers~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~5.1, 5.2 (full scope)~~ | §3.5 and §3.16 built; **four debts from Batches 13, 15, 16 and 17 paid**; 6 default retailers seeded, **0 configured — selectors are Batch 19's** |
| ~~19~~ | ~~**Scraper framework**~~ | ~~🔴~~ | — shipped | — shipped | **shipped** | ~~**5.3, 5.4**~~ | framework, nine built-ins, retry + auto-disable, SSRF-guarded fetcher, fixture tests. Page-shape checks (2026-09-09) verified **5 shops** and ruled out 4 permanently (#91); the runner's relative-URL and `written`-count defects were fixed then (#94). **Acceptance met 2026-09-09** (`DECISIONS.md` #111): all five shops `success`, zero failures, one or more `price_checks` rows each |
| ~~20~~ | ~~Price scraping + drop alerts~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~5.5, 5.6, 5.8~~ | `464e495` · `/scrapers/daily` is the whole schedule (#60 rules out an in-process timer) and **`scrape_runs` records every run** — the counts #112's corrected criterion is stated in, plus each failure with its retailer and reason. Drop alerts fire on the **transition** below `max_price`, not nightly while it stays there, and name any substituted format or edition. §5.8 rolls 90-day-old checks into `price_history_daily` and deletes them, in one transaction. **5.6 met 2026-09-10** — *"Cross of Iron is £12.99"* sent and delivered to a real device; the second person's copy correctly `suppressed` for `no_subscriptions`. **5.5 still open**: `cron-scrape` is applied and scheduled `0 3 * * *`, and the criterion is met by the first `scrape_runs` row reading `trigger=cron` |
| 21 | Price history charts | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | **5.7** — needs 7 real days of data after B20 |
| ~~22~~ | ~~Deals feed~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~5.9, 5.10 — RSS **and** scraped sources~~ | `c190129` · **5.10 met; 5.9 built, its acceptance is the owner's** — a live run against real sale pages (`OWNER-ACTIONS.md` 1e). Net-new `deals` table (029), applied in production. The batch's risk note needed a **page-level** check, not a per-card one: Batch 19's strongest rule is "does the title match the film asked for" and a deals page has no film asked for, so `check_page_shape` replaces it with agreement across the page (#150). "Skip already-owned" is format-aware — an upgrade is never already-owned (#151). Sale-page **selectors** are Batch 19's verified ones; the **URLs** all ship `verified: False`, and four of the five enabled shops had none at all, so "≥ 3 retailers" was previously unreachable (#152). Found on the way: Zavvi's `url` selector points at an `<h3>`, so every deal would have been unclickable and collided on `''` (#153). CI red once on a **pre-existing flaky** SearchBar test, fixed on its own `fix/` branch (`92c96bb`) and merged first |
| ~~23~~ | ~~Specs — scraper + display~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~3.7, 3.8, 3.9~~ | #110's bounds are **enforced in code, not described**: exact-release-URL predicate, sequential 5s-spaced requests, `403`/`429`/`451` halts the whole integration to a **database row** nothing in the runner can clear, provenance columns on every derived row, and `DELETE /specs` to make it reversible. No price, rating or review is extracted — the parser reads an allow-list and a test proves the sets disjoint. Badges and filters shipped. **Live: 0 pages ever fetched**  **§3.7 was run on 2026-09-10 (`#121`) and found the scraper broken**: ten pages fetched, nothing extracted, because the parser looked for `<strong>` rows and the site serves `<span class="subheading">` sections — and `test_specs.py`'s fixture had been invented to match the parser, so eleven tests passed against markup the site has never served. A second bug surfaced on the re-run: one audio track stored where the page listed six, on a page that wraps them in a `<span>`. Both fixtures are captured pages now and a test asserts they stay captured (`#122`). **Met on the third pass: 10 rows of 1,857, 10 distinct URLs, no halt.** `apply_specs` checks `is_empty` first, so two broken passes wrote nothing at all.|
| ~~24~~ | ~~Barcode — scan + lookup~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~3.3, 3.4 — confirmation UI mandatory~~ | `590504d` · Scan-first mobile UI with typed fallback; GS1 check-digit guard; confirmed cache → exact owned barcode → eBay → TMDB resolution; duplicate warning and mandatory human confirmation before a mapping or disc is written. Production serves the merge with `db: ok` and `ebay: configured`. **Physical acceptance remains open by explicit owner deferral:** real-phone decode in <2 seconds, correct common-disc match and unknown-code manual fallback (`OWNER-ACTIONS.md` 1d) |
| ~~25~~ | ~~Photo uploads~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~3.10~~ | Bytes in Postgres (Neon, owner 2026-09-09), a real `item_photos` table rather than §3.4's external-URL JSONB. **A phone's 4032×3024 lands at ~240 KB** — measured, not asserted. The target is `photo_target_kb` **config**, so the number `OWNER-ACTIONS.md` reserved is now an env var rather than a migration. Every upload re-encoded: EXIF applied then dropped, alpha onto white, bomb refused. **No CSP change was needed** — the note is retired |
| ~~26~~ | ~~Shelf QR~~ | ~~🟢~~ | — dropped | — dropped | **dropped** | ~~12.3, 12.4~~ — Batch 6's location filter solved the retrieval problem it existed for (`DECISIONS.md` #109) |
| ~~27~~ | ~~Gift links~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~12.1, 12.2 — high-entropy slug, rate limiter, `noindex`~~ | `888dae7` · 128-bit slug (not §3.21's UUID PK, not §6.26's 32-bit example); four failure modes answer identically; public model carries **no** ownership, ids, slug or counts. Verified anonymously in a browser |
| ~~28~~ | ~~**eBay integration**~~ | ~~🔴~~ | — shipped | — shipped | **shipped** | ~~**4.1, 4.3** — active listings, not sold comps. Browse verified live (`total=308`, `EBAY_GB`); **the effort is the match filter, not the median** — a naive median over that query is **149% high** (`DECISIONS.md` #129)~~ | `b2a6c27` · **4.3 met** — Option A does not exist (no API creates a Seller Hub draft), so Option B is primary and prefill was confirmed in a browser: the parameter is `title`, while `keyword`/`q`/`sugKw` fail **silently** (#142). **4.1 built, its acceptance NOT met — a live production call, and the owner's** (`group-start.md`; the ledger's own words: not something an unattended agent signs off). Proven instead against two captured 200-listing payloads: naive £24.74 against a matched £9.99 from 29 plain Blu-rays. Two guards were wrong first time and the fixtures caught both (#143). Sold comps remain unobtainable; every surface says "current asking prices" |
| ~~29~~ | ~~Format upgrade + sale tracking~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~4.2, 4.4~~ | `f215bf3` · **both criteria met.** No migration, as predicted. **A sold disc keeps its row** — soft-deleting it would hand it to §6.30's 90-day trash purge and destroy the record of what it fetched, so `owned_copy()` does the removing instead, replacing **eighteen** hand-written filters across seven routers (#145). Three defects found: the endpoint wrote **no audit row** (`listing_status` was unaudited, so the diff was empty), a bespoke `listing_sold` action type is refused by §3.20's closed CHECK, and `copyCount` was `ge=1` so selling your only copy 500'd the film's page (#146, #147). CI red once — a test borrowed a disc from the catalogue, which exists on Neon and not in CI's empty Postgres |
| ~~30~~ | ~~AI assistant — client + caps~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~9.1 + 9.7~~ | `ecb00dd` · Anthropic SDK on `claude-sonnet-5`, **the id validated at load against a priced list** so a typo fails at boot and an unpriced model is refused too (it would work, and log every call as free). Adaptive thinking + effort, since `budget_tokens` is a 400 on the Claude 5 family. Two ceilings — messages and dollars — checked **before** the call, refusing with a 200 and a sentence. Every call logged including failures; a failure does not spend an allowance. Live: `ai: configured`. **9.1's live call is an owner action** |
| ~~31~~ | ~~AI assistant — tools + chat~~ | ~~🔴~~ | — shipped | — shipped | **shipped** | ~~9.2, 9.3, 9.4~~ | `fe1db05` · Manual agent loop, **suspended across an HTTP boundary** so §9.4's confirmation can be answered by a person in a later request — a pending call is a row, not an in-memory future. Tools dispatch to the same endpoint functions the web app calls (#12 stays closed). **"Write" and "admin-only" are separate axes**: `log_watch` writes and a viewer keeps it. SSE chat with a floating button on every page. Cancelling leaves nothing behind, asserted against the table |
| ~~32~~ | ~~Voice input~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~**9.5**~~ | On-device Web Speech API — nothing is uploaded, and `microphone=(self)` was already live so no hosting change. **Dictation fills the input and never sends**: the engine mishears, and reading it back is both the safety net and the only way "correct transcription" is checkable. TS declares none of this API, so the used surface is declared in-repo. Interim results are **rebuilt, not appended** — the bug that yields "where where is where is Heat". **9.5's acceptance needs a person speaking — owner action** |
| 33 | **Email — accounts + OAuth** | 🔴 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | planned | **10.1, 10.2, 10.3, 10.4** |
| 34 | **Email — parsers + scanning** | 🔴 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | **10.5, 10.6, 10.7, 10.8** |
| ~~35~~ | ~~Movie night~~ | ~~🔴~~ | — shipped | — shipped | **shipped** | ~~**8.3, 8.4**~~ | Postgres `LISTEN`/`NOTIFY` + SSE (#113), **not** Supabase Realtime — no new service, no credential, no hosting step. One dedicated listening connection, opened on the first watcher and closed with the last, per #113's pool warning. **A match is derived, never stored** (gotcha 1b); the rule is "everyone here", not "two". The other person's votes are invisible. **8.4's notification arriving on a device is an owner action** |
| ~~36~~ | ~~Command palette + shortcuts~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~6.3, 6.4~~ | `1425f91` · Ctrl/Cmd+K palette (pages, admin actions, films via Batch 5's search, recent items) + centralized shortcuts hook; `.` and the AI-conversations index dropped — Batch 31 isn't built |
| ~~37~~ | ~~On-this-day + rewatch~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~**11.6**~~ | `50a4828` · caller-scoped anniversary memories and high-rated, not-recently-watched suggestions; date-controlled Postgres test proves a watch from a year ago appears on the dashboard |
| ~~38~~ | ~~E2E suite~~ | ~~🟢~~ | — built | — built | **built** | ~~13.10~~ | #94 · Playwright on Chromium, Firefox and WebKit against the production bundle with every outside service faked; five cron jobs run as Railway runs them (`DECISIONS.md` #285) |

## Group Z — what the end-to-end suite found, planned 19 Oct

**Planned 2026-10-19 from Batch 38's findings** (`DECISIONS.md` #285, items c, d, e and g), at
Craig's word to batch up the follow-ups. **Criteria authored 2026-10-19**, so `DECISIONS.md` #54
does not apply. One batch, because the four are small and each is proved by a case that already
exists or is a few lines from one. Model tier is Group V's top tier. Lands as Group Y did: a
`feat/` branch, a pull request, CI green **including the `e2e` job**, a merge commit, production
`/api/v1/health` reporting the merge SHA with `db: ok`. **Re-verify each fault in the code first**
(`batch-start.md` step 3): the four were measured on 19 Oct and the code may have moved.

| Batch | Covers | Size | Gate | Claude Code | Codex |
|---|---|---|---|---|---|
| ~~Z1~~ | The four faults below — **built 20 Oct (#287)** | 🟡 | Craig's go | top tier · high | top tier · High |

### Z1 — Four faults the end-to-end suite found
**Built 20 Oct at Craig's go (`DECISIONS.md` #287).** Re-verified first at `1faf99a`: all four
still present. **Amended, none dropped:** criterion 2 widened to a series add and a title-only
add (same fault, same call); criterion 3's grep found three more sentences with a stored code
(the Trash, the price-alert push, the offline banner), all fixed, and listed the admin-only,
CLI and CSV strings left as they are. **Each fix shown to bite by reverting it:** the vote race
test failed on night 2 at natural timing; three server format tests failed; six vitest cases
and the offline e2e case (on the TMDB-id add) failed; two vitest cases and the chat e2e case
failed. The chat card case runs in the real order again; the TMDB-id variant runs inside the
existing replay case, so no new skip.

**Why top tier.** Two are races (a client state race, a server write skew) where a fix that
passes the obvious case can leave the real one open, and one changes how the offline queue
settles a write.

**Found 19 Oct, all measured, none yet fixed:**

1. **The Yes/No card can vanish (client race).** `AiChatPage` copies the conversation record's
   `pendingToolCalls` over its own state whenever that record arrives. On a first message in a
   brand-new conversation the record is fetched as the conversation opens, and a slow answer can
   land *after* the stream has raised the card, writing an empty list over it. The write stays
   pending on the server; reopening the conversation shows the card. Seen on Firefox and WebKit
   on CI runners, not on a fast machine.
2. **A disc added by TMDB id, whose answer is lost, never settles (offline queue).** `reconcile`
   in `lib/sync.ts` returns "unknown" when the queued create has no `movieId`, which is every add
   made from a TMDB search for a film the catalogue has not seen. The banner says "we'll check
   rather than send it twice" and cannot; only Discard clears it. `GET /collection/duplicate-check`
   already answers "which copies of this TMDB id exist", so the read-back needs no new endpoint.
3. **The barcode screen shows a raw code.** "already owned on blu_ray" (`services/barcode.py`
   builds the evidence from the stored format codes). Every other screen says "Blu-ray".
4. **Two likes cast together can both miss the match (server write skew).** `detect_match` reads
   the votes without locking, so two transactions that commit within milliseconds each see only
   their own like and neither announces. Unproven in production (a real pair is seconds apart);
   seen once under CI timing.

**Acceptance:**
- **1.** A conversation record that arrives while a reply is streaming, or after the stream has
  raised a card, never removes that card; a record read on opening a conversation still restores
  a card left pending. A browser case sends the **first message in a new conversation** with the
  record held back until after the card appears, and the card stays (the `chat.spec.ts` card case
  today opens the conversation first to avoid this; it returns to the real order). Fails on the
  old code.
- **2.** A queued create with a TMDB id and no film id is read back through the duplicate check:
  landed settles it, absent returns it to `queued`, unreachable leaves it unconfirmed. Vitest
  cases for each, and the `offline.spec.ts` replay case gains a variant that adds by TMDB id.
  Fails on the old code.
- **3.** The barcode screen names formats as the rest of the app does ("Blu-ray", "4K UHD",
  "DVD"), through the one formatter the Archive uses; a test fails if the evidence string holds a
  stored code. Check the other places a stored code reaches a sentence (`grep` for
  `formats.join` in `apps/api/src` and the web) and fix or list what is found.
- **4.** Recording a vote takes a lock on the night (`SELECT … FOR UPDATE` on the session row)
  so detection sees the other person's committed like. A Postgres test casts both likes from two
  sessions at once, many times, and every run ends with exactly one match and one announcement;
  it fails on the old code. No migration.
- **Guards.** Each fix is shown to bite by reverting it. The `e2e` job is green on all three
  browsers with no new skip.
- Tests. Gate green. `STATUS.md`, this entry and `DECISIONS.md` updated.

**Not in Z1, and why.** The two WebKit skips (the lost-answer replay, the live match on an open
page) wait on Craig's two-phone check (`OWNER-ACTIONS.md` 16b): if Safari does not show the live
match, that becomes a batch of its own (a polling fallback). Stopping the existing double CI run
(push and pull request on every commit) is a separate small workflow change, Craig's call.

---

## Group AA — the 20 and 21 Oct snags, planned 21 Oct

**Planned 2026-10-21 from Craig's 23 points of 20 Oct and two more on 21 Oct**, reconciled
against the code in `docs/owner-snags-2026-10-20.md`, where his answers are recorded; the values
and deals picks are `DECISIONS.md` #289 and #290. **Criteria authored 2026-10-21:** the bullets
under each batch below are its acceptance criteria, so `DECISIONS.md` #54 does not apply.
**Re-verify each point in the code first** (`batch-start.md` step 3): the code was read at
`0dfec18` on 20 Oct. **Sitting 1 began at Craig's go; AA10a's first live eBay pass was read
back on 22 Oct (`OWNER-ACTIONS.md` 36). AA10b's code shipped 23 Oct; its live re-price remains
the owner checkpoint. Sitting 2 was authorised while that readback remains open: AA1 and AA8
shipped 23 Oct, and AA2 shipped 25 Oct.** The later sittings wait for Craig's go.

**How each lands** (Group Y's way, on Craig's Mac or from Codex): its own `feat/` branch from
`main`, a pull request, CI green **including the `e2e` job**, a merge commit, production
`/api/v1/health` on the merge SHA with `/health/ready` `db: ok`. One batch per branch and per
pull request, in the order below; never two at once (`group-start.md`).

**Models, named.** Top tier is **Opus 5** in Claude Code and **GPT-5.6 Sol** in Codex; mid tier
is **Sonnet 5** and **GPT-5.6 Terra** (Group U's and Batch 21's rows in "Batch groups"). A
sitting runs at the strictest setting any of its batches asks for, so one model and effort
cover the whole sitting.

| Sitting | Batches, in order | Claude Code | Codex | Checkpoints (the run stops for Craig) |
|---|---|---|---|---|
| 1 | AA10a the sold-price store → AA10b deals and values on the used figure | Opus 5 · `xhigh` | GPT-5.6 Sol · Extra High | AA10a's first live pass read back after deploy; Home's total before and after AA10b's re-price, reported |
| 2 | AA1 quick fixes → AA8 the artwork → AA2 Home rows | Sonnet 5 · `high` | GPT-5.6 Terra · High | AA1: the top bar's before-and-after screenshot, before its merge. AA2: the completion-set refresh that fills headshots is a live step at Craig's word, after the merge |
| 3 | AA4 movie night → AA5 a night's film details → AA6 feeling lucky | Opus 5 · `high` | GPT-5.6 Sol · High | None |
| 4 | AA7 profile pictures → AA11 lend and borrow | Opus 5 · `high` | GPT-5.6 Sol · High | AA11: the four-state story shown to Craig and signed off before building |
| 5 | AA3 the collection section → AA9 the assistant page (both reviews) | Opus 5 · `high` | GPT-5.6 Sol · High | Each stops after its report for Craig's picks; their builds are planned from them |
| 6 | AA10c settle the stand-in, **from 25 Nov** | Opus 5 · `high` | GPT-5.6 Sol · High | Needs about four weeks of AA10a's recorded sales |

*Why that grouping* (Craig's yes, 21 Oct). AA10a first so the 90 days of sales start filling
(about half the collection reaches three sales by late January); AA10b joins it because it
shares the valuation and scan code and needs AA10a's figure, which also lands the deals fix a
sitting sooner (cost: AA10b at Extra High). AA1 and AA8 both change the top bar and AA8 and AA2
both Home's header, so they run together, AA8 between. The two reviews share a method and stop
for picks. AA7 and AA11 each add a migration and touch no other sitting's files. Grouping is not
merging: each batch keeps its own branch and pull request, so any one can be reverted.

**Each batch on its own:**

| Batch | Covers (snag numbers) | Size | Claude Code | Codex |
|---|---|---|---|---|
| ~~AA1~~ | ~~2, 3, 6, 8, 10, 14, 15: start page, top bar, Top rated, best-reviewed title, film tabs, our disc first~~ — **shipped 23 Oct `4cc207d`** ([PR #103](https://github.com/CraigR973/mcu-app/pull/103)); each iPhone re-add remains an owner action | 🟢 | Sonnet 5 · `high` | GPT-5.6 Terra · High |
| ~~AA2~~ | ~~5, 7, 11, 12, 13: attention links, activity moved, picture and sound, headshots, missing films~~ — **complete 25 Oct `836df95`** ([PR #105](https://github.com/CraigR973/mcu-app/pull/105)); [PR #107](https://github.com/CraigR973/mcu-app/pull/107) (`98a04ed`) fixes unchanged-set metadata. Craig authorised the follow-up live refresh: 0 creates, 39 metadata updates, 1 unchanged, 0 removals and 0 errors; read-only proof found portraits on all 40 sets | 🟢 | Sonnet 5 · `high` | GPT-5.6 Terra · High |
| AA3 | 9: the collection section, reviewed then rebuilt | 🟡 | Opus 5 · `high` | GPT-5.6 Sol · High |
| ~~AA4~~ | ~~16, 17, 18, 20: suggest first, two lists, a planned time, add from a film~~ — **shipped 25 Oct `6e9629d`** ([PR #108](https://github.com/CraigR973/mcu-app/pull/108)) | 🟡 | Opus 5 · `high` | GPT-5.6 Sol · High |
| ~~AA5~~ | ~~19: each film’s details on a night, IMDb’s score~~ — **shipped 25 Oct `8f47f39`** ([PR #109](https://github.com/CraigR973/mcu-app/pull/109)) | 🟡 | Opus 5 · `high` | GPT-5.6 Sol · High |
| ~~AA6~~ | ~~21: feeling lucky, alone on Home and in a night~~ — **shipped 25 Oct `54dbc07`** ([PR #110](https://github.com/CraigR973/mcu-app/pull/110)) | 🟡 | Sonnet 5 · `high` | GPT-5.6 Terra · High |
| ~~AA7~~ | ~~4: profile pictures~~ — **shipped 26 Oct `e6e5e16`** ([PR #111](https://github.com/CraigR973/mcu-app/pull/111)) | 🟡 | Opus 5 · `high` | GPT-5.6 Sol · High |
| ~~AA8~~ | ~~1: the artwork in the app~~ — **shipped 23 Oct `6b039bf`** ([PR #104](https://github.com/CraigR973/mcu-app/pull/104)) | 🟢 | Sonnet 5 · `high` | GPT-5.6 Terra · High |
| AA9 | 22: the assistant page, reviewed then rebuilt | 🟡 | Opus 5 · `high` | GPT-5.6 Sol · High |
| ~~AA10~~ | 23, 24: what a disc really sells for, a design note — **written 21 Oct (`8a33c19`)** | 🔴 | — done | — done |
| ~~AA10a~~ | ~~23, 24: record used listings and their sales, value on sales~~ — **shipped 22 Oct `eb315c2`** ([PR #100](https://github.com/CraigR973/mcu-app/pull/100)); Craig's first live pass read back: 598 searches, 6,179 active listings, 0 sold yet, 1,399 pairs still due under the daily cap | 🔴 | Opus 5 · `xhigh` | GPT-5.6 Sol · Extra High |
| AA10b | 23, 24: deals and values on the used stand-in figure — **code live 23 Oct `deccd87`** ([PR #101](https://github.com/CraigR973/mcu-app/pull/101)); Craig started the one-time re-price 23 Oct: 748 pairs checked, 0 failed, 719 due. Final Home after total remains the checkpoint after the 1–2 Nov scheduled runs | 🟡 | Opus 5 · `high` | GPT-5.6 Sol · High |
| AA10c | 23: the stand-in settled from recorded sales | 🟢 | Opus 5 · `high` | GPT-5.6 Sol · High |
| ~~AA11~~ | ~~25: lend and borrow as it happens — asked for, out, back, shelved~~ — **shipped 26 Oct `b1075ec`; closed out 27 Oct; navigation repairs `30f3607`, `0b4a416`** ([PR #112](https://github.com/CraigR973/mcu-app/pull/112), [PR #114](https://github.com/CraigR973/mcu-app/pull/114)) | **shipped** | ~~Opus 5 · `high`~~ | ~~GPT-5.6 Sol · High~~ |

*Why those efforts.* AA10a adds a table of eBay data under a licence risk (#254, #289), a job
and about 600 calls a day: an irreversible-feeling store and a public provider, so `xhigh`.
AA4, AA5, AA7 and AA11 write migrations; AA10b and AA10c change every stored value, which is
money and shows on Home. AA1, AA2, AA6 and AA8 are interface work over data the app holds.

### AA1 — Quick fixes 🟢
- **3.** The manifest's `start_url` is `/`. `OWNER-ACTIONS.md` gains: each iPhone removes and
  re-adds the app.
- **2.** Every screen, dark theme (answer 7). Likely cause: the bar is a lighter brown-grey
  (`--popover`, 11% lightness) over a near-black page (6%), with the iOS clock on it. The bar takes
  the page's own near-black (or darker) with a crisp bottom rule, confirmed by a before-and-after
  screenshot at 375 px sent to Craig before merging; a test pins the bar's surface token.
- **6.** Top rated leaves Home. Worth a rewatch stays (it uses the viewer's own ratings, and hides
  for Mark as now).
- **8.** Home's collection row gains a "Browse the archive" link (answer 2).
- **10.** The row is titled for the disc ("Best discs", or as Craig words it) and its caption
  says it scores picture, sound and extras, not the film.
- **14.** The film page's tabs never scroll up and down; at 375 px all four show whole with no
  sideways scroll (shorter labels or a fitted grid); a test at 375 px.
- **15.** Where to watch opens with "On the shelf": each owned copy's format, location and loan,
  then Streaming. A download names where it is.
- Tests. Gate green. Browser check at 375 px, both themes.

### ~~AA2 — Home rows~~ 🟢 **complete 25 Oct (`836df95`, [PR #105](https://github.com/CraigR973/mcu-app/pull/105)); portrait metadata fix (`98a04ed`, [PR #107](https://github.com/CraigR973/mcu-app/pull/107)) and Craig's owner-authorised refresh populated all 40 stored TMDB portraits**
- **5.** Each Needs attention line opens the screen that fixes it (Identify, Disc specs, Retailers,
  Settings' devices, the assistant settings, Admin's jobs); a line with nothing in the app to do
  (server set-up, database size) says what to do instead. One map from check key to place, with a
  test that every key has an entry.
- **7.** Recent activity moves to the You page (answer 6); Home keeps no copy of it.
- **11.** Each best-reviewed card says what the disc is strongest at, from the stored sub-scores
  (picture from Video 4K or 2K, sound from Audio, extras), with the scores on tap.
- **12.** Completion cards show the person's TMDB headshot, stored by the set refresh, initials
  when TMDB has none. **Craig authorised the live refresh on 25 Oct:** 39 metadata updates,
  1 unchanged set, 0 creates/removals/errors; read-only production evidence confirms portraits
  on all 40 sets.
- **13.** A set's page lists its missing films on their own, each with Add to wanted (or
  "Wanted" when it is), each opening its TMDB film page; the bulk button stays. Mark sees it too
  if Wanted is shared (checked when the batch starts).
- Tests. Gate green. Browser check at 375 px.

### AA3 — The collection section 🟡
A UI/UX review of Home's collection row as its own report (`docs/reviews/`), with mock-ups, sent
to Craig; the build is planned from his picks. No code before his picks.

**27 Oct — picks received, build planned (#299):** Compact summary; count/label/value
corrections approved; **keep watched and identified with clearer definitions**.
See `docs/reviews/aa3-collection-review-2026-10-27.md` and
`docs/reviews/aa3-build-plan-2026-10-27.md`, with the selected layout. The plan proposes two
additive stats-response fields (physical copies and physical/download overlap); Craig
approved the extension and build before implementation. Implementation is under verification;
AA3 remains open.
AA9 has not started; sitting 6 excluded.

### ~~AA4 — Movie night: suggest first, two lists, a planned time~~ 🟡 **shipped 25 Oct (`6e9629d`, [PR #108](https://github.com/CraigR973/mcu-app/pull/108))**
- **16, 17.** The night opens with Suggest a film; below it "Suggested" (people's picks, who and
  when), then "Stuck for ideas? A random shortlist" (the Archive's picks).
- **18.** A night takes an optional planned date and time (one nullable `planned_start_utc`,
  shown in the person's time, in the list of nights and in the invite push). Migration granted to
  `mcu_readonly` and `mcu_backup` as `CLAUDE.md` says.
- **20.** A film page (owned or a TMDB page) offers "Add to movie night" when a night is open,
  choosing the night when more than one is.
- Tests (the e2e movie-night case updated, not loosened). Gate green.

### ~~AA5 — The film’s details on a night~~ 🟡 **shipped 25 Oct (`8f47f39`, [PR #109](https://github.com/CraigR973/mcu-app/pull/109))**
- **19.** Each film on a night shows, for each person: when they last watched it and their own
  rating (the app's, which already holds their Letterboxd ratings from the diary sync; "not
  rated" otherwise); where to watch it (shelf location first, else streaming); runtime; IMDb's
  score; a Letterboxd link. Letterboxd's average is not shown: it has no public API.
- **IMDb's score** comes from IMDb's daily `title.ratings` file, matched on the stored IMDb id,
  inside an existing nightly job (no new Railway service, so no hosting change). New columns
  granted as above.
- Tests. Gate green.

### ~~AA6 — Feeling lucky~~ 🟡 **shipped 25 Oct (`54dbc07`, [PR #110](https://github.com/CraigR973/mcu-app/pull/110))**
- **21.** "Feeling lucky" deals one film at a time until someone takes one: on Home for the person
  alone (the Archive, optionally unwatched by them), and on a night, where taking it adds it to
  the night's suggestions. Skipped films are not dealt again in that run.
- Tests. Gate green.

**Result:** one-film draws on Home and a night, caller-scoped unwatched filtering,
per-run exclusions and vote-preserving suggestion promotion. All seven PR CI jobs green
(40229655987); production API/web report `54dbc07`, database ready, all integrations configured.
Craig approved the one-path route-inventory addition; equality and access assertions remain.
See `docs/reviews/aa6-verification-2026-10-25.md`. Sitting 3 is complete; stop before sitting 4.

### ~~AA7 — Profile pictures~~ 🟡 **shipped 26 Oct (`e6e5e16`, [PR #111](https://github.com/CraigR973/mcu-app/pull/111))**
- **4.** An uploaded photo (answer 3). A person's picture shows wherever their initial does now (top bar, You,
  movie night, activity), the initial when there is none. If uploaded: stored in Postgres as copy
  photos are, resized, size-capped. Migration granted as above.
- Tests. Gate green.

**AA7 close-out:** caller-owned private photo upload/replacement/removal, all avatar surfaces,
initial fallbacks, migration 068 and read-role/credential boundaries verified. PR CI
40299605767 passed all seven jobs. Production API and web serve `e6e5e16`, db ready and
all integrations configured. Real-phone selection remains unverified. AA11's four-state story was approved before its implementation. See `docs/reviews/aa7-verification-2026-10-25.md`.

### ~~AA8 — The artwork~~ 🟢 **shipped 23 Oct (`6b039bf`, [PR #104](https://github.com/CraigR973/mcu-app/pull/104))**
- **1.** The app-icon art (the original screen-print emblem, not built from stills) shows in the
  app: Home's header and the loading screen, at the size it shows on a phone's Home Screen
  (about 60 px). **Asked 21 Oct: the art in place of the vector marks too** — the top bar (28 px
  today, 36 px from now) and the sidebar (40 px); a phone-size comparison was sent to Craig, and
  he said yes, 21 Oct. The 16 px favicon and the notification badge stay vector, where the art is
  noise. `BrandMark`'s tier table and its test change with the pick.
- **The MARKS photo hero** (the compact five-image edition) is a full-width banner at the top of
  Home, and **is served only to a signed-in person**: the two heroes leave `public/brand/`, so
  they stop being fetchable by anyone. Never on sign-in or any public screen. Supersedes #140 with
  a new decision; the source-level test moves to the new boundary (photo art on Home and
  onboarding only, never public) at Craig's word, 21 Oct.
- Tests. Gate green. Browser check at 375 px and 1,280 px.

### AA9 — The assistant page 🟡
As AA3: a review report first, then a build planned from Craig's picks.

### ~~AA10 — What a disc really sells for: values and deals, a design note~~ 🔴 **written 21 Oct (`8a33c19`, `docs/reviews/values-and-deals-2026-10-21.md`)**
- **23, 24.** One note, not code, because both rest on the same missing number: eBay gives only
  asking prices, never sold ones (#16, #228). A value is a used asking median; a deal is 30%
  under an asking median, which is often just the going rate.
- **The proposal to test:** keep each used listing seen, by eBay item id, on a weekly pass; a
  listing that vanishes before its end date most likely sold. The value becomes the median of
  "probably sold" prices with postage over 90 days, falling back to the lower quartile of current
  used asks; a deal must beat that figure, not the asking median. Mark's rule (mean of the 3
  lowest in 3 months) and today's rule are computed beside it.
- **The note gives, on live data:** the three rules side by side for a sample of discs, checked
  against eBay's sold listings read by Craig or Mark on the website; last month's deals re-judged
  under each; the extra eBay calls (inside the daily budget or not); and the options with costs.
- The build is planned from Craig and Mark's pick.

**Picked 21 Oct: option 3, every recommendation (#289); the hand check dropped (#290).** Built as three batches:

### AA10a — The sold-price store 🔴
- A table of used listings seen (eBay item number, film, format, price, postage, condition code,
  first and last seen, sold or ended, sold count): **no title, no image** (#289). Rows older than
  90 days after they end are deleted. Migration granted to `mcu_readonly` and `mcu_backup`.
- A weekly pass records each tracked disc's used Buy It Now listings and checks each vanished one
  once by item number: sold ("out of stock" with a sold count) or ended unsold. **It runs inside
  an existing cron job** so no Railway service is added; if it cannot, adding one is a hosting
  change and stops for Craig. About 600 calls a day, inside the 5,000.
- A disc with 3 or more sales in 90 days is valued at their median, postage in, labelled "based
  on N sales"; Home says how many values rest on sales.
- Tests (sold, withdrawn, a relisted item, the 90-day window, the budget). Gate green. The first
  live pass is read back after deploy.

### AA10b — Deals and values on the used figure 🟡
**No hand check (#290).** The stand-in is the lower quartile of current used Buy It Now asks,
postage in, until AA10c settles it from recorded sales.
- Every deal, New included, is judged against the disc's figure (sales when AA10a has them, else
  the stand-in) and must be 10% or more under it. A deal card says what it was judged against.
- Values without 3 sales use the stand-in; the change lands at one re-price, with Home's total
  before and after reported to Craig.
- Tests (the note's own cases: Deep Red New at £15.49 is not a deal; Reservoir Dogs 4K at £3.99
  is). Gate green.

### AA10c — The stand-in settled from recorded sales 🟢
**From 25 Nov**, once AA10a has about four weeks of sales (#290). Replaces the hand check.
- For every disc with recorded sales, compare the lower-quartile stand-in and today's used
  median against the median of its sales; report both errors (median and spread) to Craig.
- Keep the closer one as the stand-in; if it is the median, switch and re-price at the next run,
  reporting Home's total before and after.
- Tests for the comparison. Gate green.

### AA11 — Lend and borrow as it happens ✅ **shipped — 26 Oct (`b1075ec`, [PR #112](https://github.com/CraigR973/mcu-app/pull/112))**
- **25.** A loan runs **asked for → out → back, not shelved → shelved**. Craig asks in the app
  for a film with a needed-by date (Mark gets a push; Craig's word, 21 Oct), or records taking it
  himself. Either person
  marks it back (left at Mark's, or collected). Mark gets a "to put back" list, and putting one
  back confirms or changes its shelf. Loans and the film page say which state a copy is in.
- The story is shown to Craig as a short flow first and signed off before building. Migration
  (state, needed-by, returned-by, shelved-at, all nullable) granted as above.
- Tests (the e2e loans case extended). Gate green.

**AA11 shipment proof:** story and one pinned PATCH path approved before their changes.
Ten local gate commands pass at the repair source; Chromium 38, Firefox 37 plus the documented
dictation skip, cron six. All seven repair PR and merge jobs pass (40414279164, 40479165450),
including WebKit 36 plus its two documented skips, Postgres 17 without skips, migration
reversal and deployment-image boot. API/web served exact merge `0b4a416`, db ready and
push/AI/eBay/TMDB/Brave configured. Read-only checks preserve all four old Out loans and
copy places with new metadata NULL; both read-role grants and withheld credentials pass.

Earlier CI stopped on WebKit sign-out navigation (40390928359), repaired separately in
PR #113, then Firefox offline initial navigation (40409200298), repaired in PR #114.
Both repairs wait for rendered lazy screens; non-worker login isolation matches the existing
suite. Every original outcome assertion, worker-enabled offline case and zero-retry setting
is retained. No extra skip or timeout change. See `docs/reviews/aa11-verification-2026-10-26.md`
for all failures and criterion evidence. Real-phone picture selection, request push receipt
and physical handovers remain owner observations. Sitting 4 is complete; do not start sitting 5.

---

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
| — | ~~10 · solo~~ | — shipped | — shipped | Large mechanical restructure of a 2,639-line doc |
| — | ~~**checkpoint: generate VAPID keys + set them in Railway**~~ **met 2026-09-09** → ~~11~~ | — shipped | — shipped | ~~Credential change, so it stops for the owner. Solo: push shares no files with 10 or 12, and everything that *consumes* it (20, 22, 37) is far downstream~~ · **shipped.** The checkpoint's second half — a Vercel variable — turned out not to be needed at all (#114) |
| ~~**C**~~ | ~~12~~ → ~~13~~ | — shipped | — shipped | ~~Same domain (sets/collections); 13 reuses 12's UI patterns~~ · **shipped** |
| ~~**D**~~ | ~~14~~ → ~~15~~ | — shipped | — shipped | ~~Both admin-facing read surfaces, same verification shape~~ · **shipped** |
| ~~**E**~~ | ~~16~~ → ~~17~~ | — shipped | — shipped | ~~Both TMDB-driven, same client, 17 reuses 16's patterns~~ · **shipped** |
| **F** | ~~18~~ → ~~19~~ → ~~**checkpoint: live scraper acceptance runs**~~ **met 2026-09-09** → ~~20~~ | **Opus 5 · max** | **GPT-5.6 Sol · Max** | Dependency chain, same files. 5.3's acceptance needs live retailer hits — owner performs those. **All three shipped; the checkpoint cleared 2026-09-09 (#111) and 20 shipped 2026-09-10.** Group F is complete |
| — | 21 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Hard 7-day wall-clock gate after Batch 20 |
| **G** | 22 → ~~23~~ | Opus 5 · high | GPT-5.6 Sol · High | Both consume the scraper framework from 19. **23 built 2026-09-10**; its §3.7 live run waits for the owner |
| **H** | 24 → ~~25~~ | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | ~~**Both blocked on the same two `vercel.json` fixes**~~ — **neither fix was needed.** `camera=(self)` has been live since Batch 2, and photos are served from the API origin that `connect-src` already allows. **25 shipped 2026-09-10**; ~~24 (barcode) still waits on eBay~~ — **24 is unblocked as of 2026-09-10** (`OWNER-ACTIONS.md` #5: eBay Browse needs no partner approval, `DECISIONS.md` #126). Its remaining gate is a person with a phone and a disc, not a credential |
| — | ~~26 · solo~~ | — dropped | — dropped | ~~Conditional on Batch 6 proving insufficient~~ — **Batch 6 proved sufficient; dropped** (`DECISIONS.md` #109) |
| — | ~~27 · solo~~ | — shipped | — shipped | ~~The app's only public surface; needs its own security review~~ · **shipped; reviewed, four defects found and fixed.** (It is in fact the *second* public surface; Batch 17's `.ics` feed came first) |
| **I** | ~~**checkpoint: eBay production API application**~~ **cleared 2026-09-10** → 28 → 29 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | 29 consumes 28. **The checkpoint's premise was false** — Browse needs no partner approval, only a self-service keyset (`DECISIONS.md` #126). Nothing gates the group |
| ~~**J**~~ | ~~30~~ → ~~31~~ | — shipped | — shipped | ~~Strong dependency, same files; caps must exist before tools~~ · **both shipped 2026-09-10.** Group J is complete |
| — | ~~32 · solo~~ | — shipped | — shipped | ~~Small and independent~~ · **shipped 2026-09-10** |
| **K** | **checkpoint: Google + Microsoft OAuth app registration** → 33 → 34 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | 34 consumes 33; credential setup gates the group |
| — | ~~35 · solo~~ | — shipped | — shipped | ~~🔴, needs Supabase Realtime — net new integration~~ · **shipped 2026-09-10 on `LISTEN`/`NOTIFY` instead (#113); no integration was needed** |
| — | 36 · solo | Sonnet 5 · high | GPT-5.6 Terra · High | Already two phases in one batch |
| — | 37 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Table exists since Batch 6; inert until it has ~a year of history |
| — | 38 · solo | Sonnet 5 · high | GPT-5.6 Terra · High | Formalises work written across earlier batches |
| **S** | ~~S1~~ → ~~S2~~ → ~~S3~~ → ~~S4~~ → **~~S8~~ → ~~S5~~** → ~~S6~~ → ~~S7~~ | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | **Complete — all eight shipped 2026-09-15.** The 2026-09-14 owner snags. Ordered by dependency: S4 needs S3's navigation shape, S6 needs somewhere to put the merged screen, S5 reuses S8's matcher, S7 needs S8's watch history. **No blocking checkpoint** — the two owner actions (S8's live import, S5's first live fetch) sit *inside* their batches and stop there, so the group runs end to end. `xhigh` derived from S8 and S7 |
| — | 39 · solo | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | The go-live collection refresh (`DECISIONS.md` #192). Solo: it touches the import path alone, and its live run waits on a spreadsheet that does not exist yet. 🟡 by size, `xhigh` by blast radius — 1,857 live rows, and two failure modes that announce nothing |
| — | 40 · solo | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | Unblocks 1i step 2 and therefore 39's live run (`DECISIONS.md` #197). Solo: one function in the diary importer, and it must land before any identification run. 🟢 by size, `xhigh` by what it re-enables — ~396 live `movies` rows rewritten, 582 watches behind them |
| — | 41 · solo | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | The refresh's second silent failure mode, found by running 39's dry run for real (`DECISIONS.md` #198). Solo, and it must land before any `--replace-items`. 🟡 by size, `xhigh` by blast radius — 401 films and 587 watch rows were one command away from coming loose |
| — | 42 · solo | **Opus 5 · high** | **GPT-5.6 Sol · High** | Precision fix to 41's guard (`DECISIONS.md` #199). Solo and small. 🟢 — but it protects the one thing standing in front of the 1,857-row replacement, and a guard that cries wolf is worse than none |
| **T** | ~~T1~~ → ~~jobs fix~~ → ~~**checkpoint: go**~~ **given 2026-09-23** → ~~T2~~ → ~~T3~~ → ~~T4~~ → ~~T5~~ → ~~T6~~ → ~~**checkpoint: search API account**~~ → ~~T7~~ → ~~T9~~ → ~~T10~~ → ~~T8a~~ → ~~**checkpoint: eBay OAuth set-up + encryption key**~~ **passed 3 Oct** → ~~T8b~~ (`2995b26`, 4 Oct) | **Opus 5 · max** | **GPT-5.6 Sol · Max** | The 2026-09-23 owner snags. **Approved 2026-09-23**; T1 (a fix, `aa112bd`), T2–T7 and **T9 (`4d16723`, 2026-09-25)** shipped. **Craig split T8 on 2026-09-26 and added T10 (#216)**, and said go the same day. **T10 (`db75229`) and T8a (`e2142b7`) shipped on 2026-09-26**; the eBay checkpoint passed on 3 Oct, and **T8b (`2995b26`) shipped on 2026-10-04**, after V9 (#243). Ordered by dependency: T4 needs T2's search and T3's top bar; T6 and T8 share the eBay client. `max` is derived from T8b |
| **U** | ~~U1~~ → ~~U2~~ → ~~U3~~ → ~~U4~~ → ~~22b~~ → ~~20b~~ (first half `548160f`, 1 Oct; second half `abc17d6`, 2 Oct, read back 3 Oct) → 22c (parked 4 Oct with `OWNER-ACTIONS.md` 28, #247) → 21 (go given 28 Sep; from 2 Oct at the earliest) → ~~T8b~~ (`2995b26`, 4 Oct) → 38 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | **Proposed 2026-09-26, regrouped at Craig's word the same day. He said go on U1 → U2 the same day, U2's column included; U3 onwards wait on their gates. U1 (`cb1111f`) and U2 (`52fcced`) shipped 2026-09-26, and U3 (`e116ef2`) the same evening at his three picks. U4 (`3974733`) shipped and was applied on 28 Sep. 22b (`eb51568`), added at Craig's word on 28 Sep, shipped on 30 Sep.** Everything left after Group T, in "What is left — Group U, planned 26 Sep" above. U1 and U2 share the Blu-ray.com pages; U3 carries three small calls, the brand assets included (a merge Craig chose); U4 and T8b can share one Railway apply. `xhigh` is derived from U1; T8b keeps its own `max` |
| **V · 1** | ~~V1~~ → ~~V3~~ → ~~V4~~ → ~~V5~~ | top tier · high | top tier · High | **Sitting 1 of Group V, written into the plan 2026-09-30 at Craig's word (#229); go given for an overnight run, a pull request per batch (#230).** The 30 Sep snags, in "Group V — the 30 Sep snags, planned 30 Sep" above; V2 is merged into V1 (Craig's choice). No checkpoint; the two-phone check for V3 is Craig's. Same verification throughout, a browser check at 375 px; V1 carries the top-bar fix and the back arrows because they change the same file. `high` and the top tier are derived from V4; V1, V3 and V5 alone need only the mid tier. Model tiers are defined at the head of Group V |
| **V · 2** | ~~V6~~ → ~~checkpoint: Craig taps "Try bid prices" and picks~~ (neither, 1 Oct) → ~~V7~~ (shelved, #237) → ~~V8~~ (`37e7c0a`, 2 Oct) | top tier · xhigh | top tier · Extra High | **Sitting 2 of Group V. V6 shipped 1 Oct in the overnight run (`153d45b`, #230); Craig ran it on 1 Oct and picked neither: V7 is shelved (#237). V8 shipped on 2 Oct on asking prices (`37e7c0a`, #239); the sitting is done.** Same eBay pricing code throughout (`src/ebay/estimate.py`, `services/valuation.py`, `services/ebay_watch/refs.py`), and each needs the one before: V7 builds on V6's report and V8 averages V7's figure. `xhigh` is derived from V6 and V7; V8 alone is `high` |
| — | V9 · solo | top tier · max | top tier · Max | **Sitting 3 of Group V, not started.** V10 merged into it (Craig's choice). Craig's steps come first inside it: allowing blu-ray.com and avforums.com, and Brave's limit only if the credit is out. `max` for a new scraping surface under #110 as widened by #228, as Group F's scrapers ran |
| **W** | ~~W1~~ (`9dd6805`) → ~~W2~~ (`0a87625`) → ~~W3~~ (`3ad71eb`) | top tier · high | top tier · High | **The 5 Oct snags, written into the plan 2026-10-05 with Craig's answers and go (#249).** One sitting, a pull request per batch, on Craig's Mac. Criteria and each batch's model and effort are in "Group W — the 5 Oct snags, planned 5 Oct" above. `high` and the top tier are derived from W3, whose migration and loan permissions need them; W1 and W2 alone need only the mid tier. The iPhone checks are Craig's |
| **X · 1** | ~~X1~~ (`7979e19`) → ~~X2~~ (`857ee8f`) → ~~X3~~ (`adcae0d`) — **done 12 Oct** | top tier · high | top tier · High | **The wave 1 review's first sitting, written into the plan 12 Oct at Craig's word (#253), and run as one group (#255).** Craig starts it himself; X1 must land before 21 Oct 16:35 UTC. MK47-04 is settled (#254), so X1's close-out does not stop for it. Same theme throughout: what reaches each person, and what tells Craig. Criteria in "Group X — the wave 1 review, planned 12 Oct" above |
| **X · 2** | ~~X7~~ (`aa6946d`) → ~~X8~~ (`e991281`) — **done 13 Oct** | top tier · high | top tier · High | Both change what a person sees when something fails (the assistant's errors, then every screen's) |
| **X · 3** | ~~checkpoint: Craig's yes on the value basis~~ (yes, 12 Oct, #256) → ~~X6~~ (`51c81ff`, 14 Oct) → ~~checkpoint: his credential steps~~ (storage decided, #257; done by a session at his word, 14 Oct, #268) → ~~X4~~ (`87a734b`, 14 Oct) → ~~X5~~ (`19c9aad`, 14 Oct) | top tier · xhigh | top tier · Extra High | Dated: X6 before the 1 Nov re-pricing, X5 by 31 Oct. **X4 joined it at Craig's word (#255):** its one tie is landing before X5 writes live data. X6 goes first, so a stall on X4's credentials cannot hold up its date. X5's live data steps stop for his word inside it. `xhigh` from X4's credentials and X5's backfill |
| **X · 4** | X9 → X10 | top tier · xhigh | top tier · Extra High | Same identification code; X10's title key builds on X9's state. `xhigh` from X9's live identification |
| **X · 5** | X11 → X12 | mid tier · high | mid tier · High | Interface work with clear criteria |
| **Z** | Z1 | top tier · high | top tier · High | **Planned 19 Oct from Batch 38's findings (#286); not started, at Craig's go.** Four small faults in one batch: a chat card race, a TMDB-id add whose lost answer never settles, a raw format code on the barcode screen, two simultaneous likes missing the match |
| **AA** | 1: ~~AA10a~~ (`eb315c2`) → AA10b (code `deccd87`; after-total open) · 2: ~~AA1~~ (`4cc207d`) → ~~AA8~~ (`6b039bf`) → ~~AA2~~ (`836df95`, portrait fix `98a04ed`) · 3: ~~AA4~~ (`6e9629d`) → ~~AA5~~ (`8f47f39`) → ~~AA6~~ (`54dbc07`) · 4: ~~AA7~~ (`e6e5e16`) → ~~AA11~~ (`b1075ec`; navigation repair `0b4a416`) · 5: AA3 → AA9 (reviews) · 6: AA10c from 25 Nov | **by sitting** (Group AA's table) | **Sitting 4 complete: AA7 `e6e5e16`, AA11 `b1075ec`; navigation repairs `30f3607` and `0b4a416`. Seven-job PR/merge CI and exact production SHA/readiness/data preservation verified. Real-phone observations remain open. Sitting 5 authorised 27 Oct: AA3 picks recorded, both watched/identified retained; two additive stats fields and build approved (#299), implementation under verification. AA9 not started. Do not start sitting 6.** AA10b's live re-price remains open: its before total was £16,867.11 and 719 pairs remained after Craig's first run. The 1–2 Nov scheduled runs continue it; read back the final Home total when none are due. AA2's owner-authorised follow-up refresh completed 25 Oct: 39 metadata updates, 1 unchanged, no creates, removals or errors; all 40 sets now have stored TMDB portraits. Run one batch at a time, `/group-start AA · <sitting>`: the sittings differ in model, so the group is not one setting |

**Group S is defined in "Owner snag batches — from the 2026-09-14 triage" above, not in the
April spec.** Its criteria were authored 2026-09-15; there is no `**Phase X.Y:` heading to
recover and `DECISIONS.md` #54 does not apply to it.

**Net: 37 batches → 24 sessions.** Eleven groups absorb 24 batches; 13 stay solo.
*Was 38 → 25 until Batch 26 was dropped on 2026-09-09 (`DECISIONS.md` #109).*

*Batch 11 had no row here at all until 2026-09-08, and the arithmetic hid it: the old
line claimed groups absorbed 25 batches when the rows only ever added to 24, so the
totals reached 38 while one batch was listed nowhere. Found when Batch 9 dropped the
wizard's notifications step and handed 11 an obligation (`DECISIONS.md` #50) — at which
point "when does 11 run?" had no answer.*

## Risk notes carried by owner decision (`DECISIONS.md` #16)

- **Batch 19/20/22 (scraping).** Six retailer scrapers to build and keep working. A layout change does not error — it selects the wrong node and persists a plausible wrong number, which then feeds price-drop alerts and aggregates. Build a per-scraper "last known good shape" assertion, not just a success/fail counter. Phase 5.3's acceptance criterion requires live-retailer runs; keep those out of CI and run them manually.
- **Batch 33 (email credentials).** Stores two people's live mailbox tokens. Must land **after** Batch 3's rate limiting and fail-closed config, never before. ~~Encryption at rest is net-new — app-starter ships no `cryptography` dependency.~~ **Corrected 2026-09-11:** `cryptography>=50.0.0` has been a direct dependency since Batch 11, which needs it for RFC 8291 Web Push. The library is not net-new; **key management is** — where the key lives, how it rotates, and what a key the app cannot read does to the rows behind it.
- **Batch 28 (eBay).** Sold-comp data is unobtainable; the UI must say "current asking prices" — and that is now *doubly* true, since eBay put sold listings behind a login wall in late August 2026, walling the scrape-it fallback as well as forbidding it. ~~Production API access is an application, not a given — start it early, it gates the batch.~~ **Superseded 2026-09-10 (`DECISIONS.md` #126): Browse works on a self-service keyset and gates nothing.** The real risk moved: a keyword search returns the 4K, the steelbook and a double-bill alongside the disc you asked for, so **the match filter is the batch, not the median** — measured at **149% overstatement** on live data, and `condition` cannot do the segmenting because it is a localised display string (#129).
- **Batch 24 (barcode).** Expect a low hit rate on unknown discs and wrong-edition matches. Confirmation UI is mandatory.

## Dropped — not scheduled

**9.6 Voice Output (TTS)**, per `DECISIONS.md` #16, and **12.3 / 12.4 Shelf QR**, per #109 —
Batch 6's `section`/`shelf` filter answers the retrieval question printed codes were for.

13.11 remains folded into every UI batch's definition of done rather than existing as a
phase — the work happens, the phase does not.

**Reinstating a dropped phase is a `DECISIONS.md` entry, not a quiet edit to this file.**
