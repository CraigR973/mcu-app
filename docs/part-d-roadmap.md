# Part D — Roadmap critique, all 76 remaining phases

**Date:** 2026-09-07 · Against `docs/house-standard.md` and `docs/part-b-audit.md` · Read-only.

Eight clusters assessed in parallel, plus two re-runs after a premise correction (below).
Load-bearing claims were re-verified at source; three agent claims were found wrong and
are noted where they appear.

## The premise correction

The first pass was briefed that the collection is ~140 items, read from
`import_review.csv`. **That file is the TMDB low-confidence review queue, not the
collection.** The collection is **1,866 items** — the spreadsheet has 1,867 rows, the
roadmap says 1,866 in five places, and Phase 1.5's own acceptance criterion reads
*"parser produces 1,866 structured entries with no data loss."*

Two clusters were re-run at the correct figure. It reversed two verdicts (12.3, 12.4),
split one (13.4), revised two (3.6, 3.7), raised the priority of two (11.5, 11.1), and
surfaced the defect below.

---

# Headline

| Verdict | Count |
|---|---|
| **KEEP** | 26 |
| **RE-SCOPE** (kept, materially smaller or redirected) | 28 |
| **DEFER** | 5 |
| **DROP** | 17 |
| **New scope discovered** | 1 |

**17 phases drop outright. 28 more shrink.** The roadmap is not 76 phases of work; it is
roughly 54 phases of much smaller work, plus one item nobody owned.

---

# The defect the correction uncovered

**Phase 3.1b (new) — Structured location columns + backfill.**

Every link verified in code:

| Link | State |
|---|---|
| Roadmap §3.4 (`:164-180`) designs `location`, `section`, `shelf` on `collection_items` | specified |
| `spreadsheet/parser.py:63-93, 194-198` — `parse_location()` yields section (Front/Back/Lounge/Garage/Digital) and shelf | **implemented and unit-tested** |
| Migration `0003` + `models.py:56-81` | **all three columns absent** |
| `scripts/import_collection.py:324` | falls back to `notes = location_raw` — raw string survives, structure discarded |
| `0015_derived_field_triggers.py:31-60` — `search_vector` built from `movies.title/original_title/tagline/overview` | **`notes` not indexed**, so location is not searchable |
| `0012` — `shelf_qr_codes` has `section`/`shelf` + a unique constraint on the pair | **orphaned; nothing to join against** |
| §6.2 promises "show me everything on the Front 2nd shelf"; Phase 3.1's form bullet names a location field | **neither implementable** |

**1,866 discs across five physical locations, and the app cannot answer "where is this
disc?"** — the question a physical-media catalogue exists to answer.

The fix is small and blocked on nothing: add three columns, re-run the existing
`parse_location()` over the `location_raw` values already sitting in `notes`, expose
`section`/`shelf` as filter params. It also frees `notes`, which currently holds location
for imported rows and real notes for form-added rows with nothing distinguishing them.

**It is nobody's phase — which is why it survived five months.** It belongs immediately
after the deploy spine, and three committed phases (3.2, 3.6, 12.4) silently depend on it.

---

# Four patterns

### 1. Phases blocked on data or access, not difficulty

Re-tagging the model achieves nothing for these. All were tagged 🔴 Opus or treated as hard.

| Phase | Actual blocker |
|---|---|
| **3.4** Barcode → TMDB | TMDB has **no UPC field or endpoint**. Amazon PA-API requires qualifying *sales* to obtain and keep. eBay Browse is fuzzy text matching. The "cached mapping" starts empty with no public dataset to seed it |
| **4.1** eBay sold comps | Marketplace Insights API is limited-release, "not open to new users", granted to major partners. **No application path exists** |
| **7.3** Release calendar | TMDB does not track **UK physical-media street dates** — precisely what `release_calendar`'s own check constraint (`4k_uhd_release`, `blu_ray_release`) was built for |
| **11.1** Completion sets | TMDB collections cover franchises; there is **no API at all** for award winners or curated lists (BFI Top 100, Oscars). The roadmap's own §6.19 admits this, contradicting the phase's single-source framing |

### 2. Acceptance criteria that mandate the risk

Not the implementation — the tests themselves:

- **5.3:** *"Each built-in scraper runs against the **live** retailer"*
- **5.9:** *"Deals scraper run against live retailer pages... **≥ 20 rows from ≥ 3 retailers**"*
- **5.7:** *"After 7+ days of **real scheduled scrapes** (not back-dated fixtures)"* — a hard wall-clock gate; this phase cannot be verified in the week it is built

