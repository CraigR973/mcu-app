# Batch 53 — Prices, value and deals review (wave 2, pass R5)

**Pass R5** · reviewed SHA `1668071` · lens: dealer and price analyst in the UK disc market, with a
consumer-protection eye (MK) · read-only · paid calls: none. Written 16 Nov 2026. Production was
read only through `mcu_readonly`; outside reads were six requests to one shop's search page and
none to eBay, TMDB, Brave or a cinema (probe log, section 5). People are named by role: the admin
and the viewer. Household money totals are kept out of this report; it uses counts and ratios.

## 1. Summary

Grade **B−** (wave 1: D). The value is now honest: it says what it measures on every screen, and
where recorded sales exist it sits 5–8% above them at the median. Deals are the weak half: about
1 push in 18 still names a disc that is not the one filed, a fifth to a third of the deals that
can be checked were not under what the disc has recently sold for, and which five a day reach
the phones is decided by the clock, not by how good they are. One shop has been dark for five
weeks and reads as "no results". 6 findings: 0 High, 0 Med-High, 5 Medium, 1 Low.

1. **Correct and safe:** the value, yes; deals, mostly. 7 of 124 deal pushes since 23 Oct named
   another film or product (MK53-01); two wanted films carry another film's shop prices (MK53-03).
2. **Honest:** every value screen says "used, postage in", how many rest on sales, and that a
   Best Offer may close lower; a deal names its yardstick. The yardstick itself is thin: 94 of 318
   deals rest on exactly three asks, 105 on a scaled New price (MK53-04).
3. **Doing its job:** shop alerts now fire without a limit (5 alerts since 12 Oct), but 5 of 10
   wants had no shop price in the last month (MK53-02); 121 of 124 deal pushes are upgrades, 3
   are Wanted-list finds, and the cap takes the night's finds first (MK53-05).
4. **Noticed:** no. Zavvi's search has redirected every query to a campaign page since 13 Oct and
   the job records "no results" (MK53-02); a wrong-film want's prices raise nothing (MK53-03).
5. **Cheap to run:** yes. The sold-price store keeps its weekly cycle inside 598 calls a day
   (1,870 of 2,121 film-format pairs searched in the last 7 days); no paid call anywhere.

## 2. Findings

### MK53-01 — Medium — About 1 deal push in 18 still names a disc that is not the one filed
- **Evidence:** `observed` — the admin's 124 deal pushes from 23 Oct to 16 Nov (the viewer was
  sent 116 of the same): 5 name another film of the same title, the year betrayed only by cast names (*The
  Invisible Man* 2020 cast filed as 1933; *Road House* 1989 cast as 1948; *Anastasia* by Don Bluth
  as 1956; *The Letter* with Winona Ryder as 1940; *Deception* with Ewan McGregor as 1946); 2 are
  another product (*Captain Phillips* "Blu-ray Mastered in 4K" filed as 4K, 67% under; *The
  Exorcist* 4K "Extended Director's Cut ONLY, No Theatrical Or Blu-ray Copies", a part of the set,
  62% under). Two *Black Sunday* Arrow pushes are unresolved (1960 or 1977). Wave 1 counted 25 of
  265 finds and 14 of 60 pushes. `proved` — the real `match()` at `1668071` passes all seven
  titles for the filed film and format; it refuses "disc only", "case only" and "bundle".
  `implemented` — the year rule reads only a year straight after the title; the "not really 4K"
  rule knows "remastered in 4K" but not Sony's own "Mastered in 4K"; the catalogue never consults
  the cast it already stores (`movie_credits`).
- **What the user experiences:** a push such as "67% under … Filed as Captain Phillips (2013) on
  4K" for a Blu-ray. The push and the card do name the listing and the filed film (X1), so a
  careful reader can see it; a quick one buys a Blu-ray as a 4K upgrade.
- **Fix and cost:** (a) add "mastered in 4K" to the not-4K rule and "ONLY" after a cut name to the
  incomplete rule; (b) refuse a listing that names a cast or crew member absent from the filed
  film's credits while present in a same-title film's (one lookup per candidate, already local);
  (c) the seven titles join `test_ebay_wrong_products.py`. Half a day with tests.
