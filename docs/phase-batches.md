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

### ~~Batch 19 — Scraper framework~~ 🔴 **shipped, acceptance deferred to the owner**
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

**All six built-in configurations report `verified: false`** and the UI says so. A selector
nobody has run against a live page is a guess, and the honest state of a guess is
unverified (#80).

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

## Post-launch — sequenced, not scheduled

Revised 2026-09-07 by `DECISIONS.md` #16: all of Part D's drops are reinstated except 9.6.

| # | Batch | Tier | Claude Code | Codex | Status | Phases |
|---|---|---|---|---|---|---|
| ~~10~~ | ~~Architecture doc split + §17 reconciliation~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~Part C deferred half~~ | `d94a6b8` · `ARCHITECTURE.md` split off with §16 replaced by a pointer to this ledger; all 50 §17 rows carry a reconciled status; `session-log.md.txt` retired |
| 11 | Notifications + push | 🟢 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 6.1, 6.2, 5.11 |
| ~~12~~ | ~~Box sets + smart collections~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~11.3, 11.4, 11.5~~ | `881f444` · 3 tables, 7 endpoints; a saved collection and the filter bar evaluate through one function; "Unwatched 4Ks from the 2010s" listed 40 real films in the browser |
| ~~13~~ | ~~Completion sets~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~11.1, **11.2**~~ | 40 sets built live from TMDB, 0 errors; Hitchcock 12 of 61 (TMDB returns 65 director credits, 4 are screen tests); **"add to wanted list" dropped — Batch 18 owns it** |
| ~~14~~ | ~~Stats + export~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~13.1, 13.2, 13.3, 13.4~~ | stats **344 ms median** against live Neon (criterion: <1s); CSV/JSON/HTML export all 1,857 discs; **2 of 5 charts have no data and say so** |
| ~~15~~ | ~~Trash, audit UI, lending~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~13.5, 13.6, 12.5~~ | permanent delete proved on live data — row gone, cascade fired, **audit trail outlived its subject**, 1,857 discs untouched; **"overdue triggers a push" not met — Batch 11 owns push** |
| ~~16~~ | ~~Watch providers + recommendations~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~7.1, 7.2~~ | live: *North by Northwest* shows HBO Max + 6 rent + 6 buy in GB; **20 recommendations, 7 already on the shelf**; **"wanted" dropped — Batch 18 owns it** |
| ~~17~~ | ~~Release calendar + iCal~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~7.3, 7.4 — secret-token `.ics` URL~~ | live ingestion put **32 rows** in `release_calendar`, re-run idempotent; feed serves unauthenticated with hashed rotating tokens. **A security review found and closed a URL content-injection hole.** Apple Calendar check is an owner action |
| ~~18~~ | ~~Wanted list + retailers~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~5.1, 5.2 (full scope)~~ | §3.5 and §3.16 built; **four debts from Batches 13, 15, 16 and 17 paid**; 6 default retailers seeded, **0 configured — selectors are Batch 19's** |
| ~~19~~ | ~~**Scraper framework**~~ | ~~🔴~~ | — shipped | — shipped | **shipped — acceptance deferred** | ~~**5.3, 5.4**~~ | framework, six built-ins, retry + auto-disable, SSRF-guarded fetcher, 33 fixture tests. **Both acceptance criteria need live retailer runs — the owner performs them** (Group F's checkpoint) |
| 20 | Price scraping + drop alerts | 🟡 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 5.5, 5.6, 5.8 |
| 21 | Price history charts | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | **5.7** — needs 7 real days of data after B20 |
| 22 | Deals feed | 🟡 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 5.9, 5.10 — RSS **and** scraped sources |
| 23 | Specs — scraper + display | 🟡 | Opus 5 · high | GPT-5.6 Sol · High | planned | 3.7, 3.8, 3.9 |
| 24 | Barcode — scan + lookup | 🟡 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | 3.3, **3.4** — confirmation UI mandatory |
| 25 | Photo uploads | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 3.10 — needs the `vercel.json` CSP fix |
| 26 | Shelf QR | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | 12.3, 12.4 |
| ~~27~~ | ~~Gift links~~ | ~~🟡~~ | — shipped | — shipped | **shipped** | ~~12.1, 12.2 — high-entropy slug, rate limiter, `noindex`~~ | `888dae7` · 128-bit slug (not §3.21's UUID PK, not §6.26's 32-bit example); four failure modes answer identically; public model carries **no** ownership, ids, slug or counts. Verified anonymously in a browser |
| 28 | **eBay integration** | 🔴 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | **4.1, 4.3** — active listings, not sold comps |
| 29 | Format upgrade + sale tracking | 🟢 | Sonnet 5 · high | GPT-5.6 Terra · High | planned | 4.2, 4.4 |
| 30 | AI assistant — client + caps | 🟡 | Opus 5 · high | GPT-5.6 Sol · High | planned | 9.1 + **9.7 together** |
| 31 | AI assistant — tools + chat | 🔴 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | planned | 9.2, 9.3, 9.4 |
| 32 | Voice input | 🟢 | Sonnet 5 · medium | GPT-5.6 Terra · Medium | planned | **9.5** |
| 33 | **Email — accounts + OAuth** | 🔴 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | planned | **10.1, 10.2, 10.3, 10.4** |
| 34 | **Email — parsers + scanning** | 🔴 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | **10.5, 10.6, 10.7, 10.8** |
| 35 | Movie night | 🔴 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | planned | **8.3, 8.4** — needs Supabase Realtime, net new |
| ~~36~~ | ~~Command palette + shortcuts~~ | ~~🟢~~ | — shipped | — shipped | **shipped** | ~~6.3, 6.4~~ | `1425f91` · Ctrl/Cmd+K palette (pages, admin actions, films via Batch 5's search, recent items) + centralized shortcuts hook; `.` and the AI-conversations index dropped — Batch 31 isn't built |
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
| — | ~~10 · solo~~ | — shipped | — shipped | Large mechanical restructure of a 2,639-line doc |
| — | **checkpoint: generate VAPID keys + set them in Railway** → 11 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | Credential change, so it stops for the owner. Solo: push shares no files with 10 or 12, and everything that *consumes* it (20, 22, 37) is far downstream |
| ~~**C**~~ | ~~12~~ → ~~13~~ | — shipped | — shipped | ~~Same domain (sets/collections); 13 reuses 12's UI patterns~~ · **shipped** |
| ~~**D**~~ | ~~14~~ → ~~15~~ | — shipped | — shipped | ~~Both admin-facing read surfaces, same verification shape~~ · **shipped** |
| ~~**E**~~ | ~~16~~ → ~~17~~ | — shipped | — shipped | ~~Both TMDB-driven, same client, 17 reuses 16's patterns~~ · **shipped** |
| **F** | ~~18~~ → ~~19~~ → **⛔ checkpoint: live scraper acceptance runs** → 20 | **Opus 5 · max** | **GPT-5.6 Sol · Max** | Dependency chain, same files. 5.3's acceptance needs live retailer hits — owner performs those. **18 and 19 shipped; stopped at the checkpoint** |
| — | 21 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Hard 7-day wall-clock gate after Batch 20 |
| **G** | 22 → 23 | Opus 5 · high | GPT-5.6 Sol · High | Both consume the scraper framework from 19 |
| **H** | 24 → 25 | **Opus 5 · xhigh** | **GPT-5.6 Sol · Extra High** | **Both blocked on the same two `vercel.json` fixes** — camera Permissions-Policy and CSP `connect-src` |
| — | 26 · solo | Sonnet 5 · medium | GPT-5.6 Terra · Medium | Conditional on Batch 6 proving insufficient |
| — | ~~27 · solo~~ | — shipped | — shipped | ~~The app's only public surface; needs its own security review~~ · **shipped; reviewed, four defects found and fixed.** (It is in fact the *second* public surface; Batch 17's `.ics` feed came first) |
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