Passing Stage 5 means repeatedly hitting Amazon, HMV, Zavvi, Blu-ray.com, Arrow and CEX
with automated traffic during development and CI, against terms Amazon and HMV state
explicitly. And the failure mode is silent: a layout change doesn't error, it selects the
wrong node and persists a plausible wrong number — which then feeds false price-drop
pushes (5.6) and corrupted aggregates (5.8). The plan's "auto-disable after 3 fails" does
not catch that, because a wrong-but-present value is not a failure by that counter's logic.

**At 1,866 items this got worse, not better.** §5.10 queues the spec lookup "when a
collection_item is added (via spreadsheet import...)" — read literally, Phase 3.7 means
an hours-long crawl of Blu-ray.com for the entire existing catalogue. And the earlier
"just enter specs manually" fallback is weeks of data entry at this scale — a DROP wearing
a disguise. Hence 3.7's revised scope: **lazy, on-demand only, never a bulk backfill.**

### 3. Phases that collapse onto prior art

**Nine of thirteen** platform/resilience phases become "port the template and rebrand",
each verified by file:

`usePushSubscription.ts` (118 lines) · `pushNavigation.ts` · `sw.ts` (111 lines, with an
"add your app's GET endpoints here" extension point at line 56 **and** a documented iOS
update-deadlock fix) · `useOnlineStatus` · `OfflinePage` · the-coupon's 344-line E2E spec
with axe assertions baked in · its 164-line audit-log page · its 415-line `usePickEditor`
· `services/backup.py`.

**13.8 (Service Worker) and 13.9 (Offline Write Queue) were the two 🔴 Opus phases expected
to be the hardest architectural work in the roadmap. Both invert.** 13.8 becomes
configuration. 13.9 becomes "adapt a documented pattern to more entity types" — the hard
design questions (single-slot vs log, persisted vs in-memory, reconcile-by-read rather than
blind-retry on ambiguous failure) are already answered and written down.

### 4. Features from a different product

- **8.4 Movie Night Swipe & Match** (🔴 Opus) — a protocol for asynchronous matching between strangers not looking at the same screen, for two people on one sofa. `grep` confirms **zero** Supabase Realtime wiring in any repo, so "real-time sync" is a from-scratch integration. 8.3 falls with it.
- **9.6 Voice Output (TTS)** — garmin-coach needed **eight** decisions to land this reliably: on-device → hosted OpenAI → self-hosted Piper for cost → `medium` timed out on shared CPU → dropped to `low` → a CSP `media-src` gap silently ate two debugging cycles → `low` sounded robotic, reverted with tripled timeout → background pre-generation to hide a ~30s wait → voice re-picked after a listening test. That buys real value for a spoken health brief. It buys nothing for *"do we own Oppenheimer on 4K?"*
- **6.3 / 6.4 Command palette, keyboard shortcuts** — a two-person app used mostly on a phone. **Zero** of the four sibling repos has a global `metaKey` handler. `SearchBar.tsx` (161 lines) over a `websearch_to_tsquery` index already meets the need the collection's size creates.

---

# Verdicts — all 76 phases

### Stage 3 — Collection management
| Phase | Verdict | Note |
|---|---|---|
| **3.1b** | **ADD (new)** | Structured location columns + backfill. Sequence first |
| 3.2 Edit & Delete | KEEP | Port mcu_app's own `soft_delete()` BEFORE DELETE trigger forward — better than app-starter's column-only pattern |
| 3.3 Barcode Scanner UI | RE-SCOPE | Blocked in prod by `app-starter/vercel.json:27` `Permissions-Policy: camera=()` — fix before shipping |
| 3.4 Barcode → TMDB | RE-SCOPE | Drop the eBay/Amazon/TMDB chain; build a local `barcode_cache(upc, movie_id)` populated on first manual resolve |
| 3.5 Duplicate Detection | KEEP | Server logic already shipped in 3.1; this is UI |
| 3.6 Storage Location | RE-SCOPE | **Drop the suggestion algorithm** — its own §6.4 spec is self-contradictory (format vs auteur vs genre; a Kubrick 4K satisfies two incompatible shelves). Keep as filtering on 3.1b |
| 3.7 Blu-ray.com Scraper | RE-SCOPE | Lazy/on-demand only. Never bulk-queued against 1,866 items |
| 3.8 / 3.9 Spec display, filtering | KEEP | Columns already exist; Phase 2.3 was already built and accepted at 1,866 |
| 3.10 Photo Uploads | KEEP | Needs a Supabase Storage bucket **and** a CSP `connect-src` fix in `vercel.json:22` |
| 3.11 Condition Tracking | KEEP | Rides the audit-log infrastructure |

