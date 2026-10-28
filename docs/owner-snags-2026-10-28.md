# Owner snags — 28 Oct 2026, reconciled against the code

**Status: reconciliation only; no product changes or new batch run authorised.**
Craig raised eight points, then asked for them to be reconciled against the code.
Reviewed source and production were both `3e07c1983031995b69a7a60a3e27da7a04dad4c7`.
The checkout started clean on `main`. This report and the session handoff are on
`chore/owner-snags-2026-10-28`; nothing has been pushed or deployed.

## Findings that matter first

- **Needs attention is demonstrably wrong.** Production reports one waiting identification
  proposal and 48 year mismatches, while the real queue and open-doubt services both return
  zero. Re-running the check's read-only calculation still produces 1 and 48: this is a
  disagreement between queries, not merely yesterday's result waiting to refresh.
- **The watched count currently includes films outside the collection.** Craig's live
  numbers are 500 diary titles versus 482 owned diary titles; Mark's are 879 versus 878.
  There are 1,903 currently owned titles. Craig's new request changes the earlier choice
  recorded in decision #299, only for the meaning of the Home watched number.
- **The iPhone reports remain open.** Production already serves the Home start URL and the
  source has an opaque top bar. Neither observation proves what an installed iPhone shows.

## All eight points

### 1. “app still opens on archive not home”

**Current behaviour:** the manifest already declares `start_url: '/'`, including the live
manifest fetched on 28 Oct. The root page sends a signed-in person to `/dashboard` (Home),
and a signed-out person to login. Login preserves an explicitly requested destination.
There is no current root-to-Archive redirect.

**Verdict:** the code change shipped in AA1; the installed-device problem remains unresolved.
The existing owner action asks each iPhone to remove and re-add the app. This session has no
evidence that this has happened. An old installation or resuming an existing page is a
possible explanation, not a confirmed diagnosis.

**Next verification:** establish whether the affected installation was re-added after AA1,
then compare a fresh launch with resuming a page. Keep notification/deep-link destinations
working; forcing every navigation or foreground event to Home would break them.

Evidence: `apps/web/vite.config.ts`, `HomePage.tsx`, `LoginPage.tsx`, `ProtectedRoute.tsx`,
and the AA1 owner action. No iPhone session was exercised.

### 2. “do you think we neeed small descriptions under each thing in the collection piece on home page”

**Current behaviour:** all five number cards already have supporting text. They explain
titles, physical/download copies and overlap, valuation coverage, diary watches, and TMDB
matching. The valuation card has a longer explanation behind a disclosure.

**Recommendation:** yes to one short meaning under each number. Revise the wording and
hierarchy rather than adding another explanatory layer. “Titles owned” currently only says
“Films and TV series”; it could explain that several copies still count as one title.
The watched description must change with point 3.

**Verdict:** wording/design refinement over existing functionality. No new data is needed
just to add or shorten descriptions; any proposed number change is a separate contract
decision.

Evidence: `apps/web/src/components/dashboard/CollectionShelf.tsx`.

### 3. “i want the watched count to be the watched count against the collection”

**Current behaviour:** the API counts distinct titles in the signed-in person's non-deleted
diary entries, without restricting them to owned titles. Home explicitly describes this as
including titles not owned. Existing tests preserve that older meaning.

**Requested behaviour:** the person's distinct watched titles intersected with the current
collection, shown against the current owned-title total. Rewatches and multiple copies must
not increase the numerator. Sold, donated or binned copies must follow the existing ownership
rule; a title still counts while at least one owned copy remains. Downloads remain owned
copies. The diary itself stays intact.

Read-only production comparison on 28 Oct, using the real ownership predicate:

| Person | Current diary count | Owned watched / collection |
|---|---:|---:|
| Craig | 500 | 482 / 1,903 |
| Mark | 879 | 878 / 1,903 |

