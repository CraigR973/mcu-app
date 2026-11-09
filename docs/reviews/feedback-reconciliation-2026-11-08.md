# Craig's 18 points, reconciled against the code — 8 Nov 2026

**Read-only.** Code read at `417471a` (main). Live data read with the read-only database role,
13:55–14:40 GMT. Nothing was changed, committed, pushed or deployed. The Home layout point is
judged from the layout code, not seen on a phone: production needs Craig's sign-in.

**Update, 9 Nov.** Craig agreed to all six decisions (#355). The review-card build named under
Risks shipped on 9 Nov (AD1, PR 138), so point 16 no longer clashes with uncommitted work; it now
supersedes #351's private visibility for Craig and Mark. Mark's username was saved on 9 Nov
(#354), so his diary should be current after the first sync, due 10 Nov at 08:00 UTC. The batch
plan is Group AE in `docs/phase-batches.md`, with a phone copy in
`docs/reviews/group-ae-plan-2026-11-09.md`.

Sizes are agent time for the change and its tests. Each batch also needs the full gate, the
seven CI jobs and the production check, about 30–60 minutes more.

## Summary

| Point | Today | Fix size |
|---|---|---|
| 1. Rewatch card: dead space, buttons on one row | Buttons wrap on a phone; gap under the poster | ~45 min |
| 2. Most valuable as Highlights' default | Most rewatched opens first | ~10 min |
| 3. Closest to complete | Same 3 sets every visit; 2 can't be finished | 1–4 h |
| 4. Day-by-day cinema view | Day chips exist, third row down, default "Any day" | 2–3 h |
| 5. IMDb and Letterboxd from the cinema film page | Missing | ~1 h |
| 6. Trip proposal: has each invitee seen it | Names only | ~1.5 h |
| 7. Why so many listings are unmatched | A lookup backlog, draining | 1–2 h |
| 8. Select all / none for cinemas | Missing | ~20 min |
| 9. Movie night screen and flow | 11 nights, 0 matches | design first, then 4–8 h |
| 10. Format update (Contagion) | Works as designed; the form misleads | ~1.5 h |
| 11. Pricing accuracy | ~11% out where checkable; 36% of the total unchecked | nothing new; AA10c from 25 Nov |
| 12. Search | Whole words only, no typos, no accents | 3–4 h |
| 13. Collapse unmatched and events | Always open | ~20 min |
| 14. Other people's profiles | Missing | 3–5 h |
| 15. Recently added in Highlights | Missing; 60 copies added in the app since 10 Oct | ~1.5 h |
| 16. Needs you visible to both, labelled | Private per person; clashes with today's build | 2–3 h |
| 17. "How this estimate works" full width | Opens in half the card | ~15 min |
| 18. Omniplex, Renfrew Street | Not read; the existing listings source covers it | 2–3 h |

**Total: about 27–40 hours of agent work**, plus the gate per batch.

## Risks and conflicts

- **Point 16 reverses a decision approved today.** Another agent is building Mark's three review
  cards (Titanic, Dead Man's Shoes, Shetland) in this checkout now, uncommitted on `main`
  (migration 074, Needs you API changes, decision #351). #351 makes reviews private to the
  person assigned. Point 16 asks for everything visible to both, labelled by owner. That agent
  is not one of this app's sessions, so it has to be told directly before it lands.
- **No batch can start in this checkout until that work is committed or moved.** The close-out
  rule needs a tree holding only the batch's own work. A separate worktree avoids the wait.
- **Points 2 and 15 both claim the Highlights default.** One has to give.
- **Mark's watch history stops at 14 Oct.** His Letterboxd sync is not set up, so anything that
  reads his diary (points 6 and 14) under-reports for him until it is.

## Home

### 1. Worth a rewatch: dead space, and the two buttons on one row

- **Now:** a 112 px poster on the left; title, a line of detail, the buttons and the
  "Only films I haven't watched" checkbox stacked on the right. On a phone the right-hand column
  is about 180 px wide, so "Open the film" and "Deal another" wrap onto two rows. That column
  ends up roughly 100 px taller than the poster, which leaves the empty space under the poster.
  Only the button opens the film; the poster and title do not.
- **Fix:** poster and title side by side at the top; the button row ("Open the film",
  "Deal another", and "Start again" when shown) across the full width of the card beneath;
  the checkbox under it. Poster and title open the film too.
- **Size:** ~45 min, web only.

### 2. Most valuable as the Highlights default

- **Now:** tabs in the order Most rewatched, Most valuable, Best discs. The first tab with films
  opens, so Most rewatched always does. The choice is not remembered.
- **Fix:** reorder the tabs, and remember the last tab picked on the device.
- **Size:** ~10 min. Clashes with point 15: see Decisions.

### 15. Recently added in Highlights

- **Now:** no such tab. The Highlights read returns only rewatched, valuable and best-reviewed
  films. The data exists: every copy added in the app records who added it and when. 60 copies
  have been added that way, 10 Oct–5 Nov; the 1,857 spreadsheet rows carry no added date, so the
  tab would naturally show only real additions.
- **Fix:** a "Recently added" tab, newest first, each card saying who and when
  ("Mark · 5 Nov · 4K UHD"). Needs a small addition to the Highlights read and its schema.
- **Size:** ~1.5 h.

### 3. Closest to complete

- **Now:** Home shows the 3 sets with the fewest films missing, out of 40 (the 20 directors and
  20 actors with most films owned). Today, from live data:

| Set | Owned | Missing |
|---|---|---|
| Clint Eastwood, director | 39 of 40 | Piano Blues (2003), a TV documentary episode |
| Stanley Kubrick | 12 of 13 | Fear and Desire (1953), his disowned first feature |
| Alfred Hitchcock | 48 of 54 | 6 early films, including The Mountain Eagle, which is lost |

  The row is the same three sets on every visit, and two of them cannot realistically be
  finished. David Lean is complete (15 of 15) and sorts last. Sets were last rebuilt 25 Oct.
- **Options:**
  - a. Name the missing film(s) in the row with a Want button. ~1 h.
  - b. A "doesn't count" choice per film, for lost films, TV episodes and alternate-language
    versions, so Eastwood reads complete and the row moves on. Needs a small stored list. ~2 h.
  - c. Franchise sets ("Mission: Impossible, 7 of 8") from TMDB's collection data, which the
    app does not store yet, so a one-off TMDB backfill. ~3–4 h.
  - d. Lead with sets that changed recently instead of the same three. ~1 h.
- **Recommendation:** a and b first.

## Cinema

### 4. A day-by-day view like the cinema apps

- **Now:** a row of day chips exists ("Any day", "Today", "Tomorrow", "Mon 10"…), but it is the
  third filter row, it defaults to "Any day" (This week, then Coming up), and with a day picked
  each film still shows only its next time, not that day's times.
- **Fix:** the date strip as the top control, sticky, with Today selected on arrival; each film
  then lists that day's times, grouped by cinema, each time opening the booking page. Every
  showing is already in the data the view loads, so no new request.
- **Size:** 2–3 h, web only.

### 5. IMDb and Letterboxd links from the cinema film page

- **Now:** the cinema film page links to the archive page (films in the collection) or to the
  in-app TMDB page. Neither of those two pages links to IMDb or Letterboxd; only the archive
  film page does.
- **Fix:** both links on the cinema film page for matched films. Letterboxd works from the TMDB id
  the page already has (`letterboxd.com/tmdb/<id>` redirects to the film, checked today). IMDb
  needs the IMDb id, which the lookup already stores but the page's data does not yet carry.
  Unmatched listings get a Letterboxd search link only.
- **Size:** ~1 h.

### 6. Trip proposals: has each invitee seen it

- **Now:** "Who to invite" lists names only. The film page shows only the reader's own "Seen".
- **Fix:** beside each name, "Seen · 12 Mar 2024" or "Not seen", from their diary. Works for any
  matched film, owned or not, because every watched film has a row.
- **Caveat:** for Mark this misses anything since 14 Oct until his sync is set up.
- **Size:** ~1.5 h.

### 7. Why so many listings say "Not matched to a film yet"

- **A lookup backlog.** Each morning's refresh may spend 48 TMDB requests, about 2 per film, so it
  identifies about 19 new titles a day. Until 5 Nov the limit was 12 requests a morning; the
  current rule began on 6 Nov with 141 listings waiting. The queue, by morning:

| Morning | Waiting |
|---|---|
| 4 Nov (old limit) | 164 |
| 5 Nov (old limit) | 141 |
| 6 Nov | 111 |
| 7 Nov | 55 |
| 8 Nov | 29 |

- **Right now 35 listing rows are unmatched.** 26 say "not yet looked up" (Elf, Sicario,
  Prisoners, Cliffhanger, Sense and Sensibility, Rocky 50th, Arthur Christmas 15th…). 9 wait for
  Craig's identity check: Ramayana, Tabby McTat (5 cinemas) and The Devils (3).
- It should mostly clear within two mornings, but each Friday's new programme refills it, and a
  new film can wait one to three days.
- **Three titles will not match even after a lookup:** "Access Film Club: The Grand Budapest
  Hotel" (the prefix is not stripped), "Arthur Christmas (15th Anniversary)." (the trailing full
  stop defeats the cleaner) and "CBeebies Panto 2026: Treasure Island" (an event the event list
  does not know).
- **Fix:** raise the morning lookup budget from 48 to about 120 TMDB requests (TMDB is free and
  the cap is the app's own), and teach the cleaner those three patterns. ~1–2 h. This changes the
  AC3 budget rule (#335), so it is a decision.

### 8. Select all / none for cinemas

- **Now:** the Cinemas list has one checkbox per cinema, no all or none. Unticking every cinema
  already shows "Select at least one cinema".
- **Fix:** "All" and "None" at the top of the list. ~20 min.

### 13. Collapse "Not matched" and "Events and double bills" by default

- **Now:** both sections are always open, under the film grids.
- **Fix:** closed by default, with the count in the heading ("Not matched to a film yet · 35").
  ~20 min.

### 18. Omniplex Glasgow, Renfrew Street

- **Now:** the app reads nine cinemas; this is not one. It is the former Cineworld on Renfrew
  Street, reopened by Omniplex from July 2026.
- **Cheap to add.** CinemaTimes, the listings site the app already reads for the four ODEONs,
  has an Omniplex Renfrew Street page. Today it lists 29 films and 274 showings over 7 days
  (8–14 Nov), with booking links to omniplexcinemas.co.uk.
- **Work:** a tenth venue; teach the CinemaTimes reader Omniplex's booking links (it accepts
  ODEON's only); allow that booking site in the web app; replace the "all nine" wording; extend
  the end-to-end suite's fake listings. One more page read each morning.
- **Size:** 2–3 h. It changes the approved nine venues, so it is a decision.

## Movie night

### 9. Can the screen and flow be improved?

- **Usage since 10 Sep:** 11 nights, all started by Craig. Two ever had a second person. None
  reached a match. Six never had a vote. The "Nothing older than" filter has never been used.
  The 6 Nov night is still open with no shortlist.
- **So yes.** The flow stalls at getting the other person in, and 30 random films is a lot to
  choose from.
- **Proposals, for a design pass before any build:**
  - a. Invite when starting the night, as "Propose a trip" does; the push goes at once.
  - b. A shorter shortlist, about 10, mixing films put forward from film pages, "Worth a
    rewatch" picks and films neither person has seen; filters that matter on the night (under
    two hours, genre, unseen by both, 4K) in place of the year box.
  - c. Show the other person's progress without their picks ("Mark has added 3").
  - d. At the match: where the disc is, and afterwards "Log it for both of you".
  - e. Close nights nobody touched after a day or two.
- **Size:** a 30-minute sketch to choose from, then 4–8 h depending on the picks.

## Collection

### 10. How a format update works, and Contagion

- **How it works:** a film has one or more copies, each one physical item. A copy carries several
  formats only when one box holds several discs, such as a 4K + Blu-ray combo pack. "Edit copy"
  changes that one item; "Add another copy" makes a separate item; deleting moves a copy to Trash.
- **What happened to Contagion, from the audit trail:**
  - 4 Nov 21:30: Mark ticked 4K UHD on the existing Blu-ray copy. One copy, Blu-ray + 4K: the
    combo pack meaning. That is the "only 1 copy" he saw.
  - 21:31: he unticked it and added another copy. It saved as Blu-ray, because a new copy
    starts as Blu-ray.
  - 5 Nov 20:26: he changed the new copy to 4K (Front 1st shelf, £9.55 from eBay, bought 29 Oct),
    and 11 seconds later deleted the old Blu-ray copy.
  - **Now Contagion has one copy, 4K.** The Blu-ray is in Trash and can be restored.
- **The traps:** the edit form lets anyone tick a second disc format without saying that means
  "same box"; and a new copy defaults to Blu-ray.
- **Others like it:** only Contagion ever had a format added on top in an edit. Two copies carry
  both 4K and Blu-ray today: King Arthur: Legend of the Sword (added that way by Mark on 10 Oct)
  and Silent Running (from the spreadsheet). Each is worth a 10-second check that it is one box.
- **Fix:** when a second disc format is ticked on a copy, ask "One box with both discs, or a
  separate copy?", with the separate-copy answer doing the right thing; and make a new copy's
  format a required choice. ~1.5 h.

### 11. How accurate is the pricing model now?

- **Where it can be checked:** 61 discs have three or more observed eBay sales in 90 days. On
  those, the stored estimate (the used lower-quartile asking price, postage in) is typically
  **within 11%** of the sales median and 3% high on average; 64% are within ±20%. The plain used
  median would be worse, at 16%.
- **Where it cannot:** those 61 discs are £493 of the £14,740 total (3%).

| Priced by | Copies | Value |
|---|---|---|
| Used asking prices (lower quartile) | 893 | £8,943 |
| Scaled new price (used too scarce) | 355 | £5,304 |
| Observed sales | 61 | £493 |
| No price found | 162 | £0 |

- The scaled-new fallback carries 36% of the total with no sales evidence behind it, and it covers
  the scarcer discs, where error is likely biggest. 162 copies add nothing, so the total leans low
  there.
- **Caveat:** a listing that disappears is only an inferred sale, and a Best Offer can close
  lower, so true accuracy is probably a little worse than 11%.
- **Already planned:** AA10c, from 25 Nov, compares the stand-in with four weeks of recorded sales
  and switches method if the median wins. Nothing new to build now. Optional: a "how sure" line
  on Home.

### 12. Search

- **Now:** Postgres full-text search over title, original title, tagline, genres, cast and crew,
  and plot summary, English word stemming, whole words only.
- **Live tests:**

| Typed | Found |
|---|---|
| godfather | 3, correct |
| godf | 0: no matching while typing |
| godfathr, jurasic, hitchcok | 0: no typo tolerance |
| spiderman | 0 ("spider man" finds 10) |
| leon | not Léon: accents matter |
| bond | 95, Joan of Arc first (actor Ward Bond outranks the Bond films) |
| lotr | 0: no nicknames |

- **Fix:** title matches ranked first; matching on the start of a word as you type; typo and
  accent tolerance through Postgres's trigram and unaccent extensions (available on Neon, not
  installed); a short alias list (LOTR, T2, MI). ~3–4 h. Adds two database extensions and an
  index: a reversible schema change.

## People

### 14. Other people's profiles

- **Now:** none. "You" is the signed-in person's own hub (photo, saved collections, activity).
  Names and avatars elsewhere do not open anything.
- **Fix:** a person page: photo, recent diary, ratings, films watched this year, what they have
  added, their wants and loans; names and avatars link to it. A new read and a page. ~3–5 h.

### 16. Needs you visible to both, labelled by owner

- **Now:** each person sees only their own items. Loan jobs go to both shelf-keepers (Craig and
  Mark); an overdue loan also goes to its borrower; trip replies go to each invitee; the next
  screening is the reader's own.
- **Clash:** today's approved review-card build (#351) keeps reviews private (see Risks).
- **Fix:** one list for both, each item tagged "You" or "Mark", the reader's own first; act only
  on your own items, except loans, which both already act on.
- **Size:** 2–3 h, after the review-card build lands, since it touches the same files.

### 17. "How this estimate works" full width

- **Now:** it opens inside the left half of the two-figure row (Estimated used value | You've
  watched), so the text is squeezed into half the card.
- **Fix:** open it as a full-width panel under both figures. ~15 min.

## Suggested grouping — not started

| Batch | Points | Size |
|---|---|---|
| Quick wins, web only | 1, 2, 8, 13, 17 | ~2 h |
| Cinema | 4, 5, 6, 7, 18 | 8–10 h |
| Highlights and completion | 3, 15 | 3–4 h |
| Search | 12 | 3–4 h |
| Copies | 10 | ~1.5 h |
| People | 14, 16 | 5–8 h |
| Movie night | 9 | sketch, then 4–8 h |
| Pricing | 11 | AA10c, 25 Nov |

A batch plan with order, models and gates comes next, for Craig's go.

## Decisions for Craig

1. **Highlights default:** Recently added (recommended: it changes every week, while Most valuable
   barely moves) or Most valuable. The other goes second.
2. **Needs you:** shared with owner labels, superseding #351's private reviews? The agent building
   the review cards must be told before it lands.
3. **Omniplex as a tenth cinema:** recommended.
4. **Morning lookup budget 48 → ~120 TMDB requests:** recommended; free, low risk.
5. **Search extensions (trigram, unaccent):** recommended.
6. **Ask Mark:** does he still have the Contagion Blu-ray (restore it from Trash if so), and are
   King Arthur and Silent Running each one combo box?

## For the implementing agent

- Home card: `components/dashboard/FeaturedFilm.tsx`. Highlights: `components/dashboard/Highlights.tsx`,
  API `routers/highlights.py`. Completion: `components/dashboard/CompletionShelf.tsx`,
  `lib/home.ts`, `services/completion.py`, `routers/insights.py`.
- Cinema view: `components/cinemas/AtTheCinema.tsx`, `lib/cinemas.ts`. Film page:
  `pages/CinemaFilmPage.tsx`; facts schema `cinemaFilmFactsSchema` in `packages/shared`.
  Trip picker: `components/cinemas/ProposeTrip.tsx`, `TripPickers.tsx`,
  `services/cinema_trips/trips.py` (`invitable`). Lookup budget: `services/cinemas/fetch.py`
  (`METADATA_CAP`, the 120 total), `metadata.py`. Title cleaner: `services/cinemas/identity.py`.
  Venues: `services/cinemas/venues.py`; CinemaTimes reader `parse_cinematimes` in `parsers.py`
  (ODEON-only booking host and showtime-id check). Omniplex page:
  `cinematimes.com/uk/glasgow/cinemas/omniplex-glasgow-renfrew-street-city/`.
- Copies: `components/collection/CopyEditor.tsx`, `CopyForm.tsx` (`EMPTY_COPY` defaults to
  Blu-ray), `DuplicatePrompt.tsx`.
- Value note: `components/dashboard/CollectionLedger.tsx` (`Worth` inside a two-column grid).
- Search: `routers/movies.py` (`search_movies`), trigger in migration `005`.
- Needs you: `routers/needs_you.py`, and the uncommitted `services/assigned_reviews.py`.
- Movie night: `pages/MovieNightPage.tsx`, `pages/MovieNightSessionPage.tsx`,
  `services/movie_night/sessions.py` (`seeded_candidates`, 30 films).
