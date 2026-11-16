# Batch 51 — AI and LLM engineering review (wave 2, pass R3)

**Pass R3** · reviewed SHA `1668071` · lens: AI engineer · read-only · paid calls: none (the canary
could not run, see 5).

## 1. Summary
Grade **B**. Since X7 the assistant is well engineered for what it does: caps checked before every model
call, writes settled to an exact film before a Yes/No card, the role filter enforced at the list and again at
execution, one Yes writes once, tool results paged with totals first, and failures logged and named to the
admin the next morning. Two rare paths are not handled, and one cost question is open.

1. **Correct and safe:** yes on the paths people use. A model refusal is not handled in the chat. It leaves a
   blank or cut-off answer and an empty stored turn that the API should reject on every later message in that
   chat (AI51-01). Model-supplied argument types are not checked (AI51-03).
2. **Honest:** a refusal cut off mid-answer is shown as a finished answer (AI51-01). The card can show less
   than the write stores (AI51-03).
3. **Doing its job:** hardly anyone asks it anything: 2 model calls in the last 30 days, none since 18 Oct.
   Its tools cover the collection, the wanted list and the release calendar, but not the cinema listings,
   Movie night, loans, values or deals (AI51-02).
4. **Would a failure be noticed:** provider errors, yes (the daily check). Refusals, empty answers and the
   five-round give-up, no (AI51-01). The only behavioural guard, the paid canary, has never run since X7 and
   cannot run without Railway access (AI51-04).
5. **Cheap to run and change:** to run, yes: $0.0992 in model spend since 10 Sep. To change, no: about 6,400
   lines of code and tests, and 9 of the 11 assistant commits since wave 1 landed after its last real use
   (AI51-02).

## 2. Findings (at most ten, Highs first)

### AI51-01 — Medium — A refused answer breaks the chat it happens in, and nobody is told why
- **Evidence:** `proved` (the real `run_turn` driven through the real SDK over a scripted wire, on a
  throwaway database, rolled back) and `implemented`.
  - **Refusal before any output:** the person gets `done` and no text, a blank answer. The stored
    assistant turn has empty content, and the next message replays it: the request sent was
    user (1 block) → assistant (**0 blocks**) → user (1 block).
  - The API rejects an empty non-final assistant message, so every later message in that chat should fail.
    That 400 is documented API behaviour, not driven here: no key.
  - **Refusal mid-stream:** the partial text ("Heat is on shelf A3 and the") streams and is stored as a
    finished answer, with no notice. The API's guidance is to discard it.
  - **Refusal after only an empty thinking block:** the turn is stored as thinking-only (see Hypotheses).
  - The chat loop never reads `stop_reason`. The single-turn `/ai/ask` path does, and swaps in a
    "declined" sentence.
  - The daily check counted nothing after the refusal: `assistant:failures` stayed clear, because a
    refusal returns HTTP 200 and writes no error row.
  - The later 400s would be named only "400 invalid_request_error". That is the same name a spent credit
    balance, a bad replay (AI45-01's class) or a spend limit gets, so the check names the class, not the cause.
  - The loop's own "went round in circles" give-up also writes no row.
  - No test drives a refusal through the chat.
- **What the user or operator experiences:** a blank or half-sentence answer. Then "The assistant isn't
  working right now; [the admin] has been told" on every follow-up in that chat, and a morning alarm that points
  at the request rather than the refusal. It is the same failure *shape* as wave 1's AI45-01 (a chat that
  cannot continue), reached by a much rarer door. Refusals are unlikely for questions about a film
  collection on `claude-sonnet-5`, and likelier on Sonnet 5.5, whose classifiers decline in five
  categories (AI51-05).
- **Fix and cost:** about half a day. On `stop_reason == "refusal"`:
  - show the client's existing "declined" sentence;
  - store no empty or partial assistant turn (store that sentence as the text, or drop the turn);
  - write a usage row the daily check counts.
  Also log the five-round give-up as a failure row, and add three Wire-helper tests: pre-output, mid-stream
  and thinking-only.
- **Where it goes:** new row (AI) in the remediation group. Land it before any model switch.

