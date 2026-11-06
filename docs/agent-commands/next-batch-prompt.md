# next-batch-prompt

Emit a copy-ready prompt for the next unshipped batch. Mechanical, no invention.

1. Read `STATUS.md` for current state and gotchas.
2. Find the next unshipped batch in `docs/phase-batches.md`, the batch source of record:
   the first row not struck through as shipped, in its group's sitting order.
3. Pull its title, goal and acceptance criteria **verbatim**.
4. Emit a self-contained prompt containing: repo path, phase id and title, the acceptance
   criteria verbatim, the required first reads (`STATUS.md`, `AGENTS.md`, `DECISIONS.md`),
   the gate commands from `batch-verify.md`, any relevant STATUS gotcha, and the close-out
   rule: close out automatically once the gate is green (`AGENTS.md`'s protocol,
   `DECISIONS.md` #24), and the merge to `main` deploys; hosting or credential changes and
   destructive data or history operations still wait for Craig.
5. Return only the prompt plus a one-line note naming the selected phase.

Never invent a phase or an acceptance criterion. The user chooses the model.
