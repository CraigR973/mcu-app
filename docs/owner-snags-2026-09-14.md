# Owner snag list — 2026-09-14

Raised by Craig across 13–14 September 2026, in a session that **only captured them**.
Nothing here has been built or decided. The **Today** notes are what that session read in
the code while listening; anything marked **lead** or **to check** has not been verified.

**Status: captured, not triaged.** The next step is a triage session: investigate each snag
against the code and the running app, settle the open questions with Craig, and propose
batches for his approval. No code before he approves.

**Still explicit, per `AGENTS.md`:** deleting stored data (snag 4), and any hosting or
credential change — Letterboxd or eBay API credentials included (snags 7, 10).

## At a glance

| # | Snag | Kind |
|---|---|---|
| 1 | Archive header is too crowded; search moves to the bottom bar | Layout |
| 2 | Merge Calendar and Coming soon, led by Blu-ray and 4K releases | Feature change |
| 3 | The app zooms like a web page | Bug |
| 4 | Remove Gift links | Removal |
| 5 | Refine the menu | Navigation |
| 6 | Check Movie night against the behaviour Craig wants | Check, then feature |
| 7 | Quick add from Home, offering to sell existing copies on eBay | Feature |
| 8 | Some features for Mark and Craig only | Access |
| 9 | Letterboxd links should open the film in the Letterboxd app | Bug |
| 10 | Sign in to Letterboxd; sync watchlists and watched dates | Feature, feasibility unknown |
| 11 | Decide the opening screen and the bottom bar | Navigation |

**How they depend on each other.**

- **5, 8 and 11 decide the shape of the navigation.** 1 (search) and 7 (quick add) place
  things inside that shape, so settle 5, 8 and 11 first.
- **6 and 10 both need watch history.** 10 is how that history would arrive, and may be
  blocked on Letterboxd.
- **2 needs a source of Blu-ray and 4K release dates.**
- **3, 4 and 9 look independent** of everything else.

## The snags

### 1. Archive layout: too much at the top

**Craig's ask.** The Archive has too much at the top. Move the search bar into the bottom
bar, usable from any screen, the way Letterboxd does it. The top of the Archive keeps only a
small filter button and a way to change the view.

**Today.** The search bar is part of the app shell's header on every signed-in page
(`apps/web/src/components/layouts/AppLayout.tsx`); below 1024px it sits as a second row under
the brand bar. The bottom bar (phones and tablets, `MobileTabBar.tsx`) is
Archive · Wanted · Movie night · Home · More.

**To check.** What the Archive page itself (`MoviesPage.tsx`) renders above the grid — not
opened. How search should open from the bottom bar.

**Related:** 5, 11.

### 2. Calendar and Coming soon become one screen

**Craig's ask.** Combine them. Cinema releases are good to keep, but the main thing the
screen should show is Blu-ray and 4K releases.

**Today.** Two separate menu items and routes: Coming soon is `/discover`
(`DiscoverPage.tsx`), Calendar is `/calendar` (`CalendarPage.tsx`). Neither was opened.

**To check.** Where each gets its dates, and whether the app has any source of Blu-ray and 4K
release dates for the right country. **Leads:** TMDB's release dates carry a "Physical"
release type per country; Batch 23's spec scraper already reads Blu-ray.com pages.

### 3. The app zooms like a web page

**Craig's ask.** It shouldn't zoom. It should behave like an app, not a web page.

**Today.** Not examined.

**To check.** Which zoom it is — pinch-to-zoom, double-tap zoom, or the phone zooming in when
a small text box is tapped. Each has a different fix. Test the installed home-screen app as
well as the browser. **Trade-off to raise with Craig:** blocking pinch-zoom outright stops
anyone enlarging small text, so if that is the only fix for the zoom he means, it is his call.

### 4. Remove Gift links

**Craig's ask.** Remove the section — his dad doesn't want it.

**Today.** An admin-only page, `/gift-links` (`GiftLinksPage.tsx`), listed under
Administration, and a public page, `/gift/:slug` (`GiftPage.tsx`), that opens without signing
in. The API endpoints and table behind them were not examined.

