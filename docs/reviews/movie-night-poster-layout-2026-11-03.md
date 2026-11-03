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
