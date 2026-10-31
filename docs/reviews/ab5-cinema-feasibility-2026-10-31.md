# Nine-cinema source feasibility — 31 Oct 2026

**Verdict: a single-provider route is worth evaluating; nine-venue ingestion is not yet proven or approved.**
The lowest published candidate is UK Cinema API Lite at £9.99/month for up to ten cinemas.
Its chain coverage claims cover seven intended branches in principle; Glasgow Film Theatre
and Glasgow Science Centre need explicit coverage evidence. Even those seven individual
branches have not been verified in an approved provider sample. Do not buy or build yet.

**Owner stop:** source, budget, coverage and concept picks; exact specimen-read approval.
Public research is delivered. Approved real specimens, cancellation behaviour, booking-link
validation and venue-by-venue older-film coverage remain open. AB5 stays at this checkpoint,
not complete. Sitting 5, AB6/AB7 implementation and AA10c remain excluded.

## Authority and evidence boundary

Craig authorised sitting 4 only on 31 Oct using `group-start.md`. The ledger maps AB5 to
Opus 5 high / GPT-5.6 Sol High. This report does not revise that mapping or claim a model switch.
Starting checkout: clean `main`, `a3e41f1`; fetched origin matches. Main CI 41193175977
passed before research. Working branch: `chore/ab5-cinema-feasibility`.

