# AA5 — Film details on a night, 25 Oct

## Agreed scope and acceptance criteria (verbatim)

### AA5 — The film's details on a night 🟡
- **19.** Each film on a night shows, for each person: when they last watched it and their own
  rating (the app's, which already holds their Letterboxd ratings from the diary sync; "not
  rated" otherwise); where to watch it (shelf location first, else streaming); runtime; IMDb's
  score; a Letterboxd link. Letterboxd's average is not shown: it has no public API.
- **IMDb's score** comes from IMDb's daily `title.ratings` file, matched on the stored IMDb id,
  inside an existing nightly job (no new Railway service, so no hosting change). New columns
  granted as above.
- Tests. Gate green.


## Pre-flight

Clean main `006196d`; final CI 40204699272 passed all seven jobs, both production hosts on that
SHA, db ready and all integrations configured. AA4 closed in PR #108; only AA5 is in scope.
AA6 follows only after AA5 closes; sitting 4 is not authorised.

IMDb's official [dataset documentation](https://data.imdb.com/non-commercial-datasets/)
defines a daily UTF-8 gzipped TSV with tconst, averageRating and numVotes. Its
[non-commercial conditions](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX)
require personal/non-commercial use, the designated datasets and the stated attribution.
The UI will carry that acknowledgement; this remains a private two-person app.
No IMDb file or other live provider acceptance run has been performed by the agent.

## Design within the agreed scope

- Nullable IMDb fields on movies and night-only suggestions: score, votes, checked time and the source IMDb id. A corrected IMDb identity hides its old score until refreshed. Keep only ratings for
  stored IMDb ids; reject a full IMDb mirror and per-card IMDb requests.
- Unowned suggestions cache runtime and IMDb identity on their existing snapshot, with a lookup
  timestamp. Reject adding catalogue rows just because a night is opened; preserve all ids and
  votes. Existing watched/wanted film rows can supply their known metadata/history.
- Last watch and the latest explicit personal rating are separate: an unrated rewatch does not
  erase a known opinion. Only current participants and non-deleted history are shown.
- Reuse the nightly 02:00 UTC spec/review process; no new service, credential or hosting change.
  A failed or malformed file must preserve the previous scores and report failure.

## Local evidence

- API lint/format/mypy passed; full API suite 2,460 passed, nine local Unix-socket import-guard skips. Final focused suite after the historical-film correction: 56 passed. CI must run the database cases without those skips.
- Shared 154 and web 682 tests passed; shared type/build and web lint/type/build passed (11 existing lint warnings).
- Migration 067 upgraded, fully reversed to base, and re-upgraded on an isolated throwaway Postgres. All 11 new columns are readable by both guarded roles; invite tokens and PIN hashes remain withheld. No production test writes.
- Chromium and Firefox exercise personal history, shelf precedence, the real nightly command under the fake outside world, IMDb score/votes, external-film metadata without catalogue creation, and Letterboxd links. A 375 px screenshot was inspected; link spacing was corrected. Final local totals: Chromium 34 passed; Firefox 33 passed plus its documented dictation skip; cron six passed. WebKit is unavailable on macOS 13 and must pass CI. Exact-SHA CI is recorded below at close-out.
- Refusal, malformed/truncated gzip, no matching ids and whole-request timeout preserve old scores; failures are visible through the existing heartbeat and health check. Source identity correction hides stale scores; a newer cache wins. An unrated rewatch retains the latest explicit rating, and explicitly linked historical films retain history after soft deletion.

## Failures encountered and corrected

- Gzip inferred write mode from the spool; explicit read mode fixed it. A TMDB test fixture lacked its required logo field; the fixture was completed.
- Initial formatting/import and IO/generic typing errors were corrected without suppressions. IMDb attribution added a second link, making a test selector ambiguous; the selector now selects the intended film link. Testing Library did not support the attempted exact option; an anchored name matcher replaced it.
- The numeric-bound test caught a missed int32 vote limit; it failed again before the actual source patch landed, then both targeted cases and the full API suite passed. No assertion was weakened.
- The new browser fixture initially reused a film owned by the barcode test, causing its duplicate check to return 409. The AA5 scenario now owns a dedicated fictional film. The barcode test is unchanged. The obsolete browser run was interrupted and the full browser/cron run restarted.
- The first phone screenshot showed adjacent links without a gap; a wrapping, spaced row fixes it.

## Production limits

The first live IMDb refresh belongs to the existing scheduled 02:00 UTC job; no manual live IMDb/provider acceptance run was started. Until a successful scheduled refresh, the UI honestly says the score is unavailable. Real iPhone/camera/speech/push acceptance remains Craig's (6.2, 5.6, 9.5 and 8.4/16b). The production browser is signed out; signed-in rendering is exercised by the local and CI browser suites, not claimed as a live phone check.
