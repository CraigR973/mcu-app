# Owner snags — 30 Sep 2026, reconciled against the code

Craig raised 9 snags on 30 Sep 2026. The same evening, each one was checked against the code
at `8e4c6a2`, the captured eBay payloads in `apps/api/tests/fixtures/`, and the decisions that
govern them.

**Status: reconciled, waiting on Craig's answers.** Nothing is built. The proposed batches are
at the end; they go into `docs/phase-batches.md` once approved.

**Not checked:** anything live. This session had no database access and no sign-in, so
production counts (how many loans exist, for example) come from the code's rules and the last
recorded measurement, not a fresh query. AVForums could not be reached at all: this session's
network policy refuses the host.

---

## Four things to know first

1. **The top bar has no background at all.** It asks for `bg-background/94`, and Tailwind 3
   has no 94 step, so the class is never generated. The bar is see-through, with only a blur.
   Proved by building the stylesheet with the app's own config and Tailwind 3.4.19. **20
   classes in 10 files have the same fault**, among them the bottom tab bar, every badge's
   tint and the format badges.
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

---

## Proposed batches: for approval, not started

| Batch | Covers | Waits on |
|---|---|---|
| V1 Top bar, tints and the Deals wording | 7, 1 | Nothing |
| V2 Back arrows, and Loans always shown | 5, 3 | Nothing |
| V3 Movie night on one screen | 4 | Craig's OK to drop the deck |
| V4 Craig's house | 6 | The name, and shelves or not |
| V5 Value from live bids | 2 | A dry run, then Craig's pick |
| V6 Reviews for Wanted items | 8 | Craig's pick of A, B or C; #110 widened for C |
| V7 Highlights | 9 | Craig's rows; after V6 for review scores |

Each batch's order, model and effort are set when it goes into `docs/phase-batches.md`.

---

## Evidence

- Tailwind: a build of `apps/web/src/index.css` with `apps/web/tailwind.config.ts` and
  Tailwind 3.4.19 over `apps/web/src/**`. `.bg-background\/94`, `.bg-popover\/96`,
  `.bg-success\/12`, `.bg-quality-4k\/14` and `.bg-primary\/88` are absent from the output;
  `.bg-brand-ink\/70` and `.backdrop-blur-md` are present.
- eBay: `tests/fixtures/ebay_browse_blade_runner_2049.json` (requested with no filter: 200
  listings, 122 Buy It Now, 77 Buy It Now or Best Offer, 1 auction with Buy It Now, none
  auction-only) and `ebay_browse_jaws.json` (200 listings, no auctions).
- Decisions: #16, #110, #126, #129, #154, #157, #159, #202, #207, #209, #218, #223.
