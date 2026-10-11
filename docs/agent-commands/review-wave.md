# Review wave — a full review, or a monthly delta review

The canonical procedure for reviewing this app, for every agent. Claude Code runs it as Craig's
`/review-wave` skill, which this file copies; Codex and any other agent follow this file. It is
refreshed at each review's check-in (last: wave 1, 11 Oct 2026, Batches 43–48).

## Cadence

```
Always on    standing checks in CI and scheduled jobs ("guards"),
             added from earlier reviews' findings
   ▼
Monthly      delta review: what shipped since the last review,
             2–3 lenses chosen by what changed
   ▼
Occasional   full panel: after a major phase, or every 6–8 weeks
```

A full panel should find design problems, not regressions a standing check could catch, so every
synthesis names which findings become guards.

## Where a review lives here

- **State and working files:** `scratchpad/<wave-id>/` in the main checkout
  (`/Users/craigrobinson/mcu_app`), ignored by git and persistent. `STATE.md` there says what is
  done and what runs next. Never a `/tmp` folder: one was wiped mid-review elsewhere.
- **Committed outputs:** `docs/reviews/`, on `chore/review-<wave-id>`, checked out in its own
  worktree at `scratchpad/<wave-id>/branch/`, so the main checkout stays on `main` for other
  work. Commit there with `git -C`. One PR, opened at the synthesis, merged only on Craig's word.
- **Run every review session on the Mac, from the main checkout.** A worktree or a cloud session
  cannot see the scratch folder.
- **Batch numbers:** the next free numbers in `docs/phase-batches.md`, one per pass, reserved at
  check-in. Finding IDs take the batch: `CR43-01`.
- **Lenses:** core: code and architecture (CR), data, security and ops (DS), AI and LLM
  engineering (AI), product and UX with the user scorecard (UX). Domain, for this app: catalogue
  integrity (CT) and prices, value and deals (MK). Each pass's brief is in the review's pack.

## The question every lens answers

1. Is it correct and safe?
2. Is it honest with its user: does what they read match what the app decided and what the data
   shows?
3. Is it doing its job for the user?
4. Would a failure be noticed, by the app, by Craig and by the person it affects?
5. Can it be run and changed cheaply: complexity, cost, data, hosting?

For each, in the lens's own terms: what optimal looks like, the smallest set of changes that gets
there, and where it is already near-optimal. No invented findings.

## The steps (each in its own session unless noted)

1. **Panel** (the session that starts the review). The app profile on one screen: users and
   their job, the decisions the app makes for them, what it changes outside itself, its data,
   whether it calls models, where it runs, what has gone wrong. Pick the lenses (about seven at
   most; each names the harm only it would catch). Craig confirms.
2. **Check-in** (same session). Fast-forward `main`; record the SHA production serves. Read the
   source-of-truth docs and the earlier reviews. Check live state that could gate a pass; log
   surprises as pre-review findings. Post the plan in 15 lines or fewer; Craig answers on
   production access, a paid-call cap and batch numbers, then says go. Create the branch and its
   worktree; commit the scope note and this file.
