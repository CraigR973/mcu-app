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
