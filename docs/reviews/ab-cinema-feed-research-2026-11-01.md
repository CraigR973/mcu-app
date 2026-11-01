# Cinema feed research: confirm coverage before a trial

1 Nov 2026. Research/planning under #323; no supplier, paid plan or application approval.

**Recommendation: enquire about UK Cinema API Lite before opening any account/trial.**
It is the strongest documented candidate found for a small private app: ODEON is advertised,
the ten-cinema allowance could fit all nine intended venues, and published pricing is
£9.99/month. This is a candidate recommendation, not proof of branch coverage or API access.
[Coverage](https://uk-cinema-api.co.uk/) · [pricing](https://uk-cinema-api.co.uk/pricing).

Craig delegated the research direction after the hosted-browser refusals. That selects
feed-access research; it does not reverse the earlier £0 subscription choice, authorise
supplier contact/account/payment, or approve AB6/AB7. All nine venues and Film first remain
intended. Existing website-scraping permission is not being re-asked.

## Comparison checked 1 Nov

| Candidate | Published cost | Assessment for the ODEON gap |
|---|---|---|
| [UK Cinema API](https://uk-cinema-api.co.uk/pricing) | Lite £9.99/month; UK Pro £49/month | ODEON advertised. Exact branches/all-nine coverage unproved; best first enquiry. |
| [MovieGlu](https://movieglu.com/pricing/) | Quote required | Offers pricing per location or request tier. Obtain nine-venue coverage/price if first enquiry fails. |
| [International Showtimes](https://www.internationalshowtimes.com/) | No numeric tariff on inspected product page | Seven-day trial advertised; exact coverage, licence and offer still required. Second reserve. |
| [CinemaData](https://cinemadata.uk/pricing) | £20/month excluding VAT | [Terms](https://cinemadata.uk/terms) say API licensing/service terms will be published before paid access opens. Coverage and readiness unproved; defer. |
| [amodb UK directory](https://amodb.dev/cinema-api/united-kingdom/) | Not compared further | Inspected published UK chain table omits ODEON; its counts are an older dated snapshot, not a current coverage test. Not evidenced as a solution. |
| [API Cinéma](https://api-cinema.com/en) | Free tier advertised | Published product covers France/US; no UK/ODEON coverage established. Does not solve this gap on inspected evidence. |

No paid service has been selected. Numeric prices are displayed prices, not confirmed
checkout totals or supplier offers. No verified £0 ODEON machine feed emerged from these
inspected sources; this is not a claim that none exists.

UK Cinema API is the same underlying service that powers Film Chase; the publisher
documents that relationship. Its free consumer notification product does not make the
paid API free or supply API reuse permission. [About](https://uk-cinema-api.co.uk/about) ·
[Film Chase FAQ](https://www.filmchase.com/faq).

## Important limits on the leading candidate

Lite advertises showtimes/films/booking links, 1,000 daily requests, one request/second,
and cinema selection changes once a month. It omits formats, accessibility and ticket
prices. A three-day trial is advertised; card requirements, renewal, cancellation behaviour
and VAT need confirmation. £9.99 × 12 = £119.88 at unchanged monthly pricing; that is not
an annual-plan quote. [Pricing](https://uk-cinema-api.co.uk/pricing) ·
[Lite announcement](https://uk-cinema-api.co.uk/announcements).

Format omission is a real product choice: a venue's IMAX capability cannot label every
screening IMAX. Do not select Pro automatically or silently weaken the screen/data contract.
The required format/accessibility fields remain an owner choice after actual responses.

The supplier describes predominantly nightly collection. A successful API fetch every six
hours cannot prove six-hour source updates or immediate cancellations. Keep API retrieval
time separate from upstream collection time; determine what the supplier actually returns
before retaining the existing draft's eight-hour freshness rule. The about/homepage totals
also differ, so marketing counts are not nine-venue proof. [Supplier description](https://uk-cinema-api.co.uk/about).

The published paid terms allow app display and caching and require cached data deletion
within 30 days of subscription end. Trial use and durable fixtures/backups need explicit
clarification. This is a summary of published supplier conditions, not a legal assurance
about upstream material. Avoid committing real evaluation payloads or retaining them in
long-lived backups before those rights are settled. [Terms](https://uk-cinema-api.co.uk/terms).

The earlier unauthenticated historical archive request returned 403. It neither proves nor
disproves authenticated live API access. No archive retry, live API request or signup was
made during this research. The documentation UI exposes route names, but returned no
readable field-level specification to this browser; no field contract is inferred from it.
[Documentation](https://developer.uk-cinema-api.co.uk/).

## Concrete next action: one coverage/evaluation enquiry

Prepared, unsent message: `ab-cinema-feed-enquiry-2026-11-01.md`, with a ready-to-open `.eml`
alongside it. Recipient **hey@filmchase.com** is the public support address on the publisher's
[FAQ](https://www.filmchase.com/faq); the same publisher documents the API relationship.
The message asks for exact nine-venue coverage/IDs, horizon and identity/date/freshness fields,
Lite omissions, trial/billing/VAT terms and cache/fixture/backup rights.

It discloses only the private two-person app purpose, public venue list and Craig's first
name. It includes no app URL, collection, user records, tokens, credentials or hosting IDs.
There is no signup, trial, payment or billing authority in it. Supplier response time is
unknown; sending the enquiry has no quoted supplier fee and makes no purchase commitment.

**Stop before sending:** explicit supplier-contact instruction is still required. The
message can be sent through an approved email connection or opened in Craig's email client;
no email-sending connector is currently available in this session. No message was sent.

## Conditional source and build re-plan

1. **Confirm suitability without subscribing.** Ask about all nine venues, not just four
   ODEON branches. Obtain actual IDs/address matches and named gaps; a chain claim is
   insufficient. Confirm total cost and a genuinely bounded evaluation route before any
   account, key, trial or request approval. A supplier reply is evidence, not acceptance.
2. **Prepare a separate exact evaluation contract.** Once endpoints/auth/pagination/rights
   are known, specify venue IDs, GETs, request/body/retention limits, repeat timing, refusal
   stops and cleanup before asking for a sample go. No current permission is inferred for
   an authenticated third-party feed. Preserve historical archive/no-retry boundaries.
3. **Validate real programmes before building.** Correct venue identity, ordinary and
   older/reissue/event examples where offered, original-year gaps, stable IDs, local date/
   offset/DST behaviour, booking-link shape, actual horizon/completeness, provider freshness
   and withdrawal/cancellation semantics. Sparse examples cannot pass full coverage.
4. **Choose the architecture from evidence.** Prefer one API for all nine only if verified.
   If either independent is absent, assess a hybrid with the five previously sampled direct
   sources and API-backed ODEON data; no venue omission is accepted. A server HTTP client
   could remove the browser-worker dependency, but server access and hosting/key handling
   must be proved/approved first. No recurring Vercel VM is proposed on current evidence.
5. **Approve the revised full build contract.** Resolve subscription budget, formats,
   freshness, deletion on cancellation (including fixtures/backups), source attribution,
   schema/API/refresh/retention, original-year matching and navigation. Re-estimate/split
   AB6 only after source scope is known; retain one branch/PR per implementation batch.

No schema, app API, job, runtime, credential, account, production data or architecture map
was changed. No programme specimen was fetched. Documentation/source consistency checks
apply; full application gates do not apply to this research-only change and were not run.
AB6/AB7 remain unstarted; AA10c and every other sitting remain excluded.
