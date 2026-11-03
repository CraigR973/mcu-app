# AB6 verification after the separate assistant repair — 3 Nov

AB6 remains draft PR #125. The approved source/build amendment (#330) is implemented;
this report does not accept fresh cinema feasibility, import mappings, enable a venue or
close out AB6. No new cinema/TMDB request or production cinema action was performed.

## Repair prerequisite completed

Owner-approved #331 repair shipped separately in PR #126 as 7b67375. Browser/event/geometry
evidence established that empty-chat scrolling inserted Latest answer, shrinking the log
by 48px and clipping the measured click point. Following/latest now require messages;
starters still fill/focus the draft and Send stays explicit. Both regressions fail before
and pass after. Original assertions, timeouts and skips remain unchanged.

All ten repair checks/full local suites and all seven exact PR/merged-code/final-doc jobs
pass (41512031733, 41545752108, 41545982931). Final green main and production API/web serve
6d0f676, db ok and push/ai/ebay/tmdb/brave configured. Served assistant bundle contains the
guard. Physical-phone keyboard/speech and a live-model follow-up remain owner acceptance.
Full repair cause/failures/evidence are in assistant-starter-repair-2026-11-02.md and PR #126.

## Combined AB6 tree verified

Green main merged normally into preserved feat/ab6-cinema-ingestion as
5b02ab8a3dbeeb37ad65ee85f961fff276d1a1e6. STATUS/DECISIONS conflicted; both histories and
all decisions 328–331 were retained. App/tests merged without conflict. Cinema API/shared/
hosting/job code is identical to amended 5800f5d; assistant page/tests match green main.
No source-feasibility or application scope was changed during integration.

Clean 5b02ab8 passes all ten local commands: API 2,609/zero skips, shared 167, web 738,
API/web/shared lint/types/format/build. Full local E2E starts and ends on that exact commit:
Chromium 62 passed; Firefox 61 plus its documented dictation skip; jobs six passed, no
retries/new skips. The jobs exercise the real reminder entry point with nine disabled
cinema venues, zero cinema runs and zero cinema-provider calls. This proves fixture-backed
isolation, not actual source coverage. Mark's 375×500 combined-tree capture was inspected:
filled/focused question, reachable Send, no Latest answer on the empty chat.

Exact-head PR CI 41547976591 passes all seven jobs, including API 2,609/no skips,
Chromium 62, Firefox 61 plus one documented skip, WebKit 60 plus its two documented skips,
and jobs six. Migration reversal and actual image build/migrate/boot pass. Existing local
migration/grant/credential-withholding/populated-rollback-refusal proof remains unchanged
with the identical cinema schema; no production database was connected.

Portable counts, clean-head evidence, code boundaries and capture hashes are in
ab6-post-assistant-verification-2026-11-03.json. Final documentation-head CI is checked and
recorded in PR #125 before handoff; code proof above is not a claim that a later head was
already checked. No new application/test failure was found during this integration.

## Acceptance and unresolved owner stops

| Criterion | Evidence/current limit |
|---|---|
| Approved ingestion/schema/job/read API | Ten local checks, seven PR jobs and unchanged migration proof pass |
| Reported assistant failure | Separate proved repair; original and added cases pass on the combined tree |
| Fresh all-nine coverage/identity/run categories | Unproved: no new source read; New releases population remains unproved |
| Exact config/import/mapping/enable | Never applied/run; nine disabled venues; all remain owner decisions |
| Discovery UI and other sittings | AB7, AA10c and all other sittings unstarted |

The next concrete proposal is ab6-next-acceptance-read.md: one £0-source-fee bounded
all-nine pass in an owned disposable localhost database, execution day through +13 London
dates, Vue execution day/tomorrow only; at most 120 GETs total including 12 TMDB metadata
GETs, five minutes/15 seconds/2 MiB per response/64 MiB total/two global slots/one start per
second per host. Refusal stops the host, no retry/alternate. Save artifact/hash/counts/
horizons/categories/identity evidence/backlog. No mapping is accepted by this build or read
proposal. Existing compute/network/quota use remains unpriced.

This fresh read is **unapproved**. The prior #328/#329 reads and #330/#331 builds are already
accepted/completed; do not ask to repeat those decisions. After any approved new read,
review actual source/row/category/mapping evidence and re-plan before implementation if
feasibility changes scope. Exact Railway plan apply, disabled deployment if needed,
production import/selected mappings and nine-row enable remain later separate stops.
Source fees £0 does not guarantee no existing-hosting invoice increase. Keep PR #125 draft;
do not merge/close AB6, deploy or start AB7 from fixture/CI success alone.

Historical failures and fixes remain in the metadata amendment report and the separate
assistant repair report. Read-only inspection initially requested a nonexistent cinema
script filename; tree lookup located refresh_cinemas.py. No module was executed by that
inspection. No credentials, source samples or production data were exposed/changed.
