# What a disc really sells for: values and deals — Batch AA10's design note, 21 Oct

**A note, not code.** Nothing was built and no live row was written. Snags 23 (revalue discs)
and 24 (the deals aren't good deals), `docs/owner-snags-2026-10-20.md`; Group AA in
`docs/phase-batches.md`. The build is planned from Craig and Mark's pick (section 9).

**Live data, read only.** The live Neon database was read with SELECTs inside a read-only
transaction (the session also set `default_transaction_read_only`). eBay was called 128 times
through the app's own client and matcher: 83 searches and 45 single-listing checks, 2.6% of
one day's 5,000. Nothing from eBay was stored outside a scratch folder.

## The answer

- **The deals are bad because 75 of the last 90 were New listings judged against New asking
  prices.** Their "usually" was a median 2.2 times the proposal's figure for a used copy (the
  price a quarter of used copies are listed under, postage in). The median "deal" cost 18% more
  than that figure.
- **eBay says when a listing has sold.** A single-listing check still answers for an ended
  listing (25 days later, the oldest tried), with "out of stock", a sold count and an end
  date. So the proposal does not have to guess that a vanished listing sold: it can ask, one
  call each. Of 14 ended listings, 10 had sold and 4 had not: guessing would be wrong more than
  1 time in 4.
- **Values barely move on today's data; deals move a lot.** On 20 discs the proposal's
  stand-in figure comes to 0.91 of today's total. The same figure keeps 23 of the 90 deals.
- **Recommendation: option 3** (section 8). Judge deals against the used figure now, start
  recording sales now, and value each disc on its own sales once it has three in 90 days.
  About 600 extra eBay calls a day, inside the allowance.

## 1. Why the deals feel wrong

| What happened to the 90 deals since 12 Oct | Count |
|---|---|
| Judged against New asking prices | 75 |
| Judged against used asking prices | 15 |
| With a shop price in "usually" | 0 |

- **The brief's "averaged with shop prices" is out of date.** Since X1 (12 Oct) a shop's price
  can only lower a New listing's "usually", and none of these 90 had one.
- **New asking prices sit high.** Shops and long-unsold listings ask more, and the median
  takes them in. A New Blu-ray of *Deep Red* "usually" £26.46 and "41% off" at £15.49 cost
  more than a used copy: used ones ask a median £11.04, and a quarter of them are under £13.50
  with postage.
- **Fresh "deals" sit unsold.** 45 deal listings were checked on 21 Oct: 10 had sold out, 2
  had sold some of several copies, 4 had ended unsold, and 29 were still for sale. That
  includes 7 of the 15 found on 26 Sep, still for sale 25 days later. A real bargain goes fast.

## 2. The three rules, side by side

| Rule | What it is | Can it be computed today? |
|---|---|---|
| **Today** | Median of used asking prices, 3 or more, postage left out; else New's median × the format's measured factor (4K 0.60, Blu-ray 0.58, DVD 0.50) | Yes, stored 15–16 Oct |
| **Mark's** | Mean of the 3 lowest prices in 3 months | Only on current asks, postage in. On sold prices it needs the history below |
| **Proposal** | Median of sold prices, postage in, over 90 days, 3 or more; until then the lower quartile (the price a quarter of copies are under) of current used asks, postage in | Only the stand-in. **No sold history exists yet** (section 4) |

Mark's and the stand-in fall back, as today's does, to New × the factor when a disc has fewer
than 3 used listings. Only Buy It Now listings count for those two: an auction's opening bid
is not a price.

**20 discs**, chosen across formats and price bands (used listings in brackets):

