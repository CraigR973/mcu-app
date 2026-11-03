# Vue ordinary anonymous session investigation — 3 Nov

Craig's “approved” accepted only the two-GET/45-second report-only plan (#333).
It ran once on clean a1604e86e9a1aac9a07904bba099d907789a77e7 after its exact PR
CI 41611271232 passed all seven jobs. No implementation or production action follows.

## Result

At 13:14 UTC on 3 Nov, both approved Vue GETs returned 200 in **1.454 seconds**:

| Request | Decoded bytes | Result |
|---|---:|---|
| St Enoch public What's On page | 347,160 | Ordinary page, no challenge; anonymous session cookie set |
| Same session: observed 4 Nov programme URL | 134,152 | 48 screenings / 15 films; session cookie sent |

Total 481,312 decoded bytes; largest response 347,160 bytes. The request start gap was
1.011637 seconds. No redirect, retry, alternate host/endpoint, extra script fetch, browser,
login, copied credential/cookie, challenge solving, TMDB request or database connection.
Only the page's ordinary cookies persisted in memory for this client. Cookie/header values
and raw response bodies were not saved. Status/timing/body SHA-256 and bounded normalised
programme/identity facts are preserved in ab6-vue-session-investigation-2026-11-03.json.
The public page had one parseable JSON script but no recognised dated sessions for 4 Nov;
the second request was therefore within the approved conditional scope.

## What the observation establishes

The previously refused **same 4 Nov URL** was reachable after an ordinary anonymous page
visit on the current runtime. All 48 sessions have the expected venue/film/session booking
identity checked by the existing parser, dated/offset starts and director/original-title/
runtime facts. Of these, 47 expose a source-enabled booking link; one does not. No ticket
availability, seat selection or purchase was independently exercised.

The parser marks this successful single-date response complete. That marker is not a
separate proof of the full operator programme, a complete multi-date horizon, missing-day
absence or cancellations. Today/other dates were not requested by this experiment.
This is a diagnostic specimen, not an eligible all-nine import artifact.

The page-then-session sequence succeeded once. **Session causality and recurring access
remain unproved:** the earlier refusal was at 09:07 UTC, this success at 13:14; no same-time
no-session control was authorised. Time, cache or source changes remain explanations.
Do not claim that cookies are required or that a second request without the page would fail.

## Identity evidence and the independent category gap

The fresh successful Vue response supplies independent director facts for all 15 films.
Three can be compared locally with the three existing 09:08 TMDB candidates, with no new
metadata request:

| Film | Vue / TMDB director | Vue / TMDB runtime |
|---|---|---:|
| Clayface | James Watkins / James Watkins | 108 / 109 min |
| Ghosts: The Possession of Button House | Simon Hynd / Simon Hynd | 97 / 97 min |
| Kiri and Lou Go Raaa! | Harry Sinclair / Harry Sinclair and Antony Elworthy | 62 / 61 min |

The existing corroboration function returns `director` for each comparison. The one-minute
runtime differences are retained; runtime or repeated title alone is not identity proof.
These are comparisons, not three approved mappings. The saved metadata records belong to
CinemaTimes source keys; the successful Vue rows have different keys. No metadata record
or source fact is copied between providers by title. A read-only call to the real mapping
validator with these Vue picks and the existing records refuses:
“Mapping pick missing, duplicate or not an observed candidate”.
Fresh source-specific metadata/corroboration in an eligible artifact and exact owner picks
remain required. No global ID was applied. All 48 diagnostic rows remain Unclassified;
no evidence proves a current first UK run, and GB release dates alone do not do so.
The earlier 1,800-row artifact remains failed and unchanged; these 48 are not patched into it.

## Re-plan and exact stop

Prepare only the concrete public-page-first build amendment in
ab6-vue-session-build-amendment-2026-11-03.md. It is **UNAPPROVED and unimplemented**.
It proposes the observed sequence without claiming the cause: one ordinary public-page
GET before the selected today/tomorrow Vue GETs, in the same in-memory anonymous session,
inside all existing caps. No other venue/provider, category or mapping rule changes.

Reject a today-only reduction because that horizon has not been independently established;
reject eight-venue/failed-prefix acceptance because it changes the approved product.
Reject more live experiments now: the approved two requests are spent and no further
source permission follows. All-nine freshness/actual row and identity review, exact mappings,
configuration apply/disabled deployment/production import/nine-row enable remain owner stops.
AB6 stays draft/undeployed; no AB7, AA10c or other sitting. Source fees £0; existing resource
cost remains unpriced. No app/database/configuration/hosting/credential change occurred.
