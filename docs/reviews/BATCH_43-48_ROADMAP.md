# Batches 43–48 remediation roadmap (wave 1)

Synthesised 12 Oct 2026 from six passes at `527522d`; production still served that commit on 12 Oct.
Reports: R1 code (`BATCH_43_CODE_REVIEW.md`), R2 data, security and ops (`BATCH_44_…`), R3 the
assistant (`BATCH_45_…`), R4 catalogue (`BATCH_46_…`), R5 prices and deals (`BATCH_47_…`), R6 product
and UX (`BATCH_48_…`; its two-person scorecard is never published). Scope:
`BATCH_43-48_REVIEW_SCOPE.md`. Corrections and follow-through: `BATCH_43-48_FOLLOWTHROUGH.md`.

**Evidence:** observed (production rows or logs), computed (derived from production data by a script),
proved (the real function driven, or a test that fails when the fix is reverted), implemented (read in
the code). **Spend:** $0.075 of the $2 cap; TMDB 60 of 100 calls; eBay 35 of 50; Brave 0. The synthesis
re-checked every High with 23 read-only queries and one local SDK check; no outside or paid call.

## a. The verdict and the scorecard

1. The browsing half works for both people. Everything that reaches out to them (deal alerts, the eBay
   scan, pushes, the assistant's second answer) has failed quietly at least once.
2. Three things are wrong now: the eBay scan has read nothing since 9 Oct; 30 copies are confidently
   the wrong film; about a quarter of the deal pushes Craig received named the wrong disc.
3. The £23,604 value is new copies' asking prices (93% of it): roughly 1.4–1.8× what the discs ask used.
4. No failure reaches anyone, and no copy of the database exists beyond Neon's six-hour window.
5. The code is careful and well tested (1,838 API tests in CI); the fixes are about 15 days of batches.

| Question | Grade | In one line |
|---|---|---|
| 1 Correct and safe | C | Locks hold; blind scan, 30 wrong films, wrong-disc deals, no backup |
| 2 Honest with its user | C− | Says "asking prices"; not "new copies", nor that the scan is blind |
| 3 Doing its job | C− | Find it, where, seen it: yes. Buy, be told, ask twice: no |
| 4 Failures noticed | F | The app raised 0 of 7 failures since 9 Sep; people found them all |
| 5 Cheap to run and change | B | 91 MB of 1 GB; assistant $0.05 in all; Neon's hours unmeasured |

| Pass | Grade | In one line |
|---|---|---|
| R1 Code | B | Defects fixed as classes; one blind cursor, one crashing error path |
| R2 Data, security, ops | C | Sound locks, no alarms, no backup |
| R3 Assistant | D | Safe one-question tool; every second message fails |
| R4 Catalogue | C | Shelf recorded faithfully; the old import wrong 1 in 40, and certain |
| R5 Prices and deals | D | Both numbers that steer spending mislead |
| R6 Product and UX | C | Everyday screens clear; failures look fine or show machine text |

The seven: TMDB token missing (9 Sep); both crons crashing (10–23 Sep); Mark's assistant follow-up (21
Sep); Mark's phone dropped (24 Sep); Brave's credit out (28 Sep); Craig's phone dropped (8 Oct); the
eBay scan blind (9 Oct).

## b. Happening now, and before 10 Nov

| When | What | Answer |
|---|---|---|
| Now | eBay scan blind: 39 of 39 runs since 9 Oct read 0 listings; ~70 deals missed (estimate) | X1 this week |
| 21 Oct 16:35 | The scan resumes by itself and never reads 9–21 Oct | X1 before then |
| Now | Pushes reach both phones again, healed by hand on 11 Oct; the next refusal drops a phone silently | X3 |
| 1 Nov 04:00 | First re-pricing with work since 26 Sep | X6 before it, or new-copy values stand to ~1 Dec |
| ~10–19 Nov | Mark's 50-entry Letterboxd feed stops reaching back to 15 Sep | X5 by 31 Oct, then both sync |
| 8 Mar 2027 | TMDB's six-month cache limit for films synced 8 Sep | X12 |
| 30 Jun 2027 | `claude-sonnet-5` retires, not earlier | X7 |

