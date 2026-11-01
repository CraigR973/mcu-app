# Free cinema source: four ODEON venues obtained

1 Nov 2026 · decision #324 · source research, not implementation approval.

**Result: 869 screenings from all four ODEON venues, fetched both locally and from the
existing Railway API runtime using ordinary anonymous HTTP. No subscription is needed
for these public-page reads.** Craig requires this to be free. The paid API recommendation
and unsent enquiry from #323 are parked; do not send it, start a trial or buy access.

## Actual evidence

| Venue | Screenings | Observed dates |
|---|---:|---|
| ODEON Glasgow Quay | 269 | 1–7 Nov |
| ODEON Braehead | 262 | 1–7 Nov |
| ODEON East Kilbride | 201 | 1–7 Nov |
| ODEON Kilmarnock | 137 | 1–7 Nov |

Each count includes starts already past at collection time; 747 rows were future starts
at extraction. This is a seven-date source specimen, not proof of a complete seven-day
operator programme, a 14-day horizon or ticket stock. Later dates have fewer published rows.

Four local CinemaTimes GETs succeeded at 16:40 UTC; four source-only GETs from the existing
Railway API succeeded at 16:42 UTC. Every per-venue body hash and normalised programme hash
matched across runtimes. This is a short cross-runtime repeat, not a long-running reliability
test. The earlier five direct-source Railway specimens remain historical #317 evidence;
they were not re-fetched in this step. There is now a tested HTTP route for each of the
nine intended venues across these observations, not a synchronised all-nine live run.

Primary venue pages:
[Quay](https://cinematimes.com/uk/glasgow/cinemas/odeon-glasgow-springfield-quay/) ·
[Braehead](https://cinematimes.com/uk/glasgow/cinemas/odeon-braehead-renfrew/) ·
[East Kilbride](https://cinematimes.com/uk/glasgow/cinemas/odeon-east-kilbride-glasgow/) ·
[Kilmarnock](https://cinematimes.com/uk/glasgow/cinemas/odeon-kilmarnock/).

CinemaTimes publishes ISO dates in its HTML sections and operator booking/showtime IDs in
each time link. Venue names, addresses/postcodes and official operator URLs identify the
four branches. All 869 IDs are unique within their venue; booking hosts are HTTPS ODEON.
No booking link was followed. The 50 ScreeningEvent JSON-LD objects on each page agree
with their HTML starts and venue identity: 200 checks. **JSON-LD is capped at 50 per page**;
using it as the full programme would silently lose 669 rows. Extract the dated HTML instead.

Kilmarnock's 34 rows for 1 Nov have exactly the same booking IDs and local times as the
official browser specimen captured at 18:50 UTC on 31 Oct. Titles match exactly in 32 cases.
The other two are materially relevant: the ballet title is reformatted; the official
“Tabby McTat + The Room on the Broom” double bill becomes “Tabby McTat”. Showing identity
does not establish film identity. Preserve source titles/provenance and flag conflicts;
do not auto-link that double bill to a single catalogue film. No new official read was made.

## Freshness, cost and limits

The publisher says the service is free to use and syncs twice daily. That is its published
method, not a measured service guarantee. Pages say “updated Sunday 06:19”. At collection
this suggests about ten hours since upstream collection if it is the current local Sunday,
but the label has no explicit date/timezone. HTTP Last-Modified/Age values differ between
responses whose bodies are identical; neither is a dependable upstream collection timestamp.
Sources: [about](https://cinematimes.com/about/) ·
[methodology](https://cinematimes.com/methodology/).

Free viewing does not itself establish a licence for recurring ingestion. No affirmative
reuse grant was established from the inspected pages. Craig's permission to try restricted
sites remains recorded; no new permission was requested merely because of restrictive terms.
Ongoing source conditions remain explicit in the build checkpoint; no legal conclusion or
operator consent is inferred. No supplier contact, account, key or trial was used.

What’s On lists all four venues in public indexed pages and says it is free without signup,
but each of the four ordinary local venue GETs returned HTTP 429, once per distinct URL.
No retry, browser fallback, fingerprint change or alternate endpoint was attempted for that
publisher. Its terms also require written permission for automated extraction; it is not
the recommended collector. Sources: [FAQ](https://whats-on.co.uk/faq) ·
[terms](https://whats-on.co.uk/terms). Pearl & Dean and LondonNet were inspected through
public web results only; no machine programme specimen or acceptance is claimed for them.

No new host/browser runtime, deployment, schedule, variable or credential was created.
These page reads cost no provider subscription. Existing hosting resource use is not a
guaranteed zero incremental infrastructure bill; runtime/billing totals were not measured.
No recurring spend or paid alternative is approved. No app data was written.

## Revised source plan — proposed, not accepted

Retain all nine venues and Film first. Use the five already tested direct HTTP source
families plus CinemaTimes dated HTML for the four ODEON venues. Reject the paid API because
it violates Craig's £0 requirement; reject another browser VM because this HTTP route now
works on the current runtime. No need to repeat the failed ODEON VM experiment.

Return to the original **two implementation batches**, AB6 ingestion then AB7 discovery,
one branch/PR each. The earlier AB6a/AB6b browser split is withdrawn as a recommendation,
not silently accepted into the ledger. Six HTTP adapter families replace the browser stage.
This proposes no hosting change or reuse of an unsuitable existing cron.

The five-table/read-API/Film-first proposal remains a review draft. Before build approval,
revise its source provenance, title conflicts/combined programmes, observed horizon,
request ceilings, freshness and recurring execution plan from this evidence. In particular:

- Keep fetch success/time separate from source update evidence; fetching every six hours
  cannot make twice-daily upstream data six hours fresh. The old eight-hour rule is unaccepted.
- Keep missing/upstream-unknown/partial/stale coverage visible; an absent row is not a
  cancellation unless a proved-complete snapshot or explicit cancellation supports it.
- Confirm original year separately from source release dates; retain uncertain identity
  and double bills without merging remakes or inventing original-year matches.
- Bound the collector using measured HTTP bytes/requests; remove browser assets/contexts
  and new paid hosting. Validate DST/midnight semantics before enabling ingestion.

The next owner checkpoint is the complete revised source/build contract, including exact
recurring hosting/cost and any required source conditions. It is no longer a request to
approve a paid enquiry or another VM. No AB6/AB7 code starts from this report; AA10c and
every other sitting remain excluded.

## Audit and verification

Twelve explicit programme GETs: eight CinemaTimes successes across two runtimes and four
What’s On 429 responses. Public research web-tool requests are separate from those twelve.
Requests used 20-second local / 12-second hosted HTTP timeouts, a 4 MiB decoded-body cap,
no redirects or retries and one-second spacing. HTTP timeouts are not a hard total wall-clock
cap. Actual successful bodies were 235–311 KB. Raw responses/scripts/full rows stay in the
gitignored scratchpad; tracked JSON retains counts, hashes, timestamps and comparisons only.

First SSH transport attempt exited 1 with Python SyntaxError because the CLI forwarded
shell quoting literally; zero cinema requests. Corrected command encoding executed the
same read-only source script successfully and exited 0. Existing authorised SSH access;
no remote files, installs, environment reads, app imports, database or configuration changes.

Offline checks pass: 869 unique-per-venue IDs, four equal local/remote semantic hashes,
200 JSON-LD/HTML start comparisons, 34 historical official IDs/times and both title conflicts.
JSON parsing and document diff checks apply. Full application, migration, DST, cancellation,
sustained-source and production readiness checks were not run; no such change was made.

Machine audit: `ab-cinema-free-source-results-2026-11-01.json`.