3. **Pack** (a cheaper model at high). Once, in `scratchpad/<wave-id>/pack/`: `DIGEST.md` (the
   architecture as it is, decisions and work since the last review, queued and parked items,
   Craig's open asks; about 400 lines), `LIVE.md` (the live snapshot with SHA and date),
   `followthrough.md` (every earlier finding with its status and evidence; every earlier High
   checked in the code), `data/` (extracts several passes need), `COMMON_BRIEF.md`, one
   `lenses/R<n>.md` per pass, and each pass's launch line in `STATE.md`.
4. **Passes** (one session each; at most two at once). Mechanism lenses first (code, ops, AI),
   then those that judge what the app decides, UX last. Each reads the rules below, the common
   brief, the pack and its lens brief, and nothing else up front; writes its report findings
   first, at most ten findings and about 200 lines; resumes from its report if one exists;
   commits it; and sends Craig a one-screen note.
5. **Fast lane** (any time). A pass that confirms a defect hurting a user now re-checks it against
   production and tells Craig at once, with one recommended action. A fix that only adds caution
   may ship mid-review as its own small batch through the normal gate, on Craig's yes. Anything
   that removes caution or touches money, auth or data waits for the roadmap. The review itself
   stays read-only.
6. **Synthesis** (the strongest model at xhigh). Re-verify every High and every headline number;
   check what each number counts. Write the roadmap (about 250 lines) and a follow-through
   companion. Name the guards. Open the PR; publish the roadmap as a private page; prepend one
   line to `STATUS.md`'s log.
7. **Rows** (after Craig's go). Ledger rows from the roadmap, not from the passes, grouped and
   dated, each with a model and effort; corrections to queued items where their batch-start
   reads them. Then record what the review taught.

**The delta review** (monthly, one or two sessions, no pack): everything merged since the last
review's SHA plus the live state; the 2–3 lenses with the most change or risk; the standing
guards re-run; one report, `docs/reviews/<date>-delta-review.md`, of at most ten findings. Escalate
to a full panel if it finds a High in a lens it did not run, or the change touched the rules of a
decision the app makes for its users.

## Hard rules

- **Read-only.** No change to code, production data, hosting (Railway, Vercel, Neon) or
  monitoring; no account, token or credential created; nothing sent to anyone. The only writes are
  the review's files on its branch and its scratch folder. Anything else: stop and ask Craig.
- **Never `cd`** (autoenv prints the live connection string). Absolute paths and `git -C`.
- **The database** only through the read-only role, never `DATABASE_URL`, never printed:
  `NEON_READONLY_URL="$(cat ~/.mcu-secrets/neon_readonly_url)" PYTHONPATH=apps/api
  apps/api/.venv/bin/python3.12 -m src.scripts.live_sql "<one SELECT>"`. Column-projected and
  windowed; never a JSON or blob column you will not read. Credential tables stay unreadable:
  count them from `pg_stat_user_tables`, never by selecting them.
- **Railway** read-only: `deployment list`, `logs`, `config plan`, with the token from
  `~/.mcu-secrets/railway_token` and the CLI reached as `.railway/README.md` says. Never `apply`
  or `variable set`.
- **Paid model calls** only within Craig's cap; keys read only inside Railway's run environment,
  never printed; every call logged (time, purpose, model, tokens, cost) in the report and the
  scope note.
- **Tests never touch the live database** (`env -u DATABASE_URL`). Revert-the-fix tests run in a
  throwaway clone, never a shared checkout. Probe the real functions from scratch scripts outside
  the app's source; never re-implement them.
- **Evidence labels** on every finding: `observed` (production rows or logs), `computed` (derived
  from production data by a script you ran), `proved` (the real function driven with crafted
  inputs, or a test that fails when the fix is reverted), `implemented` (read in the code).
  Unverified ideas go under Hypotheses. A ledger row, close-out note or STATUS line is a claim,
  not evidence: re-derive every headline number.
- **Settled decisions** (`DECISIONS.md`) are cited by number under "For reconsideration", never
  silently re-argued. **Queued items** that already cover a problem are re-verified against the
  code, not reported again.
- **Personal data:** no extracts, screenshots, chats or names committed; they stay in scratch.
- **At most two pass sessions at once.** Write as you go, findings first; resume from disk. Stop
  every process you start.

## A pass report

```
# Batch <n> — <lens> review (<wave>, pass R<n>)
Pass R<n> · reviewed SHA · lens · read-only · paid calls
1. Summary: a grade and five lines, one per question
2. Findings (at most ten, Highs first): evidence with its label; what the user or operator
   experiences; the fix and its cost; where it goes (fold into a queued item, a new row,
   the fast lane, or defer with its trigger)
3. Follow-through corrections   4. Queued and parked items, re-verified
5. For reconsideration · Hypotheses · Limitations · Probe log (every query and paid call)
```

## Writing to Craig

The answer first; risks next, never last; decisions last, numbered, each with a recommendation
and its real cost. Updates lead with Result, Risk, You and Next. Phone-length, UK English, dates
like "8 Aug", no code and no file pointers unless asked.
