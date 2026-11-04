# Owner snags — 4 Nov 2026, reconciled against the code

**Status: reconciled; Craig's answers recorded (#335); Group AC drafted in
`docs/phase-batches.md`; no sitting authorised.** Craig accepted every recommendation except
point 4's invitees: more people may be onboarded later, as full accounts, never as guests.
Craig raised eight points, then asked for them to be reconciled against the code.
Reviewed source and production were both `b6940227d9d7a712fcc4bfbca0330cbaf1afc51a` (API
health and web `version.json`). The checkout started clean on `main`. This report is on
`chore/owner-snags-2026-11-04`; nothing has been pushed or deployed.

## Findings that matter first

- **Mark's Home cannot show anything he needs to do.** "Needs attention" is Craig-only by
  design and holds only operational checks and notes. Two discs have waited "back, not
  shelved" since 28 Oct (Pulp Fiction, Rosemary's Baby); only Loans → "To put back" shows
  them, and no reminder exists for that state.
- **The cinema programme has no film identities yet.** 0 of 174 programme films (1,850
  future showings, 4 Nov) are linked to a TMDB record. That one gap blocks posters,
  owned/watched badges, first-run/rerun classification, cross-venue de-duplication and
  reliable new-film notifications. Points 3, 6 and 7 all rest on it.
- **Point 6 conflicts with settled decisions #326, #327 and #330.** They allow only
  explicit source wording as run evidence and rule out release dates. Under that rule all
  1,850 showings are Unclassified. Meeting point 6 needs a superseding decision.
- **Points 4 and 7 change the data shape.** Cinema trips need new tables; a cinema
  notification switch needs a new preference column. Both need explicit approval first.
- **The first scheduled cinema refresh ran this morning.** 08:05 UTC, all nine venues
  succeeded, 63 requests, 1,840 rows, 233 new showings; status `partial`, as the accepted
  3 Nov manual run was. Horizons are uneven: Cineworld 14 days, Everyman 13, Science Centre
  8, ODEON 7, **GFT 2 and Vue 2**. GFT, the repertory cinema most likely to show older
  films, lists only two days ahead.

## All eight points

### 1. “for the collection section on the home page, i feel like there is still a repetition … review the full home page. Does it look absolutely premium and world class”

**Current behaviour.** Home on a phone, top to bottom: top bar with the small mark → the
photo-letter banner → Needs attention (Craig only, hidden when clear) → The collection →
Feeling lucky → an "At the cinema" text card → Coming to disc → Highlights (most rewatched,
most valuable discs, best discs) → On this day → Worth a rewatch → Completion → Pinned
collections. Every row hides when empty.

The collection section, with the latest recorded read-only figures (27 Oct) for Mark:

| Card | Figure | Sub-line |
|---|---|---|
| Titles owned | 1,903 | Each film or series counts once |
| Copies owned | 1,927 | 1,472 physical · 589 download; 134 both |
| Estimated used value | ≈ £15,939 | 1,311 of 1,472 physical copies priced; 0 from sales |
| You've watched | 878 / 1,903 | Watched titles still in the collection |
| Matched on TMDB | 1,902 | Of 1,903 owned titles |

Then "Formats at a glance" bars, "Browse the archive", and a closed "Collection breakdown"
(formats again, where they live, genres, decades, spend).

**Where the repetition is:**