### Stage 4 — Upgrades & eBay
| Phase | Verdict |
|---|---|
| 4.1 eBay API | **DROP** — no application path exists |
| 4.2 Format Upgrade Flow | KEEP, merged with 4.4 — `is_for_sale`/`asking_price`/`listing_url`/`listed_at` already exist and are eBay-agnostic |
| 4.3 eBay Listing Creation | **DROP** — OAuth lifecycle + mandatory account-deletion webhook + business policies, kept alive indefinitely, for a few listings a year |
| 4.4 Listing Status | KEEP, merged into 4.2 — needs one `sold_at` column |

### Stage 5 — Wanted list, prices & deals
| Phase | Verdict |
|---|---|
| 5.1 Wanted List CRUD | KEEP — zero external dependency; note `wanted_list` has no `currency` column despite the spec |
| 5.2 Retailer Management | RE-SCOPE — plain list + link-out; drop the scraper-config authoring UI |
| 5.3 Scraper Framework | **DROP** |
| 5.4 Test Scraper Tool | **DROP** — nothing to test |
| 5.5 Daily Price Scraping | RE-SCOPE — manual "check price", or one legitimate source |
| 5.6 Price Drop & Push | RE-SCOPE — push stack is free; fold the check into whatever inserts the row |
| 5.7 Price History Charts | DEFER — hard 7-day wall-clock gate |
| 5.8 Daily Aggregation | KEEP — the one phase here with sane acceptance criteria (permits backdated fixtures) |
| 5.9 Deals Scraper | RE-SCOPE — **hotukdeals official RSS**, first-party syndication instead of scraping |
| 5.10 Deal Filtering | KEEP — source-agnostic |
| 5.11 Sale Season Calendar | KEEP — **best effort-to-value ratio in the stage.** Hardcoded dates + cron + existing push. Survives a maximal cut |

### Stage 6 — Notifications & polish
6.1 Notification Preferences **KEEP** (free) · 6.2 Multi-Device Push **KEEP** (free) ·
6.3 Command Palette **DROP** · 6.4 Keyboard Shortcuts **DROP** ·
6.5 Optimistic UI **RE-SCOPE** — port the-coupon's queued/unconfirmed reconciliation, *not* naive optimistic-with-rollback, which can silently take a user's action backwards on an ambiguous failure ·
6.6 Mobile Gestures **RE-SCOPE** — keep swipe actions, drop haptics (iOS PWAs largely lack the Vibration API)

### Stage 7 — Streaming, recommendations & calendar
7.1 Watch Providers **KEEP** — already half-built: `client.py:133` requests `watch/providers`, models exist. Honour JustWatch attribution; display live, don't ingest ·
7.2 Recommendations **RE-SCOPE** — keep detail-page "more like this", fold the new-releases half into 7.3/7.4 ·
7.3 Release Calendar **RE-SCOPE** — TMDB-only (theatrical/streaming); park physical dates pending a real source ·
7.4 Calendar UI & iCal **RE-SCOPE** — an `.ics` feed is **public and unauthenticated by necessity**; use a high-entropy token path, decided deliberately

### Stage 8 — Discovery & movie night
8.1 Smart Search **RE-SCOPE** — drop the LLM. The real gap at 1,866 items is **missing facets**: `FilterBar.tsx` offers genre/format/exact-year only — no decade range, watched status, rating or location. Zero-latency, zero-cost. If Stage 9 ships, NL search arrives free via its search tool ·
8.2 Feeling Lucky **RE-SCOPE** — one `ORDER BY random()`; not a phase ·
8.3 / 8.4 Movie Night **DROP** — tables stay, unused

### Stage 9 — AI assistant
9.1 Claude API Client **KEEP** — port garmin-coach's `anthropic_text.py` per-phase timeouts; a flat 60s timeout caused seven briefs to fail while Anthropic had already generated and billed the work ·
9.2 Tool Definitions **RE-SCOPE** — standard work, retag down. Adopt garmin-coach's boundary: **read-only tools by construction** ·
9.3 Chat UI **RE-SCOPE** — drop token streaming for v1; garmin-coach ships non-streamed ·
9.4 Tool Execution **RE-SCOPE** — the model never holds a write tool; suggestions surface as ordinary UI buttons hitting existing endpoints ·
9.5 Voice Input **DEFER** · 9.6 Voice Output **DROP** ·
9.7 Usage Caps **KEEP, re-prioritised to ship immediately after 9.1** — plus a bounded tool loop (`MAX_TOOL_ROUNDS`/`MAX_TOOL_USES`, final round forced to `tool_choice: none`). There must never be a window where the assistant can spend uncapped

