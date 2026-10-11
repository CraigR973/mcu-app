# Batch 47 — Prices, value and deals review (wave 1, pass R5)

**Pass R5** · reviewed SHA `527522d` · lens: physical-media dealer and price analyst, with a
consumer-protection eye (MK) · read-only · paid calls: none. Written 11 Oct 2026.

## 1. Summary

Grade **D**. Both numbers that steer spending mislead: about a quarter of the deal pushes named the wrong disc,
and the collection's value rests on new copies' asking prices. The labels are honest about "asking prices".

1. **Correct and safe:** no. 25 of 265 eBay finds (9%) were another film, a disc with no case, a Blu-ray scored
   as 4K or a Region A disc; a used copy is judged against New whenever its own group is thin; the scan has
   been blind since 9 Oct (MK47-01, MK47-02).
2. **Honest:** partly. Every value says "asking prices" and that they run high; nothing says "new copies", a
   push names the owned film rather than the listing, and shop deals stay up undated for 11 days (MK47-03, -07).
3. **Doing its job:** not this fortnight. The only alert for 9 of 10 wanted films is the blind scan, shop prices
   are never shown, and the value reads about 1.4–1.8× what the discs ask used (MK47-02, -03, -05).
4. **Noticed:** no. 33 blind runs ended "finished"; a wrong deal reads like a right one (MK47-02, DS44-01).
5. **Cheap to run:** yes on eBay (far inside 1,250 of 5,000 calls a day); no on the shop check (30 minutes a
   night on three shops that refuse); eBay's licence clause on modelling prices is unexamined (MK47-04, -05).

## 2. Findings (7: 2 High, 3 Medium, 2 Low)

### MK47-01 — High — About a quarter of the deal pushes Craig received were not the disc they named
- **Evidence:** `computed` — of the 265 eBay deals stored from 26 Sep to 9 Oct, **25 (9%) are a different
  product from the film and format they were filed under**, by explicit rules over the listing titles plus a
  hand check: **14 another film** with the same title (*Halloween* 2018 ×2, *Wonder Woman 1984*, *Invasion of
  the Body Snatchers* 1978 ×2, *Night of the Living Dead* 1990, *Mary Queen of Scots* 2018, *IF* 2024, *The
  Day the Earth Stood Still* 2008, *Road House* 1989, *Maggie* 2015, *Titanic* 1997 ×2, *Dunkirk* 2017; the ten
  remakes and sequels confirmed on TMDB as separate films, 10 calls; the listing itself names Nolan's
  *Dunkirk*); **7 a disc with no case** ("disc only", "no case"); **2 a
  Blu-ray scored as a 4K** ("Not a 4K Blu-ray release", "remastered in 4K"); **2 a Region A Blu-ray**.
  **14 of the 60 deal pushes delivered to Craig (23%) were among them**, for example "Halloween on 4K: £9.68
  … 66% under its usual £28.58. It would be an upgrade on the copy on the shelf." for the 2018 film's disc
  with no case. Mark's 66 deal pushes were never delivered (DS44-02).
- `proved` — crafted listings through the real scan matcher (`Catalogue.named_in`), `match`, `yardstick` and
  `is_deal`: a year after the title is skipped, so "Halloween (2018)" and "Road House 1989" file under the
  owned film; "1984" after "Wonder Woman" reads as a year, not a sequel; "disc only", "no case", "empty
  steelbook, no disc", "damaged case, scratched disc" and "Region A" all pass; the format is the highest one
  named, so "Not a 4K Blu-ray release" is a 4K; a TV "Complete Series" passes as the film.
- `observed` (live, 14 item calls) — of 12 still-listed deals drawn at random from those judged against the
  New median, **3 were used copies** (one Like New, two Very Good). `implemented`: `yardstick` uses the
  listing's own condition group only when that group has 3 or more listings, otherwise the largest group;
  227 of the 265 deals were judged against the New median. #239's "eBay's own part stays condition-matched"
  holds only when the group has three.
- `computed` — 22 of the 265 usual prices rest on 3 or 4 listings. Young Frankenstein's "Like new" group of 3
  (£42.99) sat above its 28 new copies (£13.94) and made a £6.03 listing "86% under".
- **What the user experiences:** a push naming a film he owns, "X% under its usual", for a disc that is a
  different film, has no case, is only a Blu-ray, or is used. The push never shows the listing's own title or
  condition; the Deals card shows the title, beside the owned film's poster and link. The yardstick for an
  honest saving claim, the CTSI pricing guide (April 2026, §17–18), asks for the same product, and for a
  comparison with new prices to say so; the app is not a trader and the guide does not bind it, but these
  claims would fail it.
