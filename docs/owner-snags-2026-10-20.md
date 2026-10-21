# Owner snags — 20 Oct 2026, reconciled against the code

Craig raised 23 points on 20 Oct 2026 and two more on 21 Oct, one message each. Each was checked the same day against
the code at `0dfec18`. No live database read: `NEON_READONLY_URL` is not set on the Mac this
session, so nothing below quotes a live count. Nothing was rendered in a browser.

**Status: reconciled; Craig answered on 21 Oct (below) and added two points. Sitting 1 waits for his "now"; AA10's note may start.** The plan is Group AA in
`docs/phase-batches.md`.

## Craig's answers, 21 Oct

| Question | Answer | Recorded |
|---|---|---|
| 1. The tribute artwork: where? | Asked whether the app-icon art would sit better | Proposed below (AA8) |
| 2. A button to the Archive on Home, given the bottom bar has one? | A "Browse the archive" link on the collection row | AA1 |
| 3. Profile pictures: an uploaded photo, or a picture picked from TMDB? | Uploaded photo, stored in Postgres | AA7 |
| 4. IMDb and Letterboxd scores on movie night | Show each person's own Letterboxd rating where there is one | AA5 |
| 5. Disc values | Mark's rule was a suggestion; propose a better one. Write the note now | AA10 |
| 6. Recent activity: move it to the You page? | Yes | AA2 |
| 7. The faded top bar | Every screen, dark theme | AA1 |
| 8. Go for sitting 1 (AA1 → AA2)? | Yes, but not yet | Waiting for "now" |

**21 Oct, later:** borrowing is asked for **in the app** (Mark gets a push), not by message
only (AA11). The photographic hero goes on Home's top banner, served to signed-in people only (no longer public), and #140 is superseded for it; The app-icon art replaces the vector marks in the top bar (grown to 36 px) and the sidebar; the 16 px icon and the badge stay vector (AA8, Craig's yes after a phone-size comparison).

**Two more points, 21 Oct:** 24, the deals coming through are not good deals; 25, the lend and
borrow story, as Craig and Mark actually do it (below). Both are in Group AA.

**Found on 21 Oct:**
- **The top bar's likely cause (7).** In the dark theme the page is `hsl(24 15% 6%)`, near
  black, and the top bar is `hsl(27 17% 11%)`, a lighter brown-grey, raised since W1. On every
  screen, a lighter band over a near-black page reads as washed out. The iOS status bar is
  `black-translucent`, so the clock sits on that same lighter band.
- **The app-icon art is not used in the app at all (1).** `BrandMark` shows it only at 192 px or
  more, and no page draws one that big. It is the original screen-print illustration (ocean
  suspense, noir, moonlit London), not built from stills, so it is outside #140's rule and needs
  no decision changed.
- **Letterboxd ratings are already imported (4).** The diary sync reads each person's own
  rating from their Letterboxd feed: Craig had rated 50 of his last 50, Mark 0 of 50 when it was
  built. Letterboxd's *average* for a film is still out of reach.
- **Sold prices cannot be had (5, 24).** `DECISIONS.md` #16 (4.1) and #228: Marketplace Insights,
  eBay's only source of sold prices, is closed to new applicants. Every value and every deal's
  "usually" rests on **asking** prices.

---|---|---|
| 1. The tribute artwork: where, and lift the onboarding-only rule? | — | — |
| 2. A button to the Archive on Home, given the bottom bar has one? | — | — |
| 3. Profile pictures: an uploaded photo, or a picture picked from TMDB? | — | — |
| 4. IMDb and Letterboxd scores on movie night: which sources? | — | — |
| 5. Disc values: a design note first, before anything is built? | — | — |
| 6. Recent activity: move it to the You page? | — | — |
| 7. The faded top bar: a screenshot (which screen, light or dark, Search open?) | — | — |
| 8. Go for sitting 1 (AA1 → AA2)? | — | — |

---

## Three things to know first

1. **The app opens on the Archive because the installed app's start page is `/movies`.** The
   web manifest's `start_url` says so; `/` itself already goes to Home. **An iPhone keeps the
   start page it was installed with**, so after the fix each phone has to remove the app from
   the Home Screen and add it again. Android picks the change up on its own.
