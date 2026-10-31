# Nine-cinema source feasibility — 31 Oct 2026

**Owner choice: keep it free with official programme links; Film first concept selected.**
Craig chose £0 provider subscription and no unified showtimes yet. All nine intended
venues remain in scope; no omissions were approved. Paid API routes below remain research
alternatives, not the selected direction. A future link-based screen needs a revised build
contract; the programme ingestion/discovery sitting is not authorised by these picks.

**Approved historical sample failed:** one GET of the 29 Oct UK archive returned HTTP 403.
No rows were obtained or retained; no retry or alternate source request was made. This
provides no historical coverage, real payload, booking or older-film evidence. AB5's
original programme-evidence criteria remain unmet; Craig explicitly accepted the report
as complete with programme feasibility unproven. Integration waits for green CI.
Sitting 5, AB6/AB7 implementation and AA10c remain excluded.

Accepted finalisation contract: `ab5-finalisation-2026-10-31.md`.

## Authority and evidence boundary

Craig authorised sitting 4 only on 31 Oct using `group-start.md`. The ledger maps AB5 to
Opus 5 high / GPT-5.6 Sol High. This report does not revise that mapping or claim a model switch.
Starting checkout: clean `main`, `a3e41f1`; fetched origin matches. Main CI 41193175977
passed before research. Working branch: `chore/ab5-cinema-feasibility`.

Public venue pages, indexed public descriptions, provider documentation, pricing and terms
were read. After the report, Craig approved exactly one bounded historical archive GET;
it returned 403 before any programme data was obtained. No API data request, account,
trial, purchase, form submission, booking journey, geolocation, credential change or
production request/write was made. Search results incidentally contain titles and dates;
these are research leads, not approved programme specimens or current availability proof.
Documentation examples are provider-authored examples, not real samples of these venues.

No application code, schema, endpoint, job, route or architecture structure changes.
Document/source checks replace the application gate for this report, as AB5 specifies.
No PR merge, main push or app deployment is part of reaching this owner checkpoint.

## The nine intended venues

