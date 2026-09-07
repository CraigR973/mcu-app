# phase-closeout

Close out a batch. **This runs automatically once the gate is green** — see `DECISIONS.md`
#24, which superseded #13 on 2026-09-07. `/phase-closeout <ids>` runs the same procedure on
demand. **Pushing `main` deploys to production**, so this ships without a second prompt.

**Do not close out** — stop and report instead — if the batch touched **hosting or
credentials** (Railway variables/domains, Vercel env/domains, Neon, `.railway/railway.ts`)
or performed a **destructive data or history operation**. Those stay explicit.

1. Confirm the gate is green (`batch-verify.md`) from a clean tree, every acceptance
   criterion is met criterion-by-criterion, and the working tree holds nothing beyond this
   batch. A red or unrun gate stops the close-out.
2. Confirm `main` was green before the batch began. A pre-existing red is fixed on its own
   `fix/` branch and closed out first, never folded into the batch.
3. Stage the batch's files **explicitly** — never `git add .` or `git add -A`.
4. Commit with a Conventional Commit message.
5. Push the branch. Poll CI with `gh run list --limit 1` / `gh run view <id> --log-failed`
   until it completes. Do not foreground-poll in a tight loop.
6. Fix any CI failure, then re-push and re-poll. Never reach green by weakening the gate.
7. Merge to `main` (`git checkout main && git merge --ff-only <branch>`) and **push `main`**.
   Merging locally without pushing deploys nothing — that mistake cost Batch 2 a failed
   deploy against the previous commit.
8. **Verify the deploy.** Wait for Railway, then confirm production `/api/v1/health` reports
   the **merged commit SHA** and `/api/v1/health/ready` reports `db: ok`. Not merely HTTP
   200. If the SHA does not match, that is a failure to report, not to retry silently.
9. Strike the batch's row in `docs/phase-batches.md` — strike the cells through, set status
   to **shipped**, and fill the Result column. Tick the phase line in the roadmap doc: grep
   for the `**Phase X.Y: ...**` heading and append ` ✅ YYYY-MM-DD`. Skip if already ticked;
   don't double-tick. **Do not read the roadmap doc whole.**
10. Update `STATUS.md` — overwrite the "Now" block, prepend a dated line to the "Log".
    Append to `DECISIONS.md` only if a durable decision was made.
11. Commit the docs, push `main`.
12. Report what shipped, and **every failure encountered on the way** — including ones fixed
    on the first attempt.
