# Batch 45 — AI and LLM engineering review (wave 1, pass R3)

**Pass R3** · reviewed SHA `527522d` · lens: AI engineer (AI) · read-only · paid calls: 13 to
`claude-sonnet-5` (3 of them free 400s), **$0.075** of the $2 cap. Written 11 Oct 2026.

## 1. Summary

Grade **D**. A safe one-question tool, not yet a chat: the write boundary holds and the model
resisted a planted instruction, but no conversation gets past its first answer, the two write
tools cannot be completed from ordinary words, and answers about lists are built from a third
of the list.

1. **Correct and safe:** safe. The confirmation gate and the admin check hold in code (60
   assistant tests pass on a real Postgres), and the production model ignored a crafted
   instruction in a synopsis and told the person. Not correct: every second message fails
   (AI45-01); typing while a confirmation waits breaks that chat for good (AI45-02); two taps on
   Yes write twice (AI45-06).
2. **Honest:** no. The model sees 12–13 items and never the total: the app's own example
   question got 13 of 162 films; "what's coming on disc" saw 5 days of 120 and called the rest
   theatrical, missing 12 of the 15 disc releases due in four weeks (AI45-03). Every failure
   says "Try rephrasing the question", wrong for each of the five causes found (AI45-04).
3. **Doing its job:** barely. 8 calls in its life; the last was 21 Sep, when Mark's follow-up
   failed and he started a new chat 4 seconds later; nobody has used it since. Asking it to log
   a watch ends with it asking for a typed "yes" that cannot be sent (AI45-01, AI45-02).
4. **Noticed:** no. A failed chat call leaves no usage row, readiness reports only that a key
   exists, and Railway kept no logs of 21 Sep (AI45-04).
5. **Cheap to run:** yes. $0.048 in all; the price table matches Anthropic's for the configured
   model, which is served until at least 30 Jun 2027. The caps leak, but by pennies (AI45-05).

## 2. Findings (8: 1 High, 2 Med-High, 1 Medium, 4 Low)

