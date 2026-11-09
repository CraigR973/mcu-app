# Mark's Needs you and watch-history setup — 8 Nov 2026, 13:47 GMT

## Status and authority

Craig asked to put the outstanding choices into Mark's Needs you section, then prepare Mark's setup. This is the concrete implementation/setup checkpoint. **The cards are not in production and Mark's sync is not enabled.** No application source, schema, permissions or live data changed during preparation. Existing edits and all earlier reports are preserved; no commit, push, merge, deployment, provider request or job trigger occurred.

The definite referents are the three identity choices below. A text clarification asked whether to include a grouped disc-spec review and Mark's own phone observations too; no answer had arrived when this proposal was saved. Those extensions remain optional, not implicitly approved.

This preparation follows the read-only 8 Nov verification and reconciliation reports. Source inspection and fresh read-only database checks around 13:38–13:44 establish the Mark-specific setup figures below. Earlier cinema, value and overall queue counts retain their original observation times; they were not re-fetched for this proposal.

## 1. The three Mark review cards

Each card must explain the evidence, ask for Mark's judgement and offer “Not sure yet”. It must not guess an identity, merge films, move a disc, rewrite price history or mark a phone test passed merely because the card was opened.

| Card | Question and recorded evidence |
|---|---|
| Check Titanic's Blu-ray | “Is this affected disc Titanic (1953) or Titanic (1997)?” The current catalogue film is 1953; the selected disc-page evidence names 1997. Inspect the physical disc/edition. Scope the review to the affected copy, not every Titanic copy. |
| Check Dead Man's Shoes on Wanted | “Is the wanted film Dead Man's Shoes (2004) or Dead Man's Shoes (1940)?” The current wanted row names 1940; the retained shop-history discrepancy was documented as the 2004 release. Mark's answer is a judgement, not permission to transfer all associated records. |
| Check Shetland Series 5 | “Should this Series 5 copy use the existing Shetland series identity?” Explain that separate physical copies must remain separate. An existing Shetland series is already identified as TV 46923. No duplicate-copy deletion. |

Current stable targets, revalidated without provider access:

- Mark profile: `d900b8bc-a46c-4691-9c16-cde3b4d72cd5`, active viewer.
- Titanic movie: `219a59fc-8a0b-4eeb-ba7c-18b0391eb69f`, TMDB 16535. Resolve its exact open doubt/copy again before assignment.
- Dead Man's Shoes movie: `58df19fb-d961-457c-8374-6df550b563cf`, TMDB 416920; active wanted association. Verify the wanted association again before assignment, and keep its retained history in scope for any later correction proposal.
- Shetland Series 5 movie: `d90ea74d-8ad3-4864-9070-043c4e358e59`, currently unmatched. Revalidate the exact owned copy before assignment.

### Recommended implementation contract — awaiting approval

One bounded app change adds assigned review cards to Needs you. It is not a new notification system or a broad role change.

- Keep existing loan/trip jobs derived from their source rows. Add a separate, backwards-compatible review field to the API and shared zod contract. Existing clients must continue reading existing responses.
- Store the three explicit review assignments and Mark's answers durably. Use stable profile and target IDs, typed review kinds, a constrained choice set, revision/conflict handling, UUIDs and UTC timestamps. Repeated assignment must not create duplicates. An administrator creates/reassigns a review; a person can read and answer only their own reviews. Craig can inspect the answers. No arbitrary URL or executable payload supplied by a card.
- A response records Mark's observation. If an existing authorised film-page action resolves the underlying issue, re-check that state and close the review consistently. Otherwise show “Answered — awaiting correction”, accessible to Craig; do not equate an answer with a completed catalogue repair. “Not sure yet” leaves the review open. Retain an audit trail; do not silently erase assignments or answers.
- Use existing film pages for inspection. Mark already has film-page identification/doubt actions under decisions 273/276; the admin queue, global correction/undo controls and his viewer role stay as they are. Do not introduce a second identity-write path or automatic film merge through a review response.
- Home retains its five-item limit, existing trip/loan priority and loading/offline behaviour. Provide a real overflow destination exposing every assigned review; a link solely to Loans is insufficient. Reading Home performs no provider request and sends no notification.
- A new table requires guarded read-only/backup grants, migration reversal checks and safe handling of populated review history. The migration does not silently assign tasks to production. Exact production assignment of these three records follows reviewed release/assignment authority, not this preparation.