**Verdict:** confirmed meaning change, already requested by Craig. Recommend an additive
collection-watched field so the existing diary field keeps its contract. Plan that API/shared
schema change explicitly before implementation. Record a scoped supersession of #299 when
the build is agreed; it does not change the identified-title metric.

Evidence: `apps/api/src/routers/stats.py`, `models/collection_item.py`, shared stats schema,
`CollectionShelf.tsx`, and the Home tests.

### 4. “everyone but Mark should get a notification when he adds a new film to the collection”

**Current behaviour:** adding a copy records who added it and an audit action, then commits.
It does not enqueue a notification. Existing notification categories cover deals, sales,
releases, loans, movie nights and operational attention; there is no collection-add category.
The push outbox, recipient preferences, quiet hours and delivery service already exist.
Recent activity on You is a separate read of collection/audit history, not a push.

**Verdict:** a missing feature, not a failed existing sender.

**Recommended scope:** a successful Mark addition of a title newly entering the collection
queues one notification for each other active profile, excluding Mark. Reuse the existing
outbox and delivery preferences, link to the film, and prevent retry duplicates. Notify only
after a successful collection change; cancellation or a failed duplicate check sends nothing.

**Choice before build:** “new film” most naturally means the first owned copy of a title,
rather than another edition/copy. That is the recommendation, not a choice Craig has yet
confirmed. Do not silently broaden the trigger to additions by everyone. A new notification
preference/category may require a migration and explicit data-shape approval. No push was
sent in this review, and actual phone receipt remains an owner observation.

Evidence: `apps/api/src/routers/collection.py`, `models/notification.py`,
`services/notifications.py`, and the activity endpoint in `routers/stats.py`.

### 5. “the needs attention bit on home screen shows nothing needs my attention when i click on it”

**Current behaviour, verified live:** the latest saved check at 08:02 UTC on 28 Oct reports:

| Check | Home reports | Actionable service now |
|---|---:|---:|
| Waiting identification proposals | 1 older than a fortnight | Queue: 0 |
| Disc/review year disagreements | 48 titles | Open doubts: 0 |

The current check function produces the same two warnings when called in a read-only
transaction. Waiting proposals are counted from old `IdentifyLookup` rows without the
queue's current unidentified/owned-film eligibility. Year disagreements are counted from
spec notes and mismatched reviews, without the open/actionable-doubt rule. Historical
evidence can therefore remain counted after the thing to act on has gone.

The Home row also reads a daily snapshot, and identification actions do not invalidate its
query. Those are additional freshness gaps; invalidating the browser cache alone cannot fix
the query disagreement above.

**Verdict:** confirmed defect. Make the check use the same actionable predicates as the
destination, preserve legitimate old-proposal warnings, and refresh affected attention after
resolution. Do not delete evidence or clear historical rows merely to hide the warning.

**Related link defects:** the eBay action opens generic Settings, whose default tab is
Notifications, and “Open Assistant settings” opens the chat page. Plan precise destinations
as part of this repair. Existing attention tests check the mapping's strings, not whether a
linked screen contains the reported issue; regression coverage must cross that boundary.

Evidence: `services/health_checks.py`, `services/identify/queue.py`,
`services/identify/doubts.py`, `routers/attention.py`, `AttentionRow.tsx`,
`IdentifyFilmsPage.tsx`, and `SettingsPage.tsx`.

### 6. “the top bar is still blurred on iphone”

**Current behaviour:** the top bar and search sheet use opaque `bg-background`; the top bar
has no blur filter. Tests pin that token. The page-dimming search/modal overlays intentionally
use blur, and the bottom bar still uses blur. The document still requests iOS's
`black-translucent` status-bar style.

**Verdict:** unresolved device defect/appearance report. An opaque CSS token and passing
desktop tests do not demonstrate sharp iPhone rendering. The iOS status-bar setting and
the distinction between the app header and system clock area are diagnostic leads only.

