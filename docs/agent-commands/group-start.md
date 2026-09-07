# group-start

Run a defined group of batches end to end — each through the full
`batch-start` → `batch-verify` → `phase-closeout` cycle, sequentially, without returning
to the user between them.

**Input:** a group id (`A`, `Group A`), or an explicit batch list (`5,6`) to resume an
interrupted group. Groups are defined in `docs/phase-batches.md` under **Batch groups**.

## What this overrides, and what it does not

Close-out is **explicit on this project** (`DECISIONS.md` #13) — normally the agent stops
after `batch-start` and waits. **This command is the user's explicit, standing
authorisation to run close-out for every batch in the named group**, given once at group
level instead of once per batch. That is its entire purpose.

It authorises nothing else. Every guardrail in `batch-start.md`, `batch-verify.md` and
`phase-closeout.md` applies in full, and the stop conditions below are absolute.

## Procedure

1. Read `STATUS.md`, `AGENTS.md`, `DECISIONS.md`, `docs/phase-batches.md` and the group's
   definition under **Batch groups**.
2. Restate the group: its batches in order, each tier, and any **checkpoint** in the
   manifest. If a checkpoint is unresolved, stop there and say so.
3. For each batch in order: `batch-start` → implement → `batch-verify` → `phase-closeout`.
4. Continue to the next batch **only after** close-out returned to a clean local `main`,
   the ledger row is struck, and the push succeeded.
5. **Never put two group batches on one branch or in one commit. Never stack branches.
   Never run two in parallel. Never skip an unchecked batch.**
6. Report at the end: what landed, what did not, and the exact resume point.

## Stop conditions — absolute

Stop the group, report what has landed, and wait for the user:

- **CI is not green.** Never merge, never proceed to the next batch.
- **A spec fact is wrong** in a way that changes what the batch should build.
- **The working tree holds anything outside this batch's scope.**
- **A pre-existing red on `main`** — fix it on its own `fix/` branch first, never fold it in.
- **Three attempts exhausted** on the same failing check.
- **An unanswered decision gate.**
- **Anything requiring a credential, hosting-console, or external-API-approval change.**

## Hard stop: data and external systems

- A batch that **deletes or overwrites existing collection data** is never run unattended.
  Stop before executing and ask, naming the row count.
- A batch whose acceptance requires **live third-party requests** (scraper runs against
  real retailers, live eBay or mailbox calls) stops before those runs. The owner performs
  them. Fixture-backed tests may run unattended; live ones may not.
