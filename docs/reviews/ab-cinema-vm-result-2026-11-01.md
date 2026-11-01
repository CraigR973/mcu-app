# Cinema VM test: sandbox startup works; probe check caused the stop

1 Nov 2026. Owner-authorised experiment (#321), one VM only; completed and stopped.

Chromium launched non-root with namespace and seccomp sandboxing. **My status check used
the wrong field label**, rejected that valid evidence and ended the experiment before any
cinema request. This is a probe defect, not a Vercel sandbox failure or an ODEON access result.
The defect is fixed and tested offline. No second VM or browser retry was started.

## Approved scope and actual run

Craig's “proceed” approved the exact one-off experiment in
`ab-cinema-vm-proposal-2026-11-01.md`: existing MCU Vercel project, one VM, iad1, 1 CPU/2 GB,
30 minutes including setup, no ports/persistence/mounts/app credentials, sandbox mandatory,
offline launch check before bounded four-venue ODEON collection. This did not approve
the ingestion/discovery application contract, recurring hosting or another sitting.

The VM ran from 10:44:05 to 10:48:19 UTC, **4 minutes 13.490 seconds** of provider-reported
runtime. One creation, one browser launch, zero cinema requests and zero screening rows.
The first-pass/tomorrow/repeat source checks did not run.

| Evidence | Observed result |
|---|---|
| Resources | 1 CPU, 2,048 MB, amd64, iad1; no failover |
| Environment | Ubuntu 26.04, Node v24.22.1, UID 1000; no credential-bearing variables |
| Browser package | Playwright 1.64.1; locked package and Chromium installation succeeded |
| Exposure/storage | No public routes, mounts, persistence or snapshots |
| Launch network | Provider deny-all applied and read back before Chromium launched |
| Security result | Layer 1 Namespace; PID/network namespaces Yes; seccomp-BPF Yes |

Image resolved to
`vercel/sandbox/node@sha256:6927dfce823159a574dc3b87fa327cde48533c7498b92492c31179a5477c9fd6`.
The provider's legacy `runtime` metadata says `node22`; the executed environment actually
reports Node v24.22.1. The image digest and runtime command evidence are retained separately.

Only package/lock, source probe and launch check were uploaded. No repository, app environment,
private collection/diary data, database credential, token, copied cookie/profile or booking
action entered the VM. Sudo was used only for the approved Ubuntu HTTPS package-repository
transport correction and library installation. The browser ran without sudo or permission
relaxation. Setup used the exact dependency host allowlist; no cinema hosts were enabled.

## The check defect and correction

The captured Chromium page reports these distinct facts:

- Layer 1 Sandbox: Namespace.
- PID namespaces and Network namespaces: Yes.
- Seccomp-BPF sandbox and its TSYNC support: Yes.

The old predicate searched for a single `Namespace Sandbox: Yes` field. That field does not
exist in this Chromium output, so it returned false despite affirmative namespace evidence.
The subsequent renderer-command inspection and separate local rendering check were not
reached. Therefore the complete automated launch check has **not** passed, even though the
captured page establishes namespace/seccomp operation and an internal page rendered.

The corrected predicate requires Layer 1 Namespace **and** PID namespaces Yes **and**
network namespaces Yes **and** seccomp-BPF Yes. Missing, duplicate or negative fields fail;
the page's reassuring summary sentence alone cannot pass. Browser sandboxing, non-root,
renderer-command inspection and the source gate remain mandatory. This fixes recognition
of the actual status fields without accepting disabled or ambiguous isolation.

Eight offline tests pass: four source/credential/date guards plus four status-fixture
regressions, including negative/missing/duplicate security evidence. Syntax and evidence
checks pass. No expectation or gate in the application was changed. Full application gates
were not run because there is no application implementation.

## Access and tooling corrections

The cached CLI access token initially returned 403 on read-only account/Sandbox requests.
Normal `vercel whoami` refreshed the existing OAuth login; subsequent reads succeeded.
No new account, credential scope, application environment pull or plan upgrade was requested.
The account is active Hobby; remaining quota was not queried.

Earlier discovery incorrectly concluded the connector lacked command/stop operations.
They are exposed under **session** names. This run used the connected creation, file,
command, network, stop and verification tools. A separate local SDK deadline guard was
active and later removed. SDK controller code remains a prepared fallback, not the controller
that executed this run.

The nonwaiting command-status endpoint kept returning `exitCode: null` after npm had
finished. Waiting on that same command returned its actual exit code 0 and 1.027-second
duration. No npm command retry was made. Later commands waited for completion and reported
exit codes. Large library-install logs were provider-sampled; their successful exit and
sampling boundary remain explicit in the raw audit.

## Cleanup, production and cost

The exact session is stopped, persistence false and network deny-all. Independent reads
confirm no running project Sandbox, no snapshot for this probe and no public route. The
deadline guard is absent and the temporary local upload archive is removed. Stopped metadata
remains; provider-internal memory/disk/cache erasure is not independently verified.

Read-only production checks still return API SHA
`c63bc06a7c7d317783b03a3379eb7b2b53852728`, db ok and all five integrations configured.
There was no Vercel application deployment during the experiment. No Railway configuration,
production collection data, app dependency or application architecture was changed.

Provider usage: 23.946 active CPU seconds, 324,254,196 ingress bytes and 510,206 egress bytes.
These are dependency/setup traffic, not source traffic. Existing Hobby allowance was used;
no paid plan or subscription was enabled. Actual invoice/remaining quota was not queried.
The prior paid-rate comparison for a full 30-minute experiment remains under US$0.09 compute
plus transfer/tax, using the [official iad1 pricing](https://vercel.com/docs/sandbox/pricing).

Minimal audit: `ab-cinema-vm-result-2026-11-01.json`. Captured status, exact tool results,
package locks and corrected probe/tests remain locally under
`scratchpad/ab-cinema-research/vercel-vm-proposal/`. No successful cinema screenshot exists.

## Remaining checkpoint and concrete repeat proposal

The one-creation/no-retry approval has been used. A second VM needs a fresh hosting go;
the already granted cinema-source permission remains in force. Do not silently replace
the stopped VM, resume it, disable sandboxing or run another source method.

Recommend one replacement experiment under **all the same limits** in the approved proposal:
one VM/30 minutes including setup/1 CPU/2 GB/iad1/no failover/no ports/no persistence/no
credentials; pinned Playwright 1.64.1, corrected status check and the tested managed image
digest above. One launch check with internet denied, then a second sandbox-enabled launch
only after full preflight success. One failure stops; no retry/replacement. Four ODEON
venues only, today/tomorrow, successful-first-pass-only repeat after five minutes, maximum
eight contexts/sixteen selected days; 120 requests/15 MB stop threshold/90 seconds per
context, GET/HEAD only, refusal/queue/CAPTCHA stops and exact cleanup unchanged.

Allow up to 30 minutes of VM time and roughly 15–45 minutes of engineering/review time.
Paid-rate compute comparison remains under US$0.09 plus transfer/tax; no upgrade or new
credential is included. This repeat is **proposed, not approved or executed**.

Runtime evidence has improved; unattended four-venue source access has not been tested.
All nine venues and Film first remain intended. Complete horizon, original-year matching,
cancellation/reschedule/DST and sustained access remain open. Full source/build contract,
AB6/AB7 implementation and proposed split still need approval. AA10c and other sittings
remain excluded.
