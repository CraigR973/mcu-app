# AB6 report-head CI stop — 3 Nov

**CI failed; no cinema implementation, rerun, waiver, merge or production action.**
The approved two-request Vue research succeeded independently; its factual report remains
valid. This new verification failure blocks the proposed public-page-first build before
implementation, even if a build-only approval subsequently arrives.

## Observed failure

Exact report head 282eb9e0e17758b2952d4385133864ea361e7749, PR CI 41643751573:
six jobs pass, E2E fails. Chromium 62 pass; Firefox 61 pass/one documented skip; WebKit
59 pass/one failure/two documented skips; all six cron-job cases pass. No new skip.
Failure: “a film page adds a random pick to Suggested without losing its vote”, WebKit,
375×812. After clicking Add to movie night, the test cannot find the voted Filler Feature
031 in Suggested within the existing 10-second assertion. The saved page remains the film
page with its night selector and add button, not the expected night page.

The preserved trace records the Add to movie night click. It records the earlier vote POST
200, but no candidate suggestion POST after the final click. This narrows the observed
failure to a click/handler/navigation sequence that never produced the expected request;
it does not establish the cause. No application error or causal repair is inferred from
absence alone. No contemporaneous main reproduction was run; main is not called red on
this evidence. The affected test/component Git blobs are identical on production/main
6d0f676, prior all-seven-green a1604e8 and failed 282eb9e; all app/shared/hosting code is
unchanged between the prior green and failed report heads. This is not proof of flakiness.

Downloaded GitHub artifact `e2e-failure` (13234023092; 41,967,067 bytes) is preserved locally,
including the failed trace/error context/API and web logs. The sanitised evidence file
ab6-vue-session-ci-stop-2026-11-03.json preserves counts, exact blob IDs, relevant request
methods/paths/statuses, trace/log hashes and local artifact directory; no headers/tokens or
raw authenticated trace are committed. Full original CI:
https://github.com/CraigR973/mcu-app/actions/runs/41643751573.

No manual rerun or test/timeout/assertion/skip change occurred. Publishing this required
failure handoff may trigger new documentation CI automatically; any later pass cannot
clear this observed failure without established cause and an accepted causal repair.

## Proposed prerequisite — UNAPPROVED

Recommend a separate movie-night film-page investigation and minimal causal repair:

1. Preserve the AB6 branch, evidence and draft PR #125. Confirm current main/checks before
   any new implementation. Use one separate `fix/` branch and PR from green main; never
   fold this repair into AB6 or create a second cinema PR. No other sitting.
2. Establish the cause from the saved trace/network/DOM and a controlled reproduction;
   add a meaningful regression that fails before the repair. Investigate only film-page
   promotion of a random movie-night pick with its existing vote. Do not assume a missed
   click, selector race or navigation issue before proving it.
3. Implement the smallest demonstrated repair, preserving night selection, source title,
   voted state, Suggested promotion, ordering/navigation and existing viewport/assertions.
   No added delay/timeout, skipped test, altered random seed, rerun-until-green or weakened
   gate. If fixing a genuine test expectation or expanding scope is necessary, report
   that concrete decision first; do not take it as a route to green.
4. Run full normal clean local and exact-head seven-job PR gates, including all browser/
   jobs suites. Playwright WebKit is CI-only on this Mac; local Chromium/unit regressions
   cannot be presented as its proof. After demonstrated cause/repair/full green gates,
   normal code-only close-out may merge/deploy this repair, with exact merged production
   API/web SHA and readiness verified. This authorises no hosting/credential/configuration,
   API/schema/auth contract, destructive/live data write, cinema/TMDB/model request or
   cinema deployment/import/mapping/enable.
5. Normally merge the verified green main back into the preserved AB6 branch, retaining
   both documentation histories. Re-verify the integrated tree before any separately
   approved source-protocol build. The concrete Vue build amendment remains UNAPPROVED
   unless Craig separately accepts it; neither repair approval nor a later CI pass is
   that acceptance. Fresh all-nine source scope/actual rows/mappings and exact production
   cinema actions remain separate stops. No AB7, AA10c or other sitting.

Cost: diagnosis plus one full repair verification/production close-out and one integrated
AB6 verification cycle; existing CI/hosting resource cost unpriced, source fees £0.
The repair changes and deploys only the proven movie-night code; if wrong, the existing
vote/promotion/navigation flow could remain broken. Reject retrying unchanged CI because
it cannot explain or repair the observed failure. This plan is concrete investigation/
repair authorisation requested before work, not approval already received.