| Disc | Today | Mark's | Proposal |
|---|---|---|---|
| Venom 4K (12) | £8.06 | £8.39 | £9.90 |
| Life of Pi 4K (12) | £11.20 | £9.42 | £10.40 |
| Knives Out 4K (7) | £16.14 | £15.34 | £16.01 |
| The Green Mile 4K (8) | £19.23 | £16.48 | £17.36 |
| The Holdovers 4K (3) | £22.99 | £42.99 | £21.48 |
| Days of Thunder 4K (3) | £39.58 | £48.41 | £32.62 |
| Evil Under the Sun 4K (0, New-based) | £17.86 | £12.86 | £13.39 |
| The Butler BD (39) | £3.05 | £2.38 | £3.44 |
| The Sorcerer's Apprentice BD (23) | £3.58 | £3.06 | £3.82 |
| Reservoir Dogs BD (39) | £4.96 | £5.86 | £6.68 |
| Heat BD (14) | £7.25 | £5.60 | £7.01 |
| American Beauty BD (6) | £10.80 | £10.35 | £10.74 |
| Dark Passage BD (8) | £17.09 | £16.02 | £18.41 |
| Papillon BD (8) | £45.99 | £21.92 | £28.74 |
| The Palm Beach Story BD (2, New-based) | £10.65 | £10.63 | £10.73 |
| Monty Python and the Holy Grail DVD (82) | £2.77 | £2.03 | £3.14 |
| The Seven Year Itch DVD (27) | £3.74 | £2.59 | £3.72 |
| AC/DC: Plug Me In DVD (15) | £5.33 | £4.00 | £5.36 |
| Frankenstein Created Woman DVD (8) | £9.73 | £8.94 | £9.68 |
| The Great Lie DVD (2, New-based) | £7.98 | £7.42 | £7.01 |
| **Total** | **£267.98** | **£254.69** | **£239.64** |

"Today" is the stored value; re-run live on 21 Oct the same rule gave £264.40 (1.3% lower).

