# Owner snags — 30 Sep 2026, reconciled against the code

Craig raised 9 snags on 30 Sep 2026. The same evening, each one was checked against the code
at `8e4c6a2`, the captured eBay payloads in `apps/api/tests/fixtures/`, and the decisions that
govern them.

**Status: reconciled, and Craig answered the same evening (below).** Nothing is built. The
full plan is Group V in `docs/phase-batches.md`, summarised under "The full plan" at the end:
proposed, not approved. His answers are `DECISIONS.md` #228.

**Not checked:** anything live. This session had no database access and no sign-in, so
production counts (how many loans exist, for example) come from the code's rules and the last
recorded measurement, not a fresh query. AVForums and Blu-ray.com could not be reached at all:
this session's network policy refuses both hosts.

## Craig's answers, 30 Sep

| Question | Answer | Recorded |
|---|---|---|
| Value: blend of bids and asking prices, or bids only? | Trial first | #228, V6 then V7 |
| Movie night: keep the list, drop the swipe deck? | Yes | #228, V3 |
| Craig's house: name, shelves, counted everywhere? | "Craig's house is fine" | #228, V4 |
| Reviews: links, links and a line, or scores? | All three | #228, V9 and V10 |
| Highlights: which rows? | A mix of all | #228, V5 |
| Top bar fix, back arrows and Loans: go? | Reconcile the full plan first | This section and Group V |

**Taken from "All" and "is fine", open to overrule:** the review scores widen #110 to read
Blu-ray.com's own review scores (nothing else in #110 changes); Craig's house has no shelves,
and its discs count like any other, in the value, the stats and "already owned".

## Craig's four follow-up questions, 30 Sep

**1. Can "usually" be an average of eBay sold prices and the shops' prices?** Half of it.
Sold prices cannot be had (question 2), so eBay's part is its own figure: asking prices today,
bids where V7 brings them in. The shops' part can be done, with one limit: **the app only
holds shop prices for films on the Wanted list.** The nightly check reads every enabled shop
for every active want (`services/scraping/runner.py`), and nothing else. Even there it is
thin: on 30 Sep only 2 wants had prices from more than one shop. Most eBay finds are
upgrades on owned films, which no shop is ever asked about. So "usually" becomes the average
of eBay's figure and each shop's latest price where one exists, eBay alone where none does,
and the card says which (V8). Asking the shops about every eBay find as well would multiply
requests to three shops already answering `429` (20b), so it is left out.

