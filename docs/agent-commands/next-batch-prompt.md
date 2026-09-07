# next-batch-prompt

Emit a copy-ready prompt for the next unshipped batch. Mechanical, no invention.

1. Read `STATUS.md` for current state and gotchas.
2. Find the first phase in the roadmap doc without a ` ✅ YYYY-MM-DD` suffix.
3. Pull its title, goal and acceptance criteria **verbatim**.
4. Emit a self-contained prompt containing: repo path, phase id and title, the acceptance
   criteria verbatim, the required first reads (`STATUS.md`, `AGENTS.md`, `DECISIONS.md`),
   the gate commands from `batch-verify.md`, any relevant STATUS gotcha, and the
   instruction not to run `/phase-closeout` until explicitly asked.
5. Return only the prompt plus a one-line note naming the selected phase.

Never invent a phase or an acceptance criterion. The user chooses the model.
