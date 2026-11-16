# Batch 54 — Product and UX of the live app (wave 2, pass R6)

**Pass R6** · reviewed SHA `1668071` · lens: product designer · read-only · paid calls: none.
Seen through the rig of decision #250, rebuilt for this pass: the API's own app from the review
worktree, on production data through `mcu_readonly`, every connection `default_transaction_read_only
= on`, every non-GET answered 405, outside calls refused in-process, two fake tokens. The web build
calls the API across origins, as production does. People are named by role: the admin and the
viewer. Screens, text dumps and data stay in scratch.

## 1. Summary

Grade **B** (wave 1: C+). Wave 1's two Highs are mostly closed: by the code, an offline phone now keeps what it
read (UX48-01, not proved on a phone), and failures reach the admin as App rows in Needs you (UX48-02). The snag rounds
since wave 1 landed where they were seen: At the cinema opens on all days, Home's cinema strip
leads with reruns, Closest to complete is a glance, and Needs attention is folded into Needs you.
**The story across R1–R6 is one shape: the app now tells the truth on the screen built for the
problem, but not on the screens people actually look at first.** The cinema screens say four
cinemas are stale, at the foot of a long page; Home, the digest and the daily check do not
(UX54-01, CT52-01, DS50-01). A phone that stops getting pushes is named to the admin, never to its
owner (UX54-02). The viewer's finished answers sit at the top of the admin's Home under the
viewer's name (UX54-03). 6 findings: 0 High, 0 Med-High, 3 Medium, 3 Low.