**2. Can we get sold prices if we sign in?** No. A sign-in gives an app one person's own
account. T8b's eBay sign-in gets Mark's watch list and his selling list, sold items
included, which is the prices *he* sold at, not the market's. Market-wide sold prices are
only in eBay's Marketplace Insights, which eBay grants to approved apps and has closed to new
ones (#16, #126); no person's sign-in changes what the app is allowed. Reading the sold
listings off eBay's website with someone's account is a bot driving eBay with a password,
ruled out by #203 and by eBay's terms. **What the app can do:** a link to eBay's own sold
listings for the film and format. It opens in your browser, where you are signed in, so you
see them in one tap (V8).

**3. Loans always shown, for both.** Yes (V2). The menu and the You page list Loans for Mark
and Craig whether or not a loan exists. Both can already read loans (`GET /loans`);
lending and "Mark returned" stay Craig's, as now.

**8. Are we using Brave for the reviews?** Yes, to *find* them (V9). #110 bars Blu-ray.com's
own search, and AVForums' own search has not been checked against its terms, so a web search
engine is how the app learns a review's address, as the spec backfill already does (#202). Two searches per film,
one per site, at about $5 per 1,000. Two things follow:

- **Brave's free credit is spent.** The spec backfill used it up on 28 Sep (1,005 searches)
  and restarts on the renewal around 1 Oct, when it will use it up again. Reviews need a cap
  of their own, and Craig raising Brave's monthly limit, or they wait for each new month.
- **Brave only finds pages.** The scores (option C) mean reading the review page itself
  (V10). Blu-ray.com's comes under #110, widened by "All". AVForums' terms are read first.

---

## Four things to know first

1. **The top bar has no background at all, and has had none since the 10 Sep redesign
   (`9afc173`).** It asks for `bg-background/94`, and Tailwind 3 has no 94 step, so the class
   is never generated. The bar is see-through, with only a blur. Proved by building the
   stylesheet with the app's own config and Tailwind 3.4.19. **20 classes in 10 files have the
   same fault**, among them the bottom tab bar, every badge's tint and the format badges.
2. **eBay sold prices are still out of reach; live bids are not.** Sold listings stay closed
   to apps (#16, #126). Auctions with bids can be read by the search the valuation already
   makes, at no extra cost. Today that search never sees an auction-only listing.
3. **Blu-ray.com reviews are forbidden by #110**, the decision under which the app reads
   Blu-ray.com at all. Pulling them needs Craig to widen #110 in a new decision.
4. **Loans hides itself when no loan exists** (#154, since 14 Sep). The page and the Lend
   button still work.

---

## At a glance

| # | Snag | Today |
|---|---|---|
| 1 | Where "usually £X" on Deals comes from | eBay's current asking prices: a median, not a sale price |
| 2 | Value from eBay sold prices and live bids | Sold: not possible. Bids: possible, not built |
| 3 | Loans section gone | Hidden while there are no loans |
| 4 | Movie night: swiping or the shortlist | Both exist. Recommend keeping the list |
| 5 | Back buttons | None on a phone for any page opened from the You page |
| 6 | Craig's house as a location | Not in the vocabulary. Needs a migration and a form change |
| 7 | Top bar looks faded | Bug: the bar has no background |
| 8 | Reviews for Wanted items | Not built. Blu-ray.com reviews barred by #110 |
| 9 | Top reviews / highlights | Not built. Most of the data exists |

---

## The snags

### 1. Where "usually £X" on Deals comes from

Only eBay finds say "usually". A shop's deal shows the shop's own struck-through "was" price,
read off its sale page.

For an eBay find, "usually £X" is the **median asking price of current UK Buy It Now
listings** for the same film on the same format (`services/ebay_watch/refs.py`):

- one eBay search, judged by the film page's own matcher: standard editions only, UK sellers
  only, no bundles, sequels, accessories or multi-variation listings (`src/ebay/matching.py`);
- compared within the listing's condition (used with used) when three or more listings stand
  behind that condition, otherwise the largest condition group;
- kept for 14 days before it is searched again.

A listing is a deal when it costs 70% or less of that median, postage included
(`services/ebay_watch/scan.py`, `DEAL_RATIO`). A deal stays on the page for three days.

Two things the screen does not say:

- **It is an asking price, not a sold price.** The code comment says so
  (`DealsPage.tsx:68`); the card does not.
- **"with postage, usually £X": the £X leaves postage out.** The deal price includes it
  (`listings.py`). The comparison is cautious, but the line reads as if both include postage.

**Proposed:** reword to "£P with postage · usually £X on eBay, asking price, before postage".

**Answer (30 Sep):** make "usually" an average of eBay and the shops. See follow-up question
1 above; it is V8.

### 2. Value the collection from sold prices and live bids

**Today** each disc is valued at the median current asking price of UK Buy It Now listings for
its film and format (`services/valuation.py`, #209), re-priced once 30 days old. The Home panel says
"asking prices" and that they run above what discs sell for.

**Sold prices: not possible.** eBay's sold data is in Marketplace Insights, which is closed to
new applicants, and since late August 2026 sold listings on the website sit behind a sign-in
(#16, re-confirmed by #126). Scraping them would also break eBay's terms. T8b's eBay sign-in
does not change this: it reads Mark's own watch and selling lists, not the market.

**Live bids: possible, with no extra eBay calls.**

- The valuation's search names no buying option, and that returns Buy It Now listings only.
  The captured Blade Runner 2049 search (no filter, 200 listings) holds no auction-only
  listing (`tests/fixtures/ebay_browse_blade_runner_2049.json`).
- One search can ask for both, with `buyingOptions:{FIXED_PRICE|AUCTION}`. Each auction
  carries `bidCount` and `currentBidPrice` (the one auction in that fixture has both). The
  deal scan already sends a `buyingOptions` filter live (#218).
- So the same one search per film and format can price from both. No change to the 750-a-day
  budget or the fortnightly schedule (#223).

**Two catches:**

- **A current bid is below the final price** until the last minutes of an auction. Count only
  auctions with at least one bid; whether to also drop ones with days left is for a dry run
  to settle.
- **Bids will be thin.** Many films will have fewer than three auctions with bids at any
  moment, and three is the minimum for a price (#129). How many discs bids would cover is
  not measured: it needs a dry run against live eBay.

**Proposed:** a disc is valued on current bids when three or more auctions with bids stand
behind it, otherwise on asking prices as now. Each disc's value, and the total, says which
("£X from bids on N discs, £Y from asking prices on M"). A dry run, writing nothing, first
measures the split.

**Craig's call:** that blend, or bids only (most discs would then show no value)?

**Answer (30 Sep):** trial first (V6); the pick follows its report (V7). Sold prices stay out
of reach even signed in (follow-up question 2).

### 3. Loans section gone

**It hides itself when there are no loans.** Since Batch S3 (#154, 14 Sep), Loans, Deals, Box
sets and Collections leave the menu while their table is empty (`lib/nav-items.ts`,
`showWhen`). Loans counts every loan ever made, returned ones included
(`routers/navigation.py`). On 14 Sep there were none.

- On a phone Loans is on the You page, under Explore, and hides there by the same rule.
- The page still works at `/loans`. Lending still works: a film's page, the copy, **Lend**
  (admin only).
- Whether any loan exists now was not checked (no database access).

**Proposed:** show Loans always. Its empty page already says how to lend a disc.

**Answer (30 Sep):** always shown, for Mark and Craig (V2).

### 4. Movie night: swiping or the shortlist

A night opens on the shortlist: 30 films picked from the Archive, plus anyone's suggestions,
with your own vote on each. "Start swiping" opens a deck of the films you have not voted on,
Skip or Add, one card at a time (Batch T4, #207). A match is everyone adding the same film.

**Recommendation: keep the list and vote on it. Drop the deck.**

- You act only on the films you would watch: tap Add on three of thirty, instead of swiping
  all thirty.
- Choosing a film means comparing films, and only the list shows them side by side.
- One screen instead of two, and it works the same on a laptop.
- The deck's extra detail (synopsis, cast, runtime, who has seen it, where it streams) moves
  into the row: tap a film to expand it.

A vote can already be changed (`record_vote` updates it), so an Add / Added toggle needs no
server change. Matches, the "It's a match" push and hidden votes (#157) stay as they are.
Phase 8.4 named a swipe gesture, so dropping it gets its own decision.

**Answer (30 Sep):** yes (V3, #228).

### 5. Back buttons

**On a phone** the top bar shows a back arrow only on sub-pages: a film, a box set, a movie
night. Every menu destination counts as top-level (`isTopLevel` in `lib/nav-items.ts`),
including the ones you reach from the You page. So **Wanted, Releases, Deals, Price alerts,
Loans, Box sets, Collections, Assistant, Settings and every admin page but Add a disc** have
no back arrow on a phone, though you got to them from You.

**The film page** has its own "Back to collection" button, which always goes to the Archive
(`MovieDetailPage.tsx:414`), wherever you came from: Wanted, Deals, Home, a movie night,
search. On a phone it sits just below the top bar's arrow, which does go back. Two back
controls, two destinations.

**On a desktop** the sidebar is always there, and the detail pages carry their own back
links; only the film page's is wrong, as above.

**Proposed:**

- On a phone, only the four bottom-tab pages and You are top-level. Every other page gets the
  arrow. With no history (opened from a notification or a link) it goes to You.
- The film page's button goes back to where you came from, falling back to the Archive, and
  hides on a phone, where the top bar already has one.

### 6. Craig's house as a location

A disc's place is three fields: `location` (free text), `section` (a fixed list) and `shelf`.
The list today is Front, Back, Lounge, Garage, Digital, Top Big Cabinet, Top Small Cabinet,
Fish Room Cabinet and Black Box (`SECTIONS` in `models/collection_item.py`). A database CHECK
allows only those (migration 007). Only Front and Back have shelves.

Adding Craig's house needs:

- **a migration** widening the CHECK, and the name added to `SECTIONS` and to the location
  parser (`spreadsheet/parser.py`), so typing "Craig's house" also lands there;
- **a form change.** The Section picker lists only sections that already hold a disc
  (`GET /collection/facets`, read by `CopyForm.tsx`), so a new, empty section could never be
  picked. The form needs the whole list;
- **the apostrophe escaped.** Migration 007 builds its CHECK by pasting each name inside
  quotes, and a copy of that code would break on "Craig's".

**Craig's calls:**

- The name, exactly as it should read ("Craig's house"?).
- Shelves there, or one place like the cabinets?
- These discs will count wherever the collection counts: its value, the stats, and "already
  owned" when judging deals and upgrades. Is that right?

**Answer (30 Sep):** "Craig's house is fine": that name, one place without shelves, counted
like any other disc (V4, #228).

### 7. Top bar looks faded

**A bug: the top bar has no background.** `AppLayout.tsx:159` asks for `bg-background/94`.
Tailwind 3 builds an opacity step only from its scale (0, 5, 10 … 95, 100) or from a bracketed
value, and 94 is neither, so the class is dropped without a word. What is left is
`backdrop-blur-md`: a see-through bar with the page blurred behind it.

Proved by building the stylesheet with the app's own Tailwind config and version (3.4.19):
`bg-background/94` is absent, while `bg-background/95` is built.

The same fault, 20 uses in 10 files:

- the phone's bottom tab bar (`bg-popover/96`), also see-through;
- every tinted badge (`/12`): the Deals discount, the movie-night vote chip, the notices.
  They show their text and border, but no tint;
- the format badges on the film cards (`/14`);
- the hover shade on filled buttons (`/88`).

**Proposed fix (small):** add the missing steps (12, 14, 88, 94, 96) to the Tailwind theme,
and a test that fails when a class names a step the theme lacks, so this cannot recur
silently. Then look again at whether the bar should be fully opaque.

### 8. Reviews for Wanted items

**Nothing reads reviews today.**

- **Blu-ray.com: barred by #110.** The app reads Blu-ray.com only under Craig's risk
  acceptance, which is bounded to specs: no prices, reviews, ratings or member content. The
  parser refuses review and rating labels by name (`FORBIDDEN_LABELS` in
  `services/specs/bluray_com.py`). Reading reviews needs a new decision widening #110.
- **AVForums: not checked.** Its terms and robots.txt could not be read from this session.
- **Finding the review pages** can use the Brave search the spec backfill already uses
  (#202), which never touches either site. Its free monthly credit ran out on 28 Sep and
  renews around 1 Oct.

**Three options:**

- **A. Links only.** Each Wanted item gets "Reviews: Blu-ray.com · AVForums", found by a Brave
  search when the item is added. No scraping, no change to #110.
- **B. Links and a line.** A, plus the one-line description Brave returns for each review.
  Still no request to either site.
- **C. The review's scores** (picture, sound, extras, overall), read from the review page once,
  when the item is added. Needs #110 widened for Blu-ray.com, and AVForums' terms read first.

**Recommended:** B now; C only if Craig widens #110.

**Answer (30 Sep):** all three, found with Brave (follow-up question 8). A and B are V9; C is
V10, and widens #110 to Blu-ray.com's review scores (#228).

### 9. Top reviews / highlights

**Not built.** What there is to build from:

- **Your ratings:** 1,566 viewings from Letterboxd at the last count. Craig rates everything;
  Mark rates nothing (#159). No review text is imported.
- **TMDB's rating** on every identified film (`movies.tmdb_rating`).
- **Each disc's value**, from the valuation.
- **What Home already shows:** Coming to disc, On this day, Worth a rewatch, Collection value,
  the stats, completion sets, activity and pinned collections.

**Proposed:** a Highlights panel on Home, with rows to choose from:

- Top rated: your 4½ and 5 star films on the shelf.
- Most rewatched.
- Most valuable discs.
- Best disc reviews, once 8 is built.

**Craig's call:** which rows; and does "top reviews" mean your own ratings, or the critics'
from 8?

**Answer (30 Sep):** a mix of all: the four rows, your ratings and the critics' both (V5; the
reviews row arrives with V10).

---

## The full plan: for approval, not started

**Everything left, in one order:** the ten Group V batches from these snags, and Group U's
open batches with their gates unchanged. The criteria are in `docs/phase-batches.md`, under
"Group V". The V numbers were re-cut after Craig's answers, so they follow the order and
differ from the first draft of this document.

| Step | Batch | Covers | Gate |
|---|---|---|---|
| 1 | **V1** Top bar and tints (a fix) | 7 | Craig's go on this plan |
| 2 | **V2** Back arrows, and Loans always shown | 5, 3 | After V1, which changes the same top bar |
| 3 | **V3** Movie night on one screen | 4 | None |
| 4 | **V4** Craig's house | 6 | None |
| 5 | **V5** Highlights on Home, three rows | 9 | None |
| 6 | **V6** Trial: pricing from live bids | 2 | Built without a gate; Craig runs it from Home |
| 7 | 20b Shops that answer `429` | — | Craig's go, after the 1 Oct 03:00 UTC check (Group U) |
| 8 | 21 Price history charts | — | Starts itself once 3 wants have two shops' prices on two days, 2 Oct at the earliest (Group U) |
| 9 | 22c Every page of a sale | — | Craig's go, after 20b (Group U) |
| 10 | **V7** Value from live bids | 2 | Craig's pick, after V6's report |
| 11 | **V8** The Deals "usual" price, and the sold-listings link | 1 | After V7, whose eBay figure it averages |
| 12 | **V9** Review links, found with Brave | 8 | Brave credit, and a cap of its own |
| 13 | **V10** Review scores, and Highlights' fourth row | 8, 9 | Real pages captured; AVForums' terms read |
| 14 | T8b Connect eBay | — | `OWNER-ACTIONS.md` 18 (Group U) |
| 15 | 38 The end-to-end suite | — | Last, after every V batch, so it pins the flows as they end up |
| — | 33 → 34 Email | — | Parked (`OWNER-ACTIONS.md` 7) |

**Why this order.** V1 to V5 need nothing from anyone and are what Craig sees every day, so
they go first; V1 goes before V2 because both change the top bar. V6 costs a few hundred eBay
calls and nothing else, so its report can be waiting when the pick is due. Steps 7 to 9 keep
Group U's gates and slot in whenever those clear. V8 averages V7's eBay figure, so it waits
for V7 rather than being built twice. V9 waits for Brave's credit, and V10 for pages that this
session could not reach.

**What Craig does, and when:**

- **Now:** say go on the plan, or change it.
- **V6:** press "Try bid prices" on Home, then pick blend or bids only from its report.
- **V9:** raise Brave's monthly limit, or accept that reviews wait for each month's credit
  once the spec backfill has used it.
- **V10:** let the building session reach blu-ray.com and avforums.com (this one could not),
  so the pages are captured and AVForums' terms read before any code.
- **V3:** the two-phone match check, as for T4.

**Effort:** V1 to V5, V8 and V9 high; V6, V7 and V10 extra high. Sizes are in the ledger.

---

## Evidence

- Tailwind: a build of `apps/web/src/index.css` with `apps/web/tailwind.config.ts` and
  Tailwind 3.4.19 over `apps/web/src/**`. `.bg-background\/94`, `.bg-popover\/96`,
  `.bg-success\/12`, `.bg-quality-4k\/14` and `.bg-primary\/88` are absent from the output;
  `.bg-brand-ink\/70` and `.backdrop-blur-md` are present.
- eBay: `tests/fixtures/ebay_browse_blade_runner_2049.json` (requested with no filter: 200
  listings, 122 Buy It Now, 77 Buy It Now or Best Offer, 1 auction with Buy It Now, none
  auction-only) and `ebay_browse_jaws.json` (200 listings, no auctions).
- The top bar's class: `git log -S'bg-background/94'` finds it first in `9afc173`, "rebuild
  the application shell", 10 Sep.
- Shop prices: `run_scrape` in `services/scraping/runner.py` checks every enabled shop for
  every active want and nothing else; `price_checks` rows carry a `wanted_id`.
- Decisions: #16, #110, #126, #129, #154, #157, #159, #202, #203, #207, #209, #218, #223, #228.
