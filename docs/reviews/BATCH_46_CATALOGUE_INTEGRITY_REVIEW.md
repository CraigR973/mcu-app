# Batch 46 — Catalogue integrity review (wave 1, pass R4)

**Pass R4** · reviewed SHA `527522d` · lens: film archivist and physical-media cataloguer (CT) · read-only ·
paid calls: none (50 of the 80 free TMDB calls). Written 11 Oct 2026.

## 1. Summary

Grade **C**. The shelf is recorded faithfully and T9 identifies well; the 8 Sep import's identifications
are wrong about once in 40, look certain, and nothing tells anyone.

1. **Correct and safe:** 30 copies are confidently the wrong film (CT46-01), 27 of them from the 8 Sep
   import, and 15 imported watches sit on a different film of the same name (CT46-02). Every one of the
   1,880 sheet rows has its copy, with the same formats, place and shelf text.
2. **Honest:** where the app is unsure it mostly says so (201 copies honestly unidentified, 35 TV sets set
   aside), but an identified film carries no doubt anywhere, editions are inferred and shown as the copy's
   (CT46-05), and the app's own year checks blame the disc page, not the film (CT46-03).
3. **Doing its job:** "do we own it?" answers no for 20 of the 30 misidentified films and for films split
   across two rows (CT46-04), which is how duplicates get bought and wants raised for owned films.
4. **Noticed:** no. The spec job has already flagged 8 of the 30 as "the page is for a 1957 film and this
   one is from 2007" and asks Craig to pick another page; 166 identifications have waited 16 days untouched.
5. **Cheap to run and change:** yes. The stricter rule exists (T9: 25 of 25 sampled right, and it gets the
   probed wrong rows right or asks); the fix is to run it over what the older paths decided, then retire them.

## 2. Findings (7: 1 High, 3 Medium, 3 Low)

