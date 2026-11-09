# Scheduled cinema follow-up — 8 Nov 2026, 11:30 GMT

## Result

**The first natural post-deployment cinema run completed at 08:04 UTC. AC3 now has positive production rerun classification evidence: 8 future Rocky showings across four ODEONs. AC6 evaluated the day successfully with 0 qualifying appearances and no outbox or delivery claims; positive delivery acceptance remains open.**

Read-only evidence was obtained **11:30–11:33 GMT**. GMT and UTC coincide on this date. This report supersedes the earlier pre-08:00 snapshot only for the evidence checked here; it does not rewrite that historical observation.

## Scope and current release

The existing checkout remains on `main`, at `417471a167c4b1469a300cfe8124e5f7c1dbe39c`. Local `origin/main` and remote main, queried directly, match. The two existing untracked reports were preserved unchanged. This new report is the only addition in this scheduled follow-up.

| Check | Fresh observation |
|---|---|
| Latest exact-SHA code CI | [42402887825](https://github.com/CraigR973/mcu-app/actions/runs/42402887825), all seven jobs successful, including Chromium/Firefox/WebKit/jobs E2E |
| Latest workflow of any kind | [Backup 42472268641](https://github.com/CraigR973/mcu-app/actions/runs/42472268641), successful, same SHA; not substituted for code CI |
| API health | `ok`, commit `417471a167c4b1469a300cfe8124e5f7c1dbe39c` |
| Web version | Same full commit |
| Full readiness | `ready`; `db: ok`; `push`, `ai`, `ebay`, `tmdb`, `brave` all `configured` |
| Database access | Established `src.scripts.live_sql`, existing secret loaded without printing it, `current_user: mcu_readonly`, migration `073` |

No local test suite was rerun: no application source changed. No refresh, job, valuation, provider request, notification, trip, feed creation, token rotation, hosting change, schema change or live-data write was triggered. No commit, push, merge, deployment, status/ledger edit or new automation was performed.

## 1. Daily cinema digest — AC6

### Natural refresh

Run **`d143a0a3-c7d2-410a-9ece-ef34d74621e5`**, trigger **`cron`**:

- Started **8 Nov 08:02:47.097843 UTC**; finished **08:04:30.064862**.
- Terminal status **`partial`**, not running, failed or abandoned.
- **98 total requests**; all **9 venue results have `failed: false` and empty error lists**.
- **1,431 source showing rows** collected. These are source-run counts, distinct from current future programme counts below.
- Metadata status **partial**: **47 requests / 47 successful**, **19 lookups**, **110 cached**, **135 records**, **29 pending**, **0 errors**. The pending count was 55 in the previous day's run report; it is not zero now.

| Venue | Collected rows | Observed dates / completeness |
|---|---:|---|
| GFT | 20 | 8–10 Nov; partial |
| Vue St Enoch | 87 | 8–9 Nov; complete |
| ODEON Braehead | 247 | 8–14 Nov; partial |
| Everyman Glasgow | 88 | 8–21 Nov; partial |
| ODEON Kilmarnock | 131 | 8–14 Nov; partial |
| ODEON Glasgow Quay | 262 | 8–14 Nov; partial |
| ODEON East Kilbride | 194 | 8–14 Nov; partial |
| Science Centre IMAX | 12 | 8, 12–15, 18–21 Nov; partial |
| Cineworld Silverburn | 390 | 8–21 Nov; partial |

Coverage rows tied to this run contain **2 healthy, observed, complete venue-days**, **68 partial, observed, incomplete venue-days**, and **56 partial, unobserved, incomplete venue-days**. There are no failed coverage rows for this run. Only Vue claims complete dates. Nine successful venue observations do not establish complete programmes across the full fortnight.

The report records **1 withdrawn Vue showing** and **2 newly unconfirmed Glasgow Quay showings**. These dispositions were read, not repaired or inferred as cancellations.

### Frozen evaluated day and delivery evidence

The persisted **8 Nov London day** points to this exact run and was evaluated at **08:04:30.121428 UTC**. Its report has **9 successful venues, 0 failed venues, `appearanceIds: []`, `recipients: {}`**.

At **11:32:55 UTC**:

| Durable result | Count / state |
|---|---|
| Post-deployment cron refreshes | 1, finished partial |
| Genuine evaluated day from that refresh | 8 Nov, empty qualifying result |
| Qualifying appearances, all retained history | 0 |
| Cinema outbox rows, all statuses | 0 |
| Held cinema messages / quiet-hours or digest targets | 0; no row or target to inspect |
| Committed daily delivery claims, all outcomes | 0 |
| Sent, failed, claimed or unknown delivery outcomes | No such claims exist |

**Interpretation:** the schedule ran; eligible source observations were evaluated; this is an **empty digest**, not a missing evaluation or failed delivery. There was no qualifying payload to hold or attempt. No transport failure or successful transport can be inferred from zero attempts. This proves no-new silence for the evaluated observations, not positive delivery or complete source coverage.

Both existing people still have Cinemas **on**, Older films only **off**, digest mode **off**, and no quiet-hours interval. Device subscriptions/credentials were not read; readiness and preferences do not prove phone reachability.

### The separate 7 Nov `missed_day` row

The database also contains a **7 Nov** day row, linked to the **pre-deployment** run `a07f612e-0dd3-417e-a491-25a23a2640af`, inserted at **8 Nov 08:02:47.130263** with `status: missed_day`, no appearances and no recipients.

The inspected recovery code records the prior terminal run's missed day before new source rows can overwrite its evidence. Thus there are **2 day rows**, but only **one current-day evaluation**. The prior-day marker is neither another successful empty evaluation nor an AC6 delivery failure, and it did not back-send yesterday's programme.

### Why Rocky did not become a new-film alert

Rocky's TMDB identity **1366** is a stored silent-baseline identity: `baseline: true`, `episode_number: 0`, first observed **3 Nov 17:09:38.274318**, present through **8 Nov**, with **1 baseline alias**. Its newly obtained run classification therefore does not make it a new qualifying programme arrival under the approved baseline contract.

Across all digest state, **37 identities are baseline**, **303 aliases are baseline**, and **6 aliases are non-baseline**. There are still no appearance episodes. Counts increased from rollout as existing source listings were observed/identified; the existence of a non-baseline alias alone does not prove a qualifying verified appearance.

**AC6 acceptance remains open and unstruck.** A natural qualifying appearance, payload, outbox/claim and attempted/completed transport outcome are still absent. Quiet-hours/digest holds, positive transport and uncertain-claim recovery remain unexercised by this empty production day. Craig's phone receipt and tap remain separate observations, only when a real message naturally exists.

## 2. Cinema reruns — AC3

### Positive current production classification

The natural 8 Nov run has now linked **Rocky**, Cinematimes source identity, to **TMDB 1366**, status **verified**, with stored category **`olderFilm`**, `run: rerun`, reason **“UK release 1977 · rerun”**.

| Cinema | Future Rocky showings | Next showing, GMT |
|---|---:|---|
| ODEON Braehead | 2 | 8 Nov 18:00 |
| ODEON East Kilbride | 2 | 8 Nov 17:00 |
| ODEON Glasgow Quay | 2 | 8 Nov 17:00 |
| ODEON Kilmarnock | 2 | 8 Nov 17:00 |

All **8** are confirmed; the last are on **10 Nov at 19:50**. This is positive **future AC3 UK-release classification evidence**, unlike the retained **3 Nov Pan's Labyrinth source-anniversary** row. The historical row remains historical and is not counted among these eight.

The stored run reason maps to the rerun filter through the existing read-only category logic. The authenticated production filter UI and actual-phone rendering were not re-exercised here. No identity choice or category repair was made by this verifier.

### Current future programme counts

The refined scope follows the stored-read eligibility rules: **8–21 Nov**, enabled/non-deleted venues, non-deleted films/showings, not source-expired, start after observation time, confirmation **confirmed or unconfirmed**. A separate retained withdrawn first-run row is excluded.

| Category | Confirmed | Unconfirmed |
|---|---:|---:|
| First run | 1,132 | 2 |
| Rerun | 8 | 0 |
| Unclassified | 232 | 15 |

Total **1,389 future showings**: **1,134 first-run**, **8 rerun**, **247 unclassified**. Relative to the earlier pre-run snapshot, both the source window and time have moved, so row-count differences are not treated as a pure classification delta.

### Unresolved identities and pending work

| Identity status | Source-film rows | Future showings |
|---|---:|---:|
| Verified | 113 | 1,156 |
| Review | 9 | 37 |
| Unverified | 27 | 100 |
| Event | 19 | 96 |

Source-film rows are source aliases, not distinct canonical films. Review rows cover **3 title strings**: **Ramayana — 29 showings**, **Tabby McTat — 5**, **The Devils — 3**, all Cinematimes. These are title-level counts, not an assertion that the admin review groups equal three. Candidate selection requires retained corroborating evidence and the existing owner review path.

**27 unverified rows / 27 title strings** remain, while the run's metadata report separately records **29 pending lookups**. These measure different scopes and are not forced to agree. The unverified titles and their sources are:

- **GFT:** A Woman Under the Influence + discussion; Access Film Club: The Grand Budapest Hotel; Cocoon + Q&A; Samurai Ballerina; The Devils - 4K; The Girl; We Are Aliens.
- **Cineworld:** Arthur Christmas (15th Anniversary).; Being Heumann; CBeebies Panto 2026: Treasure Island; Cliffhanger; Fjord Unlimited Screening; Hunger Games: Sunrise on the Reaping; Hunger Games: The Ballad of Songbirds and Snakes; Instruktorius; Marie Antoinette (20th Anniversary); Prima Facie; Prisoners; Sicario.
- **Everyman:** Elf; Fatherland; Sense and Sensibility; Throwback: Almost Famous (25th Anniversary); Throwback: Rocky (50th Anniversary); Toddler Club: Arthur Christmas (15th Anniversary); Toddler Club: Festive Fun with Peppa.
- **Cinematimes:** One in a Million.

In particular, Everyman's **Throwback: Rocky (50th Anniversary)** remains unverified with **2 future showings**. It was not automatically equated with the now-verified ODEON Rocky listing by this report. Other examples still awaiting metadata are Ballad of Songbirds and Snakes **2**, Prisoners **1**, Cliffhanger **1**, and Elf **1** future showing. Event-like titles in the unverified list were not reclassified by wording alone.

**AC3's owed post-8-Nov production classification read-back now has positive rerun evidence.** Craig's earlier #340 close-out is unchanged; metadata backlog, review identities, and phone/UI observations are not declared complete.

## 3. Collection re-pricing boundary

AA10b was deliberately **not rerun or re-queried**: the earlier same-day report already proved the **1 Nov scheduled campaign finished, 0 failed / 0 remaining**. Its earlier Home snapshot was **£14,739.54**, **1,473 physical copies**, **1,309 priced**, **162 checked-unpriced**, **2 unchecked**, **61 sales-backed**. The two due pairs were additions after completion.

These numbers are explicitly the **00:44–00:49 snapshot**, not fresh 11:30 results. Preserve the scope caveat against **£16,867.11 over 1,469 copies** and the qualified original-scope reconstruction in the earlier report. No new value comparison, provider request or manual re-price was needed for this cinema follow-up.

**AA10c remains unstarted: from 25 Nov, sufficient recorded-sales evidence still required.** Neither the passing schedule nor elapsed time waives its evidence or owner gates.

## Exact proposed current-state corrections — not applied

Historical 7 Nov and pre-08:00 reports remain intact. Update only current-state records in a separately authorised documentation action.

**STATUS.md Now and the AC6 ledger row/heading note:** replace the current “No scheduled AC6 run has happened since deployment” / all-digest-tables-zero wording with:

> **8 Nov 11:33 GMT:** the first natural post-deployment cron refresh ran 08:02:47–08:04:30, terminal partial, all nine venue observations successful, 29 metadata lookups pending. The 8 Nov digest day evaluated with 0 appearances/recipients; cinema outbox and delivery claims remain 0. A separate 7 Nov `missed_day` marker is not another current-day evaluation. Empty-day silence is proved for observed partial coverage; positive scheduled delivery and Craig's phone receipt/tap remain unverified. AC6 stays unstruck.

**AC3 ledger row and STATUS.md's “read back after the 8 Nov run” commitment:** append:

> **Read back 8 Nov at 11:33 GMT:** 8 confirmed future Rocky reruns, TMDB 1366, across all four ODEONs; stored reason UK release 1977 · rerun. Current eligible future programme has 1,134 first-run / 8 rerun / 247 unclassified showings. The run reports 29 pending metadata lookups; 27 future source-film rows remain unverified and 9 remain in review, covering Ramayana, Tabby McTat and The Devils. Positive production rerun classification is now proved; phone/UI acceptance and remaining identities stay separate.

**OWNER-ACTIONS.md AC6 item:** replace its wait-for-first-run clause with:

> First natural evaluation read back 8 Nov: empty qualifying day, no message attempted. Wait for a genuine qualifying appearance and scheduled outbox/claim/transport result; do not create a test send. Craig observes phone receipt and the tap into New this week when a natural message arrives.

**Earlier outstanding-work inventory:** its pre-follow-up cinema counts and two-title review example are historical. The current review title set is Ramayana, Tabby McTat and The Devils; the current rerun read-back is positive. Preserve the inventory's other deferred work and AA10c gates. AA10b corrections proposed in the earlier report remain unapplied; do not invent a new re-pricing task.

## What is now proved

Current main/API/web SHA parity, seven-job exact-SHA CI and full readiness; natural post-deployment refresh completion; a correctly recorded empty 8 Nov digest evaluation with zero sends/claims; and eight future AC3 Rocky rerun classifications with stored reasons.

## What remains unverified or blocked

Positive AC6 qualifying appearance/outbox/claim/transport evidence and actual-phone receipt/tap. Source completeness remains partial. Metadata has 29 pending lookups; source identities and review choices remain unresolved as above. No new production defect was established by the empty digest or the approved baseline handling.

## Craig's observations or decisions

No test push or manual refresh is requested. When a genuine qualifying digest arrives, Craig observes receipt and whether the tap opens New this week. Identity mapping decisions for the review titles need candidate/evidence inspection before an owner pick; this report proposes no mapping. AC5's first real trip and other owner observations remain separate.

## Recommended next bounded task

First, reconcile the current status/ledger with these saved facts in a documentation-only sitting, preserving both earlier reports and their time-qualified observations. No implementation or production mutation is needed for that correction.

For further positive AC6 evidence, the next reasonable read-only checkpoint is **after the natural 9 Nov 08:00 command has finished**, provided it records a terminal run. Read its frozen day/appearances, then outbox/held targets/claims and actual transport outcomes; an empty result leaves positive acceptance open. No refresh or send is to be triggered. Expected read-only effort **10–20 minutes**, with no extra cinema/TMDB/eBay requests. This follow-up is **not scheduled automatically** by this one-shot session.

Stop after this report. No new batch, close-out, commit, push, merge or deployment.
