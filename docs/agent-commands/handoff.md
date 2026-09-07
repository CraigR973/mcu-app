# handoff

End the session in a state the next agent can pick up.

1. `STATUS.md` — overwrite the "Now" block (current state, next step, gotchas) and
   prepend a dated line to the "Log".
2. `DECISIONS.md` — append any durable decision (what + why). Don't re-litigate a settled
   one; supersede it with a new entry.
3. Commit.

Don't leave durable state only in a tool's private memory — Claude's memory is a cache
and Codex cannot read it. Don't end a session with uncommitted, unexplained changes.
