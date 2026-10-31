# Sitting 5 revised build proposal — 31 Oct

**Proposal awaiting Craig's approval. No implementation is authorised by this document.**

## Verified starting point

AB5 is report complete under decision #313, integrated through PR #123. Local and remote
main match c63bc06; exact-head main CI 41207241130 is green. The working tree was clean.
Free official programme links, all nine venues and Film first are recorded owner picks.
Programme feasibility remains unproven; the one approved historical GET returned 403.
Report acceptance resolves AB5's checkpoint, but not AB6's concrete build-contract gate.

The original sitting is AB6 ingestion (Extra High) then AB7 discovery (High). Its premise
has changed: official links provide venue destinations, not data to ingest or group by film.
The current ledger still marks both batches not ready. Nothing below changes that ledger.

## Recommended revised scope

Re-scope AB6 to one official-programme-links screen, with its own branch/PR and normal full
verification/close-out. Defer AB7's Film first programme discovery until an approved source
exists. Preserve the original ingestion criteria as the historical contract; do not mark
ingestion or AB7 complete. A future ingestion build needs a new plan and all source gates.
Retain AB6's recorded model/effort setting until Craig approves any routing change.

Reject building six scrapers: no permission, real specimens, reliable coverage or maintenance
budget has been approved. Reject a grouped-film imitation: links cannot supply its data.
Two implementation batches would add a separate release for an unused static directory;
the links screen has no ingestion dependency and can be reviewed and shipped as one batch.

## Concrete proposed contract

- Screen: **Local cinemas**, authenticated for Craig and Mark at `/cinemas`, with a Home
  link, a desktop sidebar/command-palette entry under Plan a screening, and a mobile You
  entry. Keep the existing five bottom tabs and Releases calendar. Approval includes this
  exact web-route/navigation addition; no API route inventory change is needed.
- Contents: nine accessible venue rows in the report's order, each with its current name,
  operator/domain and **Open official programme** action. Copy: “Browse films and times on
  each cinema's website.” A permanent note says “Film listings and showtimes are not shown
  in this app.” Film first remains a future concept; there are no film cards or filters.
- Data: a curated, typed, build-time web directory with local stable venue IDs and the nine
  exact official targets in AB5's report. These IDs identify directory entries, not provider
  films or screenings. No API, database, migration, job, provider account, secret, licence
  for copied listings, refresh schedule or retention store is introduced. Corrections go
  through a reviewed code change, not a new settings/editor flow.
- External navigation: ordinary explicit HTTPS links open a separate browser context with
  opener isolation and no referrer. Opening the screen performs no provider request,
  prefetch or link-health probe. The venue may redirect or show its own booking interface;
  the app does not submit a booking or payment. Links do not contain an MCU token/profile.
- Honesty: the directory has no “live”, “healthy”, “nothing showing” or freshness badge.
  ODEON/Cineworld access failures remain documented; shipping a URL is not proof its
  programme or booking journey works. An offline notice explains external programmes need
  internet; a cached directory is not a cached programme. Existing route-loading/error
  behaviour applies. Authentication and existing offline guards remain in force.

All nine targets are copied from the accepted AB5 report, without new network validation:
ODEON Kilmarnock; Cineworld Glasgow Silverburn; ODEON Luxe Glasgow Quay; ODEON Braehead;
ODEON Luxe East Kilbride; IMAX at Glasgow Science Centre; Glasgow Film Theatre;
Everyman Glasgow Princes Square; Vue Glasgow St Enoch. No substitution or omission.

```text
Home / You / desktop navigation
              |
        Local cinemas
         (nine links)
              |
       Official programme
      (person opens website)
```

## Acceptance and verification after approval

1. Both profiles can reach the page; unauthenticated access follows the existing sign-in
   guard. The new route has the correct title, navigation and Back behaviour. Existing
   routes, login returns, phone header clearance and bottom tabs retain their assertions.
2. Exactly nine intended venues/targets appear with accessible names and visible external
   navigation. Tests check HTTPS/operator targets, identity, keyboard use and absence of
   provider requests merely from rendering. No screening/film identity is invented.
3. Browser flow at 320px/375px in both themes proves navigation, readable rows, no horizontal
   overflow and offline messaging. Intercept external destinations in tests; do not call
   them. Existing personal-data isolation checks remain intact.
4. Full batch-verify gate, applicable E2E, exact-head seven-job PR/main CI, production
   API/web SHA and readiness pass. Update the current architecture map at implementation,
   showing a browser-to-venue link rather than an ingestion pipeline.
5. Report the delivered link directory and the unverified external-page behaviour separately.
   No live provider/sample acceptance is implied. Further agent-run source reads require
   exact approval; owner browsing is optional observation, not invented evidence.

## Cost, risks and owner decision

Provider subscription: £0. Background provider requests: zero. No new hosting or credentials.
Engineering cost: one implementation batch/PR plus full gates, CI and normal deployment.
Ongoing cost: manual reviewed URL corrections when operators change their sites; frequency
and hours are unknown. Existing hosting costs continue; no unsupported £0 total-cost claim.

Main risks: changed/blocked external pages and the remaining gap from the original aim of
finding older-film screenings in one view. No collection/watch-history data is changed.

**Decision requested:** approve the revised AB6 links-screen contract above and defer AB7,
then execute only revised sitting 5 through its normal gate/close-out. On approval, record
the revised ledger/owner contract before application edits. No AA10c, other sitting, source
retry, scraper, paid provider or hosting/credential change follows from this proposal.

## Proposal checks

Repository/remote state, accepted report, decision #313, owner actions, current navigation
and group-start/batch procedures were read. The proposal requires only document checks;
no application gate, source availability check or production smoke is claimed for it.
