# Cinema scraping investigation — 31 Oct

**Finding: investigate further; no all-nine scraping build is ready.** Six source families
cover the nine venues. Three publish express access/reuse restrictions, ODEON's policy
access is unresolved, and the independent cinemas need technical evidence and reuse-scope
clarification. No recurring collector, programme specimen, application change or deployment
was run in this investigation.

Craig authorised this investigation by replying “proceed” after the proposal to establish
permitted access and then seek approval for exact bounded sample requests. This parks the
unapproved links-only build proposal; it does not approve ingestion or reduce venue scope.
AB5 remains accepted report complete, programme feasibility unproven (#313).

## Six-source matrix

| Family / intended venues | Evidence checked | Consequence |
|---|---|---|
| ODEON: Kilmarnock, Glasgow Quay, Braehead, East Kilbride | Official legal hub and its linked gift-card policy redirect-looped. Robots could not be inspected. The help centre explicitly says VPN use is not allowed on its website. | Four venues remain unresolved. Do not use unrelated ODEON-branded businesses' terms, gift-card terms or Wi-Fi terms as a programme licence. No proxy/VPN workaround or private endpoint investigation. |
| Cineworld: Glasgow Silverburn | Official indexed Online Terms §4.2 restrict reproduction without prior written permission. Direct legal-page and robots reads returned 403. | Both reuse permission and unattended access remain unresolved. No programme request or access workaround. |
| Vue: Glasgow St Enoch | Website Terms §§4.4–4.5 require advance written permission for automated access/content extraction. §7.2 allows a personal print copy and prohibits other use. Robots disallow booking/showing/screening routes. | Explicit scraping-permission gate. A venue URL not excluded by robots is not an extraction licence. |
| Everyman: Glasgow Princes Square | Website Terms §8.3 restrict copying/republication/distribution without consent. Robots could not be inspected. | Reuse-consent gate; a public film page is not evidence of permission to build a stored programme. |
| Glasgow Film Theatre | Official Terms of Service discuss tickets and changing programmes, not a machine-use licence. Robots could not be inspected. No documented open programme feed was established by this search. | Candidate for a bounded technical diagnostic; recurring retrieval, reuse and fixture retention remain unsettled. |
| IMAX at Glasgow Science Centre | Its FOI page permits accurate, attributed, non-misleading reproduction of published information, but is presented within an FOI publication scheme. Ticket terms confirm Ticket Tailor use. Robots could not be inspected. | Useful permission lead, not a confirmed licence for programme scraping or third-party material. Clarify scope before ongoing use. Ticket Tailor's API needs a key issued by that box office. |

These are engineering gates under the repository's permission/evidence contract, not a
legal ruling about ownership of individual factual screening times. No operator was
contacted and no permission was obtained during this pass. An unreadable robots file is
not an observed allow rule. No published open feed found means “not established”, not
“none exists”. Indexed search snippets remain research leads, not programme specimens.

## Technical judgement

Scraping can feed the same Film first product originally intended: bounded background
reads, normalised films/venues/screenings, then one authenticated app view. Prefer a
documented permissioned feed or structured public data when available; parsing rendered
HTML is another option to test, not a proven requirement or a reason to assume failure.

The important proof is not whether a page contains a film title. Each source must expose
correct venue identity, individual dated start times, booking destinations, a bounded
coverage window and enough information to distinguish changed/withdrawn listings from
fetch/parse failures. Original film year cannot come from the reissue/event date.
Film matching must keep ambiguous films and multi-film events unresolved.

Six families do not promise six simple adapters or six requests: ticketing dependencies,
pagination and per-date/per-film requests may add work. One HTML response may contain only
a client-rendered shell; a failed basic test does not prove browser rendering impossible.
Automated rendering would require a separately bounded scope for its dependent requests.
No guessed private API, login, cookie/session harvesting or access-block workaround is
part of this proposal.

The app should share one refreshed result between both people and expose source ages and
partial coverage. A failed refresh must not erase the last result or say nothing is showing.
A second successful read and cancellation evidence would still be needed after a first
sample; this investigation cannot settle identity stability or removal behaviour.

## Exact first diagnostic — proposed, not executed

Recommend testing the two independent-cinema HTML entry pages first while chain permission
questions remain open. This is staged evidence gathering, not approval to omit the other
seven venues. It assesses whether a small ordinary read is useful, not a recurring service
or permission to republish listings.

Four GET requests maximum, sequentially, in this exact order within each host:

| Request | URL | Maximum response body |
|---|---|---|
| 1 | https://www.glasgowfilm.org/robots.txt | 64,000 bytes |
| 2 | https://www.glasgowfilm.org/all-listings/ | 2,000,000 bytes |
| 3 | https://www.glasgowsciencecentre.org/robots.txt | 64,000 bytes |
| 4 | https://www.glasgowsciencecentre.org/imax | 2,000,000 bytes |

Execution contract for Craig's approval:

- Run at most once per URL, with an honest research user-agent, no cookies/authentication,
  `Accept-Encoding: identity`, a 25-second timeout and the listed streamed byte ceiling.
  Maximum total body transfer is 4,128,000 bytes, excluding protocol overhead. Zero
  automatic retries or redirects; a redirect is a reported result, not a new request.
- Read each host's robots first. Skip its programme request on a matching disallow rule,
  401/403/429/5xx, timeout, redirect, unreadable rules or size-cap failure. A robots 404
  means no robots file was supplied, not a programme-reuse licence; record it explicitly.
- Fetch only the listed HTML. Do not execute JavaScript, load images/scripts, follow film,
  booking, pagination or Ticket Tailor links, call any API or use another host/browser/proxy
  after a block. A missing time or external dependency is a result to review.
- Inspect HTML/embedded structured data in memory for field presence, counts, venue
  attribution, time/year distinctions and link domains. Persist an audit of status, size,
  hash, content type and field-presence findings; no response cookies, raw HTML, posters,
  descriptions or programme rows. An older-film example can remain “not established”.
  No saved programme fixture or licence assumption follows from this diagnostic.
- No account, payment, message to an operator, production write, schema/API/job, application
  implementation or hosting change. End after the audit and propose the next exact scope
  only from what was actually seen. Do not retry the exhausted historical archive request.

This diagnostic is unexecuted because `group-start.md` requires exact approval before live
integration/sample reads. Craig's “proceed” authorised the investigation that precedes
this exact scope, as stated in the preceding reply; it did not approve these four requests.

## Permission enquiry prepared for later use — not sent

Use the operator's official contact route after Craig authorises contact, or Craig can
send this himself. Do not contact anyone merely because this draft exists.

> We run a private film-collection app for two people. We would like to display your
> venue's film titles, original years where available, screening dates/times and links
> back to your official programme or booking pages. Do you offer a feed, or permit bounded
> automated reads and caching for this purpose? Please confirm permitted fields,
> attribution, rate limits, cache/test-fixture retention, cancellation updates and any
> fee. We do not need posters, descriptions, ticket purchasing or customer data.

For ODEON name all four intended branches; for Science Centre ask whether the published
FOI copying policy extends to its IMAX programme, and whether it can supply a permissioned
schedule export without granting access to customer/orders data. For the other operators,
name only their intended Glasgow venue. No permission response is assumed.

## Cost and revised build boundary

Spend so far: no purchase/subscription; public document research only. Proposed diagnostic:
at most four requests, no paid service or production resources. These costs do not establish
free recurring operation. Permission/licence costs are unknown. Engineering involves source
adapters, scheduling, failure detection, matching, normalisation, tests and subsequent site
repairs; credible hours and request budgets require real samples.

Keep the original AB6 ingestion → AB7 discovery separation if source evidence supports it.
If source-specific adapters need separate batches, propose the whole revised sequence and
model/effort routing for Craig before implementation. No scope, model or acceptance criterion
has been silently rewritten here. Links-only is parked as an unapproved fallback, not built.
All nine venues, future source/build approval gates and the AA10c exclusion remain in force.

## Sources and research audit

Primary sources checked 31 Oct (direct reads and indexed official content distinguished):

- [ODEON legal hub](https://www.odeon.co.uk/privacy-and-legal/) — redirect loop;
  [official VPN help](https://help.odeon.co.uk/hc/en-gb/articles/30851905488146-What-is-a-VPN)
  — published access policy. The gift-card policy's official hub link also looped.
- [Cineworld Online Terms](https://www.cineworld.co.uk/online-terms-of-use/) — indexed
  official §4.2 text retrieved through search; direct fetch 403. Robots also returned 403.
- [Vue legal terms](https://www.myvue.com/legal/terms-and-conditions) — readable extractor
  showed accordion headings only. One ordinary bounded legal-document GET retrieved the
  embedded website-terms text, including §§4.4–4.5 and 7.2. Legal HTML: 507,965 bytes,
  SHA-256 `6f82e6782556b36b95b03458e8941575098b135395cce5a28a0adb9ed6ae91ca`.
  Local legal-document evidence is gitignored under `scratchpad/ab-cinema-research/`;
  no programme data is stored there. [Vue robots](https://www.myvue.com/robots.txt) read.
- [Everyman Terms](https://www.everymancinema.com/terms-and-conditions/) — website §8.3
  read; robots inaccessible through the research tool.
- [GFT Terms of Service](https://www.glasgowfilm.org/terms-of-service/) — found after the
  guessed `/terms-and-conditions/` URL was inaccessible. Robots also inaccessible.
- [Science Centre ticket terms](https://www.glasgowsciencecentre.org/terms-and-conditions),
  [FOI copying policy](https://www.glasgowsciencecentre.org/freedom-of-information) and
  [Ticket Tailor API documentation](https://developers.tickettailor.com/) — read. The API
  documentation says keys are box-office-scoped; creating our own account does not grant
  access to Science Centre's data. Guessed `/copyright` and robots were inaccessible.

ODEON robots was also inaccessible. Search results for unrelated `odeonworld.com` and
`myvue.io` were excluded; these are not the intended operators. Search snippets incidentally
showed public film listings; none was collected or accepted as an integration sample.
One shell-tool result omitted its running-session metadata; the completed legal download
was inspected locally without repeating the request. No blocked source was bypassed.

Document checks cover nine named venues/six families, exact request count/byte arithmetic,
source links, unapproved pilot status and preserved implementation boundaries. No product
tests, app gate, current programme availability or production smoke is claimed.
