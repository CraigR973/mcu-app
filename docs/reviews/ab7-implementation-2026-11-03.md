# Cinema discovery implementation and acceptance — 3 Nov

Authorisation: #327/#330/#334 and the owner's latest continue. AB6 fully closed first:
PR125/merge72ff0bd/final354f34c, exact seven-job main CI41683888744, fresh23:20UTC
API/web SHA/full readiness, accepted all-nine1838-row programme import/enable9. No AA10c,
other sitting, source request, production write, hosting or credential change in AB7.
This is the single AB7 branch/PR. The verbatim checklist is in the implementation contract.

## Behaviour and decisions

Authenticated `/cinemas` reads only the existing stored programme/zod contract. Home,
desktop Plan a screening, command palette and mobile You link to it; all five bottom slots
and the separate disc/release calendar stay intact. Intentional navigation inventory adds
only Cinemas under the already accepted #327/#334 route choice.

The default selection is one London date. Inclusive from/to controls allow up to14 dates,
venue checkboxes select known venues, and All/New/Older/Unclassified filters preserve
server counts before the category filter. Dates and showtimes use London civil time across
BST; original year, source release date, run/reissue and observation/source age stay separate.
Verified server identities group showing rows across sources; unresolved equal titles remain
separate possible duplicates. Watched older favourites are retained, with personal watch
status and ownership read from the existing server predicates.

Cached actions are checked against the current clock every30seconds, focus/online/offline,
and again at activation. Offline/failed/stale/unconfirmed/started observations have no showing
ticket action. HTTPS operator host/path validation and opener/referrer isolation apply;
Check tickets only opens the cinema. Official programme fallbacks remain, including all nine
on first-read failure. Partial/unavailable coverage, source failures, unknown release runs,
empty categories and the2,000-screening cap are explicit. Query keys include the profile;
a pending selection hides the previous selection's counts and actions.

Choices made under the approved contract: text-first cards use available programme fields,
category counts mean screenings, default one day keeps a phone readable, venue/source detail
expands on demand, and reload refreshes the stored view without initiating source collection.
No catalogue, diary, API/schema, fee or source contract extension. £0 source fees; existing
compute/storage/network usage remains unpriced.

## Verification record

Focused38 tests pass:9 URL/clock/official-fallback checks,8 page checks and21 exact navigation
inventory checks. Web/E2E typechecks and web lint pass (11 existing refresh warnings).
Browser cases use actual guarded disposable Postgres rows and the authenticated API, with no
programme response interception. They cover Craig/Mark in both375px themes, two sources for
one watched older favourite, two unresolved equal-title identities remaining separate,
pre-filter counts, category changes, source failure/unconfirmed and offline suppression,
Home/You/sidebar/keyboard/palette navigation, five bottom slots and signed-out protection.
The fixture compares catalogue/diary/programme counts before and after browsing.

Chromium first five functional groups and Firefox all6 cases have passed; the last Chromium
navigation run exposed a test readiness error before its new palette shortcut. It now waits
for the signed-in shell. Exact clean full local gate, complete browser suites, seven-job CI,
production deployment and actual programme/render comparison remain pending. No shipped claim.

Screenshots inspected from actual375px Chromium: both profile/theme filter views and the
scrolled film card; no horizontal overflow, wrapped venue rows and separate ticket/official
links. This proves simulated browser layout, not an affected iPhone's acceptance.

## Failures encountered and corrected

- New helper initially used a control-character regex rejected by eslint; character-code
  validation replaced it without a suppression. An unused import was resolved by the actual
  Today/Tomorrow controls. Approved exact navigation counts12/14 replace11/13; the unknown
  sections count initially remained13 and was corrected to the accepted14.
- New Year-unverified assertion matched two legitimate records; it now asserts exactly two.
- The DB fixture's JSON scalar was a Python mapping representation; SQL now returns JSON
  text explicitly. Canonical Vue slug and current owned listing predicate were checked
  against source before the actual case ran.
- A failed-check locator matched the new summary and date detail; the assertion now targets
  the exact venue/date detail. No failure message or assertion was removed.
- The new Chromium palette shortcut fired immediately after navigation before auth/layout
  mounted; the test now waits for its signed-in shell destination before pressing the key.

- The full local web gate caught the new London formatter outside the canonical date
  utility. Both London helpers moved into `lib/utils.ts`, preserving its shared UK date
  spelling; the date-forms guard and all existing assertions remain unchanged.

- A direct2,000-row formatting probe measured2,177ms creating formatters for each call.
  The same probe now takes74ms on this Mac (not a phone/browser benchmark). The two immutable Intl formatters are reused; date values and current-clock checks
  remain calculated per call. This removes allocation work without freezing dates/age.

## Retained live-data limits

The accepted3Nov17:13 snapshot stored1,838 rows/163 source-film identities/9 enabled venues,
with3 independently verified identities; stored Older1/New0/Unclassified1,837 at that time.
Future counts and Older availability decrease as starts pass. Original years/personal matches
remain unknown where unverified. Vue covers execution-day/tomorrow only; all other observed
partial horizons and unchecked dates are shown. New release population and recurring source
access/next08:00UTC scheduled refresh have not been proved. These limits are not waived,
invented or hidden by fixture success. Full source/write evidence remains in AB6's report.
