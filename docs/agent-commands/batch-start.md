# batch-start

Start an implementation batch. Arguments: the phase or batch id(s).

1. Read, in order: `STATUS.md`, `AGENTS.md`, `DECISIONS.md`, and the phase's own entry in
   the roadmap doc. Grep for the `**Phase X.Y:` heading — **never read the roadmap whole.**
2. Restate the phase id, title, goal and acceptance criteria **verbatim** before writing
   any code. If grep finds no matching phase, the phase does not exist — stop and ask.
3. **Treat the phase row as a proposal to verify, not an instruction to execute.** It was
   authored in April 2026 and its `file:line` references, measurements and "reuse X"
   pointers have decayed. A green test suite cannot tell you the spec was right, only
   that you built what it said. If a stated fact is now wrong, say so and stop.
4. Confirm the working tree is clean and you are on `main`. Fetch, then branch:
   `feat/<id>-<slug>` (or `fix/`/`chore/` as appropriate).
5. Build **only** this batch's phases. Do not start later ones.
6. Ship tests with the change.
7. Run the gate (`batch-verify.md`). Report every failure and fix, including ones fixed
   on the first attempt.
8. **Close out.** `phase-closeout.md` now runs **automatically** once the gate is green
   (`DECISIONS.md` #24, superseding #13) — and because pushing `main` deploys, that ships to
   production. **Stop and report instead** when the gate is red, when `main` was already red,
   or when the batch touched **hosting/credentials** or performed a **destructive data or
   history operation**.

Guardrails: never `cd` (autoenv will prompt). Don't touch hosting configuration unless
the batch requires it. When integrating an external data source, work from real sample
payloads, not guessed shapes.
