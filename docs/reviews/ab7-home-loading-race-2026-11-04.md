# Home loading race during cinema close-out — 4 Nov

Cinemas is live and its own source/read/render checks pass. Close-out is reopened by
main CI41748981329 on67d22ec: Firefox's original Home unwatched checkbox check clicks,
but the input remains false. Chromium69, Firefox67+one failure+one existing skip,
WebKit67+two existing skips and jobs6 ran; all18 cinema cases pass. The later docs-only
af8c478 run41749759834 passes all seven with identical runtime. That timing-dependent
pass does not dismiss the observed lost tap. No blind CI retry or new skip.

## Cause from the actual failed trace

The trace's input snapshot shows Counting the archive above Feeling lucky, at click
point41,663. The stats GET returns200 after118.831ms. During the same native click,
the loading panel becomes the full metric/format rows; the checkbox moves below the
pointer/viewport and remains unchecked in the after snapshot. It is not a provider
refusal or a release-category/data problem. The public trace summary contains timings,
not authentication headers; the original trace remains ignored.

A controlled browser case holds the real stats response: the old app fails the exact
assertion that Home pick/navigation controls stay unavailable while the upper layout
is incomplete. No fabricated programme, stats body or production write.

## Minimal same-branch integration repair

Home observes the existing stats, value and admin-only attention query/cache keys.
The existing child sections share those requests. Initial loading makes the Home
Feeling lucky fieldset natively disabled and its cinema link unavailable; Loading Home
explains it. After reads settle, those same controls enable. No fixed-height guess,
Home reordering, arbitrary delay, forced click, changed expected value or test retry.
Movie-night usage keeps its default behaviour; filter/run state is preserved.

The original Home test is unchanged. The new held-response case checks Craig and Mark
at375px, disabled-before/enabled-after, actual native checkbox state, cinema navigation,
no diary mutation and exactly one shared stats GET per person. The source-shaped cinema
cases remain. This is the Home entry's required integration repair within AB7, on the
same branch/single PR128, not a new sitting. Existing source/format/data/auth/hosting/fee
contracts and all acceptance assertions remain.

Focused unit29 pass. The controlled regression and original Home test pass in Chromium
and Firefox; all8 focused Firefox cases pass. One Chromium Mark login failed with a
local read ECONNRESET before its browser opened: no matching API exception/new app-code
path; the separate Chromium Mark confirmation passes both themes (1 case,19.4s). The original interruption is retained, not called a pass.
Its precise transport cause is unproved. Normal clean gates/exact full manual CI and
production Home readiness proof remain before final closure. No production source pass,
new service/credential/data write, AA10c or other sitting.

## Final repair acceptance — 4 Nov

The independent controlled Firefox contrast holds the real stats response until native
mouse-down. Removing only the new guard in the local throwaway browser lets the layout
move the checkbox555.00003px (y426.93332→981.93335) before stationary mouse-up: unchecked.
Once layout settles, the original native check succeeds. This establishes the lost-click
mechanism without altering the stats body or weakening the original Home assertion.

Same-branch190906ac (single PR128) passes all ten clean local commands: API2,621/no skips,
shared167/web757. Committed focused Chromium8/Firefox8 pass. Exact full manual
CI41753476409 passes all seven jobs: Chromium70/Firefox69+1/WebKit68+2/jobs6, including
all18 cinema cases, all3 new Home readiness cases and all3 original poster cases.
The three existing browser exclusions remain unchanged. Code-main CI41756486514 and
final documentation CI are checked separately before completion; exact final stamp in PR128.

Actual deployed API/web190906ac and full readiness pass. Craig/Mark × light/dark375px
production browsers hold each real stats read, prove native checkbox/Deal/cinema entry
unavailable, block keyboard navigation while loading, then prove native check and cinema
navigation work. Exactly one stats GET/person/theme, no extra stats call or mutating Deal.
All16 actual programme filters still match1,617 future showings/141 groups; New0/Older0/
Unclassified1,617. Partial coverage/unknowns remain explicit, raw format syntax renders0.
Core/programme counts unchanged; third-party source requests/domain mutations/page errors0.
This is browser proof, not new genuine iPhone/push/camera/speech/two-device acceptance.
Next08:00UTC scheduled source run/future access remains unobserved; source fees£0 and
existing resource/verification usage unpriced. No other sitting or new branch/PR.

The earlier local Chromium login ECONNRESET remains recorded with precise cause unproved;
separate confirmation and the committed focused/full gates pass. The failed main run and
same-runtime passing run remain evidence; neither was silently retried or called repaired.
