# AB5 finalisation — owner accepted, 31 Oct

**Accepted outcome: finish the report-only sitting with free official programme links as
the chosen direction and Film first as the future concept.** No unified programme feed,
ingestion, link screen, trial, purchase, credential or next sitting is authorised.

## Accepted deliverables

- The report covers all nine intended venue identities, source options, published costs,
  permissions and access limits, request-load assumptions and maintenance implications.
- Craig selected free official programme links, with all nine venues retained, and Film
  first. Official links alone cannot provide a grouped-film/showtime experience.
- The exact authorised historical sample was attempted once and returned HTTP 403.
  No rows were obtained; no retry, alternative source request or booking navigation occurred.
- Two explicitly illustrative phone concepts and a failure/freshness policy proposal are
  delivered. The proposed age threshold, navigation and freshness numbers are not approved.
- Document/source checks and phone-concept checks pass. No product code or architecture
  structure changed; AB5 specifically requires no invented local app gate or deployment.

## Exact owner-approved exception

The original ledger requires checking older-release coverage against real approved
programme examples. That criterion is **unmet**, alongside real nine-venue response shapes,
stable IDs, horizon, booking links and cancellation behaviour. A refused sample is not a
pass. The report and failure audit preserve those gaps.

Craig replied “accept” to closing **this report** with those evidence gaps explicitly recorded, because the
chosen direction has no unified showtime source. This is an owner-approved change to AB5's
report acceptance, not a statement that a source works. It does not waive any evidence,
fixture, permission or acceptance requirement for a future programme integration.

After green integration, mark AB5 **report complete — source feasibility unproven** in the ledger;
retain a visible note that the original programme-evidence criterion was not met and was
excluded from this report's close-out by the owner. Do not call it an implemented feature.
AB6 and AB7 remain unstarted and require re-planning before a separately authorised sitting
5. Do not replace them with a link-screen build without Craig's approval. AA10c stays excluded.

## Integration and handoff

The final report, sample-failure audit, concept and project handoff documents are committed
on `chore/ab5-cinema-feasibility`. Normal PR CI must pass before integration to clean `main`.
Although this is documentation only, a main push triggers the existing hosting rebuilds;
no deployment configuration, application behaviour or source request changes. Verify the
resulting exact CI head and normal version/readiness checks if integration proceeds.
No new live programme/sample read is part of finalisation.

**Owner accepted on 31 Oct:** Craig replied “accept” to the explicit report-complete /
programme-feasibility-unproven outcome, with missing evidence retained and documentation
integration after green CI. This answers the final report-acceptance checkpoint; no failed
programme criterion is represented as passed. PR #123 integration still waits for CI.

The first PR run 41203332844 passed. Run 41203387374 then failed the unchanged Firefox
offline replay test while locating the Search title tab (10-second click timeout), before
that part of the replay assertion. Chromium, WebKit and cron jobs passed. The change is
documentation only; root cause remains unconfirmed and no repair is claimed. Preserve
the failure and require a fresh exact-head PR run before merge; no timeout/test changes.