Public venue pages, indexed public descriptions, provider documentation, pricing and terms
were read. No programme extraction script, API data request, archive download, account,
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
| ODEON Kilmarnock | Operator help lists Kilmarnock; official cinema URL returned a redirect loop to the research browser. | UK Cinema API names ODEON as a chain. This branch, horizon, reissues and links unverified. |
| Cineworld Glasgow — Silverburn | [Silverburn venue host](https://www.shopsilverburn.com/retailer/cineworld/) confirms Cineworld; operator page returned 403. | Chain claimed by UK Cinema API. Individual programme/reissues unverified. Do not substitute Renfrew Street or Science Centre. |
| ODEON Luxe Glasgow Quay | [The Quay venue host](https://www.thequayglasgow.com/cinema/) confirms Luxe Glasgow Quay. Operator page looped. | Same ODEON candidate; branch-specific programme/reissues unverified. |
| ODEON Braehead | [IMAX theatre directory](https://www.imax.com/theatre/odeon-braehead-imax) confirms Braehead at X-scape, Kings Inch Road. Operator page looped. | Same ODEON candidate; IMAX venue capability is not proof a particular screening is IMAX. |
| ODEON Luxe East Kilbride | [EK venue host](https://eklife.co.uk/shops/odeon-luxe/) confirms ODEON Luxe in The Hub. Operator page looped. | Same ODEON candidate; branch-specific programme/reissues unverified. |
| IMAX at Glasgow Science Centre | [Science Centre](https://www.glasgowsciencecentre.org/imax) says it owns/manages this independent cinema, with Ticket Tailor box office. | Public page advertises older-film returns, including The Shining, alongside features and educational shorts. Provider inclusion and exact screening evidence unverified. |
| Glasgow Film Theatre (GFT) | [Official listings](https://www.glasgowfilm.org/all-listings/) and [Now Booking A–Z](https://www.glasgowfilm.org/now-booking-a-z/) establish the venue/programme. | Index includes anniversary/restoration labels such as Donnie Darko and Pan's Labyrinth. Strong repertory research lead; provider coverage unverified. |
| Everyman Glasgow, Princes Square | [Official venue](https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/) confirms Glasgow, Unit 3–5 Princes Square. | Chain claimed by UK Cinema API. Everyman advertises Throwback nationally; Glasgow-specific older-film availability unverified. |
| Vue Glasgow St Enoch | [Official venue](https://www.myvue.com/cinema/glasgow-st-enoch/whats-on) confirms St Enoch Centre, 55 St Enoch Square. | Chain claimed by UK Cinema API. Parsed page showed a no-matching-showings shell; that is not evidence of an empty programme. |

Count: nine identities supported; seven branches belong to explicitly advertised API chains;
zero of nine have an approved provider coverage specimen. The two independent venues are
especially important to the older-film goal and cannot silently become out-of-scope.

## Source options and permissions

### UK Cinema API — first evaluation candidate

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
cinema or TMDB data. It cannot prove upcoming coverage or booking-link health. No file was
downloaded. An exact one-file approval proposal appears below.

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

## Phone concept and policy proposals — unapproved

Open the companion `ab5-concept-2026-10-31.html` for two 375px concepts.
**Film first** is recommended: film/original year → venues → individual times → venue booking.
**Date first** is the alternative: one day's film list → venues/times. Both group by film,
preserve venue/session differences, and show coverage separately from film availability.

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

AB6 should begin only after source picks and specimens, with a concrete contract covering
nine venue IDs, licence/retention, original-year matching, cancellation evidence, requests,
timezone/DST, storage, schema/API, job schedule, failure reporting and costs. No migration,
new job, provider credentials or hosting topology is selected here.

If one provider covers all nine acceptably, retain AB6 pipeline → AB7 screen as separate
implementation batches/PRs. If independent venues need their own feeds, stop and propose
separate adapter batches with permission/specimen gates before revising sitting 5. Reduced
coverage requires Craig's explicit list of accepted omissions and visible fallbacks.
Do not silently start with seven venues. AB7 only consumes the accepted AB6 contract.

## Owner picks and exact specimen checkpoint

1. **Source and cost direction:** recommend evaluate UK Cinema API Lite first, with a
   provisional ceiling of £9.99/month if all nine pass and omitted format/accessibility tags
   are acceptable. Alternative Pro is £49/month for those tags. This is a shortlist/budget
   preference, not authorisation to subscribe, start a trial, store a key or build.
2. **Coverage:** recommend keep all nine mandatory, especially GFT and Science Centre.
   If a source misses a venue, return with the exact gap and alternative; no automatic
   reduction. Cost: possible further permission/quote work and delayed implementation.
3. **Concept:** recommend Film first, with older/watched favourites and visible venue gaps.
   Date first is available for comparison. Pick the original-year threshold/navigation
   before a build; no automatic acceptance of the policy numbers in this report.
4. **First specimen scope:** recommend one free historical file before any paid API trial:
   `GET https://uk-cinema-api.co.uk/api/archive/showtimes/gb/2026-10-29.csv.gz` once,
   maximum compressed transfer 2 MB (index currently lists 856 KB / 19,922 UK showtimes).
   This downloads one national day, not only these nine venues. Stream/filter locally to
   the nine named venues; retain only their rows and a coverage/count summary with source
   attribution, discard all other rows/raw download after analysis. No retries, other dates,
   accounts, API keys, payment, booking navigation or production writes. One read, £0
   published data charge; network/time and upstream rights limitations still apply.

That first specimen is historical only: it can establish past IDs/shape and coverage leads,
not upcoming programmes. A subsequent live scope must name the selected provider/host,
exact endpoints and venue IDs, date window, maximum requests/bytes/retries, any booking
navigation, licence and fee cap, and credential/trial implications. Return for that exact
approval before issuing requests. No placeholder endpoint/payload becomes a fixture.

## Verification and failures

| AB5 acceptance | Status |
|---|---|
| All nine intended identities; no silent branch replacement | Public-source verification done; machine source identity still awaits approved specimens. |
| Per-source shape/IDs/bookings/horizon/freshness/access/licence/limits/fees | Published findings and unknowns recorded; real nine-venue shapes/bookings/cancellations unverified. |
| Older-film coverage against real approved examples | Open: public leads found, no approved specimens collected. |
| Source options, phone concept, failure policy, coverage/cost/load/maintenance, revised scope | Delivered as proposals, awaiting owner picks. |
| Document/source verification; no invented app gate/deploy | Report, source links, nine-row count, cost arithmetic, concept interaction and document diff checks apply. No product tests or production smoke are claimed. |

Tool failures retained: first `gh run list` used an incorrect repository slug and returned
404; rerun against verified remote `CraigR973/mcu-app` showed green main. Four ODEON venue
pages returned redirect loops; Cineworld venue page returned 403; GFT plan-your-visit URL
was unavailable. UK Cinema API raw `v4.json` was unavailable in the research browser and
returned 403 to a single direct documentation GET. No access bypass attempted. These are
research-access limits, not proof those venues are closed or their programmes empty.

Document checks passed: nine venue rows, source-link syntax, monthly/yearly cost and
request arithmetic, preserved STATUS headings and unstruck AB5. Chromium concept checks
cover 320px/375px in light/dark, both carousel variants, All films, local-only ticket action,
coverage disclosure and no horizontal overflow; zero browser script errors. Visual dark
375px inspection passed. These verify the proposal, not the app or real listings.
One concept-check attempt timed out targeting the hidden variant-picker option directly;
using the visible Next/Previous variant controls passes. No product change was needed.

Source pages are time-sensitive snapshots checked 31 Oct; no current ticket availability
is asserted. No build acceptance, all-nine source acceptance, purchase or owner pick has
been inferred. Next action is Craig's picks/explicit specimen approval, then AB5 evidence
completion; no automatic sitting 5 or AA10c.
