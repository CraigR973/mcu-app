# The assistant page — review for Craig (AA9)

27 Oct 2026 · current source and production baseline `b904457fbc1641c3fcc4eb62128ac0740c07d17a`

**Recommendation: Conversation first, with the shared corrections below.**
Keep asking a question as the main job. Give a new visitor three usable examples, make recent
chats one clear action, and keep a multiline draft beneath the answer. Preserve the existing
server confirmation boundary and both people's private conversations.

[Compare the three interactive layouts](aa9-assistant-mockups-2026-10-27.html).
They are proposals, not screenshots of the current app. The sample replies, dates, allowance
and chat history are illustrative; The Quiet Engine is from the disposable test catalogue.
No question in these mock-ups reaches a model, and confirming their sample card writes nothing.
The app shell is schematic. Native dictation is retained wherever supported in any eventual
build; its real permission and recognition behaviour is not simulated here.

## Acceptance and stop point

The AA9 criterion, verbatim:

> As AA3: a review report first, then a build planned from Craig's picks.

AA3's referenced method, verbatim:

> A UI/UX review of Home's collection row as its own report (`docs/reviews/`), with mock-ups, sent
> to Craig; the build is planned from his picks. No code before his picks.

At delivery this was the review/report/mock-up stage, with no build plan or product code.
The run stopped for Craig's picks. He then selected Conversation first and Include shared
corrections (#300); only then was `aa9-build-plan-2026-10-27.md` written and implementation
started. `aa9-verification-2026-10-27.md` carries the subsequent build evidence. Findings below
describe the baseline at review time. Sitting 6 remains excluded.

## What exists today

The assistant is a dedicated page, reached from the existing top-bar robot button, sidebar
and You page. The five mobile navigation slots are settled (#201/#221); this review does
not propose a sixth tab or a floating button.

On desktop, a conversation sidebar sits beside the transcript. On phones, a native
conversation select plus new/delete icons sits above a second Assistant/chat heading and
allowance label. A single-line input, optional dictation button and send button sit beneath
the internally scrolling transcript. Replies stream into ordinary text bubbles.

Five read tools search/browse the collection, read Wanted, return collection stats and read
upcoming releases. Both people may log their own viewing after confirmation. **Only Craig
may add to shared Wanted through the assistant.** The server filters tools by role and
checks permissions again at execution. Saved chats belong to the signed-in person.
The latest 50 conversations are returned; there is no history search or pagination.

Existing protections worth retaining: the card settles the exact film/year before asking;
No declines the change; the message box stays locked while cards wait; cards survive a
return visit; stale conversation reads cannot erase a newly streamed card (#287). Dictation
fills a draft and never sends it. The cap and execution permission checks stay on the server.

## Findings, in decision order

### 1. A first visit can be blank; the later guidance over-promises to Mark

**Confirmed source defect plus a local state probe.** With no selected conversation, the
detail query is disabled. The installed query library reports `isPending: true` and
`fetchStatus: idle` for that state. The introduction requires `!detail.isPending`, so it is
hidden on the ordinary `/assistant` landing screen. Creating an empty chat first lets that
introduction appear. There are no starter prompts.

That same introduction says it can add to Wanted for everyone, while the server only gives
that tool to Craig. Replace it with role-aware capability guidance. Proposed examples fill
the draft; **they do not submit automatically**. “Log a viewing” still leads to the existing
exact-film confirmation, rather than bypassing it.

### 2. The allowance and availability states are less useful than the API already allows

**Confirmed source finding.** The header says “N of 50 left today”. The count is successful
model calls, not questions: tool rounds and the continuation after confirmation can spend
more than one call. Decision #262 explicitly retained the old wording; changing it is a new
owner pick, not an automatic reinterpretation of that decision.

The response already supplies `blocked`, `limitMessage`, spending limits and `resetsAt`.
This page only draws the remaining-call count. A spending cap may therefore stop the next
question while the header still shows calls left. The server will refuse correctly, but the
page waits for that failed send instead of showing the known limit first.

The page draws the unconfigured-server warning but leaves Send enabled. Status and usage
load failures have no specific page treatment. Proposed behaviour: “AI calls left today”,
a short explanation that a question can use several calls, and the applicable limit/reset
or unavailable state beside the draft. Preserve drafts and saved-history access. **No cap,
price, model, allowance algorithm or Railway variable changes.** A failed status request
must say availability is unknown rather than pretending the server has no key.

### 3. A reply and the conversation controls need one coherent lifecycle

**Source hazard; not reproduced in a browser.** New chat, select and delete remain enabled
while an answer streams. Selecting a chat clears local transcript/card state, but the
existing stream still appends to those same state variables. A finishing reply can therefore
appear under a different selected chat; confirmation cards and subsequent refreshes also
need to remain tied to their originating conversation.

The page also scrolls to the bottom on every arriving text fragment. It does not distinguish
somebody following the latest answer from somebody scrolling up to read an earlier turn.
There is no Stop control or documented stop/commit contract.

Recommend a conservative first pass: prevent switching/deleting chats during an active
reply, clearly say the assistant is answering, and follow new text only while the person
is already near the bottom. Keep the existing card-race protection and server persistence.
**Do not add a cosmetic Stop button, automatic resend or optimistic rollback.** Those could
promise cancellation or undo the server does not provide. If later planning finds an API
change necessary, describe it and stop for that decision before implementation.

### 4. Phone layout and history need less competing chrome

**Confirmed layout structure; device effect remains unverified.** Phones get a conversation
picker, separate create/delete icons, the app's Assistant top bar, another large heading and
the allowance. A title can be 80 characters. The heading and allowance share a flex row with
no explicit title wrapping/truncation policy. The message box itself is one line, up to
4,000 characters.

The page sizes itself from the entire viewport inside a shell that already reserves a top
bar and bottom navigation, and the transcript scrolls separately. This is a concrete risk
for a composer under the bottom bar or keyboard; **this review did not measure that overlap
on the current rendered app**. The minimum page height is 32 rem, so small/keyboard-shortened
viewports need particular care. The later build must prove the composer, last answer and
confirmation actions at narrow/short heights, with physical iPhone keyboard checks left to Craig.

Recommend one compact chat toolbar, a named Recent chats control, a multiline draft and a
layout that uses the space the shell actually gives it. A history panel can show existing
`updatedAt` dates and readable titles. It should describe these as recent chats, rather than
implying unlimited searchable history. Search/pagination is not proposed for free.

### 5. Phone history errors and deletion need explicit recovery

**Confirmed source findings.** The conversation-list error is rendered only in the desktop
sidebar, which is hidden on phones. The mobile picker silently falls back to “New
conversation” when history fails to load. A selected-chat loading error is visible, but the
page provides no dedicated reload control.

Delete immediately soft-deletes the chat. The server retains usage separately and has no
restore endpoint; the product offers no undo. Deleting a chat **does not undo** a viewing or
Wanted addition already confirmed within it. A saved-record deletion is not performed by
this review. Recommend an explicit named-chat confirmation with that consequence stated.
Do not promise Undo or silently alter existing stored history.

The draft clears before the stream completes. A failed answer leaves the question in a
local bubble, but no controlled recovery action. Recommend keeping/restoring the draft and
reloading stored state before offering a resend; an interrupted answer might already have
committed. Preserve the difference between “not sent”, “answer interrupted” and a server
refusal. Exact retry/idempotency behaviour must be settled in the later plan, not guessed.

### 6. Reading an answer should not require decoding model formatting

**Confirmed rendering behaviour, not a live-model observation.** Replies are escaped plain
text with preserved whitespace. Markdown markers and URLs would be printed as text;
headings, lists and film links have no special presentation. The mock-up shows restrained
paragraphs and emphasis as a proposed reading treatment.

Recommend safe basic formatting and ordinary links if the returned text contains them;
never execute raw HTML. This is not permission to fabricate film cards from guessed titles,
add structured model output or change the message contract. Rich film cards, catalogue
navigation inferred from arbitrary prose, citations/provenance that the current response
never supplies, and new assistant tools are outside this review's recommendation.

## Three layouts to choose from

| Layout | Main benefit | Real compromise |
|---|---|---|
| **Conversation first — recommended** | Draft and transcript are the centre; three fillable examples for a new chat; Recent chats opens when needed | Returning to an older chat takes one tap |
| Task first | Four named intentions make the assistant's uses visible before typing | More landing-page space and an extra choice before an ordinary question |
| History first | Recent conversations are immediately visible; easy to continue an ongoing thread | A first-time visitor sees more history structure; free asking is less prominent |

These are alternatives for the same assistant page, not extra routes. All retain free text,
private chats, role-aware capabilities, optional dictation, explicit write confirmation and
the existing five bottom tabs. Desktop can retain a recent-chat sidebar without creating a
new information model. The mock-ups focus on phone decisions; they do not prove iOS keyboard
behaviour or a completed desktop implementation.

The common corrections do not require a migration, provider request, new tool, model change,
spending-limit change or known new endpoint. They still have engineering cost: roughly
**3–6 agent hours plus CI/deployment waiting**, with more work around stream/history isolation and
recovery than a cosmetic re-skin; the later plan may revise this estimate. That is a comparative estimate, **not a build plan or a
promise**. Task first adds starter/draft interaction work; History first adds history-panel
work. Any contract change discovered later needs its own concrete approval.

## Picks requested — stop here

1. **Layout:** Conversation first (recommended), Task first or History first. Conversation
   first keeps free asking direct and costs one tap for older chats. The alternatives trade
   that for more visible task choices or history. All preserve the current app navigation.
2. **Shared corrections:** approve role-aware starter guidance, truthful call/limit states,
   visible history/load failures, a multiline preserved draft, conservative stream/chat
   isolation, named-chat deletion confirmation and safe answer formatting (recommended), or
   request a narrower presentation pass. The correct option costs extra lifecycle/error-state
   work and regression coverage; it changes no cap, role, model, stored conversation or API
   contract under this proposal. A narrower pass leaves the specified defects in place.

After these picks, the next step is the concrete build plan under the existing group
authorisation. Any newly discovered consequential change needs its own decision before
implementation. This review does not start that plan.

## Evidence, checks and limits

- **Baseline:** clean `main`, fetched and equal to `origin/main`, with AA3's ledger struck and
  close-out pushed before AA9's separate branch. All seven final-head jobs passed in
  [40535930619](https://github.com/CraigR973/mcu-app/actions/runs/40535930619) at `b904457`.
  Chromium 41, Firefox 40 plus the documented dictation skip, WebKit 39 plus its two existing
  documented skips, jobs six. Production API and web both served the exact baseline SHA;
  db ready and all five integrations configured. No authenticated production chat, model
  request or production data write was performed.
- **Baseline CI delay:** attempt 1 was cancelled during Ubuntu browser-dependency downloads
  after more than 10 minutes; the browser suite had not started. Retried the same final
  commit once, with no changed check, assertion or skip. The second runner also downloaded
  slowly, then completed the full suite successfully. This was an infrastructure restart,
  not a browser-test retry. Six other jobs had already passed and remain green.
- **Source:** current assistant page, API client, role-filtered read/write tools, usage/caps,
  chat storage/title/deletion, shell, mobile navigation, dictation, component tests and the
  existing end-to-end chat cases. No reliance on the old “471 lines” snag as a current fact.
  **Small local probe:** the installed query observer produced pending/idle/isPending true
  for a disabled no-data query, proving why the landing-guidance condition is false. This
  was not a model call or a browser interaction.
- **Current-app browser limitation:** the disposable fixture stack built the exact baseline,
  cloned only its local test database, and passed readiness. The first scratch launcher had
  a CommonJS/top-level-await error; renaming that scratch script to `.mts` fixed it. Sign-in
  in the in-app browser could not reach the API; direct browser access reported
  `ERR_BLOCKED_BY_CLIENT`, while local HTTP and CORS checks passed. No browser safety setting
  or gate was bypassed. The fixture stack was stopped. Existing CI proves the covered chat
  journeys, not the unmeasured phone geometry or the source-only stream-switch hazard.
- **Review-only checks:** JavaScript syntax and diff whitespace passed. All three variants
  fit a 320 px browser viewport (288 px content width and scroll width); the Conversation
  first proposal and confirmation card were inspected at 375 px, and the light palette
  inspected separately at 375 px. The carousel, starter-to-draft, Send-to-card and history
  controls were exercised; the prototype-only History first Close chats control initially
  did not hide its list and was corrected, then rechecked. An initial export refused to
  overwrite this review's own generated file; it was explicitly regenerated with `--force`.
  The exporter warns about host API references; the only referenced host APIs are
  `widgetState` and `setWidgetState`, which the standalone wrapper supports. Additional
  limit/unavailable states and person/appearance choices are preview controls; they are
  illustrative, not provider, permission or quota tests.
  Product code, contracts, tests and lockfiles are unchanged. The full implementation gate
  was not rerun for this documentation/mock-up checkpoint. Physical-phone speech/keyboard
  behaviour, live model wording/quality and a real authenticated production rendering remain
  unverified. AA10b's after-total and earlier phone/push/handover checkpoints stay open.