- **Fix and cost:** in both matchers, a year straight after the title must be the film's (±1) and a
  four-digit number there belongs to a sequel's title; add incomplete-item phrases (disc only, no case, empty,
  no disc, missing) to the rejections; read "not 4K" and "remastered in 4K" as not a 4K. In `yardstick`,
  compare a used listing with used copies only (pool Like new, Very good and Good when each is thin; no deal
  when even the pool is thin), and never against a group whose median is above New's. Make the push name the
  listing (its title and condition) and say "asking prices, n listings". Tests from these 25 titles. About a
  day (Sonnet · high).
- **Where it goes:** the roadmap's eBay group, with CR43-01 (same files). Guard: those 25 titles as a CI test.

### MK47-02 — High — The blind scan, deal side: about 62 deals missed so far, and the gap cannot be read back
- **Evidence:** `observed` — 184 runs in all. The 9 Oct 00:22 run read 232 listings and stored 21 Oct
  16:35:01 as its mark, 304 hours after its own start; the 33 runs from 9 Oct 02:21 to 11 Oct 18:20 each read
  one page, saw 0 listings and ended "finished". Before that: 2,096–8,645 new listings a day, 59–187 a day
  that were a wanted film or an upgrade, 12–29 deals a day (median 22, 2–8 Oct).
- `proved` — eBay's real first page (one call at 19:13 UTC on 11 Oct: 200 listings from the last 66 minutes,
  strictly newest first) through the real `read_new_listings`: with production's mark it finds **0 of 200** and
  keeps the 21 Oct mark; with the last run's own start time it finds **158**; one listing dated 21 Oct put on
  the same page blinds it again. The 21 Oct listing is no longer on page 1, so it cannot be identified.
- `computed` — at the 2–8 Oct rate, about **62 deals and 12,700 listings** unread by 20:00 on 11 Oct; if
  unfixed, about **279 deals and 57,000 listings** by 21 Oct 16:35. For 9 of the 10 wanted films the scan is
  the only alert there is (MK47-05).
- **What the user experiences:** no eBay alert since 9 Oct, and a Deals page emptying as finds expire after
  three days (the last eBay find expires 12 Oct 00:22).
- **Recovery, and what the mark should trust:** the run's own start time, less a few minutes for eBay's
  indexing, never a listing's date; read as the earlier of the stored mark and now. Overlap costs nothing: a
  find already stored is refreshed, and a push is keyed by listing and person. After the fix the first run
  reads at most 10 pages (2,000 listings, about 11 hours at ~180 an hour), so everything listed from 9 Oct to
  about 11 hours before the fix stays unread; the scan never searches by film. A one-off film-by-film search of
  the 10 wanted films (10 calls) recovers what matters most; reading the whole gap would take about 22 pages
  per blind day, mostly listings that have sold. About two hours, inside CR43-01's.
- **Where it goes:** merge with CR43-01 (R1 owns the class; this is its deal side and its recovery). Guard:
  DS44-01's daily check, "six runs in a row saw no listings".