1. The owned-title total appears three times (Titles owned, You've watched, Matched).
2. Three of the five big numbers read as one figure: 1,903 titles, 1,927 copies, 1,902
   matched.
3. Formats appear twice — "Formats at a glance" and "Formats (copies)" in the breakdown —
   each with the same overlap sentence.
4. The physical-copy count appears twice (Copies and Value).
5. Five cards share one shape (label, big number, sentence), so it reads as a report table.
6. "Matched on TMDB" is a data-quality figure. At 1,902 of 1,903 it tells Mark nothing; it
   belongs in Admin or Identify, and in Needs attention when matches are missing.

**Design review of the whole page.** Tidy, consistent and honest, but **not yet premium or
world-class**: it reads as a well-built data dashboard rather than a cinema app.

- **No hero moment after the banner.** The first phone screen is banner plus number cards:
  no poster, nothing personal, nothing to do tonight.
- **Carousel fatigue.** Up to nine sections share one pattern (icon heading, caption,
  sideways poster row). Premium film apps vary module type and scale: a featured backdrop,
  wide cards, poster rows, a short list.
- **Methodology captions on every row** ("Blu-ray.com scores the disc's picture, sound and
  extras, not the film."). Premium copy is shorter; method belongs behind an info tap.
- **The strongest content is the weakest module.** "At the cinema" is a sentence about
  filters, where a strip of what is on this week would sell itself.
- **Films recur across rows** (most rewatched, on this day, worth a rewatch).
- **Staged loading.** About ten requests and a 2 MB banner fetched after sign-in, with a
  grey pulse until it lands. AB7 stopped taps during settling; it did not make Home feel
  instant.
- **Dashboard idioms.** Left accent bars on stat cards, an icon on every heading, uppercase
  tracked labels.

**Recommended direction (for mock-ups, not built):**

1. **One ledger instead of five cards.** "1,903 films" as the single big figure; one line
   "1,927 copies · 1,472 on disc · 589 digital"; value as the second figure; watched as a
   progress bar ("You've seen 878 · 46%"); formats as one stacked bar that opens the
   breakdown. Matched on TMDB leaves Home. Each fact appears once.
2. **A personal top slot** above the collection: "Needs you" (point 2), then this week's
   plan (next cinema trip or movie night, new at your cinemas).
3. **A visual "At the cinema" strip** with posters and new/older badges (needs point 6).
4. **Fewer, varied modules:** one featured film with a backdrop, then three or four rows;
   On this day becomes a smaller memories card.
5. **Captions cut** to one short line or an info tap.
6. **375px mock-ups in both themes with real data** before building, as AA3 and AB2 did.

**Verdict:** design work, mostly web-only. The ledger needs no new data. A featured module
and a cinema strip need new reads; the strip waits on cinema identities.

Evidence: `DashboardPage.tsx`, `CollectionShelf.tsx`, `Shelf.tsx`, `Highlights.tsx`,
`ComingToDisc.tsx`, `PrivateHero.tsx`; the AA3/AB2 375px screenshots; the 27 Oct
read-only figures. Not rendered with real data in this session (see limits).

### 2. “the needs action should show on home page, for example Mark still has 2 films to re shelve. are they showing on his home screen”

**Current behaviour, verified live: no.**

- Needs attention is admin-only in the web and the API, so for Mark it never renders. It
  lists only operational check results and notes to Craig.
- A loan in state `back` (returned, not shelved) is not an attention item for anyone. It
  shows only on Loans → "To put back". No reminder or push exists for that state.

Open loans on 4 Nov:

| Film | State | Detail |
|---|---|---|
| Pulp Fiction | Back, not shelved | With Craig 21–28 Oct |
| Rosemary's Baby | Back, not shelved | With Craig 18–28 Oct |
| Halloween | Out | With Craig since 18 Oct, no due date |
| The Silence of the Lambs | Out | With Craig since 18 Oct, no due date |

The last two are legacy rows with no state value (read as Out) and no due date, so they can
never become overdue or appear anywhere as needing action.

**Verdict:** missing feature, plus the X2 choice that hid the only attention row from Mark.

**Recommended scope:** a personal "Needs you" row at the top of Home for both people, built
from what that person can act on: discs to put back (one tap into the existing confirm
flow, which can change the shelf), discs asked for and awaiting handover, overdue or
long-running loans, and invitations awaiting a reply (point 4). Each item deep-links to its
exact place. Craig's operational items keep their own row. Derived from existing loan
states: no migration; a new or extended read API with its shared schema.

**Decided (#335):** discs to put back show to the people who keep the shelves (admins and
Mark's stable profile, defined in one place) until one confirms, so a later onboarded
person sees no shelf jobs. Open loans with no due date surface after 14 days.

Evidence: `AttentionRow.tsx`, `routers/attention.py`, `LoansPage.tsx`, `LoanActions.tsx`,
`models/loan.py`, `services/reminders.py`; live read with the read-only role.

### 3. “on the movie night section can we collapse past screenings by default … split out the cinemas view and show all the movies showing and upcoming … click on them which shows all the showtimes across all cinemas … propose a cinema trip … from the movie night section we should also be able to plan a cinema trip”

**Current behaviour:**

- Movie night lists every session in one list. Live: 10 sessions, all ended, none planned,
  none collapsed.
- Cinemas is a separate page, reached from Home's "At the cinema" card, the "Plan a
  screening" navigation group and the command palette; the phone tab is "Movie night". It
  is filter-first: from/to dates (default today only, up to 14 days), cinema checkboxes and
  a release-category select, then a text list grouped by film, each showing a block of
  venue/time, category, screen, formats, source age and "Check tickets".
- No posters, no index of everything showing and upcoming, no film-level view of all its
  times, no way to propose a trip. Movie night cannot start anything cinema-related.

**Gaps against the request:**

- **Collapse past screenings:** web-only.
- **Split:** Movie night becomes two views, "At home" and "At the cinema". The cinema view
  is film-first: "Showing now" (next 7 days) and "Coming up" (later, as far as sources
  list), each film with poster, run badge, venue count and next time.
- **Film page:** every showing across all nine cinemas, grouped by day then venue, times as
  chips with format (IMAX, 3D …), and "Propose a trip" from a time.
- **From Movie night:** "Plan a cinema trip" beside "Start a screening", opening the cinema
  view.

**Constraints the design must show honestly:** horizons are uneven (GFT and Vue 2 days,
others 7–14), so "Coming up" thins out and must say which cinemas are listed only to a
date. Posters and badges need film identities (point 6). Coverage, staleness and
ticket-link rules stay as they are.

**Verdict:** the collapse is small; the split and film page are a new film-first read API
plus web screens, no migration; proposing a trip needs point 4.

Evidence: `MovieNightPage.tsx`, `CinemasPage.tsx`, `lib/nav-items.ts`, `MobileTabBar.tsx`,
`services/cinemas/programme.py`; live counts.

### 4. “when someone proposes a cinema trip you should be able to see the other invitees, if they have accepted. you should be able to accept, decline or propose a different show time”

**Current behaviour:** none of this exists. A movie night has participants who joined by
link, a shortlist, votes and an optional planned time. It has no link to a cinema showing,
no invitee list, no per-person reply and no counter-proposal.

**Recommended scope:** a cinema trip record holding the proposer, the chosen showing
(venue, film, time, snapshotted so a programme change does not rewrite it), the invitees,
and each invitee's reply: Invited, Going, Not going, or Suggested another time (pointing at
another showing). Everyone sees everyone's reply. When the proposer accepts a counter-
proposal, the trip moves to that showing and the other replies reset to Invited, with a
push. Pushes on invite, reply, change, and a reminder before the showing. Booking stays
with the cinema. A withdrawn or cancelled showing is flagged on the trip.

**Decided (#335):** invitees are any active profile, in any number, because more people
may be onboarded as full accounts; there are no guests and no reply link that works without
sign-in. Trips get their own tables, shown alongside movie nights.

**Verdict:** new feature and a consequential data-shape change — two new tables, with the
usual guarded `mcu_readonly` and `mcu_backup` grants. Needs explicit approval.

Evidence: `models/movie_night.py`, `routers/movie_night.py`, `models/notification.py`.

### 5. “we can still keep the release calendars but should be separate for discs and cinemas”

**Current behaviour:** one Releases page: a "Coming to disc" strip, then one month list
mixing disc dates and UK cinema dates (told apart by a chip), then a TMDB "Coming soon"
feed. Upcoming entries live: **134 cinema, 23 disc** (14 4K, 9 Blu-ray) and 11 sale events,
so discs are outnumbered about six to one in the shared list. The calendar subscription is
one feed of every type.

**Recommended scope:** two calendars — Disc releases (4K and Blu-ray, sale events as a
filter) and Cinema releases (UK opening dates) — each with its own month view. A cinema
release that is actually showing at one of the nine links to its cinema film page (needs
identities). Optionally one subscription feed per calendar. The month endpoint needs a type
filter (additive API). No migration.

**Verdict:** refinement over existing data.

Evidence: `ReleasesPage.tsx`, `ComingToDisc.tsx`, `services/calendar.py`,
`routers/calendar.py`, `services/ical.py`; live counts.

### 6. “we need to ensure we can classify first cinema runs and reruns of older movies”

**Current behaviour, verified live:** each showing carries New release / Older film /
Unclassified, with a filter on Cinemas, but **all 1,850 future showings are Unclassified**
(4 Nov). By design (#326, #327, #330):

- Older needs the cinema's own title to carry a label (anniversary, 4K restoration,
  re-release, reissue) **and** a verified TMDB match with an earlier UK cinema date.
- New needs explicit evidence of a first UK run, which no source states, so it never fires.
- Release dates and years are ruled out as evidence, title-only matching is ruled out, and
  metadata lookups are capped at 12 per run. This morning 164 films were still waiting for a
  lookup; 0 of 174 are linked.

**Decided scope (#335, superseding the strict rule):**

1. **Identify films automatically against TMDB:** source IDs where given, otherwise title
   plus year, runtime or director corroboration; a short review list for ambiguous ones.
   Raise the cap to clear the backlog (TMDB is free; the 30-day cache keeps steady state
   low).
2. **Classify by UK release history once identified:**
   - First run: first UK cinema release within 16 weeks before the showing, or after it
     (previews).
   - Rerun: first UK cinema release 12 months or more before, or the source says reissue,
     anniversary or restoration.
   - Between those, unidentified, live events and double bills: Unclassified, still shown.
3. **Show the reason on each badge** ("Released 1975 · rerun").

Craig accepted these thresholds (#335).

**Verdict:** the machinery exists; the rule and the identity gap stop it working. #335
supersedes the rule. No migration expected: existing columns hold category, evidence,
film link and release dates.

Evidence: `services/cinemas/domain.py`, `metadata.py`, `parsers.py`, `store.py`,
`models/cinema.py`; decisions #326, #327, #330, #334; this morning's run report.

### 7. “you should be able to get notifications when new movies are added to cinema”

**Current behaviour:** none. Push categories are deals, sale events, releases, loans, movie
night, collection additions and attention. The daily refresh counts new showings (233 this
morning) and sends nothing.

**Recommended scope:** after the daily refresh, at most one digest per person — "New at
your cinemas: 3 films · Jaws (rerun, GFT) …" — linking to "New this week" in the cinema
view. A new film means its first appearance anywhere among the nine, not at each venue. A
new "Cinemas" notification switch with an "Older films only" option; quiet hours and digest
mode apply.

**Dependencies and choices:** de-duplication across venues needs identities (point 6);
without them one film at five venues is five items, and title variants slip through. The
switch is a new preference column: a migration and a consequential data-shape change.
Decided (#335): all new films, with an older-films-only switch.

**Verdict:** missing feature; reuses the existing outbox, quiet hours, digest and delivery.
Receipt on a phone remains an owner observation.

Evidence: `models/notification.py`, `services/notifications.py`,
`services/cinemas/refresh.py`, `services/cinemas/store.py`.

### 8. “do you think the Marks cinematic universe sign on home screen keeps that premium look and feel”

**What it is:** AA8's photo-letter banner, a 2000×950 PNG of about 2 MB fetched privately
after sign-in because it uses film stills. MARK'S is filled with Jaws, Bogart, Cary Grant,
Hitchcock and An American Werewolf in London, with black and gold outlines, an inner gold
frame, a maroon radial gradient and "CINEMATIC UNIVERSE" in spaced white capitals. The same
image serves both themes.

**Verdict:** the idea is charming and personal; **at phone size the execution is not
premium.**

- At about 343px wide the letter photos become texture: the three black-and-white middle
  letters merge into grey; only Jaws and the werewolf read.
- Double outlines, the inner frame and the vignette make it busy — a novelty postcard
  rather than a refined title card.
- The fine frame line and the apostrophe alias at small sizes.
- In dark mode the maroon slab is the brightest thing on screen.
- A grey pulse, then a pop-in, on every open: 2 MB fetched after sign-in and not cached
  for offline use.
- Home shows two identities at once: the app's mark in the top bar and this banner.

**Recommended direction:** keep the concept and art-direct a phone version — fewer, bolder,
higher-contrast letter fills; one fine gold keyline; no inner frame or vignette; a deep
near-black or oxblood field, with a variant per theme. Ship responsive WebP or AVIF (about
100–200 KB, 1×–3×) and cache it with the app shell so it appears instantly. Optionally let
it collapse into the top bar on scroll, for one brand moment. Mock up at 375px in both
themes before replacing anything; the artwork stays private.

**Verdict:** design and asset work; web plus a small API change for format and caching. No
data change.

Evidence: `PrivateHero.tsx`, `routers/brand.py`, the asset in `apps/api/src/assets/brand/`,
`BrandMark.tsx`, `BrandLockup.tsx`, `docs/brand/`.

## Verification and limits

- Production API health and web version both reported `b6940227`, the reviewed `main`.
- Live reads used the read-only role through the live SQL helper. No write, no recorded
  check, no queued notification, no cinema-source or provider request.
- **Home was not rendered with real data in this session.** Signing in to production is
  not an agent's to do, and the local end-to-end seed has eight fake films with placeholder
  posters. The design verdict rests on the code, the real banner asset, live counts and the
  AA3/AB2 375px screenshots (fixture data, 27–28 Oct). A real-data 375px pass in both
  themes is the first step of any build.
- Point 1's collection figures are the 27 Oct read-only snapshot; the repetition does not
  depend on the exact numbers.
- No tests were run and nothing was built.

## Next step — Group AC drafted, awaiting a named sitting's go

Craig's answers are #335. Criteria, checkpoints and model/effort settings are in "Group AC
— the 4 Nov snags, drafted 4 Nov" in `docs/phase-batches.md`.

| Sitting | Batches and checkpoints |
|---|---|
| 1 | AC1 "Needs you" → Craig picks AC2's mock-ups → AC2 Home redesign and banner |
| 2 | AC3 cinema identities and first run versus rerun, stopping for the dry-run review |
| 3 | AC4 Movie night's At the cinema view and film pages → AC7 separate calendars |
| 4 | Schema approval → AC5 cinema trips → switch approval → AC6 new-film digest |

Sittings 1 and 2 are independent; 3 needs 2; 4 needs 3. Onboarding more people is not part
of the group and needs its own plan; nothing in it assumes exactly two people.
