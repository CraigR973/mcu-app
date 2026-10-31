# Browser comparison: all nine venues now have real samples — 31 Oct

**The five previously blocked venues yielded 111 additional screening rows in the Codex
in-app browser. Combined with the earlier four-venue sample, all nine intended venues now
have real screening evidence: 226 rows collected at different times/windows.**

This changes source feasibility. It does not prove a reliable background collector or
approve AB6/AB7 implementation. The earlier queue/403 failures remain genuine observations.

## What the comparison actually used

Craig said “try it” after the recommendation to compare the blocked sources in a normal
browser. The connected-browser inventory exposed Codex's in-app browser and MCP Apps only;
Craig's normal Chrome/Safari profile and native apps were unavailable. The comparison used
the available in-app browser through its documented UI controls and read-only DOM access.
It must not be reported as a successful test in Craig's everyday browser.

Ordinary venue navigation, one normal reload each for the initial ODEON/Cineworld tabs,
cookie rejection and normal page loading were sufficient to observe programmes. No login,
CAPTCHA solving, proxy/VPN, forged queue cookie, credential extraction, security-setting
change or access-control workaround was performed. No booking/seat link was followed.

## New results

| Venue | Captured screening rows | Films with captured times |
|---|---:|---:|
| ODEON Kilmarnock | 15 | 9 |
| ODEON Glasgow Quay | 28 | 14 |
| ODEON Braehead | 25 | 18 |
| ODEON East Kilbride | 18 | 10 |
| Cineworld Glasgow Silverburn | 25 | 12 |
| **Total** | **111** | **Per-venue counts; not deduplicated across venues** |

The selected day was 31 Oct, with observations between 17:33 and 17:37 UTC. Some displayed
times had already passed; counts are observations, not a promise of bookability. There are
110 unique source booking/showing references and one explicitly expired Cineworld time
without a booking link. The previous GFT 20/Vue 31/Everyman 11/Science Centre 53 samples
remain separate evidence from 14:40–14:46 UTC; 226 is their combined record count, not a
single synchronised snapshot, complete window or future-only listing.

ODEON DOM cards expose film identifiers, film titles, time, screen and a `showtimeId` in
the venue's booking link. Observed namespace prefixes are Kilmarnock `019`, Quay `530`,
Braehead `615`, East Kilbride `923`; every captured booking reference matched its branch.
Cineworld links expose `088-…` showing references, while film links identify theater `X0VQ1`.
These fields were read from the rendered programme, not guessed or taken from hidden app state.

The tracked `ab-cinema-browser-comparison-2026-10-31.json` contains exact counts, observation
times, ten minimal examples, the expired example and evidence hashes. The fuller DOM rows,
initial-extraction audit and visible Cineworld screenshot are gitignored under
`scratchpad/ab-cinema-research/browser-comparison-2026-10-31/`. No plots, images, cookies or
credentials are included in the tracked JSON. The two inspected browser tabs were retained
as visible deliverables; no claim that their session is a deployable data service follows.

## Failures, correction and limits

- The first ODEON tab creation timed out and reset the browser-control session, although
  the tab subsequently existed. Rebinding the observed tab recovered it. Glasgow Quay
  navigation also timed out before its loaded programme was inspected; it then showed
  real times. No source was repeatedly hammered to obtain a different answer.
- Kilmarnock initially showed a listings error; after one normal reload and later page
  inspection its programme appeared. Cineworld initially showed an uninitialised location
  selector/disabled dates; after one reload and later inspection it had selected Silverburn
  and loaded times. A location-control attempt made no change; a later attempt targeted
  the old label after it had changed, producing a locator timeout. The fresh DOM revealed
  successful loading. Neither a page title nor initial DOM readiness was a reliable result.
- The source/engine/session/network/readiness factors were not isolated. This evidence
  cannot establish that a longer wait alone fixes the earlier headless/HTTP failures, nor
  that cookie rejection caused the success. No fresh source HTTP-status/response-body
  capture was made through this UI-only comparison; do not invent successful API traces.
- Local validation initially assumed every captured time had a booking URL. One Cineworld
  time failed that check. DOM inspection established that the expired control is a span
  with `role=button`, `aria-disabled=true` and an accessible “expired” label, rather than a
  native disabled button. The diagnostic's expiry classification was corrected from that
  visible evidence; its original extraction is retained. The record is explicitly expired
  with no booking link, not silently dropped or fabricated. No app test/gate was changed.
- All five new samples cover one selected day. Original release year, recurring refreshes,
  cancellation/reschedule semantics, stable identifiers and complete future coverage remain
  unproved. Date/time parsing needs Europe/London rules; these post-clock-change samples
  do not exercise a DST transition. The long date-picker strip is not a proven horizon.

## Revised build prerequisite

The immediate problem has changed from “five venues yielded no times” to “nine sources
have samples, but the browser-dependent route is not operationally proven”. Keep all nine
venues and the Film first concept. The parked links-only proposal and a paid provider have
not been selected. No subscription or trial was started, and this comparison cost no
provider fee; the future collector's hosting/memory/maintenance cost is still unknown.

Before application implementation, establish a bounded repeatable collection method that
can run in the intended deployment environment, without borrowing an interactive user's
browser cookies/session. An in-app browser tool is evidence, not the production worker.
Then approve the concrete source coverage, parser/adapter split, schema/shared API, job,
request limits, refresh/failure/freshness, original-year matching, retention and navigation
contract. Any hosting/dependency-topology change needs its own explicit decision.

AB6 ingestion and AB7 discovery remain unstarted and retain their owner checkpoints. Do
not silently narrow coverage, mark them complete from samples, start AA10c or another sitting.
Architecture structure, application code, production data and hosting are unchanged. No
PR, push or deployment was performed in this comparison.

## Verification

Sample/document checks pass: five exact venue identities, 111 correctly timed rows,
110 distinct source booking IDs in their exact branch namespaces, one explicitly expired
unlinked row, no booking navigation, accurate earlier/later totals and local evidence hashes.
The screenshot visibly shows Cineworld Silverburn, selected Sat 31 and Wicker's four times.
No product gate, stable refresh, full-window acceptance or production smoke is claimed.