**What the table shows:**
- **The stand-in is close to today for most discs** (median 0.98 of today's, range 0.64–1.28),
  because postage roughly cancels the step down from median to lower quartile. On cheap
  discs postage is most of the price: a £1.16 DVD is £3.86 delivered.
- **Mark's rule swings both ways.** With 3 listings it is the mean of all three, so one stale
  £85.99 listing makes *The Holdovers* £42.99 (1.87 of today). With many listings it takes the
  cheapest, which on *Monty Python* starts with a £0.99 copy listed six years ago.
- **Stale listings inflate every asking figure.** 47% of the 566 used listings seen are over
  180 days old, and 32% over a year. On the 28 discs with enough of both, listings over 180
  days old ask a median 1.3 times what those under 90 days ask. They sit because they are
  overpriced, and today's median counts them.
- **Papillon's £45.99 mixes in the 2017 remake.** The valuation search is not told the film's
  year (the deal scan's is), so the Charlie Hunnam disc and £64.99–£79.99 stale asks sit in
  the 1973 film's median. A fix for the build, whichever rule wins.

Mark's instinct is right: asking prices overstate, so look lower. The proposal's sold median
is the same instinct made robust: it ignores the odd damaged copy at the bottom and the odd
collector's ask at the top, where a mean of the three lowest takes in the first.

## 3. For Craig or Mark to check by hand

Each link opens eBay's sold listings in the person's own browser, signed in; the app reads
nothing from it (#16, #228). About 30 minutes for all ten.

**How:** set the filter to Used. Skip steelbooks and limited editions, foreign-region discs,
disc-only or damaged copies, and anything not this film. Note the last five sale prices
**with postage**, from the last 90 days. Reply with the five numbers per disc.

| Disc | Today / Mark's / Proposal |
|---|---|
| [Papillon (1973) Blu-ray](https://www.ebay.co.uk/sch/i.html?_nkw=Papillon+Blu-ray&_sacat=617&LH_Sold=1&LH_Complete=1) | £45.99 / £21.92 / £28.74 |
| [Days of Thunder 4K](https://www.ebay.co.uk/sch/i.html?_nkw=Days+of+Thunder+4K&_sacat=617&LH_Sold=1&LH_Complete=1) | £39.58 / £48.41 / £32.62 |
| [The Holdovers 4K](https://www.ebay.co.uk/sch/i.html?_nkw=The+Holdovers+4K&_sacat=617&LH_Sold=1&LH_Complete=1) | £22.99 / £42.99 / £21.48 |
| [The Green Mile 4K](https://www.ebay.co.uk/sch/i.html?_nkw=The+Green+Mile+4K&_sacat=617&LH_Sold=1&LH_Complete=1) | £19.23 / £16.48 / £17.36 |
| [Evil Under the Sun 4K](https://www.ebay.co.uk/sch/i.html?_nkw=Evil+Under+the+Sun+4K&_sacat=617&LH_Sold=1&LH_Complete=1) | £17.86 / £12.86 / £13.39 |
| [Venom 4K](https://www.ebay.co.uk/sch/i.html?_nkw=Venom+4K&_sacat=617&LH_Sold=1&LH_Complete=1) | £8.06 / £8.39 / £9.90 |
| [Heat (1995) Blu-ray](https://www.ebay.co.uk/sch/i.html?_nkw=Heat+Blu-ray&_sacat=617&LH_Sold=1&LH_Complete=1) | £7.25 / £5.60 / £7.01 |
| [Monty Python and the Holy Grail DVD](https://www.ebay.co.uk/sch/i.html?_nkw=Monty+Python+and+the+Holy+Grail+DVD&_sacat=617&LH_Sold=1&LH_Complete=1) | £2.77 / £2.03 / £3.14 |
| [Barry Lyndon 4K](https://www.ebay.co.uk/sch/i.html?_nkw=Barry+Lyndon+4K&_sacat=617&LH_Sold=1&LH_Complete=1) (deal) | "Usually" £37.38; deals at £24.49–£25.98; proposal £14.69 |
| [Iron Man 4K](https://www.ebay.co.uk/sch/i.html?_nkw=Iron+Man+4K&_sacat=617&LH_Sold=1&LH_Complete=1) (deal) | "Usually" £38.02; deals at £16.19 and £26.04; proposal £16.12 |

The answers settle the stand-in: if used copies sell near today's figures, keep today's median
as the stand-in; if they sell near the lower quartile, use it.

## 4. Recent deals, re-judged

The 90 eBay deals found since X1's fix (12 Oct 20:23 UTC to 21 Oct), each judged against its
film and format's listings as they stood on 21 Oct. Postage is in every price here.

| Rule | Deals kept of 90 |
|---|---|
| Today: 70% or less of "usually" | 90 |
| Smallest fix: 70% or less of the used value | 22 |
| Mark's, on asks: at or under the mean of the 3 cheapest used | 28 |
| Proposal: under the used lower quartile | 32 |
| **Proposal: 10% or more under it** | **23** |
| Proposal, but a New listing against New's lower quartile | 76 |

- **Judged against New's own figure, nearly all New finds pass again** (63 of 75): New asks are
  that high. Judging every listing against what a used copy goes for is what makes a deal mean
  something on a shelf.
- **The 23 kept are 21 films**: A Fistful of Dollars, Avatar, Crimson Peak, Dog Soldiers, For a
  Few Dollars More, Hancock, Shutter Island, Star Trek Into Darkness, Thor: Ragnarok, Westworld
  and Reservoir Dogs on 4K; Innerspace, Near Dark, Night of the Living Dead, Outland, Southern
  Comfort, The Big Country, The Heiress, The Wild Geese, Thief and Village of the Damned on Blu-ray.
- **One kept is suspect:** a New *Reservoir Dogs* 4K at £3.99 against a £15.89 figure is more
  likely a wrong product than a bargain. The push's own listing title is the guard (X1).
- **Caveat:** the listings were read up to 9 days after each find, so the market had moved a
  little. Every deal and its verdict is in the appendix.

## 5. What history the store already holds

**No sold price, and no record of a listing over time, except the deals.**

| Table | Holds | Use for sold history |
|---|---|---|
| `disc_valuations` | 1 row per film and format, overwritten monthly: medians and counts | None: no listing |
| `ebay_price_refs` | 529 rows, medians per condition, overwritten every 14 days | None |
| `deals` | 355 eBay finds since 26 Sep, each with its listing number, price with postage and dates | **The one seed**: each can be checked for sold or not, one call each |
| `valuation_runs` | The 1 Oct bid trial: per-film totals only | None |
| `ebay_accounts` | 0 rows: nobody has connected eBay | None |

The 355 deal listings are biased to cheap ones, so they say whether deal-priced copies sell,
not what a disc sells for.

## 6. eBay calls each rule needs

**Today's use** (UTC day, eBay allows 5,000):

| Job | Calls a day |
|---|---|
| Deal scan, every 2 hours (cap 500) | about 60, most 143 |
| Monthly valuation (cap 750) | 748 on about 2 days a month |
| Film page checks, barcode lookups | not counted anywhere; on demand |

**Extra for each rule:**

| Rule | Extra calls a day |
|---|---|
| Today | 0 |
| Mark's, on asks | 0 |
| Proposal's stand-in alone | 0 |
| Mark's on sales, or the proposal | about 600 (weekly), 300 (fortnightly) |

**Where the 600 comes from:** one search a week for each of about 2,000 film-and-format pairs
(1,466 owned, plus the deal scan's 529), about 285 a day; and one check for each tracked listing
missing from its search, about 300 a day. That second number assumes 7.8% of used listings turn
over each week (44 of 566 were listed in the last 7 days) and allows for 16 of 83 searches
returning more than 200 results, where a listing can drop out of view unsold. **An estimate,
not a measurement:** the first two weeks of the build measure it.

**The weekly pass can replace the monthly valuation search**, since it reads the same listings,
which returns about 1,500 calls a month. Peak use stays under 1,900 of 5,000.

## 7. Risks

- **Damaged, foreign-region, mislabelled.** The matcher rejects Region A and 1 discs, bundles,
  accessories, sequels and overseas sellers, but missed a Region 4 DVD and a "Holy Grail and
  Life of Brian" pair in this sample. A median shrugs off a few; a mean of the three lowest
  does not. Damage is in descriptions, which searches do not return.
- **Withdrawn versus sold.** A vanished listing is not a sale: 4 of 14 ended listings had not
  sold. The single-listing check tells them apart ("out of stock" with a sold count), but eBay
  calls the count "estimated".
- **Best Offer.** 269 of 566 used listings (48%) accept offers, and a sale by offer shows the
  asking price, not the agreed one. Sold medians will read a little high, by an unknown amount.
- **How long eBay keeps answering for ended listings.** 25 days held for every one tried;
  longer is untested. A weekly or fortnightly pass stays inside what was seen.
- **How long the history takes.** The 90-day window fills by late January for a build in early
  November. On the 7.8% weekly turnover and 2 in 3 ended listings selling, a disc with 5 or more
  used listings should reach 3 sales in 90 days: 790 of 1,466 discs (54%). The rest stay on the
  stand-in, so Home must say how many values rest on sales.
- **eBay's licence.** §8.1.2 asks for eBay content to be deleted once it is no longer public or
  needed. A sold-price store keeps ended listings' prices for 90 days. Keeping only the listing
  number, price, postage, condition code and dates (no title, no image), as X1 does for expired
  finds, narrows it; it is still an extension of the risk Craig accepted in #254.
- **Values mix two bases for months.** A disc moves from the stand-in to its sales on the day it
  reaches three, which can shift its value and the total.

## 8. Options

**1. Smallest fix: deals only.** Every listing, New included, is judged against the disc's
used value, still 30% under. Values unchanged.
- Cost: no extra calls, no migration, a small batch.
- Effect: 22 of 90 deals kept. Values keep their stale-listing lift.

**2. The stand-in, no history.** Values become the lower quartile of current used asks, postage
in; deals must be 10% under that, whatever the listing's condition.
- Cost: no extra calls, no migration (the scan's stored figure gains a field), one batch, one
  re-price at the 1 Nov run.
- Effect: 23 of 90 deals kept; the 20 discs' total falls to 0.91 of today's.

**3. Recommended: option 2 now, sold prices as they build.** As 2, plus a weekly pass that
records each tracked used listing and checks the ones that vanish. A disc with 3 or more sales
in 90 days is valued at their median, postage in, and its deals are judged against that.
- Cost: about 600 calls a day; one new table (listings seen: number, film, format, price,
  postage, condition, first seen, last seen, sold or ended), with a migration; a new nightly
  job; a top-tier batch; the licence extension above.
- Effect: deals fixed at once, values on real sales for about half the collection from late
  January, and an honest "based on sales" label where it is true.

**Not recommended: Mark's rule.** On asks it swings from 0.49 to 1.87 of today's figure on these
20 discs; on sales, the three lowest are the damaged and disc-only copies. Its intent survives
in option 3's sold median.

## 9. Decisions for Craig and Mark

1. **Which option?** Recommend 3: the deals are fixed in its first step, and only sold prices
   answer "what does it sell for". Cost: about 600 eBay calls a day, a migration and a new
   nightly job, and three months before half the collection is on sales.
2. **A New listing judged against what a used copy goes for?** Recommend yes: judged against
   New's own figure, 76 of 90 pass and Craig's complaint stands. Cost: a New copy at a fair New
   price is never a deal.
3. **How far under the figure is a deal?** Recommend 10% or more (23 of 90) over merely under it
   (32 of 90): the figure is already the cheap end of the market. Cost: some fair finds go unpushed.
4. **Keep sold prices for 90 days, listing number and price only?** Needed for option 3. It
   extends the licence risk Craig accepted on 12 Oct (#254). Cost: a plausible keyset suspension,
   as #254 already accepts.
5. **The hand check in section 3 before the build is planned?** Recommend yes, about 30 minutes,
   signed in to eBay. It decides the stand-in: today's median or the lower quartile.

## Method and limits

- **The sample:** 20 owned discs, stratified by format (7 4K, 8 Blu-ray, 5 DVD) and by stored
  value band, with one New-based value per format; identified films only, no TV.
- **The searches** used the query stored with each value (`disc_valuations.search_query`) or the
  deal scan's own (title and format, the film's year passed to the matcher), the app's
  `EbayClient`, `listing_from_summary`, `match` and `summarise`, UK sellers only, standard
  editions only. "Today" on 21 Oct is `pricing.used_value` on the format's stored factor.
- **Lower quartile:** linear between the two nearest ranks. **Postage:** eBay's first shipping
  option, as `ebay_watch/listings.py` reads it; none stated counts as £0 (245 of 566 used were free).
- **Listing age:** `itemOriginDate`, from each search's summaries, on 21 Oct.
- **The 45 single-listing checks:** every third deal since 12 Oct (30), and the 15 oldest deals,
  all found on 26 Sep. No check answered "not found".
- **Not done:** no sold price was read; the "probably sold" column cannot exist until a store
  does. The turnover and sales estimates in sections 6 and 7 come from one day's listings.

## Appendix: the 90 deals

"Paid" includes postage. "Usually" is what the deal was judged against. "Figure" is the
proposal's stand-in on 21 Oct. "Kept" is under recommendation 3 (10% under): "just" means under
the figure but by less than 10%. Condition shows as "Used" where it was not stored (before
18 Oct) and the yardstick was a used group. A listing's state is given where it was checked.

| Deal, first seen | Paid | Usually | Figure | Kept |
|---|---|---|---|---|
| Romper Stomper BD, New, 12 Oct, still for sale | £7.85 | £19.00 | £8.20 | just |
| Romper Stomper BD, New, 12 Oct | £9.49 | £19.00 | £8.20 | no |
| Romper Stomper BD, New, 12 Oct | £9.90 | £19.00 | £8.20 | no |
| Romper Stomper BD, New, 12 Oct, 4 sold | £9.99 | £19.00 | £8.20 | no |
| Romper Stomper BD, New, 12 Oct | £10.68 | £19.00 | £8.20 | no |
| Don't Look Now BD, New, 12 Oct | £10.98 | £17.51 | £10.28 | no |
| Don't Look Now BD, New, 12 Oct, still for sale | £10.99 | £17.51 | £10.28 | no |
| Cross of Iron BD, New, 12 Oct | £10.99 | £16.10 | £7.66 | no |
| Cross of Iron BD, New, 12 Oct | £10.99 | £16.10 | £7.66 | no |
| Romper Stomper BD, New, 12 Oct, still for sale | £11.00 | £19.00 | £8.20 | no |
| Romper Stomper BD, New, 12 Oct | £12.95 | £19.00 | £8.20 | no |
| Deep Red BD, New, 12 Oct | £15.49 | £26.46 | £13.50 | no |
| Deep Red BD, New, 12 Oct, still for sale | £15.99 | £26.46 | £13.50 | no |
| Deep Red BD, New, 12 Oct | £16.15 | £26.46 | £13.50 | no |
| Deep Red BD, New, 12 Oct | £18.47 | £26.46 | £13.50 | no |
| Dog Soldiers 4K, New, 12 Oct, sold | £21.99 | £35.11 | £34.99 | yes |
| Near Dark BD, Used, 12 Oct | £22.75 | £41.33 | £33.70 | yes |
| Near Dark BD, New, 12 Oct | £29.99 | £42.99 | £33.70 | yes |
| Thor: Ragnarok 4K, New, 12 Oct, still for sale | £10.54 | £26.04 | £11.59 | just |
| Heat 4K, New, 12 Oct | £24.49 | £35.99 | £16.97 | no |
| Thor: Ragnarok 4K, New, 13 Oct | £10.37 | £26.04 | £11.59 | yes |
| Firefox BD, New, 13 Oct, still for sale | £12.99 | £24.59 | £11.90 | no |
| The Exorcist 4K, New, 13 Oct | £24.44 | £44.99 | £18.20 | no |
| Iron Man 3 4K, New, 13 Oct | £22.41 | £33.41 | £16.22 | no |
| Falling Down 4K, New, 13 Oct, still for sale | £23.99 | £39.49 | £17.99 | no |
| Village of the Damned BD, Used, 13 Oct | £9.98 | £16.15 | £16.52 | yes |
| The Monster Squad BD, New, 13 Oct | £27.95 | £42.95 | £13.54 | no |
| Iron Man 3 4K, New, 14 Oct, sold | £16.19 | £33.41 | £16.22 | just |
| Iron Man 4K, New, 14 Oct | £16.19 | £38.02 | £16.12 | no |
| The Wolf of Wall Street 4K, New, 14 Oct | £13.52 | £28.95 | £12.11 | no |
| The Trial BD, New, 14 Oct, still for sale | £14.89 | £22.99 | £15.82 | just |
| Rosemary's Baby 4K, New, 14 Oct | £22.49 | £32.66 | £18.93 | no |
| Barry Lyndon 4K, New, 14 Oct | £24.49 | £37.38 | £14.69 | no |
| The Heiress BD, Used, 15 Oct, ended unsold | £15.99 | £23.64 | £25.00 | yes |
| Airplane! 4K, New, 15 Oct | £19.36 | £35.39 | £15.00 | no |
| The Long Kiss Goodnight 4K, New, 15 Oct | £22.05 | £31.95 | £18.61 | no |
| Barry Lyndon 4K, New, 15 Oct, still for sale | £25.98 | £37.38 | £14.69 | no |
| Reservoir Dogs 4K, New, 15 Oct | £3.99 | £28.99 | £15.89 | yes |
| The Devil Rides Out BD, New, 15 Oct | £14.32 | £23.79 | £10.97 | no |
| Carrie 4K, New, 15 Oct, sold | £22.95 | £34.49 | £14.32 | no |
| Star Trek III: The Search for Spock 4K, New, 15 Oct | £24.49 | £40.99 | £16.63 | no |
| Iron Man 4K, New, 15 Oct | £26.04 | £38.02 | £16.12 | no |
| Witness 4K, New, 15 Oct, still for sale | £22.58 | £42.29 | £15.34 | no |
| Innerspace BD, Used, 16 Oct | £6.27 | £9.73 | £9.46 | yes |
| Yes Man BD, New, 16 Oct | £5.98 | £20.97 | £4.97 | no |
| Shutter Island 4K, New, 16 Oct, still for sale | £18.95 | £28.71 | £21.28 | yes |
| Deception BD, New, 16 Oct | £9.37 | £23.95 | £9.65 | just |
| Southern Comfort BD, Used, 16 Oct | £15.08 | £26.69 | £17.49 | yes |
| Crimson Peak 4K, New, 16 Oct, 1 sold | £17.00 | £38.11 | £47.18 | yes |
| Star Trek Into Darkness 4K, Used, 16 Oct | £14.38 | £21.50 | £15.38 | just |
| Night of the Living Dead BD, Used, 16 Oct | £6.25 | £10.94 | £14.13 | yes |
| Outland 4K, New, 16 Oct, still for sale | £22.95 | £48.99 | £22.43 | no |
| Barry Lyndon 4K, New, 16 Oct | £24.49 | £37.38 | £14.69 | no |
| The Monster Squad BD, New, 16 Oct | £29.49 | £42.95 | £13.54 | no |
| A Fistful of Dollars 4K, New, 16 Oct, still for sale | £13.89 | £24.00 | £19.66 | yes |
| Pretty in Pink 4K, New, 17 Oct | £25.02 | £38.24 | £18.10 | no |
| Outrage BD, New, 17 Oct | £10.32 | £17.61 | £7.24 | no |
| Star Trek Into Darkness 4K, Used, 17 Oct, still for sale | £13.28 | £21.50 | £15.38 | yes |
| The Wolf of Wall Street 4K, New, 17 Oct | £16.68 | £28.95 | £12.11 | no |
| Witness 4K, New, 17 Oct | £25.78 | £42.29 | £15.34 | no |
| Ghost in the Shell 4K, New, 17 Oct, still for sale | £20.98 | £29.99 | £15.12 | no |
| Hancock 4K, New, 17 Oct | £17.78 | £40.97 | £28.37 | yes |
| Quatermass 2 4K, New, 17 Oct | £87.78 | £142.95 | £65.76 | no |
| Sherlock Holmes 4K, New, 18 Oct, still for sale | £22.49 | £32.99 | £16.06 | no |
| Collateral 4K, New, 18 Oct | £25.02 | £35.77 | £15.29 | no |
| The Big Country BD, Like new, 18 Oct | £10.10 | £17.52 | £16.42 | yes |
| Heat 4K, New, 18 Oct, sold | £23.99 | £35.99 | £16.97 | no |
| The Green Man BD, New, 18 Oct | £6.03 | £14.20 | £6.37 | just |
| The Wrong Arm of the Law BD, New, 18 Oct | £6.03 | £14.16 | £6.47 | just |
| Thor: Ragnarok 4K, Very good, 18 Oct, still for sale | £8.15 | £12.94 | £11.59 | yes |
| The Wild Geese BD, Like new, 18 Oct | £14.99 | £21.99 | £14.93 | no |
| Scanners BD, New, 18 Oct | £14.00 | £22.07 | £13.51 | no |
| Mississippi Burning BD, Like new, 18 Oct, still for sale | £23.45 | £52.99 | £20.50 | no |
| The Monster Squad BD, New, 18 Oct | £24.80 | £42.95 | £13.54 | no |
| Westworld 4K, New, 18 Oct | £24.95 | £57.49 | £28.34 | yes |
| Blow Out BD, New, 18 Oct, still for sale | £42.30 | £61.49 | £24.97 | no |
| For a Few Dollars More 4K, New, 19 Oct | £17.00 | £26.59 | £19.49 | yes |
| Star Trek III: The Search for Spock 4K, New, 19 Oct | £22.49 | £40.99 | £16.63 | no |
| Army of Darkness 4K, New, 19 Oct, sold | £29.41 | £45.99 | £26.69 | no |
| Paths of Glory 4K, New, 19 Oct | £19.99 | £28.83 | £13.38 | no |
| Westworld 4K, New, 19 Oct | £38.78 | £57.49 | £28.34 | no |
| Avatar 4K, Very good, 19 Oct, still for sale | £13.48 | £19.32 | £22.00 | yes |
| Clear and Present Danger 4K, New, 19 Oct | £19.99 | £32.99 | £15.92 | no |
| Outland BD, Very good, 19 Oct | £8.61 | £12.98 | £11.09 | yes |
| Thief BD, New, 19 Oct, still for sale | £12.89 | £18.41 | £32.57 | yes |
| Frankenstein 4K, New, 20 Oct | £29.99 | £42.99 | £20.69 | no |
| Star Trek: The Motion Picture 4K, New, 20 Oct | £37.71 | £56.95 | — | no |
| The Wild Geese BD, Very good, 20 Oct, still for sale | £12.50 | £21.99 | £14.93 | yes |
| The Lion in Winter 4K, New, 20 Oct | £9.77 | £24.49 | £10.28 | just |
| Star Trek II: The Wrath of Khan 4K, New, 21 Oct | £22.49 | £32.99 | £14.17 | no |