- **Where it goes:** new row in the wave 2 remediation group, beside CR49-02's "found for this
  film" work.

### MK53-02 — Medium — One shop has been dark for five weeks and reads as "no results"
- **Evidence:** `proved` — one read of Zavvi's search for a want ("Dog Soldiers 4K", 16 Nov,
  14:56 UTC) through the app's own `fetch_page`: the search answers 301, then 302 to
  `/c/october/`, a campaign page with no product cards, so the extractor finds nothing.
  `observed` — Zavvi last gave prices on 12 Oct (four wants, three of them limited editions
  it was then selling); every night since it records `no_results` for all 10 wants, and its
  stored note says the shop "may not carry them, or the selectors may have stopped matching".
  The 429s that failed 22–26 checks a night stopped on 23 Oct with no code change; since then
  31 of 36 checks a night are "no results" and none fail. In the 35 nights since 12 Oct, 3 wants
  (*Cross of Iron*, *Near Dark*, *Sorcerer*) have no shop price at all and 2 have one each.
  `implemented` — `FetchedPage.final_url` is recorded but never compared with the search address;
  the daily check's `job:cron-scrape` row reads OK while a shop answers nothing; the weekly
  "refusing shops" ask (X11) counts refusals, not empty pages.
- **What the user experiences:** the Wanted list shows prices from 4 of 5 enabled shops and no word
  that the fifth has not been read since mid-October; a Zavvi sale on a wanted film raises no alert.
- **Fix and cost:** treat a search that ends on a page outside the search path, or a shop with
  "no results" for every want on N nights running, as `refused`, so the existing weekly ask and a
  Needs you row name it; repair Zavvi's address (the trailing-slash search, or its JSON search).
  Two to three hours with tests.
- **Where it goes:** new row, beside DS50-01 (what the daily check watches).

### MK53-03 — Medium — Two wanted films carry another film's shop prices, and one has pushed
- **Evidence:** `observed` — *Bad Lieutenant: Port of Call New Orleans* (2009) holds a 4K want and
  the household's one Blu-ray; the want was added for Batch 21's evidence as "Bad Lieutenant (1992) in 4K, an
  upgrade on the owned Blu-ray" (`DECISIONS.md`), and the film was corrected
  to 2009 on 16 Oct. Since 12 Oct the shop check recorded 27 prices of 101 Films' *Bad Lieutenant
  (1992)* 4K against it, and on 22 Oct both people were pushed "Bad Lieutenant: Port of Call New
  Orleans is £22.00 … Listed as 'Bad Lieutenant (1992) …'". *Dead Man's Shoes* is CT52-04's case
  (R4 owns which film): 26 more prices of the 2004 limited edition since 12 Oct, no alert so far. `implemented` — the shop
  extractor drops a year in a product title as noise ("Bad Lieutenant (1992)" is the comment's own
  example), so a shop's year never meets the want's; nothing checks a want's film (CT52-04).
- **What the user experiences:** a price-drop push and Wanted-list prices for a disc of another
  film; Batch 21's price chart, whose three films include both, would label one film's history
  with another's prices. Which Bad Lieutenant the shelf copy is is R4's and the admin's to settle.
- **Fix and cost:** compare a shop title's year with the want's film (±1, as the eBay rule does)
  and record a mismatch as "another film", not a price; run once over stored `price_checks` and
  hide the mismatched rows from the Wanted list and any chart. Two hours with tests. The admin's
  correction of each want (two taps) comes first.