### MK47-03 — Medium — The collection's value is new copies' asking prices, and its top lines are inflated
- **Evidence:** `computed` — 965 of the 1,300 priced discs, **93% of the £23,604**, are the median of copies
  listed as New. Where eBay has both groups (123 references), a Very good copy asks 0.48 (4K) to 0.53
  (Blu-ray) of the New median, and a Like new copy 0.70–0.71. Valued as used copies, the total is roughly
  **£12,800–£17,200** (rough: DVDs take Blu-ray's ratio).
- `observed` (live, 20 searches through the real estimator) — 16 of 20 stored values are within 20% of
  today's, so the sampled values are stable. **7 of the 20 medians include another product:** TV box sets
  (Westworld: 8 of its 10 New listings are the series), a sequel (*More American Graffiti*, 6 of 21), a
  two-film set, Part One + Two bundles, *Spider Labyrinth* (3 of Labyrinth's 13), *On the Town*, and a
  Blu-ray titled "Not 4K UHD". Four of the six highest values are among them. In four of those six, listings
  at twice the cheapest UK release or more are half the sample or more: Labyrinth 4K £62.99 today while the UK
  release is listed at £24.99; The Naked City £78.97 against £14.96; Dune: Part Two £43.95 against £19.99.
- `proved` — the estimator's matcher accepts another film's words before the title (*Spider Labyrinth*, *Pan's
  Labyrinth*, *More American Graffiti*, *On the Town*, *American Psycho* for *Psycho*), a TV "Complete
  Series", and "Steelbooks" (the plural) as a standard edition. The deal scan's own matcher already refuses
  the first case; the estimator does not.
- `implemented` — Home says "At current asking prices on eBay" and that asking prices run above what discs
  sell for. It does not say "new copies", and its most-valuable list leads with the inflated values. The
  sale panel pre-fills its asking price from the same median.
- **What the user experiences:** a total that reads as what the collection is worth, roughly 1.4–1.8× what
  the same discs ask used; the wrong discs at the top of "most valuable"; a sale pre-filled at £72–£79 for a
  disc whose UK release lists at £15.
- **Fix and cost:** value an owned disc against the used groups when they hold three or more listings, else
  New times the measured factor, and say "as used copies" on Home; reject a content word before the title in
  the estimator, and TV words (series, season, staffel); show the listing count and range on the
  most-valuable list. About a day. **Where it goes:** new row after MK47-01 (same matcher). #209 for
  reconsideration; #237 (asking prices) stands.

### MK47-04 — Medium — eBay's API licence restricts what the value and deal features do, and no decision has weighed it
- **Evidence:** primary source, the eBay API License Agreement (text dated 3 Sep 2025, read 11 Oct): §9.5 bars
  using eBay content, alone or with third-party information, to suggest or model prices for items listed on
  eBay without eBay's prior written consent; §8.1.3 requires displayed listing information to be no more than
  six hours older than eBay's, or to say how much older; §8.1.2 and §3.1(b) require deleting eBay content once
  it is no longer publicly available or no longer needed.
- `implemented` — the value, each deal's "usual" (eBay's median averaged with shop prices), its discount and
  the sale panel's suggested price are all computed from eBay listings; a find stays on the Deals page for
  three days with no re-check, while the push says "Listed on eBay just now"; deal rows keep the listing's
  title, image and price after they expire.
- `observed` — all 265 eBay deal rows found since 26 Sep are still stored, 1 still on the page at 20:00 on
  11 Oct; of the 14 sampled finds, 2–6 days old, 2 had ended and 2 were out of stock. No decision cites these
  clauses: #126 covers production access, #127 the deletion notices, #16 sold data.
- **What the operator risks:** eBay can suspend the keyset, which serves the value, the deals and barcode
  lookups; nothing in the app would say why.
- **Fix and cost:** Craig's decision: ask eBay's developer support for written consent for a private
  two-person use, or record an accepted risk as #110 and #121 did for Blu-ray.com. Either way, the re-check
  and the age line of MK47-07, and stripping title and image from expired eBay rows. Half a day. This is a
  reading of the licence, not legal advice.
- **Where it goes:** a decision for Craig at the synthesis; the three steps fold into MK47-01's row.

### MK47-05 — Medium — For 9 of the 10 wanted films no shop alert can fire, and shop prices are never shown
- **Evidence:** `observed` — 1 of the 10 active wants has a price limit (Cross of Iron, £14, last priced 10
  Sep); a shop alert needs one (`implemented`: it fires when a price crosses below the limit); 2 shop alerts
  ever, both on 10 Sep.
- `implemented` — nothing in the API or the web app shows a stored shop price: only the alert, V8's "usual"
  (1 deal ever) and the 90-day roll-up read them. The Wanted page shows the limit and nothing else.
- `observed` — since 3 Oct the nightly check spends 28–31 minutes waiting the asked 60 seconds on each of
  25–29 refusals (Cloudflare 429s from the three Shopify shops). Powerhouse last priced 3 Oct, Second Sight 4
  Oct; Zavvi, Arrow and 101 Films give 5–7 prices a night that nobody sees.
- **What the user experiences:** a wanted film is found only by the eBay scan, which is blind (MK47-02); the
  shop prices exist but cannot be seen.
- **Fix and cost:** show each want's latest price per shop, with its date, on the Wanted page (the data
  exists; half a day); when no limit is set, alert on a shop price under the film's usual; ask the three
  refusing shops weekly rather than nightly until `OWNER-ACTIONS.md` 28 is done, which turns a 30-minute run
  into about 2. Half a day to a day. **Where it goes:** new row in the roadmap's deals group; the cadence is
  Batch 20b's remainder (#238, #240, #247).