**Next verification:** inspect the affected screen on the installed iPhone, theme and Search
state, distinguish app content from the system status bar, and compare the served version.
Use a real-device before/after for any repair. Do not prescribe another colour change or
remove every overlay blur without reproducing the reported surface.

Evidence: `AppLayout.tsx`, `AppLayout.test.tsx`, `MobileTabBar.tsx`, and `apps/web/index.html`.

### 7. “i quite liked the collection breakdown, maybe we can find a nicer way to reintroduce this”

**Current behaviour:** it has not been removed. “Collection breakdown” is a closed disclosure
under the numbers. It contains format, location, genre and decade bar charts, plus recorded
spending when the data supports it. Genres show the top 12; multi-format and multi-genre
counts deliberately overlap.

**Recommendation:** make a small visual preview visible by default, with the full breakdown
one tap away. Review a phone-sized layout alongside the descriptions and owned-watched
number before choosing the design. Reuse the existing aggregates and preserve overlap and
missing-spend explanations.

**Verdict:** discoverability/design refinement. It needs a layout decision, not restoration
of a missing data pipeline.

Evidence: `CollectionShelf.tsx` and the Home tests that expand its breakdown.

### 8. Nearby cinema discovery, especially older releases

Craig's venues, preserved as the intended scope:

1. Odeon Kilmarnock
2. Glasgow Silverburn Cineworld
3. Odeon Glasgow Quay
4. Odeon Braehead
5. Odeon East Kilbride
6. Glasgow Science Centre
7. Glasgow Film Theatre
8. Everyman Glasgow
9. Vue St Enoch

**Current behaviour:** the calendar imports UK theatrical release dates and disc release
dates from TMDB. It does not ingest these venues, their programmes, individual showtimes or
booking links. Movie-night “screenings” are private plans, not cinema listings. A theatrical
release calendar cannot answer what an older film is showing locally this week.

**Verdict:** a new feature with a separate source-feasibility step. First establish reliable,
permitted programme sources for these nine venues and their coverage of repertory/reissue
events. Venue names, current operation, feeds, access terms, costs and coverage have not
been researched in this code reconciliation.

**Recommended product direction:** one local-cinema view, grouped by film, showing venue,
date/time and booking link, with older releases easy to find. Ownership and the person's
watch history could help explain a recommendation. Do not equate “older” with “unwatched”,
or treat failure to fetch a programme as “nothing showing”. No provider, model, geolocation,
paid plan or scraping approach has been selected.

Evidence: `services/calendar.py`, `tmdb/client.py`, `ReleasesPage.tsx`, and a source search
across API, web and shared packages for venues/showtimes.

## Verification and limits

Production API health and web version matched the reviewed SHA; readiness returned `db: ok`
and configured push/AI/eBay/TMDB/Brave. The latest exact-main CI run, 40663082493, succeeded.
The live manifest returned `/` as its start URL.

Database inspection used read-only transactions with a statement timeout. The actionable
queue, open-doubt count and health calculation were the actual application functions;
no check result was recorded and no notification was queued. The first ad-hoc watch-count
query referenced a non-existent `is_sold` column and was refused; the corrected read used
the application's canonical ownership predicate. No data changed.

Focused existing tests: **42 passed across three files** (Home, attention and app layout).
They emitted server-render `useLayoutEffect` warnings, missing Sentry-upload-token warnings
and localhost:3000 connection-refused noise; the test process still exited successfully.
These are source/fixture checks, not the full gate, browser E2E or iPhone proof. No assertions
were changed. No cinema site, eBay/TMDB/AI provider or live push was exercised.

## Suggested next step — not an execution plan

Prepare a scoped proposal covering the confirmed attention defect, collection metric/design
changes, Mark's addition notification, and real-device diagnosis. Treat cinema-source
feasibility as separate discovery. Show the whole proposed batch/sitting plan and wait for
Craig's go before a multi-batch run. Do not invent model/effort settings or start AA10c;
the existing valuation and phone owner checkpoints remain open.
