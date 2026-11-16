# Batch 52 — Catalogue integrity review, with cinema listings (wave 2, pass R4)

**Pass R4** · reviewed SHA `1668071` · lens: archivist and cataloguer · read-only · paid calls: none.
Production was read only through `mcu_readonly`; outside reads were 4 TMDB calls and 1 cinema page
(probe log, section 5). People are named by role: the admin and the viewer.

## 1. Summary

Grade **B**. Which film each copy and each screening is: right almost everywhere it was sampled,
and the re-lookups after a corrected match (#378, #380) hold across every corrected film. What is
left is the class wave 1 named, "a fact found for the film it was", surviving through doors the
fixes did not cover: a copy moved to another film, a wanted film with no copy, and a duplicate row
left from the import. Three live wrong-film facts, each found by no guard. 5 findings: 0 High,
0 Med-High, 4 Medium, 1 Low.

1. **Correct and safe:** 39 of 39 series identifications, 69 of 69 film-page corrections whose title
   changed, 15 of 15 cinema reruns and 18 of 18 digest films read right; three live wrong-film facts
   remain (CT52-02, -03, -04).
2. **Honest:** the cinema screens say a stale programme is stale and pause ticket links; Home's
   cinema strip and the digest push do not (CT52-01). An unsure edition says "probably"; a disc
   page the app could not settle waits visibly (416 lookups).
3. **Doing its job:** "do we own it" is right at the cinema (10 of 13 verified cinema films in the
   Archive are linked; the 3 unlinked have no copy). P1 took four cinemas' programmes away from
   18 Nov onward at the snapshot (CT52-01).
4. **Noticed:** every live wrong-film case in this pass was found by a person or by this pass, not
   by the app (CT52-02 to -04). Noticing P1 is DS50-01's.
5. **Cheap to change:** the fixes are small and mostly fold into CR49-02's single "found for this
   film" mechanism; one is a one-tap clean-up for the admin.

## 2. Findings

### CT52-01 — Medium — Four cinemas' programmes froze at 11 Nov's read; the cinema screens say so, Home and the digest do not (P1)
- **Evidence:** `observed` — at 14:30 UTC on 16 Nov, the four ODEONs held 282 future showings, all
  on 16–17 Nov, all `confirmed`, all last seen 11 Nov 08:04; their coverage is `failed` with no
  observed date on all 14 days of the window, so from 18 Nov they list nothing. One read of the
  Kilmarnock page (16 Nov, 14:38 UTC): 50 of the 54 stored 16–17 Nov showings are still listed with
  the same time and title; the other 4 fall beyond the page's 50-entry structured list, so they are
  unproved, not wrong. The stored times are real; the missing fortnight is the loss (the fast-lane
  read found 163–280 showings per ODEON page). `implemented` — the read (`Window.showing`) keeps
  stale rows, withholds their ticket link and marks them `observationStale`; the film page draws
  them dashed with "Saved showing is stale" and "Latest check failed · ticket links paused"; At the
  cinema shows a stale-coverage notice and lists each ODEON as "no current listing · latest check
  failed". Home's strip ("This week at your cinemas") builds from the same cards with no stale word,
  counts the four in "N cinemas" and ranks by cinema count. The digest names only films seen on a
  good read (it cannot announce a stale row) and freezes absence while any cinema failed, but its
  push says "N films newly listed at your cinemas" without saying four were not read.
- **What the user experiences:** At the cinema is honest. Home looks normal and still credits the
  four cinemas for 16–17 Nov; from 18 Nov a film showing only at an ODEON is not shown anywhere, and
  the morning push reads as complete.
- **Fix and cost:** drift: PR 161 (`a2caf8c`, merged 16 Nov) restores the reading from 17 Nov 08:00
  and adds the noticing (DS50-01). Left after it: Home's strip uses the same stale test as At the
  cinema (a short "4 cinemas not checked" line, or omit stale venues from "this week"), and the
  digest adds "N cinemas not read today" when any failed. Two hours with tests.
- **Where it goes:** read-back of PR 161 on 17 Nov (the orchestrator's); the Home and digest words
  as a new small row beside DS50-01's.

### CT52-02 — Medium — A copy moved to another film keeps the old film's disc page and facts
- **Evidence:** `observed` — the 1971 film's Blu-ray copy (wave 1's sheet row 550) carries the
  disc page, video and audio specs of the 1975 sequel's Blu-ray, accepted automatically on 25 Sep
  while the copy sat on the sequel; on 17 Oct a doubt moved the copy to the 1971 film and the page
  stayed. Its review lookup then followed that page and stored `mismatch` ("a 1975 film"), so the
  copy shows no score, the one honest symptom. 1 of the 4 copies ever moved is affected (the other
  three had no page). `implemented` — #380's re-lookup (`specs/backfill.py`) and #378's
  (`reviews/batch.py`) key on `latest_corrections()`, which reads corrections of a film row; a move
  is audited on the copy as `move_copy` and is in neither. `move_copy` re-accepts a page that
  disagreed with the old film, never forgets one that agreed with it.
- **What the user experiences:** the copy's page states the sequel's edition and specs; its link to
  Blu-ray.com opens the sequel.
- **Fix and cost:** treat a move as a correction for that copy: forget its page fields and lookup
  (`forget_page_fields`, as #380 does) and let the 02:00 job search again; a test that moves a copy
  with an accepted page and asserts it is searched again. Two to three hours. Then CR49-02's single
  mechanism (stamp a derived row with the TMDB id it was found for) closes moves, merges and undos
  together.
- **Where it goes:** fold into CR49-02's row; the one live copy is re-looked-up by that fix.

### CT52-03 — Medium — Wave 1's King Kong row is still a phantom second copy of the 2005 film
- **Evidence:** `observed` — the import review sheet names row 878 "King Kong [1976]"; it sits on
  the 2005 film as a second live 4K copy beside row 877, with the same Blu-ray.com page and shelf.
  A 1976 4K copy was added by hand on 16 Oct with the 1976 disc's own page. So the 1976 disc is
  counted twice and the 2005 film shows two 4K copies. `computed` — of the 16 sheet titles that name
  a year, this is the only one now on another film (one other differs by a release year). Of all
  live physical copies, two pairs share film, format and page: this one and two Blu-rays of
  *Hitchcock* (2012), rows 703–704 (hypothesis: a second wrong-film import row; the sheet titles are
  not in the review file).
- **What the user experiences:** a disc that is not on the shelf in the copy count, Collection and
  any put-back or move list; the 1976 film shows correctly.
- **Fix and cost:** the admin deletes row 878's copy in the app (soft delete, undoable) and checks
  the two *Hitchcock* copies on the shelf: five minutes. A guard: a Needs you row when two live
  physical copies share film, format and disc page (two groups today, so quiet). Two hours.
- **Where it goes:** an owner action now; the guard as a new small row.

### CT52-04 — Medium — Nothing checks which film a want is: one has been the wrong film since 9 Sep
- **Evidence:** `observed` — one of the 10 active wants, *Dead Man's Shoes*, sits on the 1940 film
  (no copy, no watch). The nightly shop check has recorded 53 prices since then for the 2004 film's
  Limited Edition Blu-ray against it. The review lookup said on 4 Oct "the page is for a 2004 film
  and this one is from 1940" and stored `mismatch`. No doubt exists for it. `implemented` — X9's
  rule (a review of the film's own title in another year raises a doubt, `doubt_from_page`) runs
  only when a review is read; it shipped on 16 Oct, after this row, and a `mismatch` is never read
  again, so it never fired here. The other stored `mismatch` (CT52-02) correctly raised none: its
  page names another film.
- **What the user experiences:** the wanted list shows a 1940 film with that film's poster and
  facts while its prices are the 2004 disc's; a price chart (Batch 21's third film) would label one
  film with another's prices. The admin has it as an open ask since 14 Nov (correct it on the page).
- **Fix and cost:** the admin's correction, two taps. Then: run X9's rule once over stored
  `mismatch` rows, and raise a want's doubt the same way as a copy's. Two hours with tests.
- **Where it goes:** the open owner ask; the guard folds into CR49-02's row.

### CT52-05 — Low — The cinema title rules are a per-venue list, and three current listings slip it
- **Evidence:** `proved` — `read_title` (`cinemas/identity.py`) driven with the 9 open listings that
  are neither verified nor events: "Members’ Preview: …" with a typographic apostrophe keeps its
  prefix (the rule expects a straight one), "RCS Curates: … + discussion" keeps its prefix, and
  "… - IMAX 2D (18 TBC)" keeps its suffix because of the certificate bracket. All three are known
  films (one a 2007 rerun, one a preview of a film already verified at two cinemas, one a 2026
  release), so each stays an unlinked listing: no rerun label, no digest line, no "who has seen it".
- **What the user experiences:** an older film with a discussion appears as an unmatched listing;
  a preview shows as a separate card from the same film.
- **Fix and cost:** fold apostrophes and dashes before the patterns (CR49-03's `title_key.fold`),
  accept a trailing certificate bracket, and treat "<Name> Curates:" as a prefix; add the three
  titles to the test table. One hour.
- **Where it goes:** fold into CR49-03's row.

## 3. Follow-through corrections (rows of the pack's table in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| CT46-01 doubts | 7 of the 30 still carry an open doubt | 9 carry a decided doubt (6 corrected, 3 moved); 0 doubts are open in all | observed |
| CT46-01 row 878 | probable stray duplicate (hypothesis) | confirmed: the sheet says "King Kong [1976]" (CT52-03) | observed |
| CT46-01 "28 of 30 right" | right film | right film, but row 550 still carries its old film's disc page (CT52-02) | observed |
| CT46-03 year conflicts | fixed (claimed) | fixed for reviews read after 16 Oct; the one older `mismatch` never raised its doubt (CT52-04) | observed, implemented |
| Guard 14 (`identify:year-doubt`) | runs | runs for disc pages and new reviews; blind to moved copies and wants | implemented |
| L1 | 307 stale ODEON rows | 282 still to start at 14:30; read as stale on the cinema screens, not on Home (CT52-01) | observed |
| L9 | 421 `needs_you` lookups | 416 at 14:45; 283 have waited since before October; 622 physical copies have no disc page | observed |
| LIVE "films without a TMDB id: 1" | owned | the 1979 *Salem's Lot* series, its wrong page and specs already cleared by #380; waiting to be identified as a series | observed |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| P1 fast lane, PR 161 (`a2caf8c`) | drift, not judged; its first run is 17 Nov 08:00; the read-back should find the 16–17 Nov rows seen again and 18 Nov onward listed |
| #378 / #380 re-lookups | accurate: of 377 corrected films, 0 copies' disc pages and 0 reviews predate the correction; the 16 Nov batch applied 5 of 9, sent back 1 (*Salem's Lot*, right) and queued 3 |
| Merges (12 since 11 Oct) | near-optimal: every merged copy's page was found after the merge; 0 stale |
| IMDb ratings stamp | near-optimal: 2,330 rated, 0 whose stamp differs from the film's IMDb id |
| Owner ask 1 (*Dead Man's Shoes*) | accurate, open (CT52-04) |
| Owner action 20 (disc specs queue) | accurate; the queue is 416 and ageing (above) |
| X5's 87 doubtful diary entries; owner ask 3 (three copies) | not re-checked in this pass |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**Near-optimal, leave alone.** Series identification (Y3): 39 of 39 right on their stored TMDB facts.
Film-page corrections: 69 whose title changed, each read by hand, all right now (one crossed pair
was put right later the same day). Cinema reruns: 15 of 15 right, including a *Cliffhanger* listing
held to the 1993 film while a remake of that title is dated 22 Jan 2027 on TMDB, which the
famous-classic rule (#339) chose correctly. Forty sampled verified cinema identities: new releases
rest on a matching UK release date, and every one read right. Digest: all 18 appearances ever
right, run labels faithful to TMDB's GB dates. Unsure identities say so in words ("waiting for a
check", "possible duplicate programme").

**For reconsideration:** none of #250–#380 is re-argued. #378 and #380 say "a merge is not a
correction"; this pass found the same is assumed, wrongly, for a move (CT52-02).

**Hypotheses.** *Hitchcock* rows 703–704 may be a second import duplicate (CT52-03). When the
ODEONs return on 17 Nov, a film first listed only at an ODEON during the dark days will be dated
"first listed" 17 Nov in the digest, not when the cinema listed it.

**Limitations.** No Railway reads (token rejected). The spreadsheets themselves are not in the repo;
only the import review file (ambiguous rows only) was read, so the sheet-year sweep covers 16 rows,
not the shelf. No disc was checked against the physical shelf. Wants other than the one above were
not checked against their shop titles (R5's prices).

**Probe log** (all 16 Nov, UTC):
- Database: about 45 projected `SELECT`s through `mcu_readonly` (cinema screenings, coverage, films,
  digest; copies, films, doubts, spec lookups, reviews, wants, audit rows); no credential column,
  no large JSON column selected whole; none left idle in transaction.
- TMDB: 4 GETs with the app's read token (14:33–14:35): three `/movie/{id}`, one
  `/movie/{id}/release_dates`. Wave 2 total now 4 of 100.
- Cinema pages: 1 GET of the ODEON Kilmarnock CinemaTimes page (14:38, 267 KB). Wave 2 total now
  1 of 20 (the fast lane's own reads were its batch's, not the review's).
- Local: `read_title` from the review worktree driven with 14 titles, no database. One untracked
  import review file read in place. Brave: none. eBay: none. Paid calls: none.
