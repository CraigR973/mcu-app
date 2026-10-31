# Nine-cinema scraping results — 31 Oct

**Later browser comparison supersedes the five-venue access-gap verdict below:** all five
yielded 111 additional real time rows in the in-app browser. All nine now have samples,
but deployable/repeatable collection is unproved. See
`ab-cinema-browser-comparison-2026-10-31.md` (#316). The first probe and its failures are
retained below as historical evidence, not rewritten as passes.

**Four of nine venues yielded real screening times: 115 rows in this bounded sample.**
GFT, Vue St Enoch, Everyman Glasgow and Science Centre IMAX are technically promising.
The four ODEON branches redirect to a queue; Cineworld's schedule requests return 403.
An all-nine ingestion build is still blocked. No reduced-coverage build is assumed.

Craig explicitly authorised trying all nine websites, including those with restrictions
(decision #315). This supersedes the earlier investigation-only/sample stop for these
attempts. The earlier four-request independent-cinema proposal was not the executed scope.
Owner authorisation is not represented as consent from the operators, but no further owner
permission was requested merely because a site had restrictive terms or robots rules.

## Results by venue

| Venue | Observed result | Coverage evidenced |
|---|---|---|
| ODEON Kilmarnock | HTTP 302 to `odeon.queue-it.net`; ordinary browser attempt then received 403 | No programme rows |
| ODEON Glasgow Quay | HTTP 302 to the same queue service | No programme rows |
| ODEON Braehead | HTTP 302 to the same queue service | No programme rows |
| ODEON East Kilbride | HTTP 302 to the same queue service | No programme rows |
| Cineworld Glasgow Silverburn | Venue HTML and identity read successfully; browser's actual scheduled-movies/schedule calls returned 403 | No screening times; the rendered empty message is not proof of no programme |
| Glasgow Film Theatre | HTML contains dated film headings, showing IDs and booking links | 20 screenings, 11 titles, 31 Oct–2 Nov |
| Vue Glasgow St Enoch | Venue page's ordinary public JSON supplies cinema `10097`, film/session IDs, offset-bearing times and booking links | 31 screenings, 16 titles, sampled day 31 Oct |
| Everyman Glasgow, Princes Square | Ordinary public schedule JSON supplies venue `X11DQ`, film/showing references, local starts, screens and booking links | 11 screenings, 6 titles, sampled day 31 Oct |
| IMAX at Glasgow Science Centre | Official site links to its public Ticket Tailor box office; nine event pages expose Event JSON-LD | 53 screenings, 9 event titles, 28 distinct dates between 31 Oct and 22 Dec |

Collection ran between 14:40:58 and 14:46 UTC. Counts include some screenings which had
already started; they are source observations, not a current list of bookable future shows.
No booking link was followed, no seats/cart were selected and no payment was attempted.
Film counts are per venue; they are not deduplicated across the four sources.

The longer Science Centre date span is not a guarantee that every date, event or screening
was returned. Vue/Everyman date indices advertise more dates, but individual screenings
were sampled for one day only. GFT's HTML sample may be a truncated SEO window; its full
programme/browser pagination was not established. Do not present these counts as completeness.

Evidence: `ab-cinema-scrape-samples-2026-10-31.json` contains all nine initial attempts,
four source summaries, eight minimal real examples, collection times and body hashes.
Raw public responses, local diagnostic scripts and fuller normalised rows remain gitignored
under `scratchpad/ab-cinema-research/public-probe-2026-10-31/` (scripts in its parent).
The tracked evidence contains no plots, images, customer data, cookies or credentials.

## What changed in feasibility

Scraping is now demonstrated for four venues, including one whose terms restrict extraction.
The earlier five readable HTML pages were not five working feeds: Cineworld's live schedule
is separately blocked. Everyman's second ordinary render succeeded after a first static-data
loading failure. No private endpoint was guessed: Vue/Everyman requests were observed in
their own normal public page traffic, and Science Centre event links came from its site.

```text
GFT dated HTML ------------------- 20 rows
Vue public page data ------------ 31 rows
Everyman public page data ------- 11 rows
Science Centre / public box office 53 rows
                 |
       Local diagnostic evidence
       (no production ingestion)
```

Older-film leads are real, not mocked: Vue's source returned Hocus Pocus (1993) and
Scream (30th Anniversary) with screening times; GFT returned Donnie Darko's anniversary
and restoration-labelled listings; Science Centre returned The Shining and The Polar
Express. These establish that older/reissue programmes appear in obtained data, not a
complete older-film filter. Original release years remain unverified in the normalised
sample; Vue's Hocus Pocus `releaseDate` is 2 Oct 2026, demonstrating a reissue-date trap.
Do not derive the original year from an anniversary number or silently match a catalogue film.

Identity and cancellation need design work. Everyman's showing reference includes its
date/time and tags, so rescheduling may change that reference. Ticket Tailor exposes an
event ID with multiple dated occurrences; an event is not one screening. GFT/Vue expose
showing/session IDs, but persistence across refreshes was not proved. Ticket Tailor's
EventScheduled status is observed; withdrawn/cancelled examples were not obtained.

Vue and Ticket Tailor supply offset-bearing starts. Everyman's starts are naive local
times, with Europe/London venue context; GFT headings/times also need Europe/London parsing.
The sampled dates are after the October clock change, so these reads do not prove DST
transition behaviour. The Everyman cinema-day request spans 03:00 to 03:00; retain civil
date/time separately rather than attributing a post-midnight show to the wrong day.

## Attempt scope, failures and instrumentation limits

- Nine initial venue reads used ordinary HTTP, a 25-second timeout, at most three same-host
  redirects and a 2,000,000-byte success-body ceiling. Redirects to a different operator
  host were recorded rather than automatically followed. No HTTP retry loop was used.
- Six clean, unauthenticated Chromium contexts rendered Cineworld, Everyman twice, Vue,
  one representative ODEON branch and GFT. The browser filter allowed 260 request starts
  across those contexts (at most 90 per context), excluding images/fonts/media, known
  trackers and booking/account/cart paths. No stealth, CAPTCHA solving, proxy/VPN,
  borrowed login, forged queue cookie or access-control workaround was used. Browser
  scripts made their own ordinary public-data requests; requests were not hand-enumerated.
- Science Centre's linked public box-office listing and nine public event detail pages
  were read. One `buytickets.at` event URL returned a canonical redirect; the event URL
  actually published by the public box-office list was then read at Ticket Tailor. No
  organiser account/API key or ticket-selection/purchase step was used.
- The first Everyman browser probe failed to load some static JSON and showed no times.
  Two already-observed public static JSON resources were read normally; a second normal
  render then obtained the schedule and 11 times. This is a transient probe/loading failure
  with unconfirmed cause, not proof of reliable refreshes. Intentionally blocked images,
  fonts, maps and trackers account for many browser console errors; they are not source
  programme failures. Cineworld's schedule 403 and ODEON's queue/403 are genuine access gaps.
- GFT's browser probe returned Home after a GraphQL request was rejected by the diagnostic's
  conservative read-only request filter. That request's operation was not established;
  do not claim the venue denied it or the complete browser programme worked. The 20-row
  dated HTML extraction is independent of that browser limitation.
- The initial browser capture's asynchronous JSON-slot counter exceeded its intended
  12-response save limit before bodies finished; later probes reserved slots before awaiting
  bodies. The per-context request ceiling held. Across all contexts 54 JSON bodies totalling
  6,828,300 bytes were saved. This is not total wire transfer: scripts/CSS and other responses
  were not included, and the browser's size guard was not an aggregate streamed byte cap.
  No exact total-transfer guarantee or four-request-only claim is made for this run.

The old UK Cinema API historical GET was not retried. Terms research remains recorded in
the investigation report; this technical test neither asserts a data licence nor repeats
the prior permission question. No operator contact, purchase, subscription, credential,
hosting, database, application API or job change occurred. No PR, push or deployment ran.

## Revised route to the intended all-nine build — not approved implementation

1. **Resolve the five technical gaps.** Keep all four ODEON branches and Silverburn on the
   coverage matrix. A supported export/feed or an independently accepted alternative source
   could cover them. No such source is selected here, and bypassing the observed controls
   is not the proposed route. Four successful venues cannot silently replace nine.
2. **Finish source acceptance against real specimens.** Define the required date window,
   repeat-read stability, reschedule/cancellation behaviour, original-year matching, request
   ceilings, freshness/failure policy and retention. Confirm booking destinations at an
   explicitly approved read-only scope; obtaining a URL is not booking acceptance.
3. **Approve the complete build contract and batch split.** AB6 still needs schema/API/job/
   refresh/retention and source coverage agreed before implementation. The four demonstrated
   source shapes need separate adapter handling; propose additional adapter batches if
   necessary, with the complete sequence/model/effort settings for Craig first. Keep one
   branch/PR per implementation batch and clean-main close-out between batches.
4. **Build AB7 only against accepted data.** Keep Film first, all-nine coverage and the
   distinction from the release calendar. Explicit stale/partial/blocked venue states are
   required; do not turn a 403, queue or parse error into “nothing showing”.

The immediate outcome is usable evidence, not permission to ship a four-venue product or
to begin the parked links-only proposal. AB6/AB7 remain unstarted. No AA10c or other sitting.
No new provider fee was incurred; ongoing hosting/licensing/maintenance costs and credible
engineering time still need the source/build contract. No app gate or production smoke
is claimed for diagnostic documentation.

## Verification

Local extraction checks pass: nine initial attempts; four successful sources; 115 rows;
unique sample showing keys; valid offset-bearing/UTC-normalised starts; booking-link presence;
correct Vue cinema and Everyman venue IDs; nine Science Centre event identities and matching
location; no booking navigation. Original-year/cancellation/DST/completeness gaps remain
explicit. Document checks and secret/plot-free tracked evidence checks pass.

Primary entry points: [GFT](https://www.glasgowfilm.org/all-listings/),
[Vue St Enoch](https://www.myvue.com/cinema/glasgow-st-enoch/whats-on),
[Everyman Glasgow](https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/),
[Science Centre](https://www.glasgowsciencecentre.org/imax) and its
[public box office](https://www.tickettailor.com/events/gscimax),
[Cineworld Silverburn](https://www.cineworld.co.uk/cinemas/glasgow-silverburn), and the four
ODEON targets retained in the nine-attempt JSON. These links identify inspected sources;
they do not guarantee current listings or successful booking navigation.