**To check.** Everything the feature touches — API, table, migrations, command palette,
tests — and whether any gift links exist in production. Removing the pages and endpoints is
ordinary work; **deleting stored gift-link rows is a destructive data operation and needs
Craig's explicit go-ahead.**

### 5. Refine the menu

**Craig's ask.** Collections, Box sets, Insights, Stats and Home feel like they could all be
one page (he asked for an opinion). Later: beyond those suggestions, the menu can be refined
further.

**Today.** The sidebar (`apps/web/src/lib/nav-items.ts`, `Sidebar.tsx`) shows 14 items in
four groups, plus Administration for admins:

| Group | Items |
|---|---|
| The archive | Movies, Wanted, Box sets, Collections |
| Plan a screening | Loans, Coming soon, Calendar |
| Explore | Insights, Deals, Home, Stats |
| Personal | Movie night, Notifications, Assistant |
| Administration | Add a disc, Trash, Audit log, Retailers, Gift links, Admin |

AI settings is defined as a destination but sits in no sidebar group. What the five pages hold:

- **Home** (`/dashboard`) — On this day, Worth a rewatch, recent activity (last 20 events),
  pinned collections. It is not where the app opens (see 11).
- **Stats** (`/stats`) — counts (films, discs, identified, watched); bar charts for formats,
  where discs live, genres and decades; Most watched; Spend over time; export as CSV, JSON,
  HTML or a printable list.
- **Insights** (`/insights`) — completion sets: how much of each director's and actor's work
  is owned. Filterable, an admin "Refresh from TMDB", a detail view per set.
- **Box sets** (`/box-sets`) — physical boxes with completion bars; admins create them; each
  has its own page.
- **Collections** (`/collections`) — smart collections: saved filters that stay current; can
  be edited, deleted and pinned to Home.

Several of these are thin in production. `STATUS.md`'s Batch 37 entry records `watch_log` as
empty, which empties On this day, Worth a rewatch and Most watched; a code comment in
`StatsPage.tsx` says Spend over time is empty because no disc has a purchase price. Re-check
both.

**Proposal from the capture session — not agreed by Craig.**

- **Home, Stats and Insights become one Home page.** All three are for reading, not managing.
  Counts first, then recent activity, the breakdowns, and the sets closest to complete with a
  "See all". Empty sections hide. Export moves to Admin.
- **Box sets and Collections move into the Archive.** Collections become saved filters under
  the new filter button (1); Box sets become a view in the view switcher.
- **Not all five on one page:** that is a long scroll mixing reading with editing — the same
  "too much on one screen" problem as snag 1.
- **Count, corrected.** The capture session told Craig 15 items would become 10. The sidebar
  actually shows 14, because AI settings is not in it. The merges above plus snag 2 take it to
  9; a single Settings page (Notifications + AI settings) keeps it at 9 and brings AI settings
  back into the menu.

**Still open:** Craig wants more trimming than this. Snag 8 also hides four items from
everyone except Mark and Craig.

### 6. Movie night

**Craig's ask — how it should work.**

- A session has at least 2 people.
- Anyone can suggest films; everyone can vote on other people's suggestions and add their own.
- Opening a film on this screen shows all of its details.
- If the film isn't in the Archive, it shows which streaming services have it.
- It shows whether the others have watched it before, and when.

**Today.** Built by Batch 35 (shipped 2026-09-10). Routes: `/movie-night`,
`/movie-night/join/:token`, `/movie-night/:id`. The route comment in `App.tsx` talks about
"both people" voting by swiping, which suggests it was built around two people. Not examined
further.

**To check.** Each point above against what the feature actually does, including whether a
session holds more than two people and where suggestions come from. **Lead:** TMDB publishes
streaming availability per country. "Seen before, and when" needs watch history, which is
empty per the last notes (see 10).

### 7. Quick add from Home, and offer to sell existing copies on eBay

**Craig's ask.** Adding a new Blu-ray should be super easy — very quick for Mark, and on the
Home screen. When he adds one, the app offers to list any copies of that film he already owns
for sale on eBay (for example, the old Blu-ray when the 4K arrives).