2. **The tribute artwork is kept off every page by a decision and a test.** `DECISIONS.md` #140
   gives the photographic artwork one place, the onboarding welcome, and a
   source-level test fails if it appears in any other page. Using it means superseding that
   decision. The two heroes (`hero-photo-five-v3.png`, `hero-photo-v3.png`) are built from film
   stills and portraits, and are already served to anyone who has the address, signed in or not
   (`DECISIONS.md` #221); using them on a page does not change who can fetch them.
3. **Letterboxd has no public API and IMDb scores are not stored.** The app stores TMDB's score,
   the runtime, the IMDb id and a Letterboxd slug, but no IMDb or Letterboxd score. IMDb
   publishes a free daily ratings file for personal, non-commercial use. Letterboxd's average
   can only be read from its web pages, which its terms forbid scraping.

---

## The 23 points, by area

### App-wide

| # | Point | What the code does now | Batch |
|---|---|---|---|
| 1 | Use the logo artwork | Only the onboarding welcome and the platform icons use art. The two photographic heroes ship in `public/brand/` and no page uses them | AA8, answer 1 |
| 2 | Top bar still faded | Fourth report (30 Sep V1, 5 Oct W1, 5 Oct #44). The bar is a raised `bg-popover` panel; the iOS status bar is `black-translucent`. The cause is still not pinned down | AA1, answer 7 |
| 3 | Open on Home | Manifest `start_url` is `/movies` | AA1 |
| 4 | Profile pictures | Profiles have no picture; everywhere shows an initial. Copy photos are already stored in Postgres, so a photo needs no new hosting | AA7, answer 3 |

### Home

| # | Point | What the code does now | Batch |
|---|---|---|---|
| 5 | Needs attention clickable | Each line is text only; only Mark's notes have a button (Clear). The lines come from 11 daily checks: jobs, eBay listings, push, specs halted, server set-up, database size, lock-outs, films to identify, deal freshness, the assistant, and the check itself | AA2 |
| 6 | Remove Top rated | It ranks both people's ratings; Mark rates nothing. **Worth a rewatch also runs on ratings**, so it never shows for Mark | AA1 |
| 7 | Recent activity elsewhere | The last section on Home, 10 lines, a list | AA2, answer 6 |
| 8 | A button to the Archive | The bottom bar's second tab is already the Archive, one tap from anywhere | AA1, answer 2 |
| 9 | Review the collection section | Two number cards and five charts in a sideways row | AA3 (review first) |
| 10 | Best reviewed is the disc | Caption says "Blu-ray.com's overall score for the disc"; the title doesn't | AA1 |
| 11 | What a disc is best for | **Already stored:** each review keeps Blu-ray.com's sub-scores (Movie, Video 4K, Video 2K, Audio, Extras, Overall). No new fetching | AA2 |
| 12 | Avatars on Completion | Sets are a director's or actor's films; a card shows the name only. TMDB has a headshot per person; the set refresh does not store it | AA2 |
| 13 | Show the missing films, add each | The set's page greys missing films among owned ones; one bulk button, Craig only | AA2 |

### Film page

| # | Point | What the code does now | Batch |
|---|---|---|---|
| 14 | Tabs shouldn't scroll up and down; fit without sideways | The tab strip is `overflow-x-auto`, which makes the other axis scroll too, and each tab's `-mb-px` gives it 1 px to scroll. The four labels don't fit at 375 px | AA1 |
| 15 | Where to watch: our disc first | The tab shows Streaming and "If you liked this"; nothing about the copies on the shelf | AA1 |

### Movie night

| # | Point | What the code does now | Batch |
|---|---|---|---|
| 16 | Suggest at the top, shortlist below as "stuck for ideas" | Shortlist first, Suggest a film last | AA4 |
| 17 | Suggestions in their own list | One list; a card says "Suggested by" or "From the Archive" | AA4 |
| 18 | A planned date and time | A night has no planned time; it starts when made | AA4 (migration) |
| 19 | Per film: each person's last watch and rating, where (shelf or streaming), runtime, IMDb, Letterboxd | Behind a tap: runtime, genres, cast, streaming (unowned only), and when the **other** people watched it. Missing: your own last watch, ratings, shelf, IMDb, Letterboxd | AA5, answer 4 |
| 20 | Add to an open night from a film page | Suggesting is only from the night's own page | AA4 |
| 21 | Feeling lucky, on Home and in movie night | Nothing like it | AA6 |

### Other pages

| # | Point | What the code does now | Batch |
|---|---|---|---|
| 22 | Review the assistant page | 471 lines, one page | AA9 (review first) |
| 23 | Revalue discs (Mark: average of the 3 lowest prices in 3 months) | Median of current **used asking** prices from eBay's Browse API, 3+ listings, else New's median × a measured factor; repriced every 30 days. Browse gives current listings only, not sold ones or history, so "the last 3 months" means storing every listing seen from now on | AA10, answer 5 |

### Added 21 Oct

| # | Point | What the code does now | Batch |
|---|---|---|---|
| 24 | The deals coming through are not good deals | The nightly scan calls a UK fixed-price eBay listing a deal when, with postage, it costs 70% or less of the film's "usually": eBay's median **asking** price for the format, averaged with any watched shop's price from the last week (V8). An asking median sits above what discs sell for, so 30% under it is often just the going rate | AA10 |
| 25 | Lend and borrow, as it really happens | One loan per copy: who has it, lent date, optional due date, returned date (W3). Nothing for a request, a "needed by" date, a disc back in the house but not on its shelf, or Mark putting it back | AA11 |

**Point 25, Craig's story (21 Oct):**
1. Craig messages Mark to borrow a film, often saying when he needs it by; or he goes round to
   Mark's house and takes it.
2. On return, Craig brings it back and leaves it in Mark's house, not in its place; or Mark
   collects it from Craig's house.
3. Mark then puts it back in its position.

So a loan has four states, not two: **asked for** (with a needed-by date) → **out** (at
Craig's) → **back, not shelved** (in Mark's house, or collected) → **shelved**. Today the app
records only out and back. The copy keeps its shelf location in the app the whole time, so
once a loan is marked returned the app shows it shelved while the real disc may still be on a
table.