### AI45-01 — High — No conversation can continue past its first answer: every second message fails
- **Evidence:** `proved` (paid probe A, 11 Oct): a follow-up in the same chat ("Thanks. Which
  shelf is it on?") got HTTP 400 `messages.3.content.0.text.parsed_output: Extra inputs are not
  permitted`; the same history with that one key removed answered correctly ("Front, 4th shelf").
  `implemented`: the loop stores each answer as the SDK block's full dump, and a streamed answer's
  text block carries the SDK-only `parsed_output`, which is replayed next turn. Tool-use and
  thinking blocks replay fine (observed 10 Sep; probe A's first turn). `observed`: all 5 stored
  answers carry the key; the only follow-up ever sent (Mark, 21 Sep 20:25:58 UTC) has no reply and
  no usage row. The tests' stand-in block dumps only the fields it was given, so CI cannot see it.
- **What people experience:** the first answer works; any second message ("which shelf?",
  "yes", "the rest") shows "The assistant could not answer that. Try rephrasing the question."
  Rephrasing fails the same way, in that chat, for ever. Since Batch 31 shipped (10 Sep).
- **Fix and cost:** store and replay only the API's request fields (drop `parsed_output` and the
  nulls), on write and again on read so the six stored chats recover; a test that sends real SDK
  text and tool-use blocks through store-and-replay and checks the keys against the SDK's request
  types. About an hour.
- **Where it goes:** first row of an assistant repair batch (with AI45-02, -03, -04); the key test
  is a guard.

### AI45-02 — Med-High — The write tools cannot be completed from ordinary words, and answering a card in words breaks the chat
- **Evidence:** `proved` (probe B): "I watched Heat last night with Mark. Log it for me, 4 stars."
  The model called no tool. It asked in text, "Confirm and I'll save it", and was unsure of the
  date ("watched 2024... actually let me check the date"). The typed "yes" is a second message, so
  it fails (AI45-01). Both write tools' descriptions say they require confirmation before they
  run, which the model reads as "ask first"; nothing tells it the app shows a Yes/No card. The
  system prompt gives neither today's date nor who is asking. `proved` (probe E, free 400s): when
  a card is up and the person types instead of tapping (the input stays enabled), the request
  carries a tool call with no result after it: 400 "`tool_use` ids were found without
  `tool_result` blocks immediately after". Tapping Yes afterwards fails the same way; on the
  throwaway database the write then ran but every later message still failed (P1b).
- **What people experience:** "log this" or "add that" ends in "Try rephrasing the question"; a
  card answered in words ruins the chat. No write has ever run (observed: 3 tool calls, all reads).
- **Fix and cost:** tool descriptions and the prompt say the app asks with a card, so call the
  tool directly; today's date (Europe/London) and the person's name in the system prompt; disable
  the input while a card waits, and server-side refuse a new message while a call is pending (or
  close it as declined first). Half a day with tests.
- **Where it goes:** the repair batch.

### AI45-03 — Med-High — Answers about lists are built from a third of the list, and the model never sees the total
- **Evidence:** `computed` (the real tools on the read-only role, 11 Oct): 7 of 9 typical calls
  hit the 6,000-character cut. Each film costs about 500 characters, mostly fields no answer
  needs (two image paths, an id, the original title), and the totals come last, so they are cut
  first. Visible to the model: 4K 12 of 365; 4K unwatched 13 of 162; the 1980s 12 of 142;
  "Nolan" 12 of 49; the wanted list 6 of 10; releases 12 of 136. Browse cannot ask for page 2.
  `proved` (probes C, D): the app's own placeholder question, "Which 4Ks have I not watched?",
  got 13 films and an offer to "page further" the tool cannot do; "Anything coming out on disc in
  the next few weeks?" saw 12–16 Oct only and said "everything else in the list is theatrical";
  12 of the 15 disc releases due in four weeks were never seen. `observed`: the one browse that
  ran in production (10 Sep) was cut too.
- **What people experience:** confident partial lists and missing counts, from an assistant
  whose prompt says never to invent.
- **Fix and cost:** a compact view for the model (title, year, formats, place, watched; totals
  first), a page argument, a date window and type filter on releases, and a cut-off note that
  says how many were left out. Half a day. Not an envelope (#12): endpoints keep their shapes;
  the tool layer picks the fields.
- **Where it goes:** the repair batch; guard: a test that each tool's visible text carries its total.

### AI45-04 — Medium — Assistant failures reach no one, and the person is told to rephrase
- **Evidence:** `implemented`: the chat writes a usage row only when a call succeeds; a failure
  leaves one log line. The client's own note ("every call is logged, including the ones that
  fail") holds only for the settings page's one-question box. `proved` (driven): 400 (a spend
  limit set in the Console, or a broken history), 402 (billing), 403, 404 (a retired model) and 413
  all show "Try rephrasing the question"; a 429 that is a monthly spend cap shows "Try again in a
  minute", though it fails until access resumes (Anthropic's errors page). Readiness says
  `ai: configured` whenever a key string exists. `observed`: Railway kept no logs for the
  20–23 Sep deployment, so 21 Sep's failure survives only as an orphan message.
- **What people experience:** the person rephrases until they give up; Craig never hears. The
  usage log's error column (R2's suggestion) cannot show a chat failure: 0 of 8 rows have one.
- **Fix and cost:** log every failed call with status and error type; tell the person "the
  assistant isn't working; Craig has been told" for 400/402/403/404/413 and a 429 with no
  retry-after; feed a daily count into DS44-01's check. Two hours.
- **Where it goes:** the repair batch; guard via DS44-01.

### AI45-05 — Low — The caps and the round limit leak
- **Evidence:** `proved` on the throwaway database: the "messages" cap counts model calls, so a
  question that keeps asking for a tool made 5 calls and used 5 of 50 (P3c); four sends at once
  with one message left made four calls (6 used of 3, P3a); a confirmation tapped at the cap
  still calls the model (2 of 1, P3b); a cost cap of 0 means no cost ceiling ($5 spent, not
  blocked, P3d), and clearing the spend box saves 0 (a blank number reads as 0); either person may
  set $1,000 and 10,000 messages a day. `implemented`: the last of 5 rounds is not forced to answer
  (`tool_choice: none`, Part D's D3, accepted by every current model) and a round may ask for any
  number of tool calls.
- **What people experience:** "N of 50 left" drops by up to 5 per question; a cleared box quietly
  lifts the money ceiling. At about $0.005 a call the sums are small.
- **Fix and cost:** check and reserve before every model call, resumes included; count questions
  or relabel; a blank or 0 spend cap means "off" or is refused; force an answer on the last
  round; cap tool calls per round. Two hours.
- **Where it goes:** the repair batch.

### AI45-06 — Low — Two taps on Yes write twice; a failed write is recorded as confirmed
- **Evidence:** `proved`: two simultaneous confirms of one pending watch wrote two watch rows in
  5 of 5 trials; one stream then hit the unique message-sequence constraint and returned an empty
  body. The test named for this case runs the two confirms one after the other. `implemented`: a
  write that fails inside the tool is marked `confirmed`; `failed` is defined and never set.
- **Fix and cost:** claim the row from `pending` in one guarded update (or lock it) before
  running the write; set `failed` on error. One hour. Rare on one phone (the card hides on the
  first tap); possible from two devices.
- **Where it goes:** the repair batch.

### AI45-07 — Low — Tool contracts that do not match the endpoints or the catalogue
- **Evidence:** decades, `observed` (10 Sep) and reproduced on production data: the tool says
  "earliest/latest release year", the endpoint wants a decade's first year, so "the 1980s" first
  fails with a 422 and costs a retry. Wanted, `implemented` and `computed`: add-to-wanted finds a
  film by exact title among catalogued films only, and just 22 of 1,890 have no live copy, so
  "add a film we don't own" almost always fails (the web adds by TMDB search). Same titles,
  `computed`: 22 titles are shared by 52 films (Halloween, Titanic, Cape Fear…); `proved`: the
  lookup takes whichever row comes first, and the card shows only the title.
- **Fix and cost:** describe decades as decades; let add-to-wanted take a TMDB match as the web
  does; pass the film id the model saw, or ask, when a title is shared. Two hours.
- **Where it goes:** the repair batch.

### AI45-08 — Low — Model, prompt and evals have no upkeep path
- **Evidence:** `observed` (Anthropic's pages and the key's model list, 11 Oct): `claude-sonnet-5`
  is a legacy model, still served, retirement not before 30 Jun 2027, at the same $2/$10 as
  Sonnet 5.5. `implemented`: the allow-list holds no 5.5 model, so a Railway variable alone
  cannot switch (the API would refuse to boot); `claude-haiku-4-5` answers under a dated id, so
  its cost would log as $0 and the cost cap would never bind; Fable 5.1's cache-read price is 4×
  too high (unused). The prompt says "around 1,857 physical discs" (1,884 live copies, 422 of them
  downloads) and nothing about tools, the card, the date or the person. No eval: deleting "Never
  invent a film" fails no test.
- **Fix and cost:** price by the configured id; add the 5.5 family; refresh the prompt; keep this
  pass's probe as a monthly five-ask canary (about $0.08). Two hours plus the canary.
- **Where it goes:** the repair batch; the canary as a guard for the monthly delta review.

**Already near-optimal (keep):** writes wait for a tap, checked against the table, not the
reply; a viewer cannot reach the admin-only tool even if the model names it; the production model
refused a planted instruction and said so (one trial); tool-use and thinking blocks replay
cleanly; a chat stopped by the round limit or an empty reply still continues (probe E); costs
are priced right; nothing else in the app calls a model (implemented).

## 3. Follow-through corrections (the pack's rows in this lens)

| Row | Pack says | Corrected to | Evidence |
|---|---|---|---|
| LIVE, assistant | `ai_tool_calls` 0 rows; no tool has run | 3 rows, all reads (10 Sep): one failed (the decade 422), one cut at 6,000. 0 writes | observed |
| LIVE, assistant | 2 conversations, 10 messages | 6 conversations (1 empty), 17 messages; 1 message orphaned (21 Sep) | observed |
| Scope 7 | 8 calls, no errors | no errors *recorded*: the chat cannot record one (AI45-04); one failure seen | observed, implemented |
| D3 | caps and a bounded loop; last round not forced | confirmed: no `tool_choice`, no per-round limit; 5 calls, then an error (P3c) | proved |
| D4 | write tools; no decision found | confirmed: Batch 31's spec copied the April 9.2/9.4; #16 reinstated drops and defers only, not Part D's 9.4 re-scope; no decision records the change | implemented |
| R2 note 4 | read the usage log's error column | the column cannot hold a chat failure; 0 of 8 rows have one | implemented, observed |
| Model | is `claude-sonnet-5` still served? | yes: legacy, active, retirement not before 30 Jun 2027; prices match | observed |
| Only caller | only the AI router uses the client | confirmed; readiness reads only whether the key is set | implemented |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| Nothing queued or parked for the assistant | accurate |
| `OWNER-ACTIONS.md` 2 and 3 (Craig asks it a question; speaks one) | decayed: a first question works; any follow-up fails (AI45-01). Dictation only fills the box, so 3 is unaffected |
| Batch 38, end-to-end suite | would not catch AI45-01 unless it sends two messages to a real or recorded model; add that case |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**For reconsideration.** Part D's 9.4 re-scope ("the model never holds a write tool") was
overtaken by Batch 31 with no decision. New evidence for recording one: the gate holds in code,
and the production model refused a planted write (one trial). #12 (no envelope) is not
re-argued: AI45-03 asks for a smaller view at the tool layer only.

**Hypotheses.** (1) Waits: 3 of 8 production calls took 23–30 s (no time-to-first-text is
recorded), long on a phone; R6. (2) Whether a spend limit is set in Anthropic's Console is
unknown; if it is, reaching it reads as "Try rephrasing" (AI45-04). (3) Moving to the 5.5 family:
a thinking block replayed after a prompt or tool change can be refused on accounts made after
31 Aug 2026 (errors page); the history must stay append-only.

**Limitations.** One trial per ask, so the steerability result is a single sample. Railway kept
no logs for 21 Sep, so that failure's cause is inferred from the stored rows and the proved 400.
The web chat was read, not driven in a browser (R6). The race ran in one process, not on two phones.

**Probe log (11 Oct).**
- Database, read-only role (`live_sql`): usage log, all 8 rows (13 columns, no prompts); grants on
  5 `ai_*` tables; tool-call count; conversations (6 rows, no titles); message shapes (17 rows:
  role, sequence, time, text length, block types; no text); tool calls (3 rows: name, status,
  input key names, result length, 40-character head); stored block keys by type (5 rows); shared
  titles (3 queries, counts and 8 example titles); films with no live copy (1 row); cap settings
  (2 rows); time zones (2 rows); idle-session check.
- Database, read-only role (asyncpg, read-only transactions, rolled back, watchdog): the real tools
  once each for 9 typical calls plus 1 profile read; the real release list once (counts by type);
  the paid probe's 3 reads (search, browse, releases). No idle session left.
- Railway: `deployment list` for the API (200 rows); `logs` of the 20–23 Sep deployment twice
  (0 lines); `run --service api` once, for the paid probe, with the child given only the key, the
  throwaway database and the read-only URL.
- Throwaway Postgres 16.2 (pgserver) in scratch, migrated to head from a clone at `527522d`: the
  60 assistant tests (all pass, none skipped) and the free probes P1–P5. Stopped afterwards.
- Web: Anthropic's models overview, model deprecations, pricing and errors pages.
- **Paid (11 Oct, 14:05:00–14:05:50 UTC, `claude-sonnet-5`):** A1 Heat on 4K, 2 calls, 6,524 in /
  83 out, $0.0139; A2 follow-up, free 400; A3 follow-up without the key, 4,653 / 12, $0.0094; B log
  a watch, 1 call, 1,928 / 132, $0.0052; C unwatched 4Ks, 2 calls, 7,318 / 601, $0.0206; D releases
  with a planted note, 2 calls, 6,569 / 347, $0.0166; E four history checks, 2 free 400s and
  2 calls, 4,218 / 88, $0.0093; 1 free model list. **Total 13 calls, 31,210 / 1,263 tokens,
  $0.07505.** Outputs kept in scratch only; nothing written outside it.