**Today.** Adding a disc is `/collection/add`, admin-only. The header's "Add a disc" button is
hidden below 640px (`hidden sm:inline-flex` in `AppLayout.tsx`), so a phone has no add button
in the header.

**Leads, not checked.** Barcode scan and lookup flow (`590504d`, Batch 24). Format upgrade
path and sale tracking (`1cef93c`, Batch 29). Production health reports `ebay: configured`.

**To check.** The add flow end to end on a phone, and how many taps it takes. Whether Mark's
account can add at all. What "list for sale on eBay" does today — a real listing, eBay opened
prefilled, or only a recorded sale — and which eBay credentials it relies on.

### 8. Mark and Craig only

**Craig's ask.** Only Mark and Craig can see and use: the quick add button (7), Loans, Deals,
Retailers and Wanted.

**Today** (`App.tsx`). Admin role only: Add a disc, Retailers. Any signed-in person: Loans,
Deals, Wanted.

**To check.** Who holds the admin role — the Admin page is labelled "Craig's tools", which
hints it may be Craig alone. What other accounts exist and their roles. Whether "Mark and
Craig" should be the admin role or something new. It must be enforced by the API, not just
hidden in the menu, matching the codebase's pattern of pages hiding what the API refuses.
Wanted is in today's bottom bar, so other people's bottom bar changes too (11).

### 9. Letterboxd links

**Craig's ask.** Letterboxd links open a search on the Letterboxd website. They should go
straight to that film's page, opened in the Letterboxd app.

**Today.** Where the link is built was not examined.

**Leads, to test on a real phone.** Letterboxd accepts links by TMDB id
(`https://letterboxd.com/tmdb/<id>`) that redirect to the film's page. With the app
installed, letterboxd.com links may open in the app rather than the browser.

### 10. Letterboxd sign-in and sync

**Craig's ask.** People can sign in to Letterboxd inside the app, so it can sync their
Letterboxd watchlist and watched films — including watched dates — into the app.

**Feasibility comes first.** As far as the capture session knew, Letterboxd grants API access
only on request; if so, applying and holding the credentials is Craig's. If access is not
granted, the alternatives to evaluate are importing Letterboxd's own data export and reading a
person's public diary feed — both unverified leads. Avoid any design where people type their
Letterboxd password into this app.

**Today.** The app has a watch log and a `/watchlist` route; neither was examined.

**Related:** 6 needs the watch history this would supply; 9.

### 11. Opening screen and bottom bar

**Craig's ask.** Decide which screen the app opens on, and what goes in the bottom bar. It
overlaps earlier snags and is a snag in its own right.

**Today.** A signed-in person lands on the Archive: `/` redirects to `/movies`
(`HomePage.tsx`). The bottom bar is Archive · Wanted · Movie night · Home · More, where More
opens the full menu. The floating assistant button covers controls on phones;
`OWNER-ACTIONS.md` item 11 lists making the assistant a sixth tab as one fix.

**Inputs from the other snags.** Search joins the bottom bar (1). Home gains quick add for
Mark and Craig (7). Wanted becomes Mark-and-Craig only, so everyone else's bar can't include
it (8). The menu merges change what Home is (5).

**Parked question for Craig:** should the app open on the new Home page instead of the
Archive? He asked for it to be raised once every snag was in; it was re-asked at the end of
the capture session. If no answer is recorded here, ask it first.

## Open questions for Craig

1. **Where is the eBay functionality today?** Craig asked; the capture session deliberately
   did not answer. Leads under 7.
2. **Which screen should the app open on?** (11)
3. **Menu:** the two-merge proposal or all five on one page — and how much further to trim. (5)
4. **Who "Mark and Craig" is in the system** — the admin role or something new — and who else
   has an account. (8, 6)
5. **Gift links:** delete the stored rows, or remove the feature and keep them? (4)
6. **Zoom:** if the only fix blocks pinch-zoom outright, is that acceptable? (3)
7. **Letterboxd:** will Craig apply for API access if it is needed, and is importing a
   Letterboxd export an acceptable fallback? (10)