1. **Correct and safe:** yes on every screen walked; no schema or page error came from the app's
   own data (the only errors were the rig's withheld tables, section 5).
2. **Honest:** At the cinema says what is stale, but only after the last film (UX54-01). A value
   that cannot load says so in words, and counts stay visible.
3. **Doing its job:** for knowing, finding and the cinema, yes. Pushes are the weak path: night
   upgrades to both (MK53-05), and a phone that goes quiet looks like a quiet day (UX54-02).
4. **Noticed:** by the admin, mostly, through App rows; by the person affected, rarely.
5. **Cheap to change:** each fix here is words or placement on an existing screen; none needs a
   new feature.

## 2. Findings (at most ten, Highs first)

### UX54-01 — Medium — When cinemas go dark, only the foot of At the cinema says so (P1, one story)
- **Evidence:** `observed` (rig, data as saved 16 Nov 16:44 UTC, 375 px). At the cinema, day view
  for Mon 16 Nov: under each film the four ODEONs' times are ordinary time chips beside the live
  cinemas'; the only visual difference is that a stale chip lacks the tinted border of a bookable
  one. No word marks them. The four lines "no current listing · latest check failed" come after the
  last film, about line 490 of 506 lines of page text, and the notice "Some saved programmes are
  stale or their latest check failed…" is the last line before the source footer. The top of the
  page says "Cinemas · all 10". The All days view has the same order (notice at line 387 of 395).
  Home's strip "This week at your cinemas" carries no stale word (CT52-01). The digest push and
  the daily check said nothing for five mornings (CT52-01, DS50-01).
- **What the user experiences:** a phone shows one screenful. On it, all ten cinemas look read and
  the ODEON times look like any other. Whoever opens the app to pick a showing sees no warning
  unless they scroll past every film; from 18 Nov a film showing only at an ODEON would simply not
  be there.
- **Fix and cost:** one shared "N cinemas not read since <date>" line, from the stale test the film
  page already uses, at the top of At the cinema (beside the cinema filter) and under Home's strip
  heading; a "stale" word on a stale time chip, not only a missing tint; the digest's "N cinemas
  not read today" (CT52-01). Two to three hours with tests.
- **Where it goes:** beside CT52-01's row in the first sitting. PR 161 restores the ODEONs' reading
  (drift, not judged here); the placement problem returns with the next venue that fails.

### UX54-02 — Medium — A phone that stops getting pushes is named to the admin, never to its owner
- **Evidence:** `observed` (orchestrator's re-check, 16 Nov): the viewer's pushes 9–16 Nov were 44
  sent, 1 failed (14 Nov), then 8 suppressed for no subscription on 14–15 Nov, sending again on
  16 Nov. `implemented`: the daily check's `check_people` writes "<person> has no phone getting
  notifications" and the all-undelivered case as App rows, which only the admin's Needs you shows.
  Nothing on the viewer's own Home or Settings says their phone stopped. Beside it, MK53-05: up to
  five deal pushes a day to both people, 121 of 124 upgrades, 28 of 123 delivered between midnight
  and 06:00 UK time, no quiet hours set by either.
- **What the user experiences:** for the viewer, two days of silence read as two quiet days; the
  pushes they do get are mostly night-time 4K upgrades of films on the shelf. A person who learns to
  ignore pushes, or loses them, misses the ones that matter (a cinema trip, a loan, a Wanted find).
- **Fix and cost:** show the person's own device state on their Home when the check finds none
  ("This phone is not getting notifications · Turn on"), not only to the admin; take MK53-05's
  ranking and default quiet hours (22:00–07:00 Europe/London); ask each person whether they want
  upgrade pushes at all. Half a day beyond MK53-05's row.
- **Where it goes:** new row with MK53-05 in the first sitting; the "which pushes" question goes to
  both owners in the synthesis.

### UX54-03 — Medium — The top of the admin's Home is the viewer's finished work, under the viewer's name
- **Evidence:** `observed` (rig). The admin's Needs you on Home holds 2 rows, both "For [viewer] ·
  Answered — awaiting correction", each labelled with the viewer's name. The next move on both is
  the admin's (apply or reject the answer). The Needs you page also shows a builder's control to the
  admin: a card about assigning three catalogue reviews, a "Check current targets" button, and the
  line that it "sends no notification and makes no catalogue corrections". One of the two answered
  questions is itself contested (the synthesis reconciles it with CT52-04).
- **What the user experiences:** the admin reads "the viewer" on the two rows at the top of Home
  and can take them as the viewer's to do, while the viewer, whose answers are done, waits. The
  rows are labelled by who answered, not by whose move it is.
- **Fix and cost:** label by whose move it is ("Yours · apply the viewer's answer"), and order the
  admin's own moves first, as AF1's rule does for put-backs; move the assigning control off Needs you
  to the admin's tools. One to two hours.
- **Where it goes:** new small row with AF1's follow-ups; the contested answer is the synthesis's.

### UX54-04 — Low — 44 px targets hold on the main screens, not on Settings or Needs you
- **Evidence:** `computed` (rig, 375 px, every visible control measured): the notification switches
  on Settings are 44×24 px (at least eight); the Needs you tabs are 38×20 and 81×20 px; the
  "Inspect the film and copies" links are 174×20 px. Home, the Archive, Wanted, Deals and the cinema
  film pages had at most two small controls each. No visible text was under 12 px on any screen
  walked (X12b's floor holds).
- **Fix and cost:** pad those three controls to 44 px height. An hour.
- **Where it goes:** any sitting.

### UX54-05 — Low — First open downloads 1.2 MB of script before Home can draw
- **Evidence:** `computed` (the production build at `1668071`): the entry script is 754 kB
  (231 kB compressed) and a second shared chunk 416 kB (110 kB compressed); the build warns about
  both. The installed app precaches 116 files, 1.8 MB. The rig's own timings are set by its
  distance from the database and are not quoted.
- **What the user experiences:** a first open, or the first open after each deploy, on mobile
  data pays for code most screens never use.
- **Fix and cost:** split the two chunks by route (charts, the assistant, the scanner); measure
  first-open on a throttled phone in the end-to-end suite. Half a day.
- **Where it goes:** any sitting; not urgent.

### UX54-06 — Low — The assistant, from the users' side (P2, AI51-02)
- **Evidence:** `observed`: the assistant is an unlabelled icon in the app's header (seen on Movie night), for
  both people; 2 model calls in 30 days, none since 18 Oct (AI51-02). `implemented`: its tools cover
  none of the features added since wave 1 (At the cinema, Movie night, Needs you, deals).
- **What the user experiences:** an icon both pass on every screen and neither uses; nothing in
  the snag rounds asks for it.
- **Fix and cost:** agree with R3: freeze now, retire on the dated trigger. Retiring also frees the
  header slot for UX54-02's device state. One small batch when the trigger fires.
- **Where it goes:** the owner decision in the synthesis, with AI51-02.

## 3. Corrections to the pack's follow-through

| Row | Pack said | Now |
|---|---|---|
| UX48-02 failures look fine | partly fixed, not walked | **Partly fixed, walked.** App rows reach the admin; the person affected is still not told (UX54-02), and a stale cinema is said only at the page foot (UX54-01) |
| UX48-03 machine text | fixed | **Holds:** a failed value reads "The value could not be loaded. Collection counts are still available." |
| UX48-06 small text and targets | claimed | **Text holds, targets partly** (UX54-04) |
| L1 stale ODEON rows | not yet read on screen | **Read:** listed as ordinary chips, notice at the foot (UX54-01) |

## 4. The users' own words, re-checked

13 Nov's 8 snags (Group AF), against the screens:

| Snag | Seen |
|---|---|
| 2 Needs you and Needs attention | Fixed: one card; no separate Needs attention on the admin's Home |
| 3 Closest to complete | Fixed on Home: set rows with counts, no buttons |
| 5 Home's cinema strip | Fixed: reruns lead the strip |
| 6 and 8 At the cinema opens on all days | Fixed: no day in the address shows This week, then Coming up |
| 1 Who puts a disc back | Not seen live: no put-back was open on 16 Nov |
| 4 Back keeps your place, 7 the film page's day strip | Not driven: the rig's film pages were caught loading; CI's WebKit is not iOS Safari |

8 Nov's 18 points were not walked one by one. Seen in passing: Highlights' "Recently added" (15)
is present and opens first, ahead of "Most valuable" (2): the later request won, which the
reconciliation allowed for; no overcorrection was seen on any screen walked.

## 5. Probe log, limitations and hypotheses

**Probe log (16 Nov, UTC):** production database through the API's own code (the rig), 15:08–17:05:
GETs only; Postgres refused the boot heartbeat's INSERT (proof the connection cannot write); writes
on read paths (a value-run sweep, a Movie night expiry sweep, a calendar claim) were answered as
"no rows" in the rig and logged; 405 for every non-GET. Withheld from the role, so shown failing:
the device list (`push_subscriptions`) and photos. `live_sql`: 4 projected SELECTs (column grants
twice, the two profiles' names and roles, one health-check read that matched no rows). Outside: TMDB 0, eBay 0, cinema pages 0, Brave 0; poster
images from TMDB's public image host only. Paid: none.

**Limitations.** Chromium only, light scheme only (the dark sweep was cut for usage), and only the
first screenful in each screenshot (the app scrolls inside its own panel). The viewer's Home and
several screens were caught still loading, because the rig reads Neon from the Mac; the viewer's
side was judged from the code and the admin's screens it shares. No real phone, push or install.

**Hypotheses.** Three GETs write as a side effect (above): if one of those writes fails in
production, the whole screen fails with it (seen in the rig before the no-op). R1's lens.
