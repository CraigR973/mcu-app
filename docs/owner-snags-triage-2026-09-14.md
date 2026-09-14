# Owner snag triage — 2026-09-14

Triage of `docs/owner-snags-2026-09-14.md`, which captured 11 snags and deliberately
investigated none of them. This document investigates each one against the code, the live
Neon database and the deployed app, corrects the capture where it was wrong, and proposes
batches.

**Status: investigated, not approved.** No code has been written. The batch proposal at the
end needs Craig's sign-off before anything is built.

**Method.** Code read at `8e02399`; row counts measured against live Neon on 2026-09-14 by
read-only `SELECT`; zoom behaviour measured in a real browser at 375×812 against the deployed
app at `mcu-app-fawn.vercel.app`; Letterboxd's API policy read from their own developer page.
Production API is healthy — `/api/v1/health` serves `4ce81d6` with `db: ok`.

**What could not be checked, and why.** Anything behind sign-in. Signing in needs a PIN, and
an agent must not enter a credential. Every claim below about a signed-in screen is therefore
from source, not from looking at it. Three things are explicitly deferred to a real phone:
whether the zoom Craig means is the one measured here (snag 3), whether a Letterboxd link
opens the app (snag 9), and how the add flow feels in the hand (snag 7).

---

## What the capture got wrong

Six corrections, each of which changes what the work is.

| # | The capture said | Actually |
|---|---|---|
| 4 | Deleting gift-link rows is a destructive operation needing Craig's go-ahead | **`gift_links` holds 0 rows.** Nothing to delete; no owner decision needed |
| 8 | "Who is Mark and Craig in the system" is open | **There are exactly two accounts** — Craig (admin), Mark (viewer). "Mark and Craig only" already describes everyone who can sign in |
| 7 | Unknown what "list for sale on eBay" does | **Already built, Batch 29.** The gap is reach, not capability |
| 3 | Blocking pinch-zoom may be the only fix, so it is Craig's call | **Two of the three zooms fix for free** without touching pinch |
| 9 | Where the link is built was not examined | **Every** Letterboxd link is a search link, for all 1,854 films |
| 6 | "Check Movie night against the behaviour Craig wants" | Two of his five points are met. The other three need the input side rebuilt |

And one thing the capture could not have known: **Letterboxd's API policy excludes this app
by name of category.** See snag 10.

---

## What the database actually holds

Measured 2026-09-14 against live Neon. This is the single most useful thing in this document,
because it reframes snag 5 completely.

| Table | Rows | What is empty because of it |
|---|---|---|
| `movies` | 1,854 | — |
| `collection_items` | 1,857 | — |
| `completion_sets` | 40 | — (Insights has real content) |
| `admin_actions` | 41 | — (recent activity works) |
| `release_calendar` | 32 | all `theatrical` — see snag 2 |
| `wanted_list` | 11 | — |
| `retailers` | 10 | — |
| `price_checks` | 14 | two hand-run days |
| `notifications` | 3 | — |
| `movie_night_sessions` | 2 | — |
| `scrape_runs` | 1 | the cron has never fired successfully |
| **`watch_log`** | **0** | On this day · Worth a rewatch · Most watched · "has he seen it" |
| **`smart_collections`** | **0** | the whole Collections page · pinned collections on Home |
| **`box_sets`** | **0** | the whole Box sets page |
| **`deals`** | **0** | the whole Deals page |
| **`loans`** | **0** | the whole Loans page |
| **`item_photos`** | **0** | — |
| **`gift_links`** | **0** | — (and see snag 4) |
| `collection_items.purchase_price` | **0 of 1,857** | Spend over time on Stats |
| `movies.letterboxd_slug` | **0 of 1,854** | see snag 9 |
| `movies.imdb_id` | 1,091 of 1,854 | the ceiling on snag 9's fix |
| `movies.tmdb_id` | 1,100 of 1,854 | " |

