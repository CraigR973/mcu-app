# Wave 1 evidence lists: the cases X1, X5 and X9 test against

Copied on 12 Oct, in the rows step, from the review's scratch folder (`scratchpad/wave-1/`,
gitignored, on Craig's Mac only), so that a session anywhere, cloud or Codex, can read them. They
are the review's judgement at `527522d` on 11 Oct's data: a batch re-checks them against
production (`batch-start.md` step 3) and does not take them as given.

They are described, not extracted. No eBay listing is copied whole, because eBay's API licence is
an open decision (MK47-04): X1's tests craft titles that carry the words quoted here. No watch
says who logged it, under the review's rule on personal data.

## 1. The 25 eBay finds that were another product (X1; MK47-01)

These are the stored deals of 26 Sep–9 Oct that R5 judged to be another product, by rule and by
hand, from the listing titles. • marks the 14 pushed to Craig. "Caught by" names the X1 rule that
refuses each one. **Three carry nothing a title rule can use** (*Maggie* and the two *Titanic* 3D
sets): their only defence is a push and a card that name the listing's own title and condition.

| First seen | Filed under | What it was | The tell, in the title | Caught by |
|---|---|---|---|---|
| 26 Sep | *Dunkirk* (1958), 4K | Nolan's *Dunkirk* (2017) | "(2017)" after the title | year |
| 26 Sep | *We're No Angels* (1955), Blu-ray | a Region A disc | "REGION A" | region |
| 27 Sep • | *Halloween* (1978), 4K | the 2018 film, in a steelbook with a damaged base | "2018" after the title | year |
| 27 Sep • | *The 'Maggie'* (1954), Blu-ray | *Maggie* (2015) | none: the title alone, region-free, no year | **no rule** |
| 27 Sep • | *if....* (1968), Blu-ray | *IF* (2024) | "Blu-ray (2024)" after the title | year, past a format word |
| 27 Sep | *X-Men: Days of Future Past* (2014), 4K | a disc with no case | "NO CASE" | incomplete |
| 28 Sep | *A Clockwork Orange* (1971), 4K | a Blu-ray | "Not a 4K Blu-ray release" | not a 4K |
| 29 Sep • | *Titanic* (1953), Blu-ray | Cameron's *Titanic* (1997), a 3D collector's edition | "3D"; its "2012" sits far from the title | **no rule** |
| 29 Sep • | *Contagion* (2011), 4K | disc only | "DISC ONLY", "NO CASE" | incomplete |
| 30 Sep • | *Halloween* (1978), 4K | the 2018 film, disc only | "(2018)", "DISC ONLY" | year, incomplete |
| 30 Sep • | *Despicable Me* (2010), 4K | disc only | "DISC ONLY", "NO CASE" | incomplete |
| 1 Oct • | *Air Force One* (1997), 4K | a US disc with no case | "NO CASE" | incomplete |
| 1 Oct • | *Source Code* (2011), 4K | a US disc with no case | "NO CASE" | incomplete |
| 1 Oct • | *San Andreas* (2015), 4K | a disc with no case | "NO CASE" | incomplete |
| 2 Oct | *Titanic* (1953), Blu-ray | Cameron's *Titanic* (1997), a 3D box set | "3D", "JAMES CAMERON", no year | **no rule** |
| 2 Oct | *Road House* (1948), 4K | the 1989 film | "1989" after the title | year |
| 3 Oct • | *Invasion of the Body Snatchers* (1956), Blu-ray | the 1978 film | "(1978)" after the title | year |
| 3 Oct | *Night of the Living Dead* (1968), 4K | the 1990 film | "(1990)" after the title | year |
| 4 Oct • | *Wonder Woman* (2017), 4K | *Wonder Woman 1984*, disc only | "1984" after the title, "DISC ONLY" | year, incomplete |
| 4 Oct | *My Fair Lady* (1964), 4K | disc only | "DISC ONLY" (its "1964" is the film's own) | incomplete |
| 4 Oct | *Mary, Queen of Scots* (1971), Blu-ray | the 2018 film | "Blu-ray (2019)" after the title | year, past a format word |
| 5 Oct • | *Army of Darkness* (1992), 4K | a Blu-ray | "REMASTERED IN 4K" | not a 4K |
| 5 Oct | *The Monster Squad* (1987), Blu-ray | a Region A disc | "Region A" | region |
| 7 Oct • | *Invasion of the Body Snatchers* (1956), Blu-ray | the 1978 film | "(1978)" after the title | year |
| 8 Oct | *The Day the Earth Stood Still* (1951), Blu-ray | the 2008 film | "[Blu-ray] [2008]" after the title | year, past a format word |

**Not among the 25.** R5's file tags eight more imports "region-locked". Four are German
(Region B, which plays in the UK and which X1's rule passes). Four are US imports that state no
region: R5 counted none of them, and whether a US import counts as Region A is X1's call. In the
scratch file (`r5/data/deals_classified.json`, field `cat`), the 25 are the 22 tagged as wrong
film, incomplete or wrong format, the 2 region-tagged rows that say "Region A", and *Maggie*,
found by hand and tagged "none". Selecting "`cat` not none" gives 32.

## 2. The 30 copies catalogued as the wrong film (X9; CT46-01)

R4 checked every identified copy against its own sheet row (the grouping it sits under, any year
in its title, TMDB votes and genres), then confirmed the real film on TMDB. "Row" is the copy's
`import_source_row`. 27 came from the 8 Sep import's matcher and 3 from the diary import (D).
**Three share their film row with a right copy** (‡), so X9 moves the copy, not the film.

| Row | Sheet title, format | Catalogued as (TMDB id, votes) | The real film; the tell |
|---|---|---|---|
| 115 | Arsenic & Old Lace, DVD | a 1962 film (609337, 2) | *Arsenic and Old Lace* (1944); Frank Capra grouping; a watch logged as 1944 |
| 138 | Bad Neighbours, Blu-ray | a 2026 film (1372178, 3) | *Neighbors* (2014) |
| 141 | Band of Brothers, Blu-ray | a 2019 film (484744, 6) | the 2001 series; a watch logged as 2001 |
| 231 | Bridge on the River Kwai, 4K | a 2007 documentary (930421, 0) | *The Bridge on the River Kwai* (1957); Alec Guinness grouping |
| 313 | Cloak & Dagger, Blu-ray and download | the 1984 film (48677, 166) | *Cloak and Dagger* (1946); Fritz Lang grouping; a watch logged as 1946 |
| 366 | Dangerous, download | the 2021 film (763788, 526) | *Dangerous* (1935); Bette Davis grouping |
| 550 ‡ | French Connection, Blu-ray | *French Connection II* (10711, 486) | *The French Connection* (1971); #32 names the pair; the row's "French Connection 2" copy is right |
| 592 | Ghostbusters 2, 4K | a 2014 documentary (571906, 3) | *Ghostbusters II* (1989) |
| 614 | Good Fellas, Blu-ray | a 2016 film (626867, 0) | *GoodFellas* (1990) |
| 617 | Good the bad & the ugly, Blu-ray | a 1992 film (1000945, 0) | *The Good, the Bad and the Ugly* (1966); Clint Eastwood grouping; a watch logged as 1966 |
| 635 | Great Wall, Blu-ray | a 1986 film (216472, 12) | *The Great Wall* (2016) |
| 656 | Halfway House, Blu-ray | a 2024 film (1250593, 0) | *The Halfway House* (1944); Ealing grouping; 2 watches logged as 1944 |
| 670 | Harder They Fall, Blu-ray | a 2009 film (280183, 1) | *The Harder They Fall* (1956); Humphrey Bogart grouping; 2 watches logged as 1956 |
| 713 D | Holiday, DVD | *The Holiday* (2006; 1581) | *Holiday* (1938); Cary Grant grouping |
| 714 | Holy Grail, The, Blu-ray | a 2010 documentary (600613, 0) | *Monty Python and the Holy Grail* (1975); Monty Python grouping |
| 728 | House on the River, Blu-ray | a 1986 film (259577, 1) | *House by the River* (1950); Fritz Lang grouping |
| 738 | Hunchback of Notre Dame, Blu-ray | a 2002 film (119406, 0) | *The Hunchback of Notre Dame* (1939); a watch logged as 1939 |
| 878 D | King Kong [1976], 4K | the 2005 film (254) | *King Kong* (1976); the sheet says [1976] |
| 925 | Left Right & Centre, DVD | a 2019 film (1003963, 0) | *Left Right and Centre* (1959); Alastair Sim grouping; a watch logged as 1959 |
| 934 D ‡ | Life, Blu-ray | *Life* (2017; 395992) | BBC *Life* (2009 series), as its spec page says; the row's 4K copy (row 935) is the 2017 film and right |
| 1147 | Night of the Hunter, Blu-ray | a 1991 TV film (243714, 13) | *The Night of the Hunter* (1955); 3 watches logged as 1955 |
| 1254 | Planet Earth II, 4K | a 2017 compilation (596683, 14) | the 2016 series |
| 1335 | Rome, Blu-ray | *Rome*, no year (1550418, 0) | the 2005 series; TV Mini Series grouping |
| 1473 | Spiderman, 4K | a 2015 film (1536316, 0) | *Spider-Man* (2002) |
| 1560 | Tale of Two Cities, DVD | a 1946 documentary (942168, 1) | a *Tale of Two Cities* adaptation, still to name; ITV DVD Box Set grouping |
| 1620 ‡ | Tinker Tailor Soldier Spy (TV), Blu-ray | the 2011 film (49517, 2,996) | the 1979 series; the sheet says (TV); Alec Guinness grouping; the row's 2011 copy is right |
| 1696 | Vacation from Marriage [Perfect Strangers], download | a 1927 film (513801, 1) | *Perfect Strangers* (1945) |
| 1780 | Wonders of the Solar System, Blu-ray | another 2010 documentary (164531, 3) | the BBC series (2010) |
| 1789 | X-Men 2, Blu-ray | a 2005 oddity (758075, 8) | *X2* (2003) |
| 1831 | 11.22.63, Blu-ray | a 1989 documentary (1144348, 1) | the 2016 series |

**Doubtful, not among the 30:** *No Way Out* (a film-noir copy on the 1987 film; its spec page is
the 1950 one), *Alice in Wonderland* (the 1951 film; logged as 2010; its spec page is 2010),
*Last Chance to See* (a series on a 7-vote film entry), *Jack the Ripper* (a Blu-ray on a 1988 TV
documentary), *Project X* and *A Christmas Carol*. X9's dry run decides them with the rest.

## 3. The 15 watches on a namesake (X5; CT46-02)

R4 joined each imported watch to the diary entry it came from, by viewing id. Of the 1,565 whose
film has a year, 1,535 agree with it and 30 differ by more than a year. **15 are a different film
attached by title** (below). 14 sit on section 2's films and are X9's: three on *Night of the
Hunter*, two each on *Harder They Fall* and *Halfway House*, one each on *Hunchback of Notre Dame*,
*Good the bad & the ugly*, *Cloak & Dagger*, *Left Right & Centre*, *Arsenic & Old Lace* and
*Band of Brothers*, and a 1933 *King Kong* on the 2005 film that the "King Kong [1976]" disc was
given. The last, *Force of Evil* (logged as 1948, attached to 1950), is probably the same film.

| Logged as | Attached to (TMDB id) |
|---|---|
| *Alice in Wonderland* (2010) | the 1951 film (12092); if the disc is the 2010 film (section 2's doubtful list), the copy moves, not the watch |
| *An Inspector Calls* (2015) | the 1954 film (18174) |
| *And Then There Were None* (1974) | the 1945 film (4886) |
| *Cape Fear* (1962) | the 1991 film (1598) |
| *Carrie* (2013) | the 1976 film (7340) |
| *Dad's Army* (2016) | the 1971 film (20051) |
| *Godzilla* (1998) | the 2014 film (124905) |
| *Journey to the Center of the Earth* (2008) | the 1959 film (11571) |
| *Obsession* (2025) | the 1949 film (35852) |
| *Salem's Lot* (1979) | the 2024 film (748230) |
| *The 39 Steps* (1959) | the 1935 film (260) |
| *The Enforcer* (1951) | the 1976 film (10649) |
| *The Heat* (2013) | *Heat* (1995; 949) |
| *The Thing* (2011) | the 1982 film (1091) |
| *The War of the Worlds* (1953) | the 2005 film (74) |

**Where they came from** (on the Mac): R4's `r4/probes/wrong_set.py` and `r4/probes/watch_years.py`
over `r4/data/`, and R5's `r5/data/deals_classified.json`.
