# Batches 49–54 — follow-through and corrections (wave 2)

Companion to `BATCH_49-54_ROADMAP.md`. Written 16 Nov 2026 by the synthesis, at `1668071`. People are
named by role: the admin and the viewer. Evidence labels as in the roadmap.

## 1. Corrections the synthesis made to the passes

| Finding | Pass said | Synthesis | Evidence |
|---|---|---|---|
| DS50-01 | heading **High**; summary and STATE Med-High | **Med-High.** The harm seen (four of ten cinemas dark for five days, no money or data lost) is moderate; the cinema half shipped as PR 161 (#381) on 16 Nov; what is left (reminders, backup, calendar refresh, a venue switched off on refusal) is latent. Heading corrected in the report | implemented, observed |
| CT52-04 | the *Dead Man's Shoes* want "has been the wrong film since 9 Sep"; correct it | **Premise withdrawn.** The want's film was confirmed through the app's own question on 15 Nov, the day before R4 ran; R4 saw only that the admin's ask was open. What stands: 53 shop prices of another film's disc recorded against the want (26 since 12 Oct), the class of MK53-03 (shop prices matched to a want by title, not by film). Recast on that class; **no proposal to move the want.** R4's "run X9's rule once over stored `mismatch` rows" is dropped: on this want the stored `mismatch` is now right, and would raise a false doubt | observed (1 projected SELECT, orchestrator, 16 Nov) |
| UX54-02 | Medium; "nothing on the viewer's own Home or Settings says their phone stopped" | **Low.** The notification settings page says so on that phone when opened ("This phone stopped getting notifications on … Turn them on again.", X3), and the app re-registers a phone on open. The Home half stands: the person is told only if they open that page. The "which pushes" half moves to MK53-05 and an owner decision | implemented |
| UX54-03 | Medium; "one of the two answered questions is itself contested" | **Medium, on the labelling alone.** The answer is not contested (CT52-04 above). The rows still name who answered, not whose move it is | observed, implemented |
| CR49-01 / DS50-01's failure table | the 08:00 job crashing reaches the admin "only as a Home row after 26 h (`check:stale`)" | On CR49-01's path the daily check runs and commits **before** the crash, so `check:stale` never fires and its own rows look fresh. From the second morning PR 161's `cinema:job` row names the cinema programme as not run; that push waits for the next delivery pass (the 03:00 shop job delivers everyone's queue). Reminders themselves stay unwatched | implemented (`run_reminders._run`, `scraping/daily.py`) |
| CT52-01 | 282 ODEON showings still to start at 14:30 | Time-of-read count. Recount: 307 stored for 16–17 Nov (95, 70, 88, 54), 262 starting after 14:30 UTC, 0 from 18 Nov, none seen since 11 Nov 08:04. The finding stands | observed |
| MK53-05 / MK53-01 | 124 admin deal pushes, 123 delivered, 28 at night | Window-dependent: 23 Oct–16 Nov 15:00 gives 126 queued, 125 sent, 32 sent between midnight and 06:00 UK time. Substance holds | observed |
| MK53-06 | 488 deal-push rows since 26 Sep | 502 deal-push rows in all, the oldest 10 Sep (R5 counted from the first push carrying a listing's words). Substance holds | observed |
| Owner item "Correct Dead Man's Shoes' match" (14 Nov, #378) | open; R4: "accurate, open" | **Premise contradicted** by the same 15 Nov answer: owner decision 3 in the roadmap | observed |
| `OWNER-ACTIONS.md` 9, revoke the April PAT | reasons "the repo is private" | decayed premise (R2 found it); the repo is public and stays so (decision 6, `DECISIONS.md` #382). The token is dead, so no history rewrite follows from it | observed |

## 2. Re-verification of every Med-High and headline number

All reads 16 Nov, 18:20–19:05 UTC: 20 projected `SELECT`s through `mcu_readonly` and 2 `gh` reads.
Code read in the review worktree at `1668071`.

| Claim | Result |
|---|---|
| CR49-01: the error handler reads `person.id` after its own rollback, and `_run` calls `sync_due` unguarded before delivery, the reminders heartbeat, the cinema refresh and the digest | **holds** (implemented; R1 proved it in a throwaway clone). 0 occurrences live |
| DS50-01: `JOBS` lists 4 jobs (shops, specs, eBay, values) | **holds** (implemented) |
| P1: 4 venues failed with 0 rows on each run 12–16 Nov | **holds**: 4, 4, 5 (one more failed with rows on 14 Nov), 4, 4 failed venues; 0 on 10–11 Nov |
| P1: programme rows 2,247 (11 Nov) → 888 (16 Nov) | **holds**: 2,247, 1,053, 1,055, 978, 953, 888 |
| CR49-04: every cinema run `partial` | **holds**: 14 of 14 runs 3–16 Nov, including the 9 with no failed venue |
| DS50-01: the daily check read OK on 16 Nov | **holds**: 16 rows, 16 OK |
| DS50-03: the repo is public; secret scanning and push protection off | **holds** (`gh`, 19:05 UTC): public; secret scanning, push protection and Dependabot security updates disabled |
| AI51-02: 15 model calls, $0.0992, last 18 Oct, 2 in 30 days | **holds**; 0 error rows |
| CT52-03: row 878 a second 2005 4K copy beside 877, same disc page; a 1976 4K copy added 16 Oct; *Hitchcock* 703–704 share film, format and page | **holds** |
| MK53-03: 27 shop prices of the 1992 film's 4K on the 2009 film's want, all since 12 Oct | **holds**; 4 of them flagged as having raised a push |
| MK53-01: seven named pushes another film or product | **holds**: all seven found in the admin's deal pushes (five same-title films, "Mastered in 4K", "Director's Cut ONLY") |
| MK53-02: one shop's last price 12 Oct, "no results" every night since | **holds**: last price 12 Oct, last read 16 Nov, `no_results` |
| MK53-04: 318 eBay deals since 23 Oct; 94 on exactly three asks | **holds**: 207 used-ask quartile (64 on three), 105 scaled New (27), 4 an older basis label (1), 2 on three sales (2) |
| DS50-05: 1,064 films unsynced for 60+ days, oldest 8 Sep; 24 never synced | **holds** |
| UX54-03: two answered cards waiting on the admin | **holds**: three cards, two answered 15 Nov, one open |

Not re-derived (each pass's own computation, stated as such): MK53-04's 35% and 21% against recorded
sales; MK53-05's 33 deals of 40%+ never pushed; R1's 15 crafted title pairs; R6's target sizes and
bundle sizes.

## 3. Coverage — every wave 2 finding placed

Severity after the synthesis. Packages are draft names (Group AG); the rows step confirms them.

| Finding | Sev | Package | Disposition |
|---|---|---|---|
| CR49-01 Letterboxd error path aborts the 08:00 job | Med-High | AG1 | do now |
| CR49-02 "found for the film it was", three mechanisms | Medium | AG4 | do now |
| CR49-03 a fifth title rule in the cinema code | Medium | AG7 | do now |
| CR49-04 cinema status always `partial` | Medium | AG2 | do now |
| CR49-05 a merge drops later tables' links | Low | AG4 | do now |
| DS50-01 the daily check watches 4 of 8 jobs | Med-High | AG2 (cinema half shipped, #381) | do now |
| DS50-02 PIN change unlimited guesses | Low | AG9 | do now |
| DS50-03 the repo is public, records say private | Med-High | decision 6 (#382); AG9; owner decisions 6, 7 | decided; hygiene |
| DS50-04 backup key on one Mac; drill never decrypts | Medium | owner decision 9; AG9 | owner action, then do |
| DS50-05 TMDB refresh read-driven; 24 never synced | Low | AG2 | do now, before 5 Feb 2027 |
| AI51-01 a refusal breaks its chat, unseen | Medium | AG8 | decision-gated (5) |
| AI51-02 upkeep out of proportion to use | Medium | owner decision 5 | decision |
| AI51-03 tool argument types unchecked | Low | AG8 | decision-gated (5) |
| AI51-04 no behavioural guard; canary never run | Low | AG8; owner decision 8 | decision-gated |
| AI51-05 model current; no switch yet | Low | — | defer (trigger: a deprecation notice, or keeping the assistant) |
| CT52-01 stale cinemas silent on Home and the digest | Medium | AG3 | do now |
| CT52-02 a moved copy keeps the old film's disc page | Medium | AG4 | do now |
| CT52-03 King Kong row 878; *Hitchcock* pair | Medium | owner decision 2; AG4 guard | owner action, then guard |
| CT52-04 a want's prices matched by title (recast) | Medium | AG5 | do now |
| CT52-05 three cinema titles slip the rules | Low | AG7 | do now |
| MK53-01 1 deal push in 18 names another disc | Medium | AG6 | do now |
| MK53-02 one shop dark five weeks, read as "no results" | Medium | AG2 (noticing), AG6 (repair) | do now |
| MK53-03 two wants carry another film's prices | Medium | AG5; owner decision 1 | do now |
| MK53-04 a deal's yardstick is thin | Medium | AG6, after AA10c (25 Nov) | defer with trigger |
| MK53-05 five pushes a day by clock, mostly upgrades | Medium | AG6; owner decision 4 | decision-gated (4) |
| MK53-06 push rows keep listing words | Low | AG6 | do now (fold) |
| UX54-01 stale cinemas only at the page foot | Medium | AG3 | do now |
| UX54-02 a quiet phone shown on Settings only | Low | AG3 | do now |
| UX54-03 rows labelled by who answered | Medium | AG3 | do now |
| UX54-04 small targets on Settings and Needs you | Low | AG10 | any sitting |
| UX54-05 1.2 MB first-open script | Low | AG10 | any sitting |
| UX54-06 the assistant from the users' side | Low | owner decision 5 | decision |

**Totals:** 32 findings. 0 High, 3 Med-High, 17 Medium, 12 Low. Placed: 32 of 32 (29 in packages,
2 in owner decisions alone, 1 deferred with a trigger). Pre-review findings: P1 is DS50-01, CT52-01,
UX54-01 and CR49-04; P2 is AI51-02 and UX54-06.

## 4. Wave 1 since the pack, as the passes corrected it

The pack (16 Nov) found 40 of wave 1's 44 fixed, 2 shipped differently, 1 accepted, 1 partly fixed,
and all 10 Highs holding. The passes changed these rows:

| Row | Pack | Now |
|---|---|---|
| CR43-02 error handler | fixed | fixed at the identify site; the class recurred in the Letterboxd sync (CR49-01) |
| CR43-03 one title rule | fixed | fixed for seven sites; the cinema code added its own (CR49-03) |
| DS44-01 failures reach the admin | fixed, 4 of 8 jobs | 5 of 8 since PR 161; the 08:00 job, backup and calendar still unwatched (DS50-01) |
| DS44-03 backup | fixed | the drill proves the dump, never the encrypted copy; one key copy (DS50-04) |
| DS44-05 lockout | fixed | login only; PIN change unlimited (DS50-02) |
| DS44-06 TMDB terms | fixed | refresh runs on reads; 24 films never refreshed (DS50-05) |
| AI45-01 every follow-up fails | fixed | fixed for its cause; reopened by a refusal (AI51-01) |
| AI45-04 failures reach no one | fixed | provider errors only; refusals and give-ups unseen (AI51-01) |
| AI45-07 tool contracts | fixed | argument types unchecked (AI51-03) |
| CT46-01 30 wrong films | 28 fixed, 1 wrong | row 878 confirmed a phantom copy (CT52-03); row 550 keeps its old film's disc page (CT52-02); 0 doubts open, not 7 |
| CT46-03 year conflicts | fixed | fixed for reviews read after 16 Oct |
| MK47-01 wrong-disc deals | fixed in the matcher | 7 of 124 pushes another film or product, three classes (MK53-01) |
| MK47-04 eBay licence (accepted) | stands | push rows keep listing words (MK53-06) |
| MK47-05 shop alerts | fixed | alerts fire without a limit; one shop dark since 13 Oct (MK53-02) |
| UX48-02 failures look fine | partly fixed | walked: reaches the admin; the person affected is not told on Home (UX54-01, -02) |
| UX48-06 small text and targets | claimed | text holds; targets partly (UX54-04) |

## 5. Guards

**Wave 1's twenty, now.** 18 run. Guard 9 (each job ran within its cadence) covers 5 of 8 since
PR 161. Guard 16 (bundle release) is a close-out step, not a gate. Guard 19 (the paid canary) has never
run: it needs Railway access. Guard 4 (run loops survive a failure) lacks the Letterboxd loop. Guard 6
(one title-key table) is a fixed site list. Guard 14 (year doubts) is blind to moved copies and wants.
Guard 20 (TMDB refresh) runs only on a calendar read.

**Wave 2's new guards** are listed in the roadmap, section e, each with where it runs.

## 6. Synthesis probe log

- Database (16 Nov, 18:20–19:05 UTC): 20 projected `SELECT`s through `mcu_readonly`, each one statement,
  no transaction held: column names (2), cinema runs and per-venue report fields (4), ODEON showings
  (2), health checks, assistant usage, two wants' prices, duplicate copies, pushes by category and role,
  shops, review cards (presence and dates only, no answers), the seven named pushes (2), deals by
  yardstick (2), deal-push rows, TMDB sync ages.
- GitHub: 2 `gh` reads (visibility, security settings). Railway: none; the saved token is unchanged
  since 1 Oct, so the canary was not attempted. TMDB, eBay, Brave, cinema pages: none. Paid: none.
