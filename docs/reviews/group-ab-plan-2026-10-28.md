# Approved grouping for the 28 Oct snags

**Seven batches across five sittings; sittings 1–3 complete.** AB1 (`ad2c992`) and AB2 (`c187ed7`)
shipped after their owner checkpoints. Final CI's real movie-night race was stopped, then
repaired with Craig's separate approval in PR #120 (`bf0eb36`), all full gates and exact
production proof. Sitting 2 shipped AB3 in PR #121 (`5cfa467`) after all four pre-build owner picks (#306),
full local/PR/main gates and exact production proof. Genuine later add/real-phone receipt remains
owner acceptance; approved contract: `docs/reviews/ab3-owner-checkpoint-2026-10-29.md`.
Sitting 3 authorised 29 Oct (#307): installed blur reproduced in isolated AB4-1;
AB4-2 yielded 32px (30 Oct), and the exact header/Search repair is approved (#308) and implemented.
Native actual-app sample preview is accepted in all four states with normal keyboard;
approved original-app re-add now cold-launches/resumes Home without problems (#309/#310).
PR #122 code is deployed at df6824a with final seven-job CI and exact production proof;
original production iPhone Archive/Search/both themes/keyboard acceptance now confirmed.
Sitting 3 is complete; no AB4 owner check remains.
Sittings 4–5 and AA10c remain excluded. The verification reports retain
the failures and the unrelated local shop-alert timeout's unconfirmed cause.
The first sitting fixes misleading Home information. Notifications and iPhone problems
have their own sittings. Cinema sources are researched before their build is committed.

The cost is five sittings with owner checkpoints, plus full verification and a separate
PR/deployment for each implementation batch. Cinema fees and maintenance are unknown until
the source report. The later cinema build may need regrouping if nine-venue coverage is
more complex than current evidence can establish. No time estimate is yet evidence-backed.

## The grouped run

| Sitting | Batches | Result and owner stop |
|---|---|---|
| 1 | AB1 attention → AB2 collection | Truthful attention; clearer collection with owned-watched count and visible breakdown. Pick the layout/API extension before collection build. |
| 2 | ~~AB3~~ Mark's additions (`5cfa467`) | Complete after all four picks; genuine later add/real-phone receipt remains owner acceptance. |
| 3 | ~~AB4~~ iPhone (`df6824a`) | Complete 31 Oct: measured/approved 32px repair, production-phone appearance/keyboard accepted; approved re-add fixes Home launch/resume. |
| 4 | AB5 cinema sources | Nine-venue source, coverage and cost report. Pick sources and concept; stop before implementation. |
| 5 | AB6 programmes → AB7 discovery | Approved programme pipeline, then a screen for choosing a film/venue/showtime. Conditional on the research and build-contract approval. |

Each sitting needs its own go. Each code batch retains its own branch, full gate, CI,
production deployment and verification. The source-discovery report has document/source
checks and no app deployment. Owner/device observations remain explicit if unavailable.

## Why these boundaries

Home's attention, counts and charts share the same screen and tests; the confirmed attention
fix can ship before collection design picks. Notifications add a new event and preference.
iPhone diagnosis depends on the affected device rather than more inferred CSS fixes.
Cinema discovery establishes whether all nine programmes can be obtained reliably; its
pipeline and screen then have separate acceptance criteria and PRs.

Rejected: one large implementation batch. It would couple confirmed fixes to unknown cinema
sources and make review/reversion harder. Also rejected: promising all nine cinemas before
source research, or labelling an opaque CSS token as a verified iPhone repair.

## Product recommendations to review at the checkpoints

- Collection: short definitions, watched owned titles against owned titles, and a visible
  breakdown preview with full charts on tap. Preserve whole-diary history and the existing
  identified-title meaning. The additive stats field is approved alongside the mock-up.
- Notifications: first owned copy of a new title triggers the event; extra editions do not.
  Mark is excluded from recipients. New category defaults on and follows quiet hours,
  digest and device preferences. Stable identity, exact migration and wording need review.
- iPhone: distinguish a fresh launch from resuming the previous page, and the app header
  from the iOS clock area. Preserve notification/deep links and ordinary navigation.
- Cinemas: one film with its venues/showtimes/booking links, older releases easy to find,
  including favourites already watched. Keep unknown, failed and stale listings visible
  as such; do not fabricate a film match or claim an unsupported venue has nothing showing.

## Execution settings

These retain the repository's existing named mapping, rather than changing model lineups.

| Sitting | Claude Code | Codex |
|---|---|---|
| 1 — Home (AB1 → AB2) | Opus 5 · `high` | GPT-5.6 Sol · High |
| 2 — Mark's additions (AB3) | Opus 5 · `high` | GPT-5.6 Sol · High |
| 3 — iPhone (AB4) | Opus 5 · `high` | GPT-5.6 Sol · High |
| 4 — Cinema research (AB5) | Opus 5 · `high` | GPT-5.6 Sol · High |
| 5 | Opus 5 · `xhigh` | GPT-5.6 Sol · Extra High |

Individually, AB7 needs Sonnet 5 `high` / GPT-5.6 Terra High once its source/data contract
is settled; its sitting takes AB6's stricter setting. Resolve an unavailable model before
starting. No agent delegation is part of this proposal.

## Execution boundaries

Craig approved the grouping and then separately authorised sitting 1 on 28 Oct. AB1 shipped;
AB2 shipped `c187ed7` after both owner picks. Sitting 1 completed after the approved race
repair PR #120 (`bf0eb36`). Sitting 2 shipped AB3 (`5cfa467`) on 29 Oct after all four pre-build owner
picks (#306), full gates and exact production proof; genuine add/real-phone receipt remains owner acceptance. Sitting 3 authorised 29 Oct (#307) and completed 31 Oct. AB4 first stopped at the device
checkpoint: standalone AB4-1 blurred in all positions; AB4-2 measured 32px and the exact
header/Search repair was approved (#308), implemented and verified
(`ab4-repair-proposal-2026-10-30.md`). Native sample acceptance and the approved original-app
re-add launch/resume comparison now pass (#309/#310); code deployed PR #122 (df6824a),
full final CI/readiness pass; production-phone after is accepted and sitting 3 complete. See
`docs/reviews/ab4-device-checkpoint-2026-10-29.md`. Sittings 4–5 remain unauthorised. Start only a
separately authorised named sitting; stop at the checkpoints above. Approval to run a
code batch includes normal automatic close-out/deployment after its gate and acceptance
checks, under this repo's procedure. Hosting, credentials, destructive data writes and
live-provider acceptance still have their explicit boundaries.

The approved planning commits must first be integrated through normal review/CI so the
implementation starts from clean `main`. Existing AA10b and phone checks remain open;
AA10c remains the separate sitting from 25 Nov, not part of this group.

Full acceptance criteria and per-batch settings are canonical in the Group AB section of
`docs/phase-batches.md`; the evidence is in `docs/owner-snags-2026-10-28.md`.

## Copy-ready sitting prompts

Sitting 1 — Opus 5 `high` / GPT-5.6 Sol High.

```text
Run Group AB sitting 1 (AB1 → AB2) using docs/agent-commands/group-start.md. Preserve and integrate the approved planning commits through normal review/CI before implementation from clean main. Stop at the owner checkpoints in docs/phase-batches.md, including collection layout and exact stats-contract approval before AB2 implementation. Do not start sitting 2 or AA10c.
```

Sitting 2 — Opus 5 `high` / GPT-5.6 Sol High.

```text
Run Group AB sitting 2 (AB3) using docs/agent-commands/group-start.md. Stop at the owner checkpoints in docs/phase-batches.md, including the exact notification trigger, stable Mark identity, preference/migration and wording before implementation. Do not start sitting 3 or AA10c.
```

Sitting 3 — Opus 5 `high` / GPT-5.6 Sol High.

```text
Run Group AB sitting 3 (AB4) using docs/agent-commands/group-start.md. Stop at the owner checkpoints in docs/phase-batches.md. Obtain affected-iPhone evidence and establish the cause before proposing a repair; desktop token tests cannot close phone acceptance. Do not start sitting 4 or AA10c.
```

Sitting 4 — Opus 5 `high` / GPT-5.6 Sol High.

```text
Run Group AB sitting 4 (AB5, cinema-source feasibility report only) using docs/agent-commands/group-start.md. Stop at the owner checkpoints in docs/phase-batches.md, including exact approval before live integration/sample requests. Deliver the nine-venue source/coverage/cost report and concept, then stop for my picks. Do not build ingestion, start sitting 5 or start AA10c.
```

Sitting 5 — Opus 5 `xhigh` / GPT-5.6 Sol Extra High.

```text
Run Group AB sitting 5 (AB6 → AB7) using docs/agent-commands/group-start.md only after verifying AB5's source/coverage/cost/concept picks and the concrete build contract are approved. Stop at unresolved owner checkpoints in docs/phase-batches.md; re-plan before implementation if source feasibility changed the scope. One branch/PR per batch. Do not start AA10c or any other sitting.
```
