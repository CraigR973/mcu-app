# Cinema collection: sandbox-preserving VM experiment

1 Nov 2026. Proposal only; not a hosting or application approval.

**Later 1 Nov (#321): Craig's “proceed” approved this one-off hosting experiment.** It
finished after one creation/one browser launch: Chromium's namespace/seccomp status was
affirmative, but a probe label-recognition defect stopped before cinema requests. VM stopped,
no snapshot/running probe; correction tested offline, no replacement authorised. Current
result and exact repeat checkpoint: `ab-cinema-vm-result-2026-11-01.md` and JSON. Preparation
and uncertainty statements below describe the pre-run planning snapshot, not current results.

Craig's “continue” follows the recommendation to retain Chromium sandboxing and research
a compatible runtime. No sandbox-off selection is inferred. This report completes that
planning step; #318's temporary Railway approval is spent and does not cover Vercel Sandbox.

## Recommendation and remaining uncertainty

Try one ephemeral Vercel Sandbox VM on the existing MCU Vercel project. A VM with its own
kernel is a plausible way to avoid the container permission failure, **not proof** that
Chromium's sandbox will work. Keep sandboxing mandatory and test it before any cinema call.
The alternative of disabling Chromium's sandbox is rejected for this proposal because it
reduces browser isolation. No new account, subscription or recurring collector is proposed.

Read-only connected tools confirmed the existing `mcu-app` project and its team. They did
not expose the billing plan or remaining Sandbox quota. Creation, command execution,
network-policy enforcement, launch compatibility and cleanup have not been tested here.
The connector exposes creation/configuration but lacks the command and stop operations
needed for this complete experiment; use the documented SDK/CLI for the lifecycle after
approval. An existing local CLI token's presence was verified without exposing its value;
its Sandbox entitlement is unverified. Validate caller authentication and cleanup capability before creation;
stop if a new credential, plan upgrade or unsupported control would be required.

[Vercel's runtime documentation](https://vercel.com/docs/sandbox/concepts/runtimes) describes
the dedicated-kernel VM boundary. This supports the candidate choice, not a browser result.

## Exact hosting scope for approval

| Control | Proposed value |
|---|---|
| Supplier/project | Vercel Sandbox, existing `mcu-app` project/team |
| Region | `iad1`; no automatic region failover |
| Resources | One VM, 1 vCPU / 2 GB RAM, amd64 |
| Lifetime | One creation, maximum 30 minutes including setup; no extension/resume |
| Persistence | Explicitly false; no snapshots, drives or mounts |
| Exposure | No ports, domains, deployment, schedule or app environment |
| Browser | Non-root, Chromium sandbox enabled; no permission relaxation |
| Versions | Managed Node 24 image; probe-only Playwright 1.64.1 |

The managed image tag can change: record the resolved image identity, OS, Node, package
integrities and browser version in the run audit. No custom registry/image publication is
needed. The earlier Playwright 1.60.0 container is not silently reused: the managed image's
Ubuntu 26.04 needs a supported version. The locally prepared probe package pins 1.64.1
and its dependency integrity lock; the application dependencies remain untouched.
[Managed images](https://vercel.com/docs/sandbox/concepts/images) and
[Playwright's Ubuntu support](https://playwright.dev/docs/release-notes#version-161).

Only the probe package/lock, source probe and launch check enter the VM. No repository
clone, environment files, collection/diary records, database credentials, cookies, browser
profile or provider/application tokens enter it. Caller authentication stays outside the
VM. Do not pull application environment variables to obtain credentials. Check for
credential-bearing VM variables before executing the browser; refuse if present.

## Run and stop contract

1. **Setup, at most 10 minutes.** Allow only HTTPS package/browser/OS dependencies at
   `registry.npmjs.org`, `cdn.playwright.dev`, `playwright.download.prss.microsoft.com`,
   `storage.googleapis.com`, `archive.ubuntu.com` and `security.ubuntu.com`. No broad
   internet rule or IP-range allow rule. Install the locked browser package, Chromium and
   required libraries. Permit changing only these Ubuntu repositories' transport from
   HTTP to HTTPS inside the VM so the domain firewall can match them. Sudo is permitted
   only for that transport correction and package installation inside this VM;
   never for the browser, a host change, sysctl/AppArmor/seccomp relaxation or container
   privilege expansion. Unknown redirects/missing dependencies stop setup.
2. **Launch check, internet denied.** Switch the provider firewall to deny-all. Launch
   full Chromium non-root with `chromiumSandbox: true`; render an internal/local page and
   retain Chromium's sandbox-status evidence. Require affirmative namespace and seccomp
   evidence, not merely a successful process launch. Missing/ambiguous evidence or any
   launch failure stops the experiment without a cinema request or diagnostic retry.
3. **Source check, only if launch check passes.** Close the launch-check browser, allow
   only `www.odeon.co.uk` and `vwc.odeon.co.uk`, then run the existing bounded source probe
   with a fresh sandbox-enabled browser. This second launch is not a retry after failure.
   One failure ends the run; no third launch or replacement VM. Kilmarnock, Glasgow Quay,
   Braehead and East Kilbride only. Today/tomorrow in Europe/London, two passes at least
   five minutes apart; only first-pass successes receive a second pass. Maximum eight
   source contexts / sixteen selected venue-days. Retain request/byte counters, source
   dates, stable identifiers, titles/starts, refusal outcomes and comparison evidence.
4. **Cleanup.** Controller `finally` stops the exact VM and an independent deadline guard
   checks its state. The provider's 30-minute timeout remains the backstop if the client
   disappears. Never extend it to finish a sample. Verify stopped state, persistence false,
   no snapshot/drive and no running named probe. A stopped provider metadata record may
   remain; do not claim provider-internal media/cache erasure. Remove local upload copies;
   retain minimal credential-free audit evidence and report actual charges if available.

Source limits remain **per context**: 120 allowed requests, 15 MB received-byte stop
threshold and 90 seconds. Across eight contexts that is at most 960 allowed requests and
eight 15 MB thresholds; completed/in-flight responses can exceed a byte threshold before
closure, so this is not a strict transferred-byte ceiling. The provider timeout bounds the
whole experiment, including the two launches. Setup traffic is separate from source traffic.

Only GET/HEAD source traffic is allowed. Block booking/account/payment actions, downloads,
trackers, images/fonts/media and non-approved hosts. Stop affected venues at queue/CAPTCHA,
401/403/407/429 or other access refusal, without retry, proxy, copied cookies/keys or identity
disguise. No authenticated ODEON schedule call, operator contact or purchase. Fresh anonymous
session state created by ordinary page loading stays within its temporary browser context.

[Vercel's firewall](https://vercel.com/docs/sandbox/concepts/firewall) supports runtime policy
changes. Its domain rules constrain TLS SNI, not every encrypted HTTP destination; retain
the browser's method/URL guards as well. No credential brokering or request rewriting is
needed. Require read-back/verification of each policy transition before proceeding.

## Cost and engineering time

The [official pricing table](https://vercel.com/docs/sandbox/pricing), checked 1 Nov,
quotes `iad1` Active CPU at US$0.128/hour, memory at US$0.0212/GB-hour and creations at
US$0.60/million. One CPU fully busy for 30 minutes plus 2 GB for that duration and one
creation is **US$0.0852006**. This is a compute estimate, not a guaranteed invoice cap.
Downloads are free; outgoing traffic and tax are extra. No exposed-port traffic, snapshot
or drive storage is requested. Hobby included quota may make this zero-cost; its actual
remaining quota and the team's plan are unverified. No upgrade or billing-setting change
is authorised. If the current account cannot run it, stop rather than subscribe.

Allow about 30–60 minutes of engineering/operator time for controller checks, one run,
cleanup verification and evidence review. A successful test creates no recurring monthly
commitment; a recurring architecture and its costs would need a later decision.

## Prepared evidence and acceptance limits

Local, ignored preparation: `scratchpad/ab-cinema-research/vercel-vm-proposal/` contains the
machine-readable proposal, caller SDK/package lock and a separate minimal worker bundle.
The unchanged source guards have four passing offline tests. Package locks and JavaScript
syntax are checked. The controller's default mode was run and refuses creation without its
explicit execution flag. No VM was created and no launch/source/cleanup check ran. The full
application gate is inapplicable to this research-only change and was not run.

The prepared SDK 3.9.1 controller checks returned resource/persistence/image/network settings,
uses a separate deadline guard, retains browser diagnostics and stops in `finally`. The
prepared internal sandbox-status check requires namespace/seccomp evidence before source
access. It uses an existing caller credential only after its explicit execution flag and
never forwards that credential into the VM. Their remote execution remains untested;
preparation is not a passed lifecycle.
If provider controls differ from this contract, stop before creation/source work and report
the exact mismatch rather than silently widening access or resources.

Success would establish only this bounded four-venue browser collection result. It would
not prove complete programme horizons, sustained recurring access, original-year matching,
cancellations/reschedules, DST handling or all-nine production ingestion. Failure is recorded
as setup, launch or source failure according to where it occurs; never as “no films”.

All nine venues and Film first remain intended. AB6/AB7 and the proposed split/full build
contract remain unapproved. No architecture change, application write, parked links screen,
archive retry, AA10c or other sitting is included.

## Owner checkpoint

Approve **this one Vercel Sandbox experiment only**, with the resource, version, network,
security, source, cost and cleanup contract above. Recommendation: approve, because it
tests the runtime hypothesis while retaining browser sandboxing. The real cost is the
engineering time above and estimated compute under US$0.09 plus transfer/tax; compatibility
and ODEON access can still fail. New hosting requires explicit approval under the repository's
hosting guardrail; the already granted permission to read cinema sources is not being re-asked.