- **Where it goes:** the open owner ask (Dead Man's Shoes) plus a new one for Bad Lieutenant; the
  rule folds into CT52-04's guard row; Batch 21 waits for both.

### MK53-04 — Medium — A deal's yardstick is thin for half the deals, and recorded sales disagree with a fifth to a third of them
- **Evidence:** `observed` — of 318 eBay deals since 23 Oct, 207 are judged against the lower
  quartile of used asks (64 of them on exactly 3 listings), 105 against New's median times a fixed
  factor (0.62 for 4K, 0.55 Blu-ray, 0.50 DVD; 27 of them on 3 listings), 2 against three recorded
  sales. `computed` — 167 of the 318 have at least one recorded sale of the same film and format
  in the sold-price store: 58 (35%) were priced at or above that disc's median recorded sale; of
  the 52 with two or more sales, 11 (21%). Of the 43 checkable "scaled New" deals, 19 were at or
  above while claiming 32% off on average. `implemented` — `DEAL_RATIO` is 0.90 of the yardstick;
  `MIN_SAMPLE` is 3; wave 1's "no deal when thin" (#129 reconsideration) was not taken; the
  sold-price store backs a deal only where an owned copy's value has three sales, which an upgrade
  format never has.
- **What the user experiences:** "−45%" on a green badge and "45% under £X (new asking median
  scaled to used)" in the push; the words are accurate, but the percentage overstates the saving
  whenever a few asks or a scaled New price sit above what the disc actually sells for.
- **Trading-standards view:** CMA207 (April 2025, DMCC Act 2024) covers traders dealing with
  consumers, so a private two-person tool is outside its scope; its general test (a claim that
  would cause a different purchase decision) still fits a "−45%" built on three asks. Its price
  comparison detail sits in CMA209, not read here (limitations).
- **Fix and cost:** show and push a percentage only when the yardstick rests on 5 or more asks or
  3 or more sales; otherwise say "under the few asks seen"; use recorded sales of the listing's
  own film and format when the store holds any (it tracks deal pairs already). Half a day.
- **Where it goes:** new row; re-measure after AA10c (25 Nov), when the sales store is fuller.

### MK53-05 — Medium — Five pushes a day go to whatever the night finds first, to both people, mostly upgrades
- **Evidence:** `observed` — 24 Oct to 15 Nov: 301 eBay deals, 115 pushed. 33 deals of 40% or more
  were never pushed while 35 pushed ones were under 20%. 121 of the admin's 124 pushes were "an
  upgrade on the copy on the shelf", 3 were Wanted-list finds; both people got the same ones.
  28 of the admin's 123 delivered pushes arrived between midnight and 06:00 UK time; neither person has
  quiet hours set. `implemented` — `queue_deal_pushes` ranks Wanted first, then by discount, but
  only within one two-hourly pass; the cap of 5 is per UTC day, so the 00:20 and 02:20 passes fill
  it before the day's later finds are seen; quiet hours are off unless a person sets them.
- **What the user experiences:** a stream of pushes at night about 4K versions of shelf films,
  while the day's best finds wait silently on the Deals page.
- **Fix and cost:** rank across the day (hold upgrades for a once-a-day summary at a sensible hour;
  push Wanted finds and finds of 40% or more at once); let each person choose Wanted-only; default
  quiet hours 22:00–07:00 Europe/London. Half a day with tests. Whether the viewer wants upgrade
  pushes at all is the household's call (R6).
- **Where it goes:** new row; R6 weighs it against the viewer's own words.

### MK53-06 — Low — Expired deals lose the listing's words, but 488 push rows keep them
- **Evidence:** `implemented` — `clear_ended_finds` replaces an expired eBay find's title with the
  film's and drops its image and condition (eBay licence §8.1.2, §3.1(b), #254's mitigation);
  every deal push stores the listing's title and condition in `notifications`, and nothing prunes
  them. `observed` — 488 deal-push rows since 26 Sep, the oldest 51 days.
- **What the user experiences:** nothing; it widens #254's accepted risk beyond what its
  mitigation claims.
- **Fix and cost:** after a find expires, rewrite its push rows' title to the film's, or prune
  delivered deal pushes after 30 days. One hour.
- **Where it goes:** fold into the next row that touches notifications; #254 stands.

