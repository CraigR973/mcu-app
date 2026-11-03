# Movie-night film-page click investigation — 3 Nov

Owner completion approval #334 covers the separate cause-first prerequisite fix and the
known remaining cinema work. AB6 branch/draft PR #125 is preserved at cf2cdf5; this fix
starts from main 6d0f676, whose exact seven-job CI 41545982931 is green.

## Preserved failure and hypothesis

PR CI 41643751573, WebKit at 375×812: clicking Add to movie night leaves the film page,
with no candidate suggestion POST and no voted title in Suggested. The original test and
runtime component match main and prior green commits. No failed test is waived as flaky.

The saved trace records the button click at x116.44/y482. Movie poster 404 ends at about
141413ms; the pointer click spans 141411–141418ms. Frames immediately before show a
2:3 poster; immediately after show a shorter broken image, with the add button about
48px higher. A later frame restores the 2:3 local fallback. This supports a transient
broken-image layout shift moving the target between press and release, not a mutation
or stored-vote failure. It still needs controlled regression proof before repair.

The new browser case holds the poster response, presses the movie-night button, returns
404 while holding the local fallback, measures poster/action geometry during that
interval, and releases at the original pointer position. It requires stable geometry
and navigation to the same selected night. All browsers run it; no new skip/delay/timeout
or changed assertion/random seed in the original case. Synthetic image routes make the
transition deterministic; no real provider request is required for this regression.

## Verification pending

Regression typecheck/local probe and exact PR CI are recorded as they complete. No layout
repair yet. WebKit cannot run on this Mac; Chromium/Firefox alone are not WebKit proof.
The intended minimal repair, only if the regression confirms the cause, is to reserve the
film-page poster container's 2:3 geometry independently of image loading/failure. Night
selection, click handler, votes, Suggested rules and navigation stay unchanged.

No API/schema/auth/configuration/credential/data change or cinema request. After causal
repair/full normal gates, normal separate code-only close-out and exact production proof,
then normal preserved AB6 integration. User's standing approval covers the known remaining
source build/reads/evidence-based mappings/prepared config/import/enable and AB7; missing
facts are never treated as accepted evidence. No AA10c or other sitting.

Initial local probe: test setup compared unpressed and pressed button coordinates and
failed on its intentional 1px active translation (412→413). This is not causal poster
proof. Baseline measurement is corrected to occur after pointer-down/before image failure;
the geometry invariant, tolerance and original case are unchanged. The initial trace and
log remain preserved; no runtime repair has been made. Standing #334 covers this corrected
controlled reproduction; no green rerun of the uncorrected setup is used as evidence.

The second probe caught the same intentional press animation still mid-transition
(412.457→413), not a poster shift. Final regression measures exact untransformed layout
position (`offsetTop`) rather than a transform-dependent viewport coordinate; the action
must remain at exactly the same layout position, poster-height tolerance stays unchanged,
and the original physical press/release/navigation check remains. This is a stricter
layout invariant without an artificial animation delay or timeout. Both initial probe
traces are retained and neither is represented as causal evidence or a fixed app bug.

## Cause proved and minimal repair applied

Before-runtime-change PR CI 41662029373 (41708be) deterministically fails the unchanged
WebKit poster-height invariant: 141px before failure, 94px while the fallback is held
(47px collapse). The original intermittent case passing in that run does not waive its
saved failure; the controlled case establishes the missing geometric condition.
The independent press-animation setup issues in Chromium/Firefox are not causal evidence.
A TypeScript check also required explicit HTMLButtonElement narrowing for offsetTop;
no ignore/cast/loosened type was added. The final regression uses exact untransformed
layout equality, unchanged poster-height tolerance and physical click/navigation.

The film page now reserves a 2:3 poster box independently of image decode/error state;
its image fills that box. No click, night selection, vote/promotion/navigation, data,
auth/API contract or global poster behavior changes. Design choice: reserve the detail
page's poster geometry only, rather than change every poster component or wait for images.
The parent border contributes at most a one-pixel artwork-size difference at the phone
width; no uncertainty is hidden and the action remains in stable flow. Full local/CI
verification pending; WebKit after-fix proof remains mandatory.
