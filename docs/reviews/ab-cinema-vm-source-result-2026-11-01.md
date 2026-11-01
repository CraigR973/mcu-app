# Cinema VM replacement: browser passes, four venue URLs return 403

1 Nov 2026. Owner-authorised replacement experiment (#322), completed and stopped.

The full sandbox-enabled launch check passed. Each of the four ODEON venue URLs then
returned **HTTP 403** from this VM: four source requests, zero programme samples, zero rows.
There was no retry or second pass. This demonstrates the tested browser runtime works;
it does not establish unattended ODEON collection or an all-nine programme feed.

## Approval and actual execution

Craig's “approve” accepted the same-limits replacement proposed in
`ab-cinema-vm-result-2026-11-01.md`: one creation, maximum 30 minutes, iad1/1 CPU/2 GB,
non-root sandbox-enabled Chromium, no public ports/persistence/mounts/app credentials,
mandatory offline launch check before source work and exact cleanup. The full application
contract and batch split remain unapproved.

The VM ran from 11:07:27 to 11:10:58 UTC; provider-reported runtime **3m31.070s**. Exactly
two browser launches: the successful launch check, then the permitted source collector.
UID 1000, Ubuntu 26.04, Node v24.22.1, Playwright 1.64.1, Chromium 156.0.8078.4.
The same managed image was pinned to
`sha256:6927dfce823159a574dc3b87fa327cde48533c7498b92492c31179a5477c9fd6`.

Eight offline checks passed before creation. The remote launch check then passed with
internet denied and read back, affirmative layer-one/PID/network namespace/seccomp status,
three renderer processes without sandbox-disabling flags, and separate local page rendering.
No permission relaxation, host privilege expansion or browser-sandbox disabling occurred.

Only four probe files were uploaded. Package/browser/library installation used the approved
dependency hosts; sudo was confined to HTTPS repository transport and library installation.
No repository, environment file, private app data, token or copied browser profile/cookie
entered the VM. Credential-variable and non-root checks passed before package setup.

## Source result

After preflight success, the provider firewall was replaced with only `www.odeon.co.uk`
and `vwc.odeon.co.uk`, then read back. The fresh collector browser made one main-page GET
per venue, with its existing method/booking/asset/tracker/request/byte/time guards active.

| Venue | Outcome |
|---|---|
| Kilmarnock | Main venue URL HTTP 403; no sample |
| Glasgow Quay | Main venue URL HTTP 403; no sample |
| Braehead | Main venue URL HTTP 403; no sample |
| East Kilbride | Main venue URL HTTP 403; no sample |

The source cycle emitted completion after 2.320 seconds, four contexts/four requests/zero
successful contexts. Refused contexts closed immediately. The resulting “page/context has
been closed” messages are consequences of that deliberate stop, not another browser-startup
failure. No schedule API request, date selection, screenshot, booking action, repeat,
different host/provider or authenticated request followed. Today/tomorrow and repeatability
acceptance therefore remain untested here.

The response issuer is unconfirmed: headers/bodies were not retained, so a 403 at a venue
URL does not by itself identify which upstream/proxy layer issued it. The received-byte
counter reports zero because contexts closed before request-finished accounting; this is
**not evidence of zero transferred bytes** or an empty cinema programme.

## Observability limits retained

Four complete venue/refusal objects and the completed-event prefix/counters were captured
in the progress summary. The connector truncated strings at 2,000 characters, including
the base64 of the 3,053-byte source log and the final resource-usage tail in the summary.
The complete original source log is not locally recoverable after stopping; partial original
and complete captured venue summaries are explicitly labelled. The 268-byte sandbox status
and empty stderr were captured intact. No successful source screenshot exists.

A read-only progress-reader command initially had a syntax error; it was corrected without
restarting the collector or making another source request. A command-status read attempted
after cleanup returned 410 `sandbox_stopped`, so the final source process exit code was not
verified. These are audit limitations, not a green source gate. Any future approved experiment
must capture bounded file chunks and command exit status before stopping; no extra run was
made just to repair this record.

## Cleanup, production and cost

The exact VM is stopped, persistence false, with no public route or snapshot. Independent
reads confirm no running Sandbox in the project. The deadline guard is terminated/absent
and the temporary upload archive is removed. Source-only network policy remains in stopped
metadata; there is no executing VM. Provider-internal media/cache erasure is unverified.

Read-only API checks still serve `c63bc06a7c7d317783b03a3379eb7b2b53852728`, db ok and all
five integrations configured. No application change, migration, recurring job, live collection
write, hosting-variable change, PR/push or other sitting occurred. No application gate ran.

Provider usage: 37.948 active CPU seconds, 323,569,061 ingress bytes and 400,986 egress bytes.
This includes dependency setup and the source phase; the provider totals do not separate them.
Existing Hobby account, no paid upgrade/new credential scope/subscription. Invoice/remaining
quota were not queried. The approved paid-rate comparison was under US$0.09 compute for
30 minutes plus transfer/tax, not an invoice guarantee.

Minimal audit: `ab-cinema-vm-source-result-2026-11-01.json`. Local raw tool results, intact
status, partial original log and extracted venue evidence are under
`scratchpad/ab-cinema-research/vercel-vm-proposal/`. Capture boundaries remain explicit.

## Re-plan and owner checkpoint

The proposed ordinary hosted-browser route has now been tested and does not provide the
four ODEON programmes in this configuration. Do not create another identical VM, relax
browser protections or infer source feasibility from earlier in-app-browser specimens.
Five venues' earlier Railway HTTP specimens remain historical evidence, not complete/live
nine-venue acceptance. All nine venues and Film first remain intended.

The ingestion contract is on hold at its source/coverage/cost checkpoint. A revised route
needs to establish an obtainable programme feed for the four ODEON venues (including
permission, coverage, freshness, identities, dates and any fees), or an explicitly accepted
owner-supplied capture/import workflow. Neither route is selected or proved here; no
operator contact, account, paid provider, trial or new programme request is authorised by
this replacement approval. Existing source-read permission is not being revoked/re-asked.

The next owner choice concerns **planning direction**, not another scrape approval:

| Plan next | Purpose | Cost or uncertainty |
|---|---|---|
| Feed-access research, recommended | Preserve automated updates for all nine venues | Supplier availability, coverage, permission and fees unproved; no contact/account/spend included |
| Owner-supplied capture/import design | Supply the four programmes through an agreed manual workflow | Repeated owner effort and staleness; format, identity and freshness rules still need approval |

Recommend researching feed access first because the original goal is an automatically
maintained programme. This recommendation does not claim such a feed exists or select a
supplier. Research output must make feasibility/cost concrete before any account, request,
contract or build decision. Manual capture is an alternative planning direction, not an
accepted fallback. No source/coverage requirement is silently changed.

Re-plan that source route before approving the full ingestion/discovery contract and AB6
split. No reduced venue scope is adopted. AB6/AB7 remain unstarted; AA10c and other sittings
remain excluded. This report is an experiment result, not a batch close-out.