**Five of the fourteen sidebar destinations lead to a page with nothing on it**, and Home is
three-quarters empty. That is a different problem from "the menu is badly organised", and it
wants a different answer.

---

## The snags

### 1. Archive layout — the crowding is in the shell, not the Archive

**Verified.** `AppLayout.tsx` renders `<SearchBar />` **twice**: once at line 77 in the header
row, and again at lines 97–98 inside a `lg:hidden` block — a **second full-width row under the
brand bar, on every signed-in page**, not just the Archive.

Below that, the Archive adds two more bands: a `PageHeader` (title + `ViewToggle`) and
`FilterBar`, which is a full-width bordered `<section>` carrying two selects, a Filters
disclosure button, a sort select and a result count, with six more controls when expanded.

So a phone shows **four stacked bands** before the first poster. Craig's description is exact.

**What his ask resolves to.** The Archive page itself is already close to what he asked for —
it renders a view switcher and a filter control and nothing else. The work is in the shell:
drop the mobile second search row, move search to the bottom bar, and collapse `FilterBar` to
a single button on small screens.

**Related:** 5, 11. Do not build this before the bottom bar is settled.

---

### 2. Calendar and Coming soon — the physical release types exist and nothing writes them

**Verified, and better news than expected.** `models/release_calendar.py` already declares the
vocabulary Craig wants:

```
RELEASE_TYPES = ("4k_uhd_release", "blu_ray_release", "streaming_release",
                 "theatrical", "award_ceremony", "sale_event")
```

with GB as the default `region` and display labels for each. **But `services/calendar.py`
hardcodes `"theatrical"` as the only type it ever writes** (line 140). All 32 live rows are
cinema dates. The two physical types have never been written.

**The two screens genuinely overlap.** Calendar reads `release_calendar`; Coming soon
(`/discover`) reads `/discover/new-releases`, a TMDB feed filtered by the genres you already
own (§7.2). Both answer "what is coming out". Merging them is well-founded.