## 3. Follow-through corrections (rows of the pack's table in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| MK47-01 | fixed (matcher) | partly: 7 of 124 pushes since 23 Oct another film or product, three classes the rules miss (MK53-01) | observed, proved |
| MK47-03 / L5 | value fell; 132 of 1,321 on 3+ sales | 1,473 physical copies valued, 1,312 priced, 133 on sales (about 8% of the total), New-scaled 36% of the total; stand-ins 1.04–1.08× recorded sales at the median, quartiles between 0.88 and 1.27 | computed |
| MK47-05 / L6 | 1 of 10 wants has a limit; 31 of 36 no result | alerts no longer need a limit (5 since 12 Oct, 10 pushes); the "no results" are Zavvi's redirect plus shops not stocking; 3 wants unpriced for a month (MK53-02) | observed, proved |
| MK47-07 | oldest active deal last seen 30 Sep | the six Zavvi rows of 30 Sep are hidden by the two-day shop freshness rule; the table count is not the page | implemented, observed |
| MK47-04 | expired deals lose title and image | true for deals; push rows keep them (MK53-06) | implemented, observed |
| L4 | 5 pushes a day, saturated; 15 of 45 on 3 listings | 115 of 301 pushed, chosen by time of day; 94 of 318 deals on exactly 3 listings (MK53-04, -05) | observed |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| AA10c, stand-in settled from sales (25 Nov) | accurate: the store keeps up (1,870 of 2,121 pairs searched in 7 days; 50–87 sales recorded a day; 2 runs abandoned on 11 Nov, none since). Add MK53-04's deal check to its read-back |
| Batch 21, price history charts | decayed: two of its three films are wrong-film wants (MK53-03, CT52-04); build only after both are corrected and the year rule lands |
| Batch 22c, every page of a sale | accurate, still parked on owner action 28 |
| #254, eBay licence (accepted) | stands; residue MK53-06 |

**Near-optimal, leave alone:** the value basis and its words (Home's "Estimated used value", the
method note naming inferred sales and Best Offer, Insights' count of sales-backed discs); a deal
re-checked with one item call before its push; postage in every comparison (UK listings in the
captured pages all state postage; foreign ones without it are filtered out by country).

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**For reconsideration.** #129's "no deal when thin" (wave 1's proposal, not taken in X1): new
evidence in MK53-04. #258 "a used copy is judged only against used copies" was replaced by AA10b's
one used figure for every listing; a New copy judged against a used yardstick is a real saving,
so this is not reopened.

**Hypotheses.** (1) Zavvi's redirect began with an October campaign and may end with it; the fix
should not depend on that. (2) The factor behind "scaled New" is measured on films that have both
used and New listings; films with scarce used listings may be newer or rarer, so the factor may not
transfer. Testable once AA10c's sales accumulate. (3) The viewer's 7 suppressed deal pushes on
14–15 Nov ("no subscriptions") look like a device gap; R6's.

**Limitations.** No eBay call: the rules allow keys only inside Railway's run environment and the
Railway token is still rejected, so no live listing was re-read (all deal evidence is stored rows
and pushes). Recorded "sales" are last advertised prices of listings that sold out, most deals
have one or two of them, and Best Offer closes lower; MK53-04's ratios are indicative. CMA209 and
the 2017 pricing-practices guidance were not read in full. One shop page only.

**Probe log** (16 Nov, UTC; no paid calls; eBay 0, TMDB 0, Brave 0, cinema pages 0):
- Database, `mcu_readonly`, ~30 projected SELECTs, none idle in transaction: columns of 10 price
  tables; valuations by basis and format, joined to owned copies; stored value vs recorded sales;
  deals since 23 Oct by yardstick, sample size and discount; deals vs recorded sales; pushes by
  person, hour and listing; suppressed reasons; notification preferences (switches only); wants,
  shop checks and retailers; scrape runs and failures 21–23 Oct; sold-store runs and scan ages.
- Local, scratch only: the real `match()` and `listing_from_summary()` driven with 13 crafted
  listings; three captured eBay pages in the test fixtures read for postage fields.
- Shop: zavvi.com, 6 requests, 14:55–14:56: two plain GETs and one HEAD (301, 302), then one search
  through the app's `fetch_page` (3 hops, ending 200 on `/c/october/`).
- Web: gov.uk CMA207 landing page and guidance chapters, read once.
- Extracts (pushes, values by basis, wants) stay in the session scratchpad, uncommitted.