Why persistence: Titanic and Shetland can largely be derived from existing queues, but Dead Man's Shoes' documented mismatch and the requested assignment/answer have no current structured state. Hard-coded Home cards would become stale and could not reliably distinguish “Mark answered” from “catalogue corrected”. Rejected shortcuts are fake loan/trip rows and making Mark an administrator. The recommended store records review work only; it does not replace the underlying queues.

This extends decision 336's “a read, not a store” design for these new explicit reviews only. Record an approved amendment and a canonical batch entry with acceptance/model/effort before implementation. No decision is appended merely because this proposal exists.

Main risks are leaking another person's tasks, losing/duplicating an answer, or presenting a resolved/changed record as the old question. Caller checks, revisions, idempotent assignment and target-state revalidation must cover these. A failed release must not corrupt catalogue identities or existing loans/trips.

Acceptance must prove Mark sees the three exact reviews, another viewer sees none of them, Craig can inspect responses, forged cross-profile reads/writes fail, uncertainty stays open, stale targets do not permit silent corrections, overflow exposes every task and normal loan/trip behaviour remains intact. Run the full repository gate and role-aware browser flows before release; exact-SHA CI and production parity/read-back are still required at release. Mark's actual phone experience is a separate observation.

Estimated effort: **2–4 hours agent work for the three-card feature and full checks**, subject to gate failures and review; a few minutes for Mark's first answers. No new service, provider fee or hosting change. This is an estimate, not a completion claim. Existing uncommitted documentation must be preserved/reviewed before any clean-tree implementation workflow; no stash, discard or replacement checkout.

### Optional broader scope — answer still pending

One grouped “Review disc details” card would represent the existing **419** spec-review items, not 419 Home cards. However `/specs` and its queue/read/accept/skip endpoints are currently admin-only. Extending those review-only operations to Mark requires an explicit narrow access decision; bulk backfill, fetch/run/halt and destructive controls must stay admin-only. Accepting a spec candidate queues later fetching; a Home card must not fetch specs. Re-query the count when rendered.

A grouped “Your phone checks” card must enumerate only observations that actually apply to Mark. Do not assign Craig's phone receipt/tap checks to Mark or ask him to repeat Craig's accepted launch/header/Search observations. Personal confirmations require explicit observed/not-observed/blocked answers, and cannot close the shared positive cinema-delivery criterion without real scheduled evidence. The exact checklist must be agreed before populating it.

If both extensions are wanted, estimate **4–6 hours total** for the wider feature, including access tests and durable personal observations. This scope is not selected by silence on the clarification.

## 2. Mark's setup — prepared, not enabled

### Verified starting point

Mark's stable profile remains an active **viewer**, with `letterboxd_username = null`, **0 sync records** and **972 current watch rows**. The already-recorded intended username is `markr973`; no new username decision is needed. No password, Letterboxd Pro purchase or administrator promotion is required for the existing public-RSS integration.

The existing UI is **Settings → Watch history**, `/settings?tab=history`. Saving a username updates only the signed-in person's profile and does not immediately fetch the feed. The endpoint deliberately has no administrator override. Mark should save it while signed in as Mark; an agent must not impersonate him or broaden account administration to bypass that contract.

After the username is saved, the already-deployed 08:00 UTC reminder command considers his never-synced profile due. If saved before the next normal run, the first eligible run is **9 Nov at 08:00 UTC**, followed by the existing roughly weekly cadence. This is expected behaviour, not a booked/completed run. There is no new automation to create.

That natural sync requests at most 50 parsed diary entries, deduplicates by viewing ID, writes accepted new watch rows and may create bare catalogue films where required. Clearing the username prevents later due-sync selection; it does not undo watches/films already created. A failed feed read must remain visible in the sync record.

