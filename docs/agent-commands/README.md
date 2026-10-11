# Agent commands — canonical procedures

Tool-agnostic procedures, written as plain markdown so **any** agent (Claude Code,
Codex, …) executes identical steps. Each tool may add a thin wrapper that just points
here (a Claude slash-command in `.claude/commands/`), but the real procedure lives in
this folder — **never duplicate the steps into a wrapper.**

| Command | Does |
|---|---|
| `next-batch-prompt.md` | Emit a copy-ready prompt for the next unshipped batch |
| `batch-start.md` | Start an implementation batch on a fresh branch |
| `batch-verify.md` | Run the gate and report pass/fail per acceptance criterion |
| `phase-closeout.md` | Close out a reviewed batch — **never automatic on this project** |
| `handoff.md` | End a session in a state the next agent can pick up |
| `review-wave.md` | Run a full review (a panel of expert passes) or a monthly delta review |