“Identity confirmed” below means a current operator or venue-host page supports the venue
name; it does not establish a machine-readable programme, licence or provider coverage.
ODEON's current help list includes all four intended branches. Branded names are preserved
as aliases, never used to substitute a different venue. [ODEON branch list](https://help.odeon.co.uk/hc/en-gb/articles/360015944860-Which-ODEON-cinemas-offer-Order-and-Collect)

| Intended venue / current identity | Public-source evidence | Programme / older-film coverage |
|---|---|---|
| [ODEON Kilmarnock](https://www.odeon.co.uk/cinemas/kilmarnock/) | Operator help lists Kilmarnock; official cinema URL returned a redirect loop to the research browser. | UK Cinema API names ODEON as a chain. This branch, horizon, reissues and links unverified. |
| [Cineworld Glasgow — Silverburn](https://www.cineworld.co.uk/cinemas/glasgow-silverburn) | [Silverburn venue host](https://www.shopsilverburn.com/retailer/cineworld/) confirms Cineworld; operator page returned 403. | Chain claimed by UK Cinema API. Individual programme/reissues unverified. Do not substitute Renfrew Street or Science Centre. |
| [ODEON Luxe Glasgow Quay](https://www.odeon.co.uk/cinemas/glasgow-quay/) | [The Quay venue host](https://www.thequayglasgow.com/cinema/) confirms Luxe Glasgow Quay. Operator page looped. | Same ODEON candidate; branch-specific programme/reissues unverified. |
| [ODEON Braehead](https://www.odeon.co.uk/cinemas/braehead/) | [IMAX theatre directory](https://www.imax.com/theatre/odeon-braehead-imax) confirms Braehead at X-scape, Kings Inch Road. Operator page looped. | Same ODEON candidate; IMAX venue capability is not proof a particular screening is IMAX. |
| [ODEON Luxe East Kilbride](https://www.odeon.co.uk/cinemas/east-kilbride/) | [EK venue host](https://eklife.co.uk/shops/odeon-luxe/) confirms ODEON Luxe in The Hub. Operator page looped. | Same ODEON candidate; branch-specific programme/reissues unverified. |
| [IMAX at Glasgow Science Centre](https://www.glasgowsciencecentre.org/imax) | [Science Centre](https://www.glasgowsciencecentre.org/imax) says it owns/manages this independent cinema, with Ticket Tailor box office. | Public page advertises older-film returns, including The Shining, alongside features and educational shorts. Provider inclusion and exact screening evidence unverified. |
| [Glasgow Film Theatre (GFT)](https://www.glasgowfilm.org/all-listings/) | [Official listings](https://www.glasgowfilm.org/all-listings/) and [Now Booking A–Z](https://www.glasgowfilm.org/now-booking-a-z/) establish the venue/programme. | Index includes anniversary/restoration labels such as Donnie Darko and Pan's Labyrinth. Strong repertory research lead; provider coverage unverified. |
| [Everyman Glasgow, Princes Square](https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/) | [Official venue](https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/) confirms Glasgow, Unit 3–5 Princes Square. | Chain claimed by UK Cinema API. Everyman advertises Throwback nationally; Glasgow-specific older-film availability unverified. |
| [Vue Glasgow St Enoch](https://www.myvue.com/cinema/glasgow-st-enoch/whats-on) | [Official venue](https://www.myvue.com/cinema/glasgow-st-enoch/whats-on) confirms St Enoch Centre, 55 St Enoch Square. | Chain claimed by UK Cinema API. Parsed page showed a no-matching-showings shell; that is not evidence of an empty programme. |

The venue names above link to the nine official programme targets found during research.
ODEON redirect loops and Cineworld 403 remain unresolved access limits; those links are
not represented as validated booking journeys. No new source requests were made to add
these already researched targets to the report.

Count: nine identities supported; seven branches belong to explicitly advertised API chains;
zero of nine have an approved provider coverage specimen. The two independent venues are
especially important to the older-film goal and cannot silently become out-of-scope.

## Source options and permissions

### UK Cinema API — evaluated paid alternative, not selected

[Published coverage](https://uk-cinema-api.co.uk/) names ODEON, Cineworld, Vue and Everyman,
plus independents. The operator says collection updates daily. “All UK” marketing is not
a guarantee of these nine venues, every special event or cancellations in real time.

| Question | Published evidence / remaining gap |
|---|---|
| Shape and identity | [v4 documentation index](https://developer.uk-cinema-api.co.uk/) lists films, cinemas, showtimes and lookups by chain/external ID. Record fields, nullability, authentication header and ID persistence could not be inspected in the raw specification: browser unavailable, direct documentation GET 403. Do not infer them. |
| Film matching | Operator claims IMDb/TMDB matching. Its archive documentation describes optional IMDb/TMDB IDs. Real ambiguous, unmatched, reissue and multi-film responses still need approved specimens. |
| Booking and horizon | Plans advertise booking links. Destination correctness, link longevity, maximum horizon and event inclusion need samples; no guaranteed horizon found. |
| Freshness/cancellations | Daily collection advertised; not a cancellation SLA. Archive documentation describes first/last-seen and omitted withdrawn shows, but this is not a guarantee of corresponding live fields or immediate withdrawal. |
| Access and limits | Paid API; Lite 1,000 requests/day, 1 request/sec, ten selected cinemas, selection change once/month. Exact API credential handling remains to verify. |
| Licence/retention | [Current terms](https://uk-cinema-api.co.uk/terms) allow paid subscribers to display/cache supplied data; delete cached data within 30 days after subscription ends. They do not supply a numerical accuracy/cancellation SLA. Trial cache rights and whether permitted regression fixtures can survive cancellation need clarification before storing samples long-term. |

The [free historical archive](https://uk-cinema-api.co.uk/archive) is a useful evaluation
option, not a live source. It publishes daily compressed CSVs after screenings have started;
one row per film per showing, shared showing ID for multi-film events. Its licence covers
the provider's compilation rights only, with attribution; it grants no rights over underlying
cinema or TMDB data. It cannot prove upcoming coverage or booking-link health. The one approved file request returned 403; no file or rows were obtained. Its exact
scope and result appear below.

### MovieGlu — quote-based alternative

[Pricing](https://movieglu.com/pricing/) offers per-location and request-tier options without
public numeric tariffs. [FAQ](https://movieglu.com/contact/) describes cinema deep links,
not seat selection/payment. No price enquiry was sent.

[Showtime documentation](https://developer.movieglu.com/v2/api-index/cinemaShowTimes/)
describes a cinema object, films array, film IDs/IMDb title IDs and nested showtime information;
cinema/date requests can optionally filter a film. It permits caching, but storage duration,
fixture retention, request allowances, SLA and these nine venues need a contract and samples.
Authentication uses client, API key, authorisation, territory and version headers; some
resources require geolocation. Use only fixed venue IDs for any later approved evaluation,
not the person's location. [Header documentation](https://developer.movieglu.com/v2/api-index/setup/)

**Specific hazard:** MovieGlu treats the cinema day as 03:00–02:59 and returns published
local times without timezone/DST adjustment. A 01:00 screening belongs to the next civil
date even when returned under the previous programme date. Never store that date/time
naively as UTC. [Date/time rules](https://developer.movieglu.com/v2/api-index/cinemaShowTimes/)

### International Showtimes — second quote-based alternative

[v5 documentation](https://api-trial.internationalshowtimes.com/documentation/v5/) documents
API-key authentication; cinema/movie/showtime identifiers; offset-bearing `start_at`;
optional TMDB/IMDb IDs; and nullable `booking_link` with `movie_page_link` fallback.
Its published example contains null booking fields, so a provider row alone cannot promise
a direct booking action. Conditional GET/304 is documented; cancellation semantics,
retention, actual ID stability and nine-venue coverage still need evidence.

[Product page](https://www.internationalshowtimes.com/) advertises a seven-day trial and
direct booking links. A numeric tariff was not published on the inspected pages. Its public
website terms are not the API data licence: request a specific offer covering this two-user
app, attribution, caching, test fixtures, cancellation handling, limits and deletion.
No trial or contact was initiated.

### Direct venue sources — fallback only after permission and specimens

Six source families would be needed: ODEON, Cineworld, Vue, Everyman, GFT, Science Centre.
Public access for a person does not settle automated retrieval or republication permission.
No documented public programme API or machine-use licence was established for any family.

ODEON loops and Cineworld 403 make unattended HTML retrieval unproven. Vue's empty parsed
shell demonstrates why a successful page fetch cannot mean a successful programme fetch.
[Everyman's website terms](https://www.everymancinema.com/terms-and-conditions/) restrict
copying/distribution without consent. GFT machine-use permission/limits/retention remain
unknown. Science Centre's Ticket Tailor partnership does not grant access to the organiser's
API or make a public ticket page an open data feed. Its [ticket terms](https://www.glasgowsciencecentre.org/terms-and-conditions)
concern ticket purchases, not a programme data licence.

Direct-source fees are unknown, not £0. A permissioned feed could be useful if an aggregator
misses either independent, but adapter work, monitoring and site-change repair remain costs.
Do not bypass access blocks or build against guessed private endpoints.

## Coverage and real-shape evidence still required

For each of the nine named venues, an approved specimen must establish these five groups:

1. Correct venue name/address plus provider and upstream venue ID; no same-chain substitution.
2. One ordinary film and one older/reissue/event example where actually offered, with original
   year, programme date, local start, timezone/offset and film/screening IDs or explicit gaps.
3. Actual booking URL and final venue/film/date/time after permitted navigation; null, expired,
   film-page-only, sold-out and blocked links remain distinct.
4. Earliest/latest available dates, pagination, returned counts, last-seen/fetched timestamps,
   partial coverage and refresh cadence. A seven-day sample proves only seven days.
5. A bounded repeat read or a provider-documented cancellation/reschedule specimen showing
   withdrawal, correction and identity behaviour. Disappearance alone does not prove cancellation.

Public research leads for the older-film test are GFT anniversary/restoration titles and the
Science Centre's returning classics. These are not coverage passes. No expectation that all
nine have an older film on one date: use “no example evidenced in sampled window”, preserving
the programme and the gap. National Everyman Throwback advertising does not pass Glasgow.

Original release year, anniversary label, restoration version, reissue date and screening
start are separate facts. Never derive an original year by subtracting an anniversary number.
Do not treat a concert, shorts programme or double bill as one confidently matched feature.
The two phone concepts use explicitly illustrative times/years, never provider fixtures.

## Cost and request-load comparison

Prices below are displayed GBP monthly prices checked 31 Oct; VAT and checkout total need
confirmation before any purchase. Annual amounts are 12 × monthly, not annual-plan quotes.
[UK Cinema API prices](https://uk-cinema-api.co.uk/pricing)

| Route | Fee | Capability / cost implication |
|---|---|---|
| UK Cinema API Lite | £9.99/month; £119.88 at 12 monthly payments | Nine fit the ten-cinema limit if all covered. Omits format, accessibility and ticket-price information. Cannot promise IMAX/3D/subtitle filters. |
| UK Cinema API Pro, UK only | £49/month; £588 at 12 monthly payments | Adds formats/accessibility/event tags; advertised 5 requests/sec. Confirm request allowance and actual field completeness. £468.12/year more than Lite. |
| UK Cinema API Ultra, UK only | £99/month; £1,188 at 12 monthly payments | Adds prices; 20 requests/sec. £1,068.12/year more than Lite. Ticket prices are unnecessary for the proposed booking-out concept. |
| MovieGlu / International Showtimes | Quote required | Do not assume cheaper or better coverage. Exact nine-venue, low-volume quote and licence needed. |
| Direct permissioned feeds | Unknown | Up to six source families, separate permissions/monitoring and repairs. No paid licence or free operation established. |

**Illustrative budget, not measured demand:** nine venues × two refreshes/day × one
all-dates page = 18 requests/day, or 558 in a 31-day month. If a provider needs one query
per venue/day across 14 days: 9 × 14 × 2 = 252/day, 7,812/month, before pagination and metadata.
At 28 days it is 504/day, 15,624/month. A hard proposal of 800 total requests/day, including
retries, metadata, pagination and lookups, leaves 200 of Lite's allowance unused. Stop at
the cap; expose partial coverage rather than silently truncating or retrying indefinitely.
The exact load is unknowable until the request shape and page sizes are inspected.

Twice-daily polling does not make daily-collected upstream data current twice a day.
Share the result between Craig and Mark; do not make provider calls per page view.
No extra infrastructure is selected or costed as £0: existing worker capacity, credential
storage and deployment implications require the sitting-5 build contract.

Maintenance comparison uses source counts rather than invented engineer-hour estimates:
one aggregator adapter plus nine coverage checks versus up to six direct-source adapters
plus nine checks. Any hybrid adds adapters and permissions. Price the build only after
samples establish matching, cancellation, pagination and independent-venue gaps.

## Phone concept — Film first selected; policy details unapproved

Open the companion `ab5-concept-2026-10-31.html` for two 375px concepts.
**Film first** was selected from the two concepts: film/original year → venues → individual
times → venue booking. **Date first** remains the comparison. These demonstrate a future
programme experience; they are not deliverable from official links alone. Under the chosen
free-links direction, the immediate possible product is nine official programme links,
without film grouping, showtimes or an older-film filter. Do not fabricate film cards to
imitate the chosen future concept. No link screen has been built or authorised.

“Older films” proposal: original release year at least five years before the viewing year
(2021 or earlier in 2026), or an explicitly identified reissue/restoration. Unknown year gets
“Year unknown” and remains browseable. This threshold is a proposal, not an existing decision.
Watched favourites stay included. Ownership/watch labels describe the signed-in person's
relationship to a confidently matched film; no confident match means no such label.

Filters: selected venues, next seven days initially, expandable date range, older/all.
No geolocation or model ranking. Films sort by next screening, with older-film filtering
easy to reach. Cinema discovery has its own entry from Home; the disc/release calendar
and existing bottom navigation remain until navigation is explicitly picked.

| Coverage state | Proposed phone behaviour |
|---|---|
| Healthy, complete window | Show source observation time and fetched time separately; list upcoming sessions with “Check tickets” links, never a live seat guarantee. |
| Confirmed empty window | Say “No listings returned for these dates” only after a complete successful response; show the covered date window. |
| Unsupported / not checked | Keep the venue visible, labelled “Programme unavailable”; offer its official programme page. |
| Failed / partial | Keep the last complete result and its age; label the failed/partial venue/window. No “nothing showing”. |
| Stale / withdrawn / past | Proposed stale threshold: 26h since upstream observation where available; otherwise disclose age unknown and daily provider cadence. Past/confirmed withdrawn sessions lose booking actions; stale sessions offer “Check venue”, not a current-showtime claim. |

Twenty-six hours is a proposed operational threshold with a two-hour allowance over the
published daily cadence, not a source SLA or owner-approved acceptance rule. Cache retrieval
time must never reset upstream age. Missing upstream timestamps remain missing. Ambiguous
cancellations remain unavailable/pending confirmation; do not invent a cancelled flag.

## Revised sitting-5 shape — proposal only

Craig's free-links choice changes the build premise: a nine-venue link screen does not
need ingestion and cannot supply unified Film first results. Propose a separate link-screen
contract only if Craig later asks to build it. The chosen Film first concept remains the
future preference should a free permissioned programme source become available. Do not
convert the links choice into permission for six scrapers or an archive-based live feed.

Any future AB6 ingestion work should begin only after source picks and specimens, with a concrete contract covering
nine venue IDs, licence/retention, original-year matching, cancellation evidence, requests,
timezone/DST, storage, schema/API, job schedule, failure reporting and costs. No migration,
new job, provider credentials or hosting topology is selected here.

If one provider covers all nine acceptably, retain AB6 pipeline → AB7 screen as separate
implementation batches/PRs. If independent venues need their own feeds, stop and propose
separate adapter batches with permission/specimen gates before revising sitting 5. Reduced
coverage requires Craig's explicit list of accepted omissions and visible fallbacks.
Do not silently start with seven venues. AB7 only consumes the accepted AB6 contract.

## Owner picks and exact specimen checkpoint — answered 31 Oct

1. **Source/cost:** Craig chose “Keep it free — official programme links; no unified
   showtimes yet”. No paid provider, trial, subscription, key or recurring request budget
   is approved. The proposed paid Lite evaluation is not the selected direction.
2. **Coverage:** all nine intended venues remain; the question retained this condition.
   No reduced venue list was proposed or accepted.
3. **Concept:** Craig chose Film first. This selects the future grouped-film layout, not
   invented data or approval of the proposed five-year threshold, navigation or freshness
   numbers. Official links alone cannot provide that film grouping.
4. **Historical specimen:** Craig approved the exact one-file read below. It was attempted
   once at 12:39 UTC on 31 Oct and returned HTTP 403 Forbidden. No retry, redirect follow,
   alternative date/host or subsequent request was made. No CSV shape or venue data was
   obtained. Audit evidence: `ab5-historical-sample-2026-10-31.json`.

Exact approved request: `GET https://uk-cinema-api.co.uk/api/archive/showtimes/gb/2026-10-29.csv.gz`.
Maximum compressed transfer: 2 MB (enforced as 2,000,000 bytes); zero retries. The published
index describes one national day, so the approved processing was to retain only the nine
venues' rows and a summary with attribution, discarding national/raw data. No account,
API key, payment, booking navigation or production write. The server refused access;
no downloaded national file or filtered venue rows exist.

A failed read is not evidence of a missing venue, an empty programme, or permission to
retry through a different browser/proxy. Future source specimens require a new exact
scope/approval. No further action is implied by the successful choice submissions.
The next possible work is a separately requested revised free-links build proposal or
new evidence scope, not sitting 5's ingestion pipeline. Stop here.

## Verification and failures

| AB5 acceptance | Status |
|---|---|
| All nine intended identities; no silent branch replacement | Public-source verification done; machine source identity still awaits approved specimens. |
| Per-source shape/IDs/bookings/horizon/freshness/access/licence/limits/fees | Published findings and unknowns recorded; real nine-venue shapes/bookings/cancellations unverified. |
| Older-film coverage against real approved examples | Unmet: public leads found; approved historical GET failed 403, no specimens obtained. |
| Source options, phone concept, failure policy, coverage/cost/load/maintenance, revised scope | Delivered; free official links and Film first selected. No implementation or policy-number approval. |
| Document/source verification; no invented app gate/deploy | Report, source links, nine-row count, cost arithmetic, concept interaction and document diff checks apply. No product tests or production smoke are claimed. |

Tool failures retained: first `gh run list` used an incorrect repository slug and returned
404; rerun against verified remote `CraigR973/mcu-app` showed green main. Four ODEON venue
pages returned redirect loops; Cineworld venue page returned 403; GFT plan-your-visit URL
was unavailable. UK Cinema API raw `v4.json` was unavailable in the research browser and
returned 403 to a single direct documentation GET. No access bypass attempted. These are
research-access limits, not proof those venues are closed or their programmes empty.

Document checks passed: nine venue rows, source-link syntax, monthly/yearly cost and
request arithmetic, preserved STATUS headings and accurate report-versus-programme acceptance status. Chromium concept checks
cover 320px/375px in light/dark, both carousel variants, All films, local-only ticket action,
coverage disclosure and no horizontal overflow; zero browser script errors. Visual dark
375px inspection passed. These verify the proposal, not the app or real listings.
One concept-check attempt timed out targeting the hidden variant-picker option directly;
using the visible Next/Previous variant controls passes. No product change was needed.

The concept export initially refused to overwrite its existing generated HTML; rerunning
with the documented replacement option succeeded. No app/source request was involved.

The approved historical request's 403 is an additional source-access failure. No retries
were permitted or attempted. Its audit JSON records no credentials or response body.

Source pages are time-sensitive snapshots checked 31 Oct; no current ticket availability
is asserted. Free official links and Film first are recorded owner picks; they do not meet
the original ingestion-evidence criteria. No build acceptance, all-nine programme source
acceptance or purchase is inferred. Craig subsequently replied “accept” to finalising AB5
as report complete / programme feasibility unproven, explicitly excluding the unmet
programme-evidence criterion from report close-out only (#313). This waives nothing for
future ingestion. PR #123 still requires green exact-head CI; no automatic sitting 5 or AA10c.

Finalisation CI audit: PR run 41203332844 passed; subsequent run 41203387374 failed the
unchanged Firefox offline replay test at the Search title tab (10-second click timeout).
Chromium, WebKit and jobs passed. No root cause, repair or programme evidence is inferred;
no assertion/timeout/retry setting changed. Fresh exact-head CI is required before merge.