**Do not press Sync now as a setup test.** Besides feed import, the current route calls `fill_bare_films`, which may request TMDB details for up to 20 bare catalogue films beyond Mark's own diary scope. Saving the username and awaiting the natural cron is the narrower setup path. No existing code is changed for this plan.

### Proposed next read checkpoint

Before enabling, recommend one explicitly authorised, read-only preflight of `https://letterboxd.com/markr973/rss/`: one GET, no retries, no followed redirects, 20-second timeout, 1 MiB response cap and at most 50 parsed entries. Stop on redirect, refusal, malformed data or size overflow; no alternate provider, page crawl or TMDB lookup. Parse and compare locally against current stored viewing IDs; keep real diary contents private/gitignored and record only sanitised counts in the report. This request has **not** been made.

Estimated cost: 2–5 minutes agent work, one public feed request, no charge and no database write. A current successful feed read is not proof of a future scheduled import.

After that result is reviewed, the separate enable checkpoint is Mark saving `markr973` once in his own Settings. Explain that this enables the future feed reads and database writes above. Read back username/status and then the first natural cron outcome; do not manufacture it with a manual job. Only a completed successful record plus its actual counters establishes sync completion.

### Historical recovery is a separate scope

Saved Mark plan: `.letterboxd-export/mark-backfill.json`, SHA-256 `720781da63843cbeaa743944c07de0a2372fec0f49fda760ca3e542702cc8fa0`. Do not copy private diary contents into tracked documents.

| Saved-plan comparison | Current read-only result |
|---|---|
| Total entries | 177 |
| Doubtful entries, held | 19 |
| Non-doubtful entries | 158, all viewing IDs currently absent |
| Original owned/existing targets | 57 entries; all target film rows still live |
| Previously “new” entries | 101 entries over 95 distinct TMDB film IDs |
| Previously “new” now in live catalogue | 23 entries; re-use/revalidate rather than blindly create |
| Previously “new” still absent | 78 entries over 74 distinct TMDB film IDs; none of the relevant target IDs found only in Trash |
| Still-old proposed watch corrections | 6 belong to Mark; the seventh belongs to Craig and is excluded |

The 158 absent viewing IDs are **not an approved import count**. A manual/legacy watch may already represent the same viewing, live film IDs alone do not prove correct physical/diary identity, and the natural recent feed can overlap this old plan. Revalidate dates, targets, equivalences/duplicates and all six correction source/target histories immediately before any proposal/apply; derive a new private dry-run manifest and exact counts/hash. Hold the 19 doubtful entries. Do not fetch 74 film records or create them under this preparation.

Exclude Craig's 480 missing saved viewing IDs and his one watch correction. Exclude all unrelated identification, collection pricing, cinema refresh/delivery and AA10c work. Enabling Mark's recent feed cannot recover the entire historical gap because RSS carries only its newest 50 entries.

## 3. Approval boundaries and next task

The request to prepare is satisfied by this proposal; the requested live cards remain unimplemented. Craig's “Before anything consequential” instruction requires a decision before schema/access changes. Ask approval for the durable three-review contract above, and resolve whether the optional spec/phone extensions are included. No permission is needed to preserve this report or perform the completed read-only checks.

The history setup is ready for the one-feed-read checkpoint; username enabling and historical writes remain separate, concrete owner checkpoints. Do not bundle hundreds of watch imports into approval for the three review cards or one feed request. No commits, pushes, merges or deployment are authorised by this preparation.

Recommended next bounded task: approve the review-card contract, record its canonical acceptance/decision, implement only the selected app scope with the existing checkout preserved, and stop at the authorised release boundary. Separately authorise the single-feed preflight when ready to enable Mark. AC6 natural positive delivery and AA10c's 25 Nov recorded-sales gate remain open and untouched.

Preparation checks: existing three reports' preserved hashes, Markdown structure/local link checks and `git diff --check`; no application tests run because no application code changed.