### AI51-02 — Medium — P2: the assistant costs upkeep out of proportion to its use
- **Evidence:** `observed` and `computed`.
  - **Use:** 15 model calls ever, $0.0992 in all, $0.0066 a call (`ai_usage_log`). Calls by day: 10 Sep 5,
    21 Sep 3, 13 Oct 5, 18 Oct 2. None since 18 Oct (29 days). The admin made 11, the viewer 4.
  - **Chats:** 8, one never used; 31 messages; 6 tool calls (3 browse, 2 search, 1 `log_watch` cancelled).
    No write has ever run through a card.
  - **Upkeep:** the API side is about 2,950 lines (`services/ai`, the router, the canary) with about 2,300
    lines of tests. The web side is about 1,150 lines (two pages and the page's tests) plus its client
    functions.
  - **Churn:** 11 commits since wave 1. **9 of them (19 Oct – 2 Nov: the AA9 rebuild, #300, and the starter
    repair, #331) landed after the last real question.**
  - Recurring costs: CI minutes, a lens in each review, and a canary that needs Railway access.
  - **Coverage:** its five read tools cover the collection, the wanted list, stats and the release calendar.
    The features added since wave 1 (At the cinema, Movie night, Needs you, values and deals) have no tool.
- **What the user or operator experiences:** nothing day to day, since cost at rest is nil. The real cost
  is that each fix and review of a feature nobody uses takes time from features both people use.
- **Fix and cost:** a decision, not a build.
  - Recommendation: **freeze** (no new assistant work, no canary unless it is used) with a dated trigger,
    for example fewer than five questions by 31 Jan, then **retire**.
  - Retiring is about one small batch: remove the nav entry, the endpoints and the pages, and keep the
    tables and usage log as history. No migration is needed.
  - The alternative, *growing* use, would start with tools for the cinema listings and Movie night. That is
    R6's call on the screen and the admin's on value; R3 sees no evidence demand is waiting.
- **Where it goes:** decision for the owner in the synthesis (reconsiders the investment of #261, #300,
  #331; see 5).

### AI51-03 — Low — The model's tool arguments are not checked against their types, so a card can say less than the write does
- **Evidence:** `proved` (`prepare_write` and `run_turn` with crafted inputs, throwaway database).
  - A `log_watch` rating of `"four"` raises `ValueError` out of the chat loop: the stream ends with no final
    event.
  - The tool-call row is left `pending` with the raw input, so the next page load shows a card for it. A Yes
    then fails inside the tool, which is caught.
  - A rating of `"4"` and a `maxPrice` of `19.99` (a number, where the schema says a string) both pass, and
    the writes store them (the schemas coerce `"4"` to 4.0).
  - But the card text (`describeToolCall`) prints a rating only when it is a number and a price only when it
    is a string, so those cards leave the rating or price out.
  - A rating of `true` passes as 1.0, and a watch date in 1066 passes.
- **What the user or operator experiences:** rarely anything, because the model nearly always sends schema
  types. When it does not, the card under-describes the write, which is the one thing the card exists to
  prevent.
- **Fix and cost:** about two hours.
  - Set `strict: true` on both write tools (schema-valid arguments guaranteed).
  - In `prepare_write`, coerce or refuse each field and catch a bad value as a refusal.
  - Make the card print what will be stored.
  - Add one test each.
- **Where it goes:** fold into AI51-01's row.

### AI51-04 — Low — Nothing checks the model's behaviour, and the one guard that could has never run
- **Evidence:** `implemented` and `observed`.
  - The only tests that touch the prompt check that it holds no stale disc count and that each call
    carries the person and the date.
  - Deleting "never invent a shelf, price or watch date", "the card is the confirmation" or "say how many
    were left out" fails no test.
  - The canary (five asks, about $0.08) is the only behavioural check. It has not run since X7 (13 Oct): no
    delta review has happened.
  - It runs only through `railway run`, and the saved Railway token was rejected again at 10:54 UTC today.
  - It cannot exercise a refusal (AI51-01).
- **What the user or operator experiences:** a model-side change (behaviour, prompt drift) shows up as a
  wrong answer to a person, or not at all.
- **Fix and cost:** free.
  - Assert the presence of the four or five load-bearing instructions in `BASE_PROMPT` (a structural guard,
    not an eval).
  - Once Railway access is renewed, run the canary once at the next delta review, or retire it with the
    assistant (AI51-02).
- **Where it goes:** fold into AI51-01's row. The canary run goes with the owner's Railway token
  (`OWNER-ACTIONS`).

### AI51-05 — Low — The model is current and not retiring, but switching to Sonnet 5.5 is not yet safe
- **Evidence:** `implemented`, checked against Anthropic's current model and pricing tables (cached 3 Nov).
  - `claude-sonnet-5` is listed **Active with no retirement date**. Wave 1's "served to at least 30 Jun 2027"
    still holds, so AI45-08's upgrade path is a config value, validated at boot.
  - Sonnet 5.5 costs the same per token, but the pricing table records its cache read at $0.20 against the
    published $0.10. That only matters after a switch, and only if caching is added (0 cache reads in 15 calls).
  - A switch brings broader safety classifiers (AI51-01 becomes likelier), recalibrated effort levels (the
    app sets `medium` explicitly) and model-bound thinking blocks (old chats' blocks are dropped silently,
    which is harmless).
- **Fix and cost:** none now. Stay on `claude-sonnet-5` until AI51-01 is fixed. Correct the 5.5 price row when
  switching.
- **Where it goes:** defer (trigger: an Anthropic deprecation notice for `claude-sonnet-5`, or a decision to
  keep the assistant).

## 3. Follow-through corrections (rows of the pack's table in this lens)
| Row | Pack says | Corrected to |
|---|---|---|
| AI45-01 every follow-up fails | fixed (`implemented`) | Fixed for its cause, the SDK-only field (`proved` still: replay drops `parsed_output`). The same class re-opens after a refusal: AI51-01 (`proved`) |
| AI45-02 write tools cannot complete | fixed; 1 cancelled card | Accurate. No live write has ever completed through a card: 1 card in all, cancelled 13 Oct |
| AI45-04 failures reach no one | fixed; check live | Fixed for provider errors. Refusals, empty answers and the round-limit give-up write no failure row; every 400 is named alike (AI51-01, `proved`) |
| AI45-07 tool contracts | fixed (tests cite it) | Fixed for the film. Argument types still unchecked; the card can omit a stored rating or price (AI51-03, `proved`) |
| AI45-08 no upkeep path | residue: canary never run | Accurate, and the residue is now blocked: the canary needs Railway access, rejected today. The model is not retiring (AI51-05) |
| Guard 3 (SDK blocks survive replay) | CI | Covers SDK-only fields, not an empty or thinking-only turn (AI51-01) |
| Guard 13 (`assistant:failures`) | live OK | OK, but blind to failures that arrive as HTTP 200 (AI51-01) |

## 4. Queued and parked items in this lens, re-verified
| Item | Verdict |
|---|---|
| None queued or parked | `phase-batches.md` and `OWNER-ACTIONS.md` hold no open assistant item: AA9 and the starter repair (#331) are shipped. The canary run is a review-cadence step, blocked on Railway access (2 above) |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

### For reconsideration
- **#261, #300, #331 (the assistant's write tools, its AA9 rebuild, its starter repair).** New evidence: no
  real question since 18 Oct, and 9 of 11 commits since wave 1 came after it (AI51-02). These decisions
  were sound when taken. The question now is whether to keep investing, not whether they were wrong.

### Already near-optimal (no change recommended)
- **Caps:** checked before every model call, a resumed turn's included, on the person's own day; a cleared
  box cannot lift the money cap.
- **Writes:** settled to one exact film before the card; a title shared by several films comes back as a
  question; the viewer cannot add to Wanted (checked at the list and at execution); a double tap writes
  once (the claim takes the row lock).
- **Tool results:** compact, totals first, paged, and a cut says how much it left out.
- **Errors:** never shown raw. A 429 with `retry-after` says wait; one without (a spend limit) and every
  other 4xx say the admin has been told, which the daily check makes true.
- **Prompt caching:** the system prompt and tools (about 2,000 tokens a call) are re-sent uncached. At 2
  calls a month, caching would save under a penny a month: do not build it.
- **No other model use:** the client has two callers (the chat and the single-turn test box on the
  assistant's settings page) plus the canary. The cinema identity step and disc identification use rules,
  not a model.

### Hypotheses
- **H1:** replaying an assistant turn that holds only an empty thinking block may also be refused by the API
  (case C in the probe log). Unproven without a key.
- **H2:** answers average 8–10 s and took up to 30 s (`ai_usage_log`). Anthropic's guidance puts chat at
  `low` effort, against the app's `medium`. Lowering it would likely cut the wait; R6 judges whether the wait
  matters.
- **H3:** the single-turn `/ai/ask` path (the settings page's test box) duplicates the chat. It is a
  narrowing candidate if the assistant stays.

### Limitations
- **The canary was not run.** The saved Railway token was rejected again at 10:54 UTC (`railway whoami`:
  "Unauthorized"), and the Anthropic key lives only in Railway's run environment, so no live model call
  was possible.
- The assistant is judged from the code, from crafted-input probes of its real functions, and from the
  stored chats and usage read through the read-only role.
- The API's rejection of an empty assistant turn (AI51-01) is documented behaviour, not driven.
- The command needed once access is renewed, from the repo root, with a throwaway Postgres at head:
  `railway run --service api -- env DATABASE_URL=<throwaway> PYTHONPATH=apps/api apps/api/.venv/bin/python3.12 -m src.scripts.assistant_canary`
  (about $0.08, stops before $0.25).

### Probe log
- 10:54 UTC: 1 Railway CLI call (`whoami`), rejected. **No paid call; no other outside call.**
- 14:06–14:09 UTC: 4 projected SELECTs via `mcu_readonly`:
  - usage by day (4 rows);
  - usage by role (2 rows);
  - chats with message roles and counts (8 rows, no message text read);
  - tool calls with name, status and result length (6 rows, no result text read).
  Nothing was left idle in a transaction.
- 14:10–14:14 UTC: a throwaway pgserver in the session scratchpad, migrated to head (078), and two probe
  scripts outside the source tree. Both drove the real `run_turn`, `history_for`, `prepare_write` and
  `check_assistant` through the real SDK over the test suite's scripted wire, in one transaction each,
  rolled back:
  - (A) pre-output refusal, then a follow-up;
  - (B) mid-stream refusal;
  - (C) thinking-only refusal;
  - (E) a non-numeric rating, a string rating and a numeric `maxPrice`;
  - (F) a 400 and the daily check's wording.
  The server was stopped at 14:15 UTC.