### MK47-06 — Low — V8's "usual" counts one shop's price as much as eBay's whole median
- **Evidence:** `proved` (`UsualPrice`): eBay's £20.00 from 15 listings and one Zavvi £35.00 make a usual of
  £27.50. `implemented` and recorded in #239: a used listing is averaged with new shop prices. `computed`: 1
  of the 152 deals stored since V8 carried a shop price.
- **What the user experiences:** rarely anything today; when a wanted film turns up used, a new shop price
  lifts its usual and flatters the discount.
- **Fix and cost:** weight by listings, or use the shops only as a ceiling, and only for New listings. An
  hour. **Where it goes:** fold into MK47-01. #239 for reconsideration.

### MK47-07 — Low — Deals stay on the page long after their price was last seen, with no date on the card
- **Evidence:** `observed` — 6 Zavvi sale-page deals were found once, at 19:14 UTC on 30 Sep, and are still
  on the Deals page on 11 Oct (6 of the 7 deals live at 20:00), each with Zavvi's own "was" price struck
  through (*Ambulance* 4K £17.99, was £34.99, −49%). `implemented` — the sale-page check runs only from an
  admin button (no job runs it; 22c is parked), and a shop's deal has no expiry because "its page is scraped
  again", which nothing does. eBay finds stay three days with no re-check; 4 of 14 sampled had ended or sold
  out within 2–6 days. The card shows no date. One of the six, *Goodfellas* 4K, is a film Craig owns on a
  misidentified record (CT46-01), so the "already owned" filter did not hide it.
- **What the user experiences:** an 11-day-old shop price read as today's.
- **Fix and cost:** "seen 30 Sep" on every card; expire a shop's deal two days after it was last seen; re-check
  an eBay find with one item call before pushing it and when the page shows it. About two hours.
  **Where it goes:** fold into MK47-01's row (MK47-04's compliance steps are these).

