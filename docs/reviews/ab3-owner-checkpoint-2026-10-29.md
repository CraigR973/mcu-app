# AB3 — Mark's addition notifications: owner checkpoint

29 Oct. **Proposal only; implementation is blocked on the four picks below.**
Craig authorised Group AB sitting 2 using `group-start.md`, with its pre-build stops intact.
Sitting 3, AA10c, hosting/credentials and live test additions/pushes remain excluded.

## Four decisions

### 1. Exact event — recommended: first currently owned copy

Notify when an authenticated, successful **Add to collection by Mark** changes a catalogue
title from zero currently owned copies to one. Use the canonical `owned_copy()` rule:
downloads count; copies listed for sale still count; sold, donated, binned or soft-deleted
copies do not. Evaluate the before state while serialising adds for that title.

The proposed scope includes film and TV-series titles, including manual/unmatched titles,
because the existing add flow supports all three. This inclusion needs Craig's explicit
pick; it is not inferred from the heading's word “film”. Title identity is the existing
catalogue UUID, never a string comparison or a new attempt to match different catalogue
records. Existing duplicate/lookalike checks remain intact.

An extra copy, edition or format does not notify. A **new add after all previous copies
ceased to be owned does notify again**; restoring an old copy does not. These are proposed
semantics, not an already approved interpretation of “new”. Concurrent Craig/Mark adds
notify only if Mark's transaction makes the zero-to-one transition. Craig's own add sends
no addition notification.

Each other active, non-deleted profile gets one durable event; Mark gets none. One event
can reach that recipient's several enabled devices. Disabled categories/no devices retain
the existing suppressed-row explanation. Quiet hours and digest can delay/combine delivery.
Cancelled, failed, duplicate-refused adds, edits, imports, restores, identity corrections
and historic additions generate no new event. No historical scan/backfill runs.

Rejected: every added edition, which makes upgrades noisy; all senders, which broadens
Craig's request. Cost: missed events if separate catalogue records actually represent the
same title remain an existing identity-quality limitation, not a reason to invent a match.

### 2. Stable Mark identity — recommended: verified profile UUID

The live, read-only profile query on 29 Oct returned exactly two active, non-deleted rows:

| Person | Stable profile UUID |
|---|---|
| Craig | `1a090c0b-9fed-45e4-84a8-03dd7918c54d` |
| Mark | `d900b8bc-a46c-4691-9c16-cde3b4d72cd5` |

Bind this feature to Mark's exact UUID as a named product constant; compare authenticated
actor IDs. A rename or role change does not retarget the feature. A missing, inactive or
deleted Mark profile produces no event; recreating his account requires a reviewed binding
change. Tests use an explicit actor binding and must prove that another viewer, including
one named Mark, is not treated as this profile.

Rejected: runtime display-name comparison or “every viewer is Mark”, both of which can
attribute someone else's additions to him. A new environment variable would add an
unnecessary hosting checkpoint. Cost: one code change if Mark's account is recreated;
no account, PIN, role or hosting change now.

### 3. Preference, migration and retry contract — recommended: additive, default on

One new category and one per-recipient switch:

| Layer | Exact proposed name |
|---|---|
| Outbox category | `collection_additions` |
| Preference column | `notification_preferences.collection_additions_enabled` |
| Preference JSON | `collectionAdditionsEnabled` |

The preference column is non-null Boolean, Python/server default true, including existing
preference rows. GET returns the Boolean; the existing partial update accepts an optional
Boolean, with omission preserving the stored value. Extend the category vocabulary,
preference DTOs, mapper, shared zod schema, client types and Settings switch together.
Old/cached preference responses may omit the new field: render the switch unavailable,
never invent off/on; refresh from the API. Existing clients' partial updates preserve it.
Existing quiet-hours, digest, device, suppression and delivery rules remain in force.

**Retry finding:** the current collection POST has no durable client request ID. An outbox
key by itself cannot identify a replay after collection state changes. The proposal therefore
includes optional UUID `clientRequestId` on the existing collection-create body. The updated
client creates one per deliberate submission and retains it through offline queueing,
lost-response/manual retries and automatic replay. A changed, newly confirmed submission
is a new attempt; a network retry keeps the same ID and payload. All collection-create
call sites must be inventoried before build; no new endpoint or response field is proposed.

Migration **070**, from current head **069**, would add the preference column and a new
`collection_add_requests` receipt table: UUID primary key, `user_id` (profile FK),
`client_request_id` (UUID), `request_hash` (64-character SHA-256 of the normalised create
body excluding its request ID), nullable `item_id` (collection FK, SET NULL on hard delete),
`response_payload` (JSONB holding the successful create response), and `created_at_utc`
(naive UTC with `UTC_NOW`). Unique `(user_id, client_request_id)`; no historic receipts.
Keep receipts without scheduled expiry so an old queued request cannot become new again.
Only successful creates are receipted; validation/duplicate refusals create nothing.

Serialise keyed requests before side effects, then serialise the resolved title's add
decision. Reusing the same user's key with the same payload returns the original successful
201 response, without adding another copy/event; a different payload returns 409 with a
distinct `CLIENT_REQUEST_ID_REUSED` code, not a duplicate-confirmation prompt. Other accounts
cannot access that receipt. Older clients may omit the ID; title serialisation still avoids
duplicate notification events for concurrent/repeated adds while the title remains owned,
but exact request replay after an intervening removal requires the new client ID.