**Owner steps now, no code (about 20 minutes):**
1. Take Neon's one free manual snapshot.
2. `OWNER-ACTIONS.md` 22: rotate the Neon owner password and take it out of `apps/api/.env`.
3. Put Mark's Letterboxd username in his profile (none is stored); press Sync now after X5.
4. Close `OWNER-ACTIONS.md` 16b: Mark's first push arrived 11 Oct 17:45, a movie-night match.
5. One look each: GitHub's plan (CI runs ~3,000 minutes a month) and Neon's usage page.

## c. How the app works now

```
 Craig's iPhone · Mark's Android   (PWA on Vercel)
        │  offline: the worker keeps no API answers
        ▼
 API on Railway ────────▶ Neon Postgres
        ▲                 91 MB of 1 GB · 6 h restore
        │
 5 jobs: specs+reviews 02:00 · shops 03:00
         values 04:00 · reminders 08:00 · eBay 2-hourly
        │
        ├─▶ pushes: a refused phone is deleted, silently
        └─▶ failures: exit code + 7-day log, read by no one
```

The paths out of the app work; the return path does not. A failure becomes a row or a log line that no
screen, push or person reads, and screens show a job's last start, not what it found. X2 and X3 add the
return path:

```
 08:00 job ─▶ daily check (tables the app already writes)
              ├─▶ "Needs attention" row at the top of Home
              └─▶ push to Craig
```

| The docs say | The code or production says |
|---|---|
| ARCHITECTURE §9.9: weekly dump, offsite copy, quarterly restore test | None exists (DS44-03) |
| ARCHITECTURE §6.15, Batch 8, #47: browse offline | Only where the API shares the page's origin; production's does not (UX48-01) |
| ARCHITECTURE §2: Sentry error tracking | Off in the API, the jobs and the web (DS44-01) |
| `AGENTS.md`: ~140 discs; mid re-scaffold; the web "does not boot" | 1,889 copies, live since mid-Sep (CR43-08) |
| `docs/agent-commands/README.md`: close-out never automatic | Automatic since #24 (CR43-08) |
| The worker's comment: the page re-registers a rotated push subscription | Nothing does (DS44-02; found in synthesis) |

## d. Work packages

**Dispositions:** do now · fold into a queued item · decision-gated · defer with a trigger · accept and
close. **Models:** "top" is the ledger's top tier (Opus 5.5 / GPT-5.6 Sol), "mid" its mid tier (Sonnet
5.5 / GPT-5.6 Terra). X1–X12 are draft names; the rows step confirms them.

| Package | Findings | When |
|---|---|---|
| X1 eBay: unblind, right disc, fresh | CR43-01, MK47-02, MK47-01, -06, -07, CR43-06 | do now, by 17 Oct |
| X2 Failures reach Craig | DS44-01, DS44-05, UX48-02 | do now |
| X3 Push heals itself | DS44-02, UX48-02 | do now |
| X4 Weekly dump, restore drill | DS44-03 | decision-gated (4) |
| X5 Watch history | Craig's 11 Oct choice, CT46-02, UX48-04 | do now, by 31 Oct |
| X6 Value as used copies | MK47-03 | decision-gated (3), by 1 Nov |
| X7 Assistant repair | AI45-01 to -08 | do now |
| X8 Offline, drift, failure words | UX48-01, -03, CR43-04, DS44-04, -07 | do now |
| X9 Catalogue truth | CT46-01, -03, -05, CR43-02 | do now, early Nov |
| X10 One title rule, owned twins | CR43-03, CT46-04 | after X9 |
| X11 Wanted: shop prices, alerts | MK47-05 | do now, Nov |
| X12 Polish and terms | UX48-05, -06, -07, CT46-06, -07, DS44-06, CR43-08 | Nov |
| Batch 38 (queued) | CR43-05, CR43-07 | fold into queued |
| eBay's licence | MK47-04 | decision-gated (2) |

