# Movie-night film-page click investigation — 3 Nov

**Repair deployed in PR #127, code 3d71b71.** Controlled WebKit poster-height failure
141→94px before repair; all three browsers pass after reserving the parent geometry.
All ten clean local checks and exact seven-job PR CI 41665030709 pass; exact production
API/web SHA/db ok/five integrations verified. Merged-code main CI 41668022890 and final
documentation-head CI must finish before returning to AB6; evidence goes in PR #127.
Standing #334 approval covers continuation without another known-stage permission ask.


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

## Verification and release

Clean 3d71b71: API 2,549/no skips/shared 159/web 737, all ten normal commands green.
Full local C63/F62+one documented skip/jobs6, identical start/end SHA/no retries. Exact
PR CI 41665030709: all seven jobs, API 2,549/no skips/C63/F62+1/W61+2/jobs6, migration
reversal/real image boot. Only the three documented browser skips. Original vote/promotion
assertions and new height/layout/pointer/navigation regression pass on all three browsers.

Normal fast-forward main push marks PR #127 merged at the tested 3d71b71. Production
API/web serve exactly that SHA; db ok and push/ai/ebay/tmdb/brave configured. No hosting,
credential, API/schema, catalogue/diary or source/model action. No new real-iPhone evidence
is claimed. Architecture pipeline/routes/data shape unchanged; only film-detail poster
layout reservation changes. Preserved AB6 branch/PR #125 remains undeployed.

Failure history retained: original WebKit dropped-click CI; controlled pre-fix 47px
height failure; two probe coordinate setups caught intended active animation; offsetTop
needed HTMLButtonElement type narrowing. None was waived or hidden by a later pass;
only the causal parent-geometry repair clears the original failure. Merged-code and
final-doc exact-head CI/deployment evidence is recorded in PR #127 before AB6 resumes.
