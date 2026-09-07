# phase-closeout

Close out a reviewed batch. **This is never automatic on this project** — see
`DECISIONS.md` #13. Run it only when the user explicitly asks.

1. Confirm the user asked for close-out of this specific batch.
2. Confirm the gate is green (`batch-verify.md`) and the working tree holds nothing
   beyond this batch. A red or unrun gate stops the close-out.
3. Stage the batch's files **explicitly** — never `git add .` or `git add -A`.
4. Commit with a Conventional Commit message.
5. Push the branch. Poll CI with `gh run list --limit 1` / `gh run view <id> --log-failed`
   until it completes. Do not foreground-poll in a tight loop.
6. Fix any CI failure, then re-push and re-poll. Never reach green by weakening the gate.
7. Merge to `main` (`git checkout main && git merge --ff-only <branch>`).
8. Tick the phase line in the roadmap doc — grep for the heading, append ` ✅ YYYY-MM-DD`
   to the matching `**Phase X.Y: ...**` line. If it already ends with a ✅ date, skip;
   don't double-tick. **Do not read the roadmap doc whole.**
9. Update `STATUS.md` — overwrite the "Now" block, prepend a dated line to the "Log".
   Append to `DECISIONS.md` only if a durable decision was made.
10. Commit the docs, push `main`.
11. Report what shipped, and every failure encountered on the way.

Once the re-scaffold lands a deploy pipeline, add: wait for the deploy, then verify
production reports the expected commit SHA — not merely HTTP 200.