### CT46-01 — High — 30 copies are confidently the wrong film, and nothing marks them
- **Evidence:** `computed` — every identified copy (1,679) checked against its own sheet row: the person
  the sheet groups it under (sub-category), any year in the title, TMDB votes and genres. 30 are wrong:
  27 of the 1,115 copies the 8 Sep import (and the 18 Sep refresh) matched, 3 of the 404 the diary import
  identified, 0 of the 156 T9 identified. Examples: *GoodFellas* on a 2016 "Good Fellas" with 0 votes;
  *Spider-Man* on a 0-vote 2015 "Spiderman"; *The Bridge on the River Kwai* (4K, Alec Guinness grouping) on a
  2007 documentary; *The French Connection* on *French Connection II* (both copies); *Ghostbusters II* on a
  2014 documentary; *The Night of the Hunter* on a 1991 TV film; *Arsenic and Old Lace* (Capra grouping) on a
  1962 film; *Dangerous* (Bette Davis) on 2021; *House by the River* (Lang) on a one-vote 1986 film;
  *Band of Brothers*, *Rome*, *11.22.63*, *Planet Earth II*, BBC *Life* and the 1979 *Tinker Tailor* on films
  of the same name; *King Kong [1976]* on 2005; *Holiday* (Cary Grant) on *The Holiday* (2006).
  `observed` — TMDB, 20 searches: each real film exists with 14 to 21,553 votes, and 20 of the 22 real ids
  are not in the catalogue at all. The people's own diaries name the real film for 9 of them.
  `proved` — the real `MatchingEngine` with crafted TMDB pages: a sheet title written without "The" is an
  exact hit for an obscure namesake (1.000) while the real film scores 0.90–0.95, so there is no tie and
  #31's ambiguity flag never fires; the scoring prefers "French Connection II" (0.919) to "The French
  Connection" (0.900), and a 0.9 floor for any title containing the query takes "Ghostbusters 2" to the
  documentary (0.900 against 0.897); "(TV)" and a bracketed "[1976]" are stripped before the year is read.
  One results page is read: the 1935 *Dangerous* cannot have been on it, or it would have tied. The engine
  never reads vote counts. The diary path wrote a watched film onto an owned one by title (CT46-02's rule:
  a 2005 watch identified the 1976 *King Kong* disc; a 2017 *Life* watch, BBC's *Life*).
  The shipped T9 rule on three of these rows, live: identifies *The Bridge on the River Kwai* (1957) from
  the grouping, and asks about "Good Fellas" and "French Connection" (24 TMDB calls).
- **Sampled rates** (25 a stratum, `random.Random(46)` over copy ids): import 24 right, 1 wrong
  (*11.22.63*); diary 23 right, 2 undecidable from the record; T9 25 right; set aside 25 right.
- **What the user experiences:** another film's poster, cast, year and overview; 3 copies carry another
  disc's specs and 2 another film's Blu-ray.com score (*French Connection II* 3.5, *King Kong* 2005 4.5);
  16 carry a value (£304 in all) priced against the wrong film's record; 23 watches hang on the wrong film.
  Search, recommendations, the add form and the scanner treat *GoodFellas*, *Spider-Man* or *The Good, the
  Bad and the Ugly* as not owned and offer "add to wanted", so a duplicate is one tap away.
- **Fix and cost:** (1) run T9's `Identifier` as a dry run over the 1,109 import-matched and 397
  diary-identified films (no Brave; about 10 TMDB calls a film, free) and put every disagreement in the
  Identify queue with its evidence; Craig settles them (the 30 above, plus whatever the run finds) through
  the existing pick, which merges and is undoable. Three of the 30 share their film row with a correct
  copy (*French Connection II*, *Tinker Tailor Soldier Spy*, *Life*), and a copy cannot be moved to another
  film today, so the row needs "this copy is another film". (2) Retire `MatchingEngine` from the four places
  it still decides or ranks: the collection refresh, the diary import, the film page's "Correct match" list
  and the Identify queue's search. About a day of build, then an hour of Craig's taps.
- **Where it goes:** new row, first in the roadmap's catalogue group; before any fresh sheet import
  (`OWNER-ACTIONS.md` 1k), which would match new rows with the same engine.

### CT46-02 — Medium — 15 watches of one film sit on another of the same name, and the sync uses the same rule
- **Evidence:** `computed` — the 1,566 imported watches joined to the diary rows they came from (by viewing
  id): of the 1,565 whose film has a year, 1,535 agree with it and 30 differ by more than a year. 14 of the
  30 sit on CT46-01's films (13 are watches of the real film). 15 are a different film attached by title: a
  logged *The Heat* (2013) sits on Michael Mann's *Heat* (1995); *Cape Fear* 1962 on the 1991 film; *Carrie*
  2013 on 1976; *The Thing* 2011 on 1982; *Godzilla* 1998 on 2014; *War of the Worlds* 1953 on 2005; *Salem's
  Lot* 1979 on 2024; and eight more. One (*Force of Evil*, two years apart) is probably the same film.
  `proved` — the real `match_entry`: a watch of *Psycho* (1998) is written
  against an owned *Psycho* (1960), and *The Heat* against *Heat*. `implemented` — the matcher drops the
  leading article, and "the year breaks a tie; it never excludes a candidate" (#158, #160) even when both
  years are known. The RSS sync falls through to the same title path whenever the feed's TMDB id is not
  owned, about a third of entries (#158).
- **What the user experiences:** "unwatched" lists, movie night's "seen it" and recommendations read these
  watches, so 15 owned films show as watched when only a namesake was, and the namesakes are nowhere.
- **Fix and cost:** exclude a title candidate whose year is known and differs by more than one; keep "never
  excludes" for year-less rows, which is what #158 was protecting. One hour with tests. Re-pointing the 15
  rows is a data change for Craig's word (most become "not in the collection").
- **Where it goes:** new small row, before the first "Sync now" if it can land by early November (section 4).

### CT46-03 — Medium — The app already sees many wrong films, and sends the evidence the wrong way
- **Evidence:** `observed` — 36 spec lookups carry the note "The page is for a 1957 film and this one is
  from 2007, so its specs were not used. Pick the right page."; 8 of CT46-01's 30 films are among them, where
  the page was right and the film wrong (9 notes; the other 27 are mostly wrong pages, correctly refused).
  The review job's one "mismatch" is *Dead Man's Shoes*, the want Craig picked from TMDB on 9 Sep, on the
  1940 film. `computed` — 166 Identify proposals have waited since 25 Sep with 0
  decided; the splits in CT46-04 wait among them. `implemented` — neither signal reaches identification: a
  year conflict only parks the disc on Disc specs, and an identified film shows no doubt anywhere.
- **What the user experiences:** Craig is asked to find another Blu-ray.com page for *The Bridge on the River
  Kwai* when the fix is to say which film it is; the app knows and says the opposite.
- **Fix and cost:** when a disc's page or review names the copy's own sheet title in another year, add an
  Identify proposal ("this copy may be the 1957 film") instead of the "pick the right page" note, and show
  "identification in doubt" on the film page while one is open. About half a day. **Guard:** the daily check
  (DS44-01) counts identified films whose page or review names another year, and open proposals older than
  a fortnight.
- **Where it goes:** fold into CT46-01's row.

### CT46-04 — Medium — The same film held as two rows, so "do we own it?" says no for films on the shelf
- **Evidence:** `computed` — 31 groups of films share a title (the diary rule, article dropped); most are
  genuinely different films (*Fury*, *Gaslight*, *The Killers*, three *Mummy*s). Five are one film split in
  two: the *Misery* disc is on an unidentified row while its 2 watches are on the 1990 row; *Sorcerer* (1977)
  is an active want while its download sits on an unidentified "Sorcerer, The (1977)", so the want says not
  owned; *Goodbye, Mr. Chips* and *The Da Vinci Code* likewise; *Crime and Punishment* (1935) has its watch
  on one 1935 version and its download on the other. 8 copy-less film rows were left behind when the 18 Sep
  refresh minted new rows for ambiguous titles (*Dunkirk*, *Titanic*, *Halloween*…). `implemented` — the add
  form's duplicate check and TMDB search mark "in collection" by TMDB id only, so an unidentified twin is
  invisible (Search's own lookalike check is not used there). `observed` — on 10 Oct a scanner add of
  *Invasion of the Body Snatchers* (1978) met no duplicate prompt beside an unidentified Blu-ray of that title
  on Front 4th; and two copies of *12 Angry Men* were added under one barcode, one as 4K and one as Blu-ray,
  each through the prompt as "another copy", where #101 would make one combo copy.
- **What the user experiences:** a disc on the shelf is "not owned" on the add form and on its want; watch
  history and the disc disagree; one gift counts as two copies.
- **Fix and cost:** use Search's lookalike rule (unidentified owned titles) in the add form and the barcode
  flow; warn when a barcode is already on a copy; T9's queue already proposes the merges, so they cost Craig
  taps, not code. About two hours. Removing the 8 empty rows is a data change at Craig's word.
- **Where it goes:** new small row after CT46-01.

### CT46-05 — Low — Editions are filled from an incomplete search and shown as the copy's
- **Evidence:** `computed` — 146 copies carry an edition; all 146 were filled by the spec job ("the one UK
  edition the search found", #220), none by a person. 16 name a steelbook; the sheet mentions a steelbook on
  no row. `observed` — in three copies' own stored search results the plain UK release was there and was
  excluded only by spelling: *Kill Bill: Volume 1 Blu-ray (United Kingdom)* against TMDB's "Vol. 1", so the
  copy reads "Zavvi Exclusive SteelBook"; *Star Wars: Episode IX - …* against "The Rise of Skywalker"; and
  *Mission: Impossible 2* against "II". `implemented` — the page's film name is compared with the catalogue's
  title rule, which does not equate "Volume"/"Vol." or numerals; T9's `compare` does.
- **What the user experiences:** a copy page states a retailer exclusive that may not be on the shelf. No
  price or alert reads a copy's edition today.
- **Fix and cost:** show an inferred edition as "probably", with its source, until Craig confirms; compare
  release names with T9's title rule. About two hours. **Where it goes:** fold into CT46-01's row.

### CT46-06 — Low — Watch providers are shown without the JustWatch credit TMDB requires
- **Evidence:** `implemented` — the film page and the not-owned film page list TMDB's watch providers; no
  JustWatch credit exists in the web app. TMDB's documentation for that endpoint (read 11 Oct): "In order to
  use this data you must attribute the source of the data as JustWatch", and "we will revoke access to the
  API" for non-compliance. Part D's 7.1 asked for it on 7 Sep. TMDB's own logo and notice are DS44-06's.
- **What the user experiences:** nothing, until a revoked key stops search, identification and the calendar.
- **Fix and cost:** one line under the providers, 15 minutes. **Where it goes:** fold into DS44-06's row.

### CT46-07 — Low — Completion sets are chosen by any credit, so most actor sets are uncredited extras
- **Evidence:** `observed` — 12 of the 20 actor sets are background players (Bess Flowers, 18 of 353;
  Franklyn Farnum; Kenner G. Kemp…). Director sets count shorts and compilations (Nolan: 8 of 19 owned, and
  6 of the 19 are shorts or compilations), and *Reservoir Dogs* twice. All 40 were chosen on 8 Sep; the 550
  films identified since never re-chose them, so Billy Wilder (17 copies) has no set. `implemented` —
  `candidate_people` counts a person in any billing position.
- **Fix and cost:** count the top ten billed; drop shorts and compilations from members; re-run the refresh.
  An hour. **Where it goes:** the UX row (R6), or defer until a person opens the page.

**Already near-optimal (no change):** the sheet is recorded faithfully (1,880 of 1,880 rows, same formats,
place and shelf text; the two workbooks parse identically but for 2 retitled rows); T9's rule (25 of 25
sampled, TV set aside 25 of 25, and on the probed rows it identifies right or asks); the spec job's year
check and box-set hold (151 grouped discs never auto-accepted); the review job's year check; the refresh's
film index (#198) and history guard (#194, #199); Blu-ray.com scores come from the reviewed edition the
spec page links to, on a format on the shelf, for all 608 owned films (#241); AVForums is links only.

## 3. Follow-through corrections (rows of the pack's table in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| Seed: Dead Man's Shoes | A known wrong match, catalogued as the 1940 film | A want, not a copy: 0 copies, 0 watches; picked from TMDB on 9 Sep; the review job flagged it on 4 Oct ("the page is for a 2004 film") | `observed` |
| T9 counts | 156 auto, 35 set aside, 166 waiting | Confirmed; 0 of 166 decided since 25 Sep; the 156 sampled 25 of 25 right | `observed`, sample |
| 210 films without a TMDB id | 201 owned | Confirmed; their 201 copies have 0 specs, 0 scores, 145 a value by title | `observed` |
| Disc specs | 729 done automatically, 525 waiting | Confirmed. The 525: 176 no UK page matched, 155 several UK editions, 88 no year on the film, 48 box sets, 36 year conflicts (CT46-03), 22 no UK page | `observed` |
| 146 copies with an edition | U2's editions | All 146 inferred by the spec job, none by a person (CT46-05) | `observed` |
| Reviews | 616 scored, 72 found, 47 no review, 1 mismatch | Confirmed; 608 via the copy's spec page (536 of them a different release, the reviewed one, by design), 8 by Brave for wants; the mismatch is Dead Man's Shoes; 2 scores are of a wrong film | `observed` |
| Scope 6, watch history | Stops at the 20 Sep import; sync never run | Confirmed: last row written 20 Sep 10:29, last watch dated 14 Sep, 0 syncs. Deadline in section 4 | `observed`, `computed` |
| LIVE: 1,884 copies | Live copies | Includes the sheet's junk row "Test 15.04.26" (no format, no place; T9 set it aside as not a film) and Mark's 4 scanner adds of 10 Oct, two of them one barcode | `observed` |
| R3 note 5 | 22 titles shared by 52 films; judge as duplicates | By the diary rule, 31 groups of 70 films; most are different films; 5 are one film split (CT46-04) and 8 are copy-less leftovers of the 18 Sep refresh | `computed` |
| R1, CR43-03 | Four title rules disagree; R4 to judge the matching impact | The differences that moved identifications are the import engine's kept leading article and its 0.9 floor (CT46-01), and the diary rule's dropped one (CT46-02), not "&". A shared title key should start from T9's `compare`, the only rule that handles numerals and the sides of a colon | `proved` (both probes) |
| Spreadsheets | Two untracked workbooks | Both parse to 1,880 rows through the real parser; they differ in 2 titles (*A Christmas Carol*, *The Secret Identity of Jack the Ripper*); every row has its live copy | `computed` |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| `OWNER-ACTIONS.md` 1j, press "Sync now" | Accurate, and now dated. At 5–6 entries a week, Mark's 50-entry feed stops reaching back to 15 Sep around **10–19 Nov** (`computed` from his diary's last 8 and 26 weeks); after that his viewings since the import are lost to the app for good (#161: it never scrapes). Craig's lasts to about March. Each person syncs their own. Decayed: "a cron is not possible yet" — the jobs have run nightly since 23 Sep, so a weekly sync can be scheduled (a guard) |
| "166 films to identify" | Accurate; 0 decided in 16 days. The splits (CT46-04) and two obvious ones (*Lion King (Animation)*, *(Live Action Movie)*) wait here |
| "525 discs on Disc specs" | Accurate count; 8 of the films behind it are misidentified, and the queue asks for another page (CT46-03) |
| Dead Man's Shoes, "Correct match" | Accurate: the film page's pick re-identifies the want. Its candidate list still ranks with the old engine (CT46-01) |
| `OWNER-ACTIONS.md` 1k, a fresh sheet import | Still open; it would match new rows with the old engine, so CT46-01's step 2 goes first |
| 21, 22c, 33–34, 38, T8b | Not this lens |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**For reconsideration.** #31: the ambiguity rule sees only exact ties, and 27 import matches were wrong
without one; new evidence that a confident match needs T9's rival test, not a tie test. #158/#160 ("the year
breaks a tie, never excludes"): right for year-less rows, wrong when both years are known (15 watches,
CT46-02). #220 ("the one UK edition the search found" is the copy): three counter-examples in stored results
(CT46-05).

**Hypotheses** (no proof yet):
- The import stratum holds more wrong films than the 27 the sweep found: the sweep needs a grouping, a year,
  low votes, a genre clash or a long-title match to see one; T9's dry run (CT46-01) is the measurement.
- Doubtful, not counted: *No Way Out* (a Film Noir row on the 1987 film; its page is 1950), *Alice in
  Wonderland* (1951 film; a 2010 watch and a 2010 page), *Last Chance to See* (a series on a 7-vote film
  entry), *Jack the Ripper* (a Blu-ray on a 1988 TV documentary), *Project X*, *A Christmas Carol*.
- The 10 Oct *Body Snatchers* scan may be a second copy of the unidentified Blu-ray already on the shelf.
- 3 of the 6 discs from a Columbia box set (named only in the category, not the grouping) were given
  standalone spec pages; their specs may be another release's.

**Limitations.** Right-or-wrong judged from the sheet's words and grouping, the format, TMDB's record and
the people's diaries; no live Blu-ray.com (editions judged from stored search results only). Samples of 25
bound rates loosely (0 of 25 wrong still allows about 11%). The diary files were read on the Mac for counts
only. No local Postgres was needed: no test was run in this pass.

**Probe log** (11 Oct; full list in `scratchpad/wave-1/r4/probe_log.md`):
- Production, read-only role: 54 SELECTs, column-projected; the largest the live copies with their films
  (1,884 rows, 1.4 MB JSON), all films (1,890 rows), key credits for grouped films (~16k rows, 1.2 MB), spec
  candidates for the 146 edition copies (0.8 MB); no `movies` overview or credits JSON, no photo data.
- TMDB, app token read inside the script: 26 calls at 14:34 UTC (20 film and 6 TV searches) and 24 at 14:37 UTC
  (T9's Identifier on 3 rows, no Brave). 50 of 80. Brave, Blu-ray.com, eBay, shops: none. Paid: none.
- Read: TMDB's watch-providers documentation page (attribution terms).
- Local, scratch only: both workbooks through the real parser; the real `MatchingEngine`, diary `match_entry`
  and T9 `Identifier`; the diary CSVs joined to `watch_log` by viewing id. Nothing committed but this report.