**Near-optimal already:** GB sellers only (532 of 532 matched live listings, #144); postage in every deal
price; one push per listing and person, five a day, after quiet hours; rejections counted; stored values stable
(16 of 20 within 20%); eBay calls far inside both shares; the scan's "title opens the listing" rule. Craig's
11 Oct decision (watches of films not owned) adds copy-less film records, which the scan and the value never
read (`implemented`).

## 3. Follow-through corrections (rows of the pack's table in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| LIVE, deals | "87 of 160 eBay 4K and 65 of 105 Blu-ray rows carry a 'usual' price built from other sources" | 152 rows carry `usual_sources` (every find since V8); 151 list eBay alone; 1 deal ever averaged a shop's price | `computed` |
| LIVE, eBay scan | 28 blind runs (to 08:23) | Drift: 33 by 18:20, 184 runs in all; the 00:22 run on 9 Oct read 232 listings and set the mark | `observed` |
| LIVE, deals | 34 active (morning) | Drift: 7 by 20:00, 1 eBay (expires 12 Oct 00:22) and the 6 Zavvi deals of 30 Sep, which never expire (MK47-07) | `observed` |
| Scope 4, valuation | No run on 1–2 Oct; next due 24 Oct (STATUS) | By design (#223): prices fall due 24–26 Oct and the first run with work is 1 Nov 04:00, so values are 36–38 days old when replaced. The job writes no row when idle (DS44-01) | `implemented` |
| Scope 5, shop check | About 29 minutes of retries | The three Shopify shops answer Cloudflare 429s to every request; each of the 25–29 refusals waits the asked 60 s once; 0 alerts queued since 10 Sep | `observed` |
| Seed, Batch 21 | `price_history_daily` 0 rows; Batch 21 waits on it | Batch 21 waits on `price_checks` (a third want with two shops on two days). `price_history_daily` fills only with checks older than 90 days, from about 8 Dec | `implemented` |
| R2 note 5 | `deals_pushed` counts queued, not delivered | Confirmed, and it counts finds pushed to anyone: "5 a day" is Craig's cap; Mark's 66 were queued, none delivered | `observed` |
| R4 note 6 | 16 wrong-film copies carry values (£304) | Accepted, not re-derived: the value searches the film record's title, so a copy on the wrong film is priced as that film | `implemented` |
| DIGEST, #223 | "Fortnightly re-pricing" | Each price is 30–45 days old when replaced, as #223 itself records | `implemented` |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| 21, price history charts | Accurate; still two of the three wants it needs (Castle Freak: 101 Films 12 days, Zavvi 18; Dead Man's Shoes: Second Sight 9, Zavvi 18). Dog Soldiers is one Second Sight day short since 4 Oct and cannot get it while the Shopify shops refuse. Dead Man's Shoes' want sits on the 1940 film (R4), while its shop prices are the 2004 film's |
| 22c and `OWNER-ACTIONS.md` 28, sale pages | Parked, accurate. Decayed in one way: with no job, the one manual run's six deals have stayed "live" for 11 days (MK47-07) |
| T8b, Connect eBay | Accurate: 0 accounts, so nothing in prices depends on it yet; still unproved until Craig connects (`OWNER-ACTIONS.md` 29) |
| T8a price targets | 0 targets ever. The film-and-format kind uses the estimator's matcher, so MK47-01's wrong products would reach it too (`implemented`) |
| V7, value from bids (#237) | Shelved, accurate; nothing in this pass changes it |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**For reconsideration.** #209 (the value is the largest condition group, "often New"): new evidence that New
carries 93% of the total and that used copies ask 0.5–0.7 of New (MK47-03). #239 ("eBay's own part stays
condition-matched"): true only when the listing's own group has three listings; 3 of 12 sampled finds were used
copies judged against New (MK47-01); its "condition is not matched" for shops is MK47-06. #129's three-listing
minimum suits a value; for a saving claim it is thin (22 of 265 finds rest on 3–4). #126 and #127 stand; the
licence clauses in MK47-04 are a new question, not a re-argument. #237 (asking prices) is not re-argued.

**Hypotheses.** (1) The 21 Oct listing was a scheduled or relisted item whose creation date eBay reported
ahead; it has left page 1 and cannot be read back. (2) More finds than the 25 carry a wrong yardstick: the five
*Westworld* finds at 72–81% off were the right film judged against a "usual" made of the TV series (proved live),
and are not counted. (3) A collection-only listing (no postage option) counts its postage as £0 (`proved` in
code, never seen in the 265). (4) Sold prices: the app cannot read them (#16, #126). Comparing about 20 discs'
values with their sold listings would take Craig, signed in to eBay, about 30 minutes; **needs Craig's OK**.

**Limitations.** No sold-price comparison. The condition sample is 12 listings, so "3 of 12" bounds the rate
loosely (roughly 5–57%). Seller identities were not recorded, so "import listings" is read from titles and
prices. Wrong products were judged from listing titles by rule and by hand; the counts are a floor. No test
was run in this pass (none was needed; every probe drove the real functions from scratch scripts).

**Probe log** (11 Oct, UTC; full list in `scratchpad/wave-1/r5/NOTES.md`):
- Production, read-only role: 11 SELECTs, projected, no `movies` JSON or photo data: column lists; 184 eBay
  runs (73 KB); 271 deals with film and reference (201 KB); 134 deal notifications (45 KB, no bodies); 1,454
  valuations (442 KB); 441 eBay references (133 KB); 19 shop-check runs; 11 Oct failures and refusals; prices per
  want and shop; the 10 wants. `live_sql` sends each statement over HTTPS; no session held.
- eBay Browse, keyset read only inside `railway run --service cron-ebay`, database and push variables removed:
  **35 of 50** — 1 at 19:13:50 (the scan's first page), 20 at 19:14:37–55 (the estimator, 20 films), 14 at
  19:17:31–39 (one listing each); 2 token mints; seller fields not kept.
- TMDB, token read only inside `railway run --service api`, every other variable removed: **10 of 10** at
  19:18:14–16. Brave, Blu-ray.com, shops: none. Paid calls: none.
- Read: eBay API License Agreement (edp.ebay.com, text dated 3 Sep 2025: §3.1, §8.1.2–8.1.4, §9.5); eBay's Buy
  API requirements page (no retention rule there); CMA207, *Unfair commercial practices* (HTML, updated 18 Nov
  2025: second-hand status is material, chapter 6); CTSI, *Guidance for Traders on Pricing Practices* (April
  2026, §17–18; not statutory, binds no one but traders, and the app is not one). Evidence is weakest on
  whether eBay would treat a private two-person app's use as §9.5 modelling; only eBay can say.
- Local, scratch only: eBay's real page through the real `read_new_listings`; crafted listings through the real
  `named_in`, `match`, `yardstick`, `is_deal` and `UsualPrice`; the recorded searches through the real
  `listing_from_summary` and `match`; rules and a hand check over the 265 stored finds. No process left running.