Queue per-recipient outbox rows in the **same transaction** as the addition, audit and
receipt. Dedupe by qualifying new copy UUID plus recipient UUID, so reacquisition can be a
new event while retrying the same add cannot. Commit before transport; delivery errors
cannot turn a saved addition into a failed add or undo it. Use the existing immediate
delivery path and queued-delivery jobs, retaining their retry behaviour and honest status.

Guarded SELECT grants go to `mcu_readonly` and `mcu_backup` for the preference column and
the new non-credential receipt table. Prove credential columns remain withheld using
catalogue privilege checks, never selecting their contents. Migration reversal is tested
only on disposable Postgres; applying a rollback to production would need fresh approval
because it would discard stored preferences/receipts. No existing collection/history rewrite.

Rejected: send inline before committing, no preference, or dedupe only in browser memory.
Cost: one additive migration, a persistent receipt per keyed successful add, changes across
API/shared/client, and full Postgres/concurrency/browser gates. No new paid service or
credential. This adds retry safety to the same collection-add contract; it is included
in the approval request rather than silently added during implementation.

### 4. Exact wording — recommended

| Surface | Text |
|---|---|
| Push title | Mark added a title |
| Push body, year known | Heat (1995) is now in the collection. |
| Push body, year unknown | Heat is now in the collection. |
| Settings switch | Mark's additions |
| Settings explanation | When Mark adds the first owned copy of a film or series. Extra copies and editions stay quiet. |

Replace Heat/year with the saved catalogue title/year; tap opens `/movies/{movieId}` using
the saved catalogue UUID. The Settings explanation also applies to reacquisition through a
new add after zero owned copies. Digest delivery retains the existing digest wording.
Mark is always excluded as a recipient, even with the preference on. Renaming the profile
does not change the approved literal wording until Craig chooses otherwise.

Rejected: “new film”, which implies first-ever acquisition and excludes series.
Cost: the push can reveal the film/series title on a recipient's lock screen, under their
existing device settings. Craig can disable this category independently.

## Proposed mechanism

```text
Mark submits Add (stable request ID)
                 ↓
Serialise request → replay saved response if already committed
                 ↓
Serialise title → zero owned copies before this add?
                 ↓ yes
Add + audit + receipt + other profiles' outbox rows
                 ↓ one commit
Existing delivery → preferences / quiet hours / digest / devices
                 ↓
Tap opens the saved title
```

All successful adds save normally when the notification condition is false; failed adds
roll back the whole transaction. No transport call occurs inside that transaction.

## Build acceptance criteria (ledger, verbatim)

- **Checkpoint before build:** approve the exact trigger, stable identification of Mark,
  preference/contract change and wording. Recommended: first currently owned copy of a
  title; an extra edition alone does not notify. Do not silently generalise to all senders,
  compare mutable display names, or assume every viewer is Mark.
- Each other active profile gets one event; Mark gets none. Link to the title. Cancelled,
  failed and duplicate-refused additions send nothing. Edits, imports, restores, identity
  corrections and historic additions do not trigger a retrospective flood.
- Queue atomically with the collection addition in the existing outbox. Concurrent adds,
  offline replay and lost-response retries cannot duplicate the event. Delivery failure
  cannot roll back a committed add. Prove these cases against real Postgres and fake push.
- Proposed category `collection_additions`; DB `collection_additions_enabled`; JSON
  `collectionAdditionsEnabled`; default on. Preserve existing quiet-hours/digest/device/
  suppression rules. Approve the exact additive migration/DTO/shared-schema plan first;
  guarded read/backup grants must preserve withheld credential columns.
- Full gate/E2E/exact-head CI and production SHA/readiness. A genuine later addition and
  real-phone receipt remain owner acceptance; no production test film or fabricated push.

## Verification after approval

- Real Postgres: actor identity/rename/role/active-state, zero-to-one/reacquisition/extra-copy
  cases, every excluded mutation, per-recipient isolation, atomic rollback and suppressed rows.
- Deterministic two-connection tests: same/different request IDs, both actors adding the
  same title, first transaction commit/rollback, replay after intervening removal, same key
  with changed payload, and existing preference-row creation races.
- Fake push and browser: decrypted title/body/URL, offline/lost-response replay, failed
  transport after commit, quiet hours/digest/category/device rules and preference save/load
  at phone width in both themes, including missing-field compatibility.
- Full `batch-verify.md`, exact-head seven-job PR/main CI and production API/web SHA/full
  readiness under normal close-out. No route/access assertion or gate weakened.
- Owner only after shipment: a genuine later qualifying addition by Mark and a push received
  on Craig's real phone. This remains open until observed; no synthetic production event.

## Preflight evidence and handoff

Clean local main and origin/main were `588e552b2a93f140fc603bf51ae80c348cc0f835` after fetch.
Latest main CI **40858327603** succeeded; API health and web version both served that exact
SHA; readiness reported `db: ok`, push and all other reported integrations configured.
These checks verify the baseline, not AB3 or real-phone receipt.
The profile query selected only ID, display name, role, active and deleted state in a
read-only transaction. No credential values, live writes or provider/push calls were made.

AB3 is yellow (ledger: Opus 5 `high` / GPT-5.6 Sol High). No agents delegated.
No product code, tests, migration or external contract has been changed. The working branch
is `feat/ab3-mark-additions`, with checkpoint/handoff documents only. No PR/deployment or
AB3 full gate has run. Resume only after Craig explicitly resolves decisions 1–4; record
his choices and revise this proposal before implementation. Stop again if that review
changes the approved schema/API scope. Sitting 3 and AA10c must not start.