**Where physical dates come from.** TMDB's `/movie/{id}/release_dates` returns per-country
release types, where **type 5 is Physical** — which is exactly `blu_ray_release` and
`4k_uhd_release` for GB. `tmdb/client.py` does **not** have this method today; it has
`get_movie_full`, `get_upcoming`, `get_watch_providers` and others, so adding one is a small
extension of a working client rather than new integration. Blu-ray.com (Batch 23's scraper) is
a second source but is heavier and carries the access-policy risk recorded in `DECISIONS.md`.

**Honest caveat.** TMDB's physical dates for UK releases are community-maintained and
patchy. Expect coverage well below 100%, and design the screen so a film with no physical date
is not silently dropped.

---

### 3. Zoom — three different behaviours, two of them free to fix

**Measured on the live app at 375×812**, not inferred:

| Behaviour | Live? | Cause | Cost to fix |
|---|---|---|---|
| **Phone zooms in when a text box is tapped** | **Yes** | `.form-control` is `text-sm` = **14px**. Measured: both inputs on the sign-in page compute to `14px`. iOS Safari zooms any input under 16px | **Free.** Raise form controls to 16px on touch widths. Pinch-zoom untouched |
| **Double-tap zooms the page** | **Yes** | `touch-action: manipulation` is scoped to `button, [role='button']` only. Measured: `html`, `body` and the inputs all compute `touch-action: auto` | **Free.** Apply `manipulation` at the root. Pinch-zoom untouched |
| **Pinch zooms the page** | **Yes** | By design — the viewport meta sets no `user-scalable=no` and no `maximum-scale` | **Has a real cost.** Blocking it stops anyone enlarging small text |

**This dissolves the trade-off the capture raised**, unless Craig specifically means pinch. The
"behaves like a web page, not an app" feeling is most likely the first two, and both are
ordinary CSS fixes with no downside.

**Needs Craig's phone to settle**, and it is one question: *when it zooms, what were you
doing?* Tapping a box, double-tapping, or pinching.

---

### 4. Remove Gift links — no destructive operation, and nobody ever used it

**`gift_links` holds 0 rows. Total. Zero views.** The capture's warning about deleting stored
rows, and open question 5, both dissolve — there is nothing stored.

**Surface to remove**, all verified present:

- API: `models/gift_link.py`, `routers/gift.py`, `schemas/gift.py`, registration in `main.py`
- Coupling: `services/trash.py` registers `gift_links` in the trash/restore table registry —
  a revoked link is soft-deleted and restorable, so removal must unwind that registry entry
- Web: `GiftLinksPage.tsx`, `GiftPage.tsx`, routes in `App.tsx`, the item in `nav-items.ts`,
  the client functions in `lib/api.ts`
- `packages/shared/src/schemas.ts` and its tests
- `sw.ts` lines 93–114 — a service-worker exclusion for `/api/v1/gift/`, added to fix a real
  bug where a public gift page was being cached
- A migration to drop the table. With 0 rows this destroys no data, but it is still a schema
  change and should be flagged as such at close-out

Clean, self-contained, and a good first batch.

---

### 5. Refine the menu — the problem is emptiness, not organisation

**The sidebar's real shape**, verified in `nav-items.ts`: 15 destinations are defined, 14 are
placed in four groups, and **AI settings is defined but sits in no group** — reachable only
from the header. Admins see six more under Administration. So Craig sees 20 destinations;
Mark sees 14.

**The capture's proposal was argued from organisation. The data argues something stronger.**
Of the five pages Craig named:

| Page | Real content today |
|---|---|
| **Stats** | Counts and four breakdown charts — **real**. Most watched and Spend over time are **both empty** (0 watch logs, 0 purchase prices) |
| **Insights** | 40 completion sets — **real** |
| **Home** | Recent activity works (41 admin actions). On this day, Worth a rewatch and pinned collections are **all empty** |
| **Box sets** | **0 rows. Entirely empty page** |
| **Collections** | **0 rows. Entirely empty page** |

And beyond the five: **Deals 0, Loans 0**.

So the menu does not merely feel long — **a third of it leads nowhere**. Two separate
remedies follow, and they should not be confused:

1. **Merge what is thin but real.** Home + Stats + Insights into one reading page, as the
   capture proposed. The argument is stronger than it knew: two of the three are mostly empty,
   so the merged page is not a long scroll — it is one page of genuine content.
2. **Hide what is empty until it has something in it.** Box sets, Collections, Deals and Loans
   could disappear from the menu entirely while their tables are empty, and reappear on first
   use. That is a smaller change than moving them into the Archive and it removes four items
   rather than two.

Together those take 14 sidebar items to **8**, without deciding anything about the Archive's
internals — and without the capture's proposal to fold Collections into a filter menu and Box
sets into the view switcher, which can be decided later on its own merits.

**AI settings should join Notifications as one Settings page** either way, which brings it back
into the menu instead of leaving it header-only.

**Still open, and genuinely Craig's:** he asked for more trimming than any of this.

---

### 6. Movie night — two of five points met, and the input side is not built

Scored against Craig's own five points.

| His ask | Built? | Evidence |
|---|---|---|
| A session has at least 2 people | **Yes**, and it generalises past 2 | `detect_match` requires `len(people) >= 2` and matches when **everyone** has liked a film (`set(people).issubset(liked_by)`), so 3+ works |
| Anyone can suggest films; everyone votes on others' suggestions | **No — not built at all** | There is no suggestion concept. `candidate_movies` draws a random deck straight from `movies`, filtered only by decade and rating |
| Opening a film shows all of its details | **No** | The swipe card renders poster, title and `overview`. No cast, runtime, genres, or link to the film's page |
| If the film isn't in the Archive, show streaming services | **No — impossible today** | The deck is `select(Movie)`, so only films already in the collection can ever appear. *However:* `tmdb/client.py` already has `get_watch_providers`, so the data source exists |
| Show whether the others have watched it, and when | **No** | Needs `watch_log`, which holds **0 rows** |

**What is built is a random swipe deck over your own collection.** What Craig described is a
shared suggestion board, open to films outside the collection, showing who has seen what.
Those are different features sharing a name. This is not a tweak — it is a rebuild of the
input side, and it should be scoped and priced as one.

**A defect found in passing.** `candidate_movies` documents itself as *"seeded per session so
both people are shown the same deck in the same order"*, but the query is
`order_by(func.random())` with **no seed** — every call returns a different order, for each
person and on every refetch. Low impact, but the comment asserts a guarantee the code does not
give. Worth fixing whether or not the rest of snag 6 is built.

---

### 7. Quick add and the eBay sell-offer — already built, and out of reach

**The feature Craig is asking for exists.** Batch 29 built it, and the flow works end to end:

1. `/collection/add` → choose the film and format
2. `checkDuplicate` fires → `DuplicatePrompt` offers **"This is an upgrade"**, which is also
   the save
3. Saving navigates to `/movies/<id>?upgraded=1`
4. The film's page opens with `UpgradePrompt`, naming the superseded disc with a one-tap
   **"List for sale"** and an eBay price already in the box

**What "list for sale on eBay" actually does** — open question 1, answered.
`POST /api/v1/ebay/listing-url` returns a **pre-filled eBay listing URL**, a suggested title
and a suggested price derived from `POST /api/v1/ebay/price-estimate`'s median of current
asking prices. **It does not create a listing.** `DECISIONS.md` #142 records why: eBay's
Inventory API has no true draft — an offer is invisible until published, at which point it is
live with a buyer on the other end. So the app takes you to eBay's own form with everything
filled in, and you press the last button.

**So snag 7 is entirely about reach.** Three things put it out of Craig's and Mark's hands:

- The header's "Add a disc" button is `hidden sm:inline-flex` — **invisible below 640px**,
  so a phone has no add button at all
- `/collection/add` is wrapped in `AdminShell` — **Mark cannot reach it**
- Both eBay endpoints are `AdminUser` — **Mark cannot get a price or a listing link**
- None of it is on Home

That is a small, well-defined batch, and it is the same batch as snag 8.

---

### 8. Mark and Craig only — there is nobody else

**`UserRole` has exactly two values, `admin` and `viewer`, and `profiles` holds exactly two
rows:** Craig (admin, last login 2026-09-13) and Mark (viewer, last login 2026-09-10). Both
active, both with a PIN set. The model's own docstring says the table "is expected to hold
exactly two rows for the life of the app", and there is no public sign-up.

**So "only Mark and Craig can see these" is already true of every page**, because no third
person can sign in. Read literally, snag 8 is already satisfied and there is nothing to do.

It is much more likely Craig means the opposite of how it was captured: not *restrict these
from others*, but **give Mark access to things only Craig can reach today.** Today's split:

| | Craig (admin) | Mark (viewer) |
|---|---|---|
| Wanted, Deals, Loans | ✅ | ✅ already |
| Retailers, Add a disc, eBay price + listing, Trash, Audit, Gift links, Admin | ✅ | ❌ |

Of the five things Craig listed — quick add, Loans, Deals, Retailers, Wanted — **three are
already open to Mark** and two are admin-only.

**This is question 4 reframed**, and it is the one that most needs his answer: *should Mark be
able to add discs and see eBay prices?* If yes, this is a permissions change in the API as well
as the UI — `AGENTS.md`'s pattern is that pages hide what the API refuses, so both move
together.

**One consequence to note:** if anything does become Craig-only, the bottom bar differs per
person, which feeds snag 11.

---

### 9. Letterboxd links — every link is a search link

**Verified in `MovieDetailPage.tsx:356-358`:**

```ts
const letterboxdUrl = movie.letterboxdSlug
  ? `https://letterboxd.com/film/${movie.letterboxdSlug}/`
  : `https://letterboxd.com/search/${encodeURIComponent(movie.title)}/`
```

**`letterboxd_slug` is NULL for all 1,854 films.** The model says so outright — *"TMDB does not
supply it and no import populates it yet; the read surface falls back to a search URL"* — and
the database confirms it. So the search fallback is not an edge case; **it is the only branch
that ever runs.**

**The fix, and its honest ceiling.** Letterboxd resolves films by external id:
`letterboxd.com/imdb/<imdbId>` and `letterboxd.com/tmdb/<tmdbId>` both redirect to the film's
own page. `MovieDetailResponse` **already carries `imdbId`**, so the fix needs no schema change
at all — only the fallback chain.

But the ceiling is real: **1,091 of 1,854 films have an IMDb id** (1,100 have a TMDB id). The
other ~760 are unidentified, and for those a search link remains the only honest option. So the
fix takes roughly **59% of films** from a search page to their real page, and the remainder
improve only when they are identified.

**Opening in the Letterboxd app** is a phone-side behaviour: with the app installed,
`letterboxd.com` links are claimed by it via universal links. Nothing in the code controls it,
and it cannot be verified from here — **a real-device check for Craig**, after the link is a
film link rather than a search.

---

### 10. Letterboxd sign-in and sync — the API is a dead end

**Feasibility, settled.** Letterboxd's own developer page states access is by application only,
and lists the categories they will **not** grant for. Two of them describe this app exactly:

- **"private or personal projects"** — MCU is a private two-person app
- **"LLM or GPT-related use"** — MCU ships an AI assistant

They also exclude data-analysis, visualization and recommendation projects, and anything
recreating their paid-tier features. They state they cannot reply individually or guarantee
access.

**Recommendation: do not apply.** The application is very likely to be refused, and it would
park the batch behind an answer that may never come.

**What does work**, in order of usefulness:

| Path | Gives | Cost / limit |
|---|---|---|
| **Import a Letterboxd data export** | `diary.csv` — every logged film with **the date watched**, rating, and rewatch flag; plus `watchlist.csv`, `ratings.csv`, `reviews.csv`, `lists.csv` | **Requires Letterboxd Pro — about $35/year, per account.** Both Craig and Mark would need it for both histories |
| **Public diary RSS** (`letterboxd.com/<user>/rss`) | Recent diary entries with dates | Free, no credential — but **recent only**, so no backfill, and needs a public diary |
| ~~API~~ | — | Excluded by policy |

**Never** a design where anyone types a Letterboxd password into this app. The capture's
instinct was right.

**Matching will need care.** Letterboxd exports carry title, year and a Letterboxd URI — **not
TMDB or IMDb ids**. So an import matches on title + year against 1,854 films and will need a
confirmation step for ambiguities, the same shape as Batch 24's barcode confirmation.

**Why this matters more than it looks.** `watch_log` is empty, and the app already has the UI
to write it (`WatchPanel` on the film page, logging a date and a rating). **One import brings
four dead things to life at once:** On this day, Worth a rewatch, Most watched, and the
"has he seen it" that snag 6 needs. It is the highest-leverage item on the whole list.

---

### 11. Opening screen and bottom bar

**Today.** `/` redirects to `/movies`, so a signed-in person lands on the Archive. The bottom
bar is Archive · Wanted · Movie night · Home · More. The floating assistant button is
`fixed bottom-[5.5rem] right-4` on phones — clearing the tab bar but sitting over page content,
which is `OWNER-ACTIONS.md` item 11.

**Everything else feeds this**, and it cannot be settled before them: search wants a slot (1),
Home gains quick add (7), and what Home *is* changes if the menu merges (5).

**Craig's parked question — which screen to open on — is deferred by his own decision of
2026-09-14: decide after the triage.** It is now answerable, and the answer follows from snag 5:
if Home absorbs Stats and Insights and gains quick add, it becomes a page worth opening on. If
the merge does not happen, Home stays three-quarters empty and the Archive remains the right
landing screen. **So decide 5 first, and 11 falls out of it.**

---

## Open questions — all closed

Craig answered the four outstanding decisions on 2026-09-14. They are recorded as
`DECISIONS.md` **#154–#157**.

| # | Question | Outcome |
|---|---|---|
| 1 | Where is the eBay functionality today? | **Answered.** Admin-only price estimate + pre-filled listing URL; no listing is created |
| 2 | Which screen should the app open on? | **Follows from #154** — Home becomes the merged reading page and gains quick add, so it is worth opening on. Confirm at plan approval |
| 3 | Menu: which merge, and how much further? | **Decided, #154.** Merge *and* hide-when-empty. 14 items → 8 |
| 4 | Who is "Mark and Craig" in the system? | **Answered, and reframed** into question 9 |
| 5 | Gift links: delete the rows or keep them? | **Dissolved.** There are no rows |
| 6 | Zoom: is blocking pinch acceptable? | **Moot.** Both free fixes ship; pinch is left alone. If it still zooms on Craig's phone afterwards, pinch is the one he meant and we revisit |
| 7 | Letterboxd: apply for API access? | **Decided, #156. No** — policy excludes this app twice over |
| 8 | Letterboxd Pro for the export? | **Decided, #156.** Staged: free RSS first, the paid export later for backfill. Usernames given and both diaries confirmed public 2026-09-14 — `OWNER-ACTIONS.md` 1f closed, 1g holds the Pro decision |
| 9 | Should Mark be able to add discs and see eBay prices? | **Decided, #155. Yes, both.** API moves with the UI |
| 10 | Movie night: rebuild or accept? | **Decided, #157. Rebuild** to Craig's description |

---

## The batch plan

Eight batches. Ordered so nothing is built before what it depends on. Model and effort follow
`docs/phase-batches.md`'s conventions.

| # | Batch | Covers | Depends on | Effort |
|---|---|---|---|---|
| **S1** | **Remove Gift links** | 4 | — | 🟢 Sonnet 5 · medium |
| **S2** | **App-feel fixes** — zoom + Letterboxd links | 3, 9 | — | 🟢 Sonnet 5 · medium |
| **S3** | **Navigation shape** — menu, search, Archive header, opening screen | 5, 11, 1 | #154 | 🟡 Opus 5 · high |
| **S4** | **Quick add within reach** — Home/bottom-bar add, Mark's write access | 7, 8 | S3, #155 | 🟡 Opus 5 · high |
| **S5** | **Watch history, stage 1** — Letterboxd diary RSS + identify-on-match | 10a | #156 · **unblocked** | 🟡 Opus 5 · high |
| **S6** | **Physical release dates** — merge Calendar + Coming soon | 2 | S3 | 🟡 Opus 5 · high |
| **S7** | **Movie night rebuild** — suggestions, outside films, streaming, seen-it | 6 | S5, #157 | 🔴 Opus 5 · xhigh |
| **S8** | **Watch history, stage 2** — Letterboxd export backfill | 10b | Craig buying Pro | 🔴 Opus 5 · xhigh |

**Order:** S1 → S2 → S3 → S4 → S5 → S6 → S7. S8 lands whenever Craig decides to pay for Pro;
it writes the same `watch_log` rows through the same matcher as S5, so it is additive rather
than a rework.

### What each one is

**S1 — Remove Gift links.** Both pages, both routes, the router, model, schemas and client
functions, the `services/trash.py` registry entry, the `sw.ts` cache exclusion, the shared zod
schemas and their tests, and a migration dropping the table. 0 rows, so no data is destroyed —
but it is still a schema change and says so at close-out.

**S2 — App-feel fixes.** Raise form controls to 16px at touch widths so tapping a box stops
zooming; apply `touch-action: manipulation` at the root so double-tap stops zooming. Pinch-zoom
is deliberately left working. Change the Letterboxd fallback from a search URL to
`letterboxd.com/imdb/<imdbId>` — no schema change, and it fixes 1,091 of 1,854 films.
**Ends with two checks on Craig's phone:** does it still zoom, and does a Letterboxd link open
the app.

**S3 — Navigation shape.** Merge Home + Stats + Insights into one reading page; hide Box sets,
Collections, Deals and Loans while their tables are empty; fold Notifications and AI settings
into one Settings page. Move search out of the shell header into the bottom bar, reachable from
any screen. Collapse `FilterBar` to a single button on small screens. Set the opening screen to
the merged Home. Export moves to Admin.

**S4 — Quick add within reach.** A quick-add entry point on Home and in the bottom bar, visible
below 640px. `/collection/add` and both eBay endpoints stop being admin-only, in the API as
well as the UI. The existing upgrade → "List for sale" flow is surfaced in the add flow rather
than only on the film page afterwards.

**S5 — Watch history, stage 1.** *Rescoped 2026-09-14 after measuring both live feeds —
`DECISIONS.md` #158, #159.* Craig's and Mark's diaries are `CraigR973` and `markr973`, both
already public, so this is unblocked.

Read each person's diary RSS and write `watch_log` rows with their real watched dates. **Every
entry carries a `<tmdb:movieId>`**, so the primary match is an exact TMDB id — not the fuzzy
title+year match this plan originally assumed. Measured across 100 entries:

- **42 link immediately** on `tmdb_id`
- **24 are films they own that the April import never identified** (`tmdb_id IS NULL`). The
  diary supplies the exact id, so the sync **identifies the film as well as logging the
  watch** — filling in year, poster, runtime, cast, and the Letterboxd link snag 9 needs
- **34 are genuinely not in the collection** — cinema and streaming
- **0 were ambiguous**, but the confirmation step stays: 754 unidentified rows with messy
  titles (`'Collector, The'`, `'Out of The past'`) will produce ambiguity eventually, and
  anything not a single unambiguous candidate is offered, never guessed

Idempotency keys off the feed's stable `<guid>`, so a re-run updates rather than duplicates
and a genuine rewatch still becomes its own row. Manual sync first — both Railway crons are
crashing — but **the interval is a correctness property, not a preference**: the feed holds
only the last 50 entries and Mark's already reaches back just eight weeks, so a sync running
less often than monthly silently loses his history. Mark rates nothing, so a null rating on
his rows is correct.

**Lights up On this day, Worth a rewatch, Most watched and snag 6's "seen it" — and identifies
24 films on the way.**

**S6 — Physical release dates.** Add `/movie/{id}/release_dates` to the TMDB client and ingest
GB **type 5 (Physical)** dates as `blu_ray_release` and `4k_uhd_release` — both types already
exist in the vocabulary and nothing has ever written them. Merge Calendar and Coming soon into
one screen led by physical releases, with cinema dates kept. Expect patchy coverage and do not
silently drop a film that has no physical date.

**S7 — Movie night rebuild.** Replace the random deck with a suggestion board: anyone suggests,
everyone votes on anyone's suggestion. Allow films outside the Archive, with streaming
availability from `get_watch_providers`. Open a card to the film's full details, including
whether the others have seen it and when.

**S8 — Watch history, stage 2.** Import a Letterboxd export ZIP — `diary.csv` for watched dates
and rewatches, `watchlist.csv` for wants, `ratings.csv` for scores. Same matcher and same
confirmation step as S5.

### Carried separately

- **`candidate_movies`'s false "seeded per session" comment** — `order_by(func.random())` with
  no seed. Its own `fix/` branch, per `AGENTS.md`, independent of S7.
- **The cron crash still blocks Batch 21.** Hosting, so Craig's. `OWNER-ACTIONS.md` item 1.
  Unrelated to these snags, and S5 is designed not to depend on it.
