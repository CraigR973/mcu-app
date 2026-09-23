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

### Batch 38 — E2E suite 🟢
**Covers Phase 13.10:**

> **Phase 13.10: Playwright E2E Tests** 🟢
> - Critical flows: login, import, search, add via scan, price alert, chat session, movie night match
> - Runs in CI
> - **Acceptance:** All flows pass on CI in Chromium + Firefox + WebKit

**The flow list names a flow that does not exist.** "Add via scan" is Batch 24, which is not
built. Either 38 runs after 24, or it ships six flows of seven and **says which one is
missing and why** — the one thing it must not do is quietly drop it and call the criterion
met.

**Every other named flow is built:** login (Batch 3), import (4), search (5), price alert
(20), chat session (31), movie night match (35).

**"Chromium + Firefox + WebKit" has one known casualty.** Firefox has no Web Speech API, so
Batch 32 hides the dictation button there rather than showing it dead. Any assertion that
touches dictation must skip on Firefox, not fail — and skipping must be visible, because a
silent skip is the failure mode `AGENTS.md` calls out for `test_derived_field_triggers.py`.

**Two people can sign in**, which is what the login flow and the movie-night match need:
Mark's PIN was set on 2026-09-09.

**Playwright is not installed today**, and CI does not run a browser — the web job builds the
bundle but never boots it. This batch is what changes that, so expect the CI wiring to be a
real part of the work rather than a `pnpm add`.

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

### T4 — Movie night 🔴
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

### T5 — Releases 🟡
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

### T6 — Collection value 🟡
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

### T7 — Blu-ray.com backfill 🔴
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

### T8 — Mark's eBay 🔴
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
| **T** | ~~T1~~ → ~~jobs fix~~ → ~~**checkpoint: go**~~ **given 2026-09-23** → ~~T2~~ → ~~T3~~ → T4 → T5 → T6 → **checkpoint: search API account** → T7 → **checkpoint: eBay OAuth set-up + encryption key** → T8 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | The 2026-09-23 owner snags. **Proposed, not approved** — only T1 shipped (as a fix, `aa112bd`). Ordered by dependency: T4 needs T2's search and T3's top bar; T6 and T8 share the eBay client. `max` is derived from T8 |

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