### Stage 10 — Purchase detection
**10.1, 10.2, 10.3, 10.5, 10.6, 10.7, 10.8 — DROP. 10.4 (generic IMAP) — DEFER.**
Eight phases of OAuth, credential encryption and mailbox scanning to pre-fill a form that
already works, for someone buying a few discs a month. The blast radius changes class: a
compromise today exposes a disc collection; with this it exposes two people's inboxes — on
an app with no rate limiting and no fail-closed config. Google's restricted scopes stay
free only inside a test-user allowlist. Substitute: forward order confirmations to a
dedicated address, or add at unboxing. 10.4 stays filed because an app password sidesteps
both OAuth regimes. **10.6 also has a hard dependency on 9.1.**

### Stage 11 — Insights, box sets & memories
11.1 Completion Sets **RE-SCOPE** — split; ship the TMDB franchise half, park award/curated lists pending a data source. Priority up at 1,866 ·
11.2 Completion UI **DEFER** (gated on 11.1) ·
11.3 / 11.4 Box Sets **KEEP** — real data trapped in a `sub_category` string today ·
11.5 Smart Collections **RE-SCOPE** — retag down (a saved WHERE clause); priority **up** ·
11.6 On-This-Day **DEFER** — hard cold start: `parser.py:153-158` reads no watch dates, so `watch_log` is empty at launch and stays empty for ~a year. Size-independent

### Stage 12 — Sharing & physical integration
12.1 / 12.2 Gift Links **RE-SCOPE** — **the app's only public surface**, and `gift_links.id` is a sequential BigInteger, so URLs are trivially enumerable; §3.21 specifies a UUID slug. Needs a high-entropy token, server-side expiry/active enforcement, an anonymous rate limiter and `noindex` before it ships. Consider substituting an emailed export ·
12.3 / 12.4 Shelf QR **RE-SCOPE** (reversed from DROP) — real at 1,866 across five areas, but **fix 3.1b first**: search-by-location may solve retrieval without printed codes. QR then shrinks to a write-side flow plus a label sheet bounded by section/shelf pairs — a handful, not 1,866 ·
12.5 Lending Tracker **KEEP**

### Stage 13 — Stats, export & resilience
13.1 Stats **KEEP** (recharts already present) · 13.2 Activity Feed **KEEP** ·
13.3 Export CSV/JSON **KEEP** — genuine round-trip value; the collection *originated* as a spreadsheet ·
13.4 Export PDF/HTML **SPLIT** — promote the plain insurance-documentation table (real risk mitigation for 1,866 items, as cheap as 13.3); defer the glossy poster catalogue ·
13.5 Trash & Restore **KEEP** · 13.6 Audit Log UI **KEEP** ·
13.7 Backup & Restore **RE-SCOPE to documentation** — app-starter ships a real scheduled `pg_dump`; the remaining work is confirming Supabase PITR is on and writing the re-import runbook. garmin-coach's lesson: *"a backup you have actually restored"* ·
13.8 Service Worker **RE-SCOPE** — configuration. **Move much earlier**: offline browsing of a physical catalogue is unusually apt here — you are standing at a shelf with no signal ·
13.9 Offline Write Queue **RE-SCOPE** — port the pattern, adapt the shape ·
13.10 Playwright E2E **KEEP** — written alongside each rebuilt feature, not as one late phase ·
13.11 Visual Polish **DROP as a phase** — fold "empty, error, loading state" into the definition of done for every UI phase; keep a single axe-core accessibility gate on 13.10's harness

---

# Corrections made during this part

Three agent claims were checked and found wrong; none are propagated:

1. **"`DECISIONS.md` #31"** cited for a soft-delete pattern — the file has 15 entries. Fabricated citation, sound underlying point.
2. **"5.6's Postgres-trigger design is architecturally wrong because a trigger can't call `pywebpush`"** — overstated. A trigger writing to a queue table that a job drains is legitimate; the phase is underspecified, not broken.
3. **"`app-starter/vercel.json` could not be located"** — it exists (1,245 bytes, `Permissions-Policy` at line 27). The agent searched the wrong repo. The camera-policy finding for 3.3 stands.

---

# What Part E inherits

- **Sequence 3.1b first** after the deploy spine. Cheapest item in the roadmap, three phases depend on it, and it fixes the app's central defect.
- **Pull 13.8 forward** into the deploy-adjacent PWA wave.
- **Ship 9.7 with 9.1**, never after.
- **Two `vercel.json` fixes** — the camera Permissions-Policy and the CSP `connect-src` — before 3.3 or 3.10.
- **The gift-link public surface** needs its own security decision before 12.1/12.2.
- **Decision #12 (no response envelope) stands.** The AI cluster resolved its own revisit trigger: garmin-coach's `coach_tools.py` does **not** call its own enveloped REST API — it runs `select()` in-process and returns tool-shaped JSON. Under the re-scoped read-only design, the assistant is a second consumer of the *data layer*, not of the versioned HTTP API. No envelope needed.