### X1 — eBay: unblind the scan, name the right disc, say how fresh
CR43-01 ≡ MK47-02 High · MK47-01 High · MK47-06, MK47-07, CR43-06 Low.
- **Evidence:** observed 12 Oct — 39 of 39 runs since 9 Oct read 0 listings; the mark (21 Oct 16:35)
  came from one listing dated 12 days ahead (proved). Computed — 25 of 265 finds were another product;
  14 of the 60 pushes delivered to Craig were among them.
- **Fix:** the mark is the run's own start, read as no later than now (that unblinds the stored row
  with no data write); a year after the title must be the film's; "disc only", "no case", "not 4K"
  refused; a used listing judged against used copies; the push names the listing and its condition; a
  find re-checked before its push; every card dated; shop deals expire; expired eBay rows lose title and
  image; TMDB waits bounded. Then 10 film-by-film searches recover the wanted films' gap.
- **Cost:** ~1.5 days · first, before 21 Oct · top · high. One batch: the mark alone would resume pushes
  with about 1 in 4 naming the wrong disc.

### X2 — Failures reach Craig
DS44-01 High · UX48-02 High (the screens' half) · DS44-05 Low.
- **Evidence:** implemented — error reporting needs a DSN and has none; the shop job exits as failed
  whenever a shop refuses, so Railway shows it Crashed nightly; idle jobs write no row. Observed — no
  spec row 4–10 Oct while reviews ran nightly.
- **Fix:** a daily check in the 08:00 job over tables the app already writes (the "daily" guards in
  section e), reaching Craig by a "Needs attention" row on Home and a push; a heartbeat when a job finds
  nothing due; the shop job exits clean on refusals alone (#240); Price alerts says how many listings the
  last checks read; Deals stays in the menu, saying when each source last answered; repeated lockouts
  escalate and reach the row.
- **Cost:** ~1 day · after X1 · top · high. Backend Sentry (one Railway variable, Craig's) can follow.

### X3 — Push that heals itself
DS44-02 High, with UX48-02's Settings line.
- **Evidence:** observed — Mark had 0 deliveries of 102 before 11 Oct; Craig none 8–11 Oct. Implemented —
  a refused phone is deleted with an info log; Settings reads the phone's own subscription, so it can say
  "Notifications are on" above "No devices are registered yet"; nothing registers the phone again.
- **Fix:** on app open and on the worker's change event, register this phone again if the server lost it;
  a banner when someone's last device goes; Craig told through X2; count delivered, not queued.
- **Cost:** half a day · after X2 · top · high.

### X4 — A copy outside Neon, and a tested restore
DS44-03 High. Decision 4.
- **Evidence:** observed — Neon's free plan: restore within 6 hours, one manual snapshot, no scheduled
  backups. Computed — a loss found next morning takes 191 identifications, 729 discs' specs, 616 scores,
  1,300 values (~3,600 outside calls to rebuild) and what nothing rebuilds: Mark's edits, wants, deals,
  chats.
- **Fix:** a weekly encrypted dump from a GitHub Actions schedule (8 kept), through a role that reads
  everything but credentials; a monthly restore drill that counts rows. ~0.4 GB of the free 5 GB egress.
- **Cost:** half a day, plus Craig's 10 minutes for the role and one secret (his credential changes) ·
  when he answers · top · xhigh.

### X5 — Watch history: films not owned, the backfill, the year rule
Craig's decision of 11 Oct · CT46-02 Medium · UX48-04 Medium.
- **Evidence:** computed — 15 imported watches sit on a different film of the same name; proved — the
  real matcher puts a 1998 *Psycho* watch on the owned 1960 film; observed — Mark has no Letterboxd
  username stored and has never synced.
- **Fix (Craig's scope):** a watch of a film not owned kept on a film record with no copies (out of
  counts and value); a dry-run-first backfill of the 756 dated diary entries not yet recorded (Craig 579,
  Mark 177), doubtful matches queued for Craig; a known year more than one apart excludes a candidate;
  the feed's TMDB id kept on each watch; the 15 re-pointed at Craig's word; the diary import leaves the
  old engine; a weekly sync inside the 08:00 job (no new Railway service); a line on the 50-entry window.
- **Cost:** ~2 days plus Craig's look at doubtful matches · by 31 Oct · top · xhigh (live data).

### X6 — Value the shelf as used copies
MK47-03 Medium. Decision 3 (#209 for reconsideration; #237's asking prices stand).
- **Evidence:** computed — 965 of 1,300 values (£21,843 of £23,604) are new-copy medians; used copies ask
  0.48–0.71 of new; as used the total is roughly £12,800–£17,200. Observed — 7 of 20 live re-searches mixed
  in another product; four of the six highest values among them.
- **Fix:** used listings when there are 3 or more, else new times the measured factor, labelled "as used
  copies"; the estimator refuses a word before the title and TV words; Most valuable shows listing counts.
- **Cost:** ~1 day · before 1 Nov 04:00 · top · high.

### X7 — The assistant answers more than once
AI45-01 High · AI45-02, -03 Med-High · AI45-04 Medium · AI45-05 to -08 Low.
- **Evidence:** proved (paid probe) — a follow-up fails with a 400: each answer is stored with a field only
  the SDK uses, then replayed; observed — all 5 stored answers carry it; no use since Mark's follow-up
  failed on 21 Sep. Proved — "log it, 4 stars" calls no tool; the example question saw 13 of 162 films.
- **Fix:** replay only request fields (on read too, so old chats recover); the app's card, today's date
  and the person in the prompt; input paused while a card waits; compact lists, totals first, with paging;
  failures logged, worded honestly, counted into X2; caps checked before each call; one write per Yes;
  the 5.5 models priced; a decision recording Part D 9.4's change.
- **Cost:** ~1.5 days · after X3 · top · high (R3 proposed mid; raised for the write gate and money caps).

### X8 — Offline, version drift and failure words
UX48-01 High · UX48-03, DS44-04 Medium · CR43-04, DS44-07 Low.
- **Evidence:** proved — the worker's caches held 0 API answers; offline a film reads "You can still
  browse…" above "Failed to fetch". Implemented — it caches only its own origin, and production's API is
  on Railway, the page on Vercel. Proved — a server error reads like no signal; a newer API's value turns a
  page into raw JSON; a missing chunk after a deploy fails until a full reload.
- **Fix:** match the API's origin, each person's cache kept apart; one error describer with a Reload; reload
  once on a failed chunk; CORS on error answers; readiness adds TMDB and Brave; the gate checks the
  bundle's release is the merged commit; a contract test of API against shared schemas; a tighter CSP.
- **Cost:** ~1.5 days · after X7 · top · high.

### X9 — Catalogue truth
CT46-01 High · CT46-03, CR43-02 Medium · CT46-05 Low.
- **Evidence:** computed — 30 copies confidently the wrong film: 27 of 1,115 from the 8 Sep import, 3 of
  404 from the diary, 0 of 156 by T9; observed 12 Oct — all unchanged. 20 read "not owned" (*GoodFellas*,
  *Spider-Man*); 16 carry a value (£304). Proved — the old engine takes an exact namesake over the real
  film; the identify run's error handler crashes on its first failure.
- **Fix:** T9's identifier as a dry run over the 1,506 films the old paths decided, every disagreement into
  Identify with evidence; "this copy is another film"; a disc page naming another year proposes an
  identification, not another page; editions shown as "probably"; reload by id after a rollback; the old
  engine retired.
- **Cost:** ~2 days, then an hour of Craig's taps · early Nov, before any future import · top · xhigh.

### X10 — One title rule, and owned twins found
CR43-03, CT46-04 Medium.
- **Evidence:** proved — four title rules disagree on 7 of 8 pairs; computed — 5 films split across two
  rows (*Sorcerer* wanted while owned); observed — a 10 Oct scan met no prompt beside an unidentified twin.
- **Fix:** one title key from T9's comparison, a dry-run diff showing no identification moves; Search's
  lookalike check in the add form and the scanner; a warning for a barcode already on a copy.
- **Cost:** ~1 day · after X9 · top · high.

### X11 — Wanted: shop prices shown, alerts without a limit
MK47-05 Medium. Observed — 1 of 10 wants has a limit, so shop alerts can fire for 1; shop prices are
stored nightly and shown nowhere. **Fix:** each want's latest shop prices with dates; an alert under the
usual when no limit; the refusing shops asked weekly. ~1 day · Nov · mid · high.

### X12 — Polish and terms
UX48-05 Medium · UX48-06, -07, CT46-06, -07, DS44-06, CR43-08 Low. **Fix:** one number per fact ("Films
owned 1,869"); one date style; a 12 px floor and 44 px targets; compressed answers; TMDB's logo, notice
and JustWatch credit; decided Brave results deleted; TMDB fields refreshed before six months; completion
sets from top billing; agent docs corrected; a "Tell Craig" line for Mark. ~1.5 days · Nov · mid · high.

**Batch 38 (queued) gains six cases:** the offline replay that may have landed (CR43-05); each job's entry
point run (CR43-07); the built bundle against a cross-origin API (UX48-01); a drift and a missing-chunk case
(UX48-03); a two-message chat on a recorded model (AI45-01); the screens never used yet.

| Queued or parked | Verdict |
|---|---|
| 38, end-to-end suite | Accurate; six cases added |
| 21, price history | Accurate: 2 of 3 wants; Dead Man's Shoes' want sits on the 1940 film |
| 22c with `OWNER-ACTIONS.md` 28 | Parked; its one manual run left 6 deals "live" 11 days (X1 expires them) |
| T8b, Connect eBay | Accurate: 0 accounts; unproved until Craig connects (29) |
| `OWNER-ACTIONS.md` 1k | Done 18 Sep, not open (R4); a future import still uses the old engine |

## e. Coverage, follow-through, guards, open questions

**44 findings, every one placed:** 10 High, 2 Med-High, 13 Medium, 19 Low; 41 in X1–X12, 2 in Batch
38, 1 a decision. Two span packages (UX48-02 across X1–X3; CT46-01's diary share in X5), and CR43-01 and
MK47-02 are one defect. The finding-by-finding table is the companion's section 2.

**Follow-through in brief.** No panel review came before this one. The 7 Sep alignment review's Highs are
fixed except the April PAT (`OWNER-ACTIONS.md` 9). All 14 pre-review findings are answered. The synthesis
corrected three pass claims: `OWNER-ACTIONS.md` 1k is done; ~70 deals missed by 12 Oct, not ~62; Mark has
had 5 pushes delivered of 108, not 1 of 104.

**Guards: what becomes a standing check, and where it runs.**

| Guard | Runs in | From |
|---|---|---|
| A future-dated listing never moves the scan's mark | CI | CR43-01 |
| The 25 wrong products never match; used never meets the new median | CI | MK47-01 |
| SDK blocks survive store-and-replay; tool text carries its total | CI | AI45-01, -03 |
| Every run loop survives an injected failure | CI | CR43-02 |
| The API's answers match the shared schemas | CI | CR43-04 |
| One title-key table with namesake and article cases | CI | CR43-03, CT46-01 |
| A known, different year excludes a diary candidate | CI | CT46-02 |
| The worker caches a cross-origin API | CI, 38 | UX48-01 |
| Each job ran within its cadence (a heartbeat when idle) | daily | DS44-01 |
| The eBay scan read listings in one of its last six runs | daily | CR43-01 |
| Each person has a live device; recent pushes not all suppressed | daily | DS44-02 |
| Integrations not halted; readiness configured; database under half; lockouts | daily | DS44-01, -05 |
| Assistant failures in the last day | daily | AI45-04 |
| Disc pages naming another year; proposals over a fortnight old | daily | CT46-03 |
| No deal older than its source's freshness | daily | MK47-07 |
| Readiness all configured; the bundle's release is the merged commit | gate | DS44-04 |
| Weekly encrypted dump; monthly restore drill counting rows | Actions | DS44-03 |
| Weekly Letterboxd sync for each person | 08:00 job | UX48-04 |
| A five-question paid canary (~$0.08) | monthly delta | AI45-08 |
| TMDB fields refreshed before six months | calendar job | DS44-06 |

**For reconsideration** (settled decisions with new evidence; none re-argued here):

| Decision | New evidence | Proposed |
|---|---|---|
| #209 value = largest condition group | New carries 93%; used asks 0.48–0.71 of new | As used (X6) |
| #239 eBay part condition-matched | Only with 3 in the group; 3 of 12 sampled were used vs new | Used vs used (X1) |
| #129 three listings | 22 of 265 saving claims rest on 3–4 | No deal when thin (X1) |
| #31 ambiguity = exact tie | 27 wrong import matches had no tie | T9's rival test (X9) |
| #158, #160 a year never excludes | 15 namesake watches with both years known | Exclude then (X5) |
| #220 the edition found is the copy's | 3 counter-examples in stored results | "Probably" (X9) |
| #154, #165 hide while empty | Deals vanishes exactly when its source fails | Deals stays (X2) |
| #17 Neon's free plan | 6-hour restore, no scheduled backups | Keep; add the dump (X4) |
| Part D 9.4, no write tools | Two shipped behind a card; no decision records it | Record one (X7) |

#24, #237, #12, #126 and #127 stand. Infrastructure note: the pending Railway plan's restart-policy change
likely cuts restarts from 10 (Railway's default) to 3; not worth applying as it stands (R2).

**Hypotheses:** two likes in one instant can both miss "It's a match"; CI's ~3,000 minutes a month may pass
GitHub's free allowance; more finds carry a wrong "usual" than the 25; a sold-price check of ~20 values
needs Craig signed in to eBay (~30 minutes, his OK).

**Limitations:** one evening's walk, Chromium only (no iOS); one paid trial per question; samples of 25;
no sold prices; no billing pages; 7 days of Railway logs; 25 wrong products is a floor.

## f. Decisions for Craig

1. **Go on this order, then X1 straight away.** Recommended: the stored 21 Oct mark makes each day of delay
   unreadable. Cost: the rows step (~30 minutes), then ~15 days of batches, each deploying on merge.
   Command: `/review-wave rows`
2. **eBay's licence (MK47-04):** record an accepted risk, as #110 and #121 did for Blu-ray.com, and ship
   X1's freshness and deletion steps. Recommended. Asking eBay is optional; a "no" ends value and deals on
   eBay data. Cost: one decision entry.
3. **Value as used copies (#209):** recommended, before 1 Nov. Cost: ~1 day; the total falls to roughly
   £12,800–£17,200.
4. **Backup storage:** GitHub Actions artifacts, encrypted, weekly, 8 kept. Recommended: no new account.
   Cost: half a day, plus your 10 minutes; the alternative is Neon's paid plan at Neon's price.
5. **The five owner steps in section b:** ~20 minutes; the snapshot and the password first.
6. **Merge this pull request** once read: review files and one STATUS line only.

## g. Draft ledger rows (written only after Craig's go)

| Row | Covers | Size · Claude Code |
|---|---|---|
| X1 | eBay: unblind, right disc, fresh | 🟡 · top · high |
| X2 | Failures reach Craig: daily check, Home row | 🟡 · top · high |
| X3 | Push heals itself | 🟢 · top · high |
| X4 | Weekly dump and restore drill | 🟢 · top · xhigh |
| X5 | Watch history: not owned, backfill, year rule | 🔴 · top · xhigh |
| X6 | Value as used copies | 🟡 · top · high |
| X7 | Assistant repair | 🟡 · top · high |
| X8 | Offline, drift, failure words | 🟡 · top · high |
| X9 | Catalogue truth | 🔴 · top · xhigh |
| X10 | One title rule, owned twins | 🟢 · top · high |
| X11 | Wanted: shop prices and alerts | 🟡 · mid · high |
| X12 | Polish and terms | 🟡 · mid · high |
| 38 | End-to-end suite, six more cases | 🟢 · mid · high |

**Sittings** (each at its strictest batch's setting; Codex takes the same tier):
1. 13–17 Oct: X1 → X2 → X3, top · high.
2. When decision 4 is answered: X4 alone, top · xhigh.
3. 20–24 Oct: X7 → X8, top · high.
4. 27–31 Oct: X6 → X5, top · xhigh; then both people press Sync now.
5. 3–7 Nov: X9 → X10, top · xhigh; then Craig's taps in Identify.
6. 10–14 Nov: X11 → X12, mid · high. Batch 38 stays at Craig's go, last.
