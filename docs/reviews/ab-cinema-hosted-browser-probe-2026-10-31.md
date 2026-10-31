# Isolated hosted browser experiment — 31 Oct

**Result: runtime blocked, not an ODEON programme result.** Three sandbox-enabled Chromium
launches failed before a browser context or cinema request. All temporary services were
removed. The six original service deployment IDs and production SHA/readiness are unchanged.
No application, programme store, recurring collector or source subscription was enabled.

The original experiment lasted 15 minutes 55 seconds from first temporary service creation
to final deletion, within the approved 30 minutes. The original deadline was retained across
setup replacements. Three launch failures exhaust Group AB's retry stop; no fourth launch,
sandbox disabling, privileged host change or alternative host was attempted.

## Approval and isolation

Craig's “approve” accepted only the temporary experiment described in
`ab-cinema-ingestion-contract-2026-10-31.md` (#318), not its proposed application contract or
batch split. Four venues: Kilmarnock, Glasgow Quay, Braehead and East Kilbride. The intended
two-pass/today-and-tomorrow programme comparisons did not run because browser startup failed.

- One temporary service at a time, one replica, 1 vCPU and 2,000,000,000 bytes RAM; NEVER
  restart, no cron, domain, volume, GitHub source or inherited app credentials. Shared
  variable names were empty. New-service variable names and runtime checks confirmed no
  database/JWT/VAPID/TMDB/model/eBay/Brave/other credential variables. Only platform metadata
  such as service/project IDs and the API's public URL were present.
- Only five files were uploaded: Dockerfile, pinned package manifest/lock, probe script and
  deployment configuration. The repository, environment files, tokens, collection, diary
  and application code were excluded. The local temporary upload directory was removed.
- Official Playwright v1.60.0 Noble image, pinned to manifest digest
  `sha256:9bd26ad900bb5e0f4dee75839e957a89ae89c2b7ab1e76050e559790e946b948`.
  Package/integrity lock matches Playwright 1.60.0; runtime was Linux/Node v24.15.0 as supplied
  by that image. Browser runs used non-root UID 1001 and requested Chromium's sandbox.
- Network guards would allow only the two already observed ODEON hosts, read-only GET/HEAD,
  and the approved page dependencies; block bookings/account/payment, trackers, images,
  fonts and media; enforce 120 allowed requests/15 MB stop threshold/90 seconds per context.
  These guards were unit-checked but not exercised against a live cinema here. No browser
  context started, so cinema requests, validated screenings and successful screenshots are
  all zero. Image/package downloads are separate build traffic.

The image/package combination follows [Playwright's Docker documentation](https://playwright.dev/docs/docker).
Its recommendation for untrusted-page crawling includes non-root execution and a compatible
Linux sandbox/seccomp configuration. That recommendation is not evidence that this Railway
configuration supports the required permissions.

## What ran and what failed

| Stage | Evidence | Outcome |
|---|---|---|
| Empty setup service | `a8d5ba89-5e7a-4b64-8f0a-8bf5a46ef304` | Removed before upload when a legacy region-field guard failed; no worker launch. |
| Headless shell, first launch | deployment `915d39ec-0277-417e-9f1d-9f0d7f982b0f` on temporary service `c1c2754b-cbe2-49cb-bd9a-60c9a4ef7e8f` | Browser launch closed; first diagnostic was truncated before its useful tail. Zero cinema requests. |
| Headless shell, diagnostic launch | deployment `2ce51ada-ded4-46c4-ab17-ecd9460368de`, same service | Sandbox credentials check failed with Permission denied (13). Zero cinema requests; service then removed. |
| Full Chromium, final launch | deployment `40e696b8-35ad-415b-9bad-2842879e4ca3` on temporary service `d03b7529-deea-41a9-bbe4-1ce09d021fff` | Same sandbox credentials failure; SIGABRT. Zero cinema requests; service removed. |

The decisive diagnostic in the latter two launches is
`FATAL:sandbox/linux/services/credentials.cc:131 … Permission denied (13)`.
This establishes failure of the **tested sandbox-enabled worker configuration**, not a
universal statement about all Railway configurations, browser modes, hosts or ODEON access.

Full Chromium uses Playwright's documented `chromium` channel rather than its separate
headless-shell binary; both kept the sandbox enabled. See
[Playwright's browser modes](https://playwright.dev/docs/browsers#chromium-new-headless-mode).
No browser fingerprint/UA disguise, proxy, copied profile/cookie/key, CAPTCHA solver,
authenticated ODEON API call, host permission expansion or browser-sandbox-off run occurred.

## Setup and diagnostic corrections retained

1. Two public-API configuration requests incorrectly used `DOCKERFILE` as a GraphQL Builder
   enum. The deployment-file schema accepts it; the live GraphQL Builder enum does not.
   Corrected by keeping Dockerfile configuration in the uploaded deployment file and
   applying only supported settings through the public API. No application service changed.
2. The CLI scale invocation rejected its selector syntax. One-replica configuration was
   applied through the public API and verified. The old `region` output remained null;
   an overstrict pre-upload guard removed that empty service. The replacement used supported
   multi-region configuration; the eventual deployment manifest confirms **ams: one replica**,
   1 CPU/2 GB, Dockerfile, NEVER restart and no schedule/domain. Region verification moved
   to the deployment manifest; the resource/replica requirements were retained.
3. Railway promoted the first JSON log's fields into its structured record. The initial
   collector expected JSON inside a message, and the launch error retained only its head.
   Corrected the emitter to preserve JSON in the message and retain the error tail. The
   original failed launch/logs remain in the audit. The diagnostic retry made no site call.

These were probe setup/observability defects, not repaired application defects or successful
cinema reads. They are not hidden by the four passing offline checks.

## Cleanup, checks and cost

Deletion responses are recorded for all three temporary service IDs. Final inventory has
exactly the six original services, all with their original deployment IDs. API health
still serves c63bc06a7c7d317783b03a3379eb7b2b53852728; readiness is db ok with all five
integrations configured. No original service/variable/domain/credential/data change occurred.
An independent deadline guard also exited after cleanup; no test process/service remains.

Four offline probe tests pass: credential rejection, network/booking/budget policy,
stale-day/duplicate identity rejection, and London date selection across summer midnight/
year boundaries. JSON/document/evidence checks apply. Full application gates were not run:
there is no application implementation. No live programme, DST fold/gap, cancellation,
retention, write, job or browser-to-app ingestion acceptance passed in this experiment.

Source subscription: £0. Actual Railway build/runtime/network/tax charges were not measured;
the approved runtime estimate was not an invoice or guaranteed total. Runtime limits and the
30-minute overall deadline were retained, and all temporary services are removed. Railway's
internal image/build-cache purge is not independently verified; no credential or private
application data was uploaded. Research scripts/logs remain local/gitignored as evidence.

Minimal audit and hashes: `ab-cinema-hosted-browser-probe-2026-10-31.json`.
Raw evidence: `scratchpad/ab-cinema-research/isolated-worker/`. Screenshots are absent because
no cinema page opened successfully.

## Revised stop and next design decision

Do not start AB6/AB7 or treat this as nine-venue feasibility. The earlier five HTTP source
samples from Railway and all-nine in-app-browser specimens remain valid historical evidence;
this experiment adds no ODEON access result and cannot turn runtime failure into “no films”.

The proposed Railway browser stage is blocked for the tested sandbox-enabled configuration.
Re-plan the collection runtime before approving the complete build contract. Recommend
preserving browser sandboxing and assessing a compatible runtime; its supplier, credentials,
fees and exact experiment need a concrete proposal before any hosting change. A disposable
sandbox-off container is a different security trade-off, not an accepted fallback. No such
choice or further run is authorised by the previous “approve”.

The owner's next choice is deliberately separate from application approval:

1. **Recommended: keep Chromium sandboxing and plan a compatible runtime.** This authorises
   planning/research only; new hosting, credentials and spend await a priced concrete plan.
   Cost is further engineering time; supplier/recurring costs are not established.
2. **Alternative: separately authorise one sandbox-off isolated test.** The only browser
   launch change would be Chromium sandbox disabled, still non-root inside a disposable
   credential-free container; no host permission expansion. Retain the exact four venues,
   two-pass/success-only second pass, refusal stops and request/transfer/context limits in
   the original experiment. One worker at a time, 1 vCPU/2 GB/one replica/NEVER restart/no
   domain or schedule, a fresh maximum 30-minute window and explicit cleanup. Expected
   runtime compute ceiling comparison remains about US$0.028 before build/network/tax;
   actual bill unmeasured. A malicious page would face fewer browser process isolation
   barriers. No app/DB credentials/data may enter that worker. A successful diagnostic
   would still require a separately approved runtime/ingestion/security contract before
   recurring operation or application writes. No such test has run.

All nine venues and Film first remain intended. No reduced-coverage screen, parked link-only
build, paid provider, archive retry, AA10c or other sitting follows automatically.
