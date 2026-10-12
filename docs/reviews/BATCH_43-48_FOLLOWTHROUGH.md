# Batches 43–48 follow-through companion (wave 1)

The companion to `BATCH_43-48_ROADMAP.md`, written at the synthesis on 12 Oct 2026 at `527522d`.
Corrections first: what the synthesis corrected in the passes, then what the passes corrected in the
pack, the scope note and each other. Then every finding's place, the 7 Sep review followed through, the
14 pre-review findings, and the queued and owner items re-verified. Evidence labels as in the roadmap.

## 1. Corrections

### 1a. By the synthesis (every High and headline number re-checked, 12 Oct 08:00–08:30 UTC)

| Claim | Corrected to | Evidence |
|---|---|---|
| R4: `OWNER-ACTIONS.md` 1k, a fresh sheet import, "still open" | Done 18 Sep. R4's risk stands for any future import or refresh: that path still matches with the old engine | implemented (the owner file) |
| R5: ~62 deals missed by 20:00 on 11 Oct | ~70 by 08:00 on 12 Oct, at 2–8 Oct's median of 22 a day (28, 12, 22, 15, 22, 23, 29). An estimate: the gap cannot be read back | observed (runs), computed |
| R6: Mark 1 notification delivered of 104 | 5 of 108: the 08:02 reminders on 12 Oct reached both people (4 release pushes each); 2 live devices | observed |
| R2: nothing registers a dropped phone again | Confirmed, and the worker's own comment says the page "re-registers on its next load regardless"; the hook only reads local state | implemented |
| R5: 25 of 265 finds a different product | What it counts: rules flag 32; the hand check removed German imports (Region B, the UK's own) and region-free ones and added one namesake (*Maggie*, 2015). 14 of the 25 were among the 60 pushes delivered to Craig, one push per listing and person | computed (R5's extracts) |
| R4: 30 copies the wrong film | The 29 wrong film rows hold 31 live copies, 2 of them right (*French Connection II*, *Tinker Tailor* 2011), plus 1 of the 2 copies on *Life* (2017): 30. All 29 rows unchanged since 18–26 Sep | observed |
| R5: 93% of the value is new copies | 92.5%: £21,843.24 of £23,604.29, 965 of 1,300 rows | observed |
| R3: stored answers carry an SDK-only field | Text blocks carry `parsed_output` (5 of 5); tool-use blocks also carry two SDK-only keys, which replay fine (R3's probe A). SDK 1.4.0's streamed text block dumps exactly the stored four keys | observed; proved locally, no call |
| Live counts (pack, passes) | 1,889 copies, 1,891 films, 209 without a TMDB id; Identify 165 waiting (1 decided 11 Oct); Disc specs 734 done, 525 waiting; Letterboxd: Craig 1 sync, Mark no username and 0 | observed |
| The eBay scan | 39 of 39 runs blind from 9 Oct 02:21 to 12 Oct 06:24; the mark still 21 Oct 16:35:01 | observed |

### 1b. By the passes

**R1 (code):** schema coverage is complete (131 of 145 web calls parse, 14 read no body); plain-string
errors are accepted in practice; the root Supabase-era migration is dead; 650 database tests skip on the
Mac, not 644; CI ran all 1,838 for `527522d`; 168 routes confirmed.

**R2 (data, security, ops):** the web bundle does carry its commit (as the Sentry release id), so scope
finding 10 was half wrong; "43 refresh tokens live" counts rows, revoked ones included; no device was live
from 8 Oct 00:21 to 11 Oct 08:39; Mark had a device on 24 Sep, refused on its first send; Railway's
documented default restart policy is On Failure ×10, so the pending apply would likely cut it to 3; Neon
is on the free plan (1 GB, 6-hour restore); idle jobs leave no record (confirmed); migration 030 drops
`gift_links`.

**R3 (assistant):** `ai_tool_calls` holds 3 rows (reads, 10 Sep), not 0; 6 conversations and 17 messages,
not 2 and 10; "no errors" means none recorded, since a failed chat call writes no usage row; the last round
is not forced to answer (D3 confirmed); no decision records the two write tools (D4); `claude-sonnet-5` is
served until at least 30 Jun 2027.

**R4 (catalogue):** Dead Man's Shoes is a want, not a copy; T9's counts confirmed; the 525 Disc specs
waits break down as 176 no UK page, 155 several editions, 88 no year, 48 box sets, 36 year conflicts, 22
other; all 146 editions are inferred; 2 review scores are of a wrong film; the 1,884 copies included the
sheet's junk row and a combo entered twice; "22 titles shared by 52 films" is 31 groups of 70 films, most
genuinely different, 5 one film split, 8 leftovers; the two spreadsheets differ in 2 titles.

**R5 (prices):** 151 of 152 "usual" prices use eBay alone (1 deal ever averaged a shop); 33 blind runs by
18:20 on 11 Oct; active deals fell from 34 to 7 that day; the first re-pricing with work is 1 Nov, not 24
Oct; the three Shopify shops answer Cloudflare 429s; Batch 21 waits on `price_checks`, not the daily
roll-up; the eBay run's "pushed" counts finds pushed to anyone; each price is 30–45 days old when replaced.

**R6 (UX):** Mark uses an Android phone; fast-lane item 2 was fixed by hand on 11 Oct; Mark has no
Letterboxd username stored; Home's most valuable line is a DVD TV box set at £138.99; Settings' "on"
above "no devices" proved by render; box sets and collections are hidden, loans, price alerts, photos and
eBay accounts shown empty.

## 2. Every finding, and where it goes

| Finding | Severity | Goes to |
|---|---|---|
| CR43-01 blind eBay mark | High | X1 |
| CR43-02 identify error handler crashes | Medium | X9 |
| CR43-03 four title rules | Medium | X10 |
| CR43-04 no API–web contract test | Low | X8 |
| CR43-05 offline replay untested | Low | Batch 38 |
| CR43-06 TMDB waits unbounded | Low | X1 |
| CR43-07 three jobs' entry points never run in a test | Low | Batch 38 |
| CR43-08 agent docs contradict procedures | Low | Rows step (`AGENTS.md`, the commands index); the rest X12 |
| DS44-01 no failure reaches Craig | High | X2 |
| DS44-02 a phone's push dies silently | High | X3 |
| DS44-03 no copy outside Neon | High | X4 |
| DS44-04 the gate misses a key or a stale web build | Medium | X8 |
| DS44-05 PIN lockout neither escalates nor alerts | Low | X2 |
| DS44-06 Brave and TMDB terms | Low | X12 |
| DS44-07 the page's security policy too wide | Low | X8 |
| AI45-01 every follow-up fails | High | X7 |
| AI45-02 write tools cannot complete | Med-High | X7 |
| AI45-03 lists cut before totals | Med-High | X7 |
| AI45-04 failures reach no one | Medium | X7 (count into X2) |
| AI45-05 caps and round limit leak | Low | X7 |
| AI45-06 two taps write twice | Low | X7 |
| AI45-07 tool contracts mismatch | Low | X7 |
| AI45-08 no upkeep path for model and prompt | Low | X7 (canary a guard) |
| CT46-01 30 copies the wrong film | High | X9 (diary share X5) |
| CT46-02 15 watches on a namesake | Medium | X5 |
| CT46-03 year conflicts blame the page | Medium | X9 |
| CT46-04 one film on two rows | Medium | X10 |
| CT46-05 editions inferred, shown as fact | Low | X9 |
| CT46-06 no JustWatch credit | Low | X12 |
| CT46-07 completion sets of extras | Low | X12 |
| MK47-01 a quarter of deal pushes the wrong disc | High | X1 |
| MK47-02 the blind scan's deal side | High | X1 (one defect with CR43-01) |
| MK47-03 value on new copies | Medium | X6 (decision 3) |
| MK47-04 eBay's licence unweighed | Medium | Decision 2; steps in X1 |
| MK47-05 no shop alert or shop price for 9 of 10 wants | Medium | X11 |
| MK47-06 one shop weighs as much as eBay | Low | X1 |
| MK47-07 old deals, undated | Low | X1 |
| UX48-01 offline shows nothing | High | X8 |
| UX48-02 every screen looks fine while things fail | High | X1, X2, X3 |
| UX48-03 machine text on failure | Medium | X8 |
| UX48-04 Mark's history gap | Medium | X5 and an owner step |
| UX48-05 one fact, two numbers | Medium | X12 |
| UX48-06 small text and targets | Low | X12 |
| UX48-07 the Archive waits for every film | Low | X12 |

Totals: 44 findings; 10 High, 2 Med-High, 13 Medium, 19 Low; 41 in X1–X12, 2 in Batch 38, 1 a decision.
Craig's 11 Oct decision on watch history is X5.

## 3. The 7 Sep alignment review, followed through

| Row | Then | Now |
|---|---|---|
| B1.1, B1.3, B2.3, B2.4, B4.1, B4.2, B6.1, B7.1, B7.2 | Highs | Fixed (pack, implemented; CI observed) |
| B2.1, B2.2, B2.6 | Supabase on every request; RLS bypass | Superseded: no Supabase |
| B2.8 | A PAT in history | Open: `OWNER-ACTIONS.md` 9; no other credential in history (R2's scan) |
| B1.5 | Two migration systems | Residue: the dead root migration, deleted in X12 |
| B3.4 | Errors are plain strings | Accepted in practice (R1) |
| B5.1, B6.3 | Shared types unused; one web test | Fixed: 194 schemas; 525 web tests |
| D3 | Caps; force the last round to answer | Partly: caps exist; the last round is not forced (X7) |
| D4 | The model never holds a write tool | Shipped differently, no decision; X7 records one |
| D5 | Camera policy and CSP | Camera fixed; CSP residue in X8 |
| D6 | Gift links' public surface | Superseded: removed 15 Sep |
| D8 | "All 76 phases given a verdict" | Holds (pack, computed) |
| D9 | Owner overrides | Superseded by #16 |

## 4. The 14 pre-review findings, answered

| # | Finding | Answer |
|---|---|---|
| 1 | eBay scan blind | Fast lane; Craig chose the roadmap: X1 (still blind 12 Oct) |
| 2 | No push since 8 Oct | Healed by hand 11 Oct; the mechanism is X3 |
| 3 | Shop job Crashed nightly by design | X2 (exit clean on refusals) |
| 4 | Idle jobs leave no record | X2 (heartbeats) |
| 5 | Shop check refused, 29 minutes | X11 (weekly for refusing shops); `OWNER-ACTIONS.md` 28 left |
| 6 | Watch history stops at the import | X5; Craig synced 11 Oct; Mark needs his username |
| 7 | Assistant: 8 calls, "no errors" | X7; failures cannot be recorded today |
| 8 | Features with no use | Kept (route-tested, 7% of the code); Batch 38 drives them |
| 9 | Stale agent docs | X12 |
| 10 | Only the API reports its commit | Half wrong: the bundle carries it; X8 compares the two |
| 11 | Open credential items | `OWNER-ACTIONS.md` 22 and 9: section b's owner steps |
| 12 | eBay account parsers never met a real answer | Unchanged until Craig connects (29) |
| 13 | No PIN sign-in since 22 Sep | No sign of guessing in 7 days of logs; X2 escalates and reports lockouts |
| 14 | Two spreadsheets untracked | X12 ignores them; they are the import source, so X4's backup matters more |

## 5. Queued, parked and owner items, re-verified

| Item | Verdict |
|---|---|
| Batch 38, end-to-end suite | Accurate; gains six cases (roadmap, section d) |
| Batch 21, price history | Accurate: 2 of 3 wants; Dog Soldiers one Second Sight day short while the Shopify shops refuse |
| Batch 22c, `OWNER-ACTIONS.md` 28 | Parked; the one manual sale-page run left 6 deals live 11 days |
| Batches 33–34, email | Parked; not reviewed |
| T8b, Connect eBay | Sound locks (sealed tokens, one-time sign-in state); real answers unproved (29) |
| T8a price targets | 0 ever; the film-and-format kind would inherit X1's matcher fixes |
| V7, value from bids | Shelved (#237); nothing changes it |
| `OWNER-ACTIONS.md` 1j, Sync now | Craig's done; Mark's needs his username; "a cron is not possible" decayed |
| `OWNER-ACTIONS.md` 1h, 30 | Open; iPhone-only checks |
| `OWNER-ACTIONS.md` 2, 3 | 2 decayed: a first question works, a follow-up fails (X7); 3 unaffected |
| `OWNER-ACTIONS.md` 16b | Done in effect on 11 Oct; close it |
| `OWNER-ACTIONS.md` 22 | Weightier than it reads: step 3 undone and no backup |
| `OWNER-ACTIONS.md` 9 | Accurate: the April PAT is the only credential in history |
| #74, the calendar feed token | Holds; the access log records the address with its token for 7 days |
| #127, eBay deletion notices | Holds: about 1,750 a day, answered without touching the database |
| Dead Man's Shoes | A want on the 1940 film; the film page's Correct match fixes it; its list still ranks with the old engine (X9) |

## 6. Synthesis probe log (12 Oct)

- Production: 2 GETs (`/health` reported `527522d`; `/health/ready` `db: ok`, push, AI and eBay
  configured).
- Database, read-only role: 23 queries (1 refused for a wrong column name, then re-run), each under 30
  rows, no JSON body, blob or credential column: eBay runs by day and the blind runs; notifications by
  person and since 11 Oct; device-table statistics; Neon's cap and size; each job's last run; stored
  answer block keys (keys only); assistant usage; the 29 wrong film rows and their copies; *Life*'s rows;
  value by condition group and totals; live counts; Identify and Disc specs queues; Letterboxd usernames
  (booleans) and syncs; column names for six tables.
- Local: R5's and R4's stored extracts re-read; the SDK's streamed text block dumped once, no network.
- Outside services: none. Paid calls: none. Nothing written outside the review branch and scratch.
