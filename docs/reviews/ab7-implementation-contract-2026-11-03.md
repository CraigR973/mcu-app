# AB7 implementation contract — 3 Nov

Authorised #327/#330/#334; standing completion approval and latest continue apply.
AB6 fully closed on clean main354f34c: final seven-job CI41683888744/API2621 no skips/
C63 F62+1 W61+2 jobs6, exact API/web/full readiness freshly rechecked23:20UTC. PR125
merged; actual all-nine Railway acceptance/exact1838-row programme-only import/enable9/
role guards/both-profile reads are documented. Data scope remains accepted; no new source
protocol/provider/category heuristic, paid service or request pass is required for AB7.
One new branch/PR, no stacking or other sitting. Ledger tier: GPT-5.6 Terra High.

## Acceptance criteria, verbatim

### AB7 — Find a film showing nearby (conditional)

**Authorised within sitting 5 (#327); waits for accepted AB6.** Film first and the full
contract including #326 categories are accepted. Do not start before AB6 closes on clean
green main with actual source/coverage acceptance and exact live checkpoints met.

- One view grouped by film, with approved venue selection, date/time and validated booking
  links. Multiple venues/showtimes remain distinct under a film. Show coverage and freshness;
  booking opens the venue, never buys a ticket. Preserve the current disc/release calendar.
- Include current new releases and older/reissue screenings, with the proposed
  All films/New releases/Older films/Unclassified selector (#326). Final run-category
  definitions are accepted in #327; Older films has no ten-year cut-off.
  Keep watched older favourites discoverable. Ownership and personal watch status may explain relevance; “older”
  cannot mean “unwatched”. Clearly label uncertain identity/year; no paid/model ranking assumed.
- Honest loading/empty/failed/stale/partial states. Settle navigation in the picked design,
  retain route/access assertions and seek approval for intentional inventory additions.
- Fixtures-backed browser → API → programme flow, personal watch isolation, multiple
  venues/showtimes, bookings and provider failure at 375 px/both themes. Full gate/exact-
  head seven-job CI/production SHA/readiness. Actual programme reads need separate live
  acceptance authorisation; show the delivered coverage, including any approved gaps.


## Concrete implementation and verification

- Authenticated `/cinemas`, existing stored GET/zod contract, shared navigation item under
  Plan a screening (automatically reaches command palette and mobile You), Home discovery
  link. Add only that approved route/access inventory entry; preserve five bottom tabs.
- Default one London calendar date; inclusive from/to controls up to14days plus known
  venue selection and server category filter/counts. Unchecked dates/venues never imply
  empty. No time/age/title guess, watched-film exclusion, model, poster fetch or data write.
- Film-first groups preserve server identity; source titles/venue/time/formats remain
  distinct. Explicit unknown identity/year, nullable ownership/personal watch status,
  separate run/reissue evidence and source/official links. Text-first layout avoids
  inventing poster or metadata dependencies absent from the accepted API.
- Profile/date/venues/category query keys; safe selection transitions, no old-selection
  booking actions. Last observation/attempt/source age and partial/failure/stale states
  remain visible even for empty category results. Booking actions check online/error,
  wire and current-clock age, future start and allowed host/path; official fallback stays.
- Meaningful component tests cover selection/counts/uncertainty/offline age/error/loading/
  truncation/keyboard and personal cache separation. Real browser→API→stored fixture
  programme tests cover both people/themes at375px, navigation, multiple venues/showings,
  watched older favourite, provider failure, external link attributes and no domain writes.
- Full normal ten-command clean gate, exact seven-job PR/main/final CI; Chromium/Firefox/
  jobs locally, WebKit in CI. Inspect actual screenshots; production real programme/render
  comparison and exact API/web/full readiness. Source gaps remain explicit, not test skips.

Decisions made under the accepted contract: date-range controls default to today, text
cards use only the available programme contract, category counts are screenings (labelled),
source/official links live with coverage, and cached/offline uncertainty suppresses booking.
Source subscription fees£0; existing resource cost remains unpriced. No new owner decision.
