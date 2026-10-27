# AA9 — assistant build from Craig's picks

27 Oct · baseline `b904457`; review checkpoint `b84ffd3`

Craig chose **Conversation first** and **Include shared corrections** in chat after the
review was delivered. The existing Group AA sitting-5 authorisation continues through build,
verification and automatic close-out. Sitting 6 is excluded. No further owner choice is
needed for the following presentation and recovery design; a newly discovered consequential
contract change would stop implementation before that change.

## Behaviour to build

The current top-bar Assistant entry and five bottom tabs stay. A compact page toolbar offers
Recent chats and New chat. Recent chats expands in place on phones and stays beside the
conversation on desktop, with readable titles, update dates, loading/error/reload states and
an honest recent-history label (the API returns at most 50). New chat opens a local empty
view; the existing conversation-creation endpoint runs only when the first question is sent.
Deleting asks about the named chat and explains that confirmed diary/Wanted changes survive.
There is no restore/Undo promise, and this build does not delete existing stored chats.

A new chat shows three examples that fill, rather than submit, the multiline draft. Both
people get collection/shelf/viewing guidance; only Craig is told he can add to Wanted. The
optional existing mic still fills the draft and never sends. Enter adds a new line; Send
is explicit. The page uses the height given by the existing shell rather than calculating
another full-viewport height inside it. At narrow/short heights the answer scrolls and the
composer remains available above the app navigation. Physical iPhone keyboard/speech checks
remain owner-only; reduced desktop viewports do not prove an iOS keyboard.

The allowance is explicitly **AI calls**, not questions. Existing remaining/cap, blocked,
limit message and reset fields drive the page. A question may use several calls; the spending
cap also applies. Known-unconfigured, offline, loading and status/usage failures get truthful
states beside the draft; saved conversations remain accessible. A failed status request
means availability is unknown, not that a key is missing. No cap or model changes.

## One active reply and safe recovery

Disable new/select/delete while creating, sending or resolving, including synchronous
double-click guards. Bind streamed transcript, errors and pending cards to their originating
conversation so browser Back/URL changes cannot show a finishing reply under another chat.
On unmount, stop updating that page's local state but let the existing request finish and
refresh its stored-query cache; no cosmetic cancellation or rollback.

Retain the exact-film write card, Yes/No meanings, role enforcement and the stale-read race
protection (#287). Scope stream-freshness counts by conversation rather than letting an old
chat's finishing reply invalidate another chat's card authority. New text follows the end
only while the reader is near it; offer a latest-answer action when they have scrolled up.

Keep the sent question in the locked draft until a successful answer/card terminal event.
A failed or prematurely ended stream retains the draft and transcript. Do not automatically
resend: the server may already have committed. Require a successful **Reload conversation**
before continuing. Compare newly stored user turns after the attempt's starting sequence:
if that question is already saved, show that fact and require starting a different draft;
if it was not saved, the preserved draft can be edited/sent explicitly. Failed reloads leave
this guard in place. A failed confirmation is also reloaded before its card can be retried;
use the stored pending-card state and warn that a confirmed action may already have run.
Never infer that deleting a chat or stopping a display undoes a viewing/Wanted entry.

## Readable answers without changing the message contract

Render a deliberately small safe subset: paragraphs, simple headings/lists, emphasis,
inline code and ordinary HTTP(S) links. React escapes all content; no raw HTML, images,
script links or title-to-film guesses. Keep unsupported markup as text. No new dependency
is needed for this bounded text treatment. This is not full Markdown or structured film
cards; tests will cover unsafe links/HTML and long text alongside the readable cases.

## Scope and proof

Frontend only: page/state, small presentation components and their tests, plus fixture-backed
end-to-end cases and the batch's docs. Existing API paths, response shapes, stored messages,
role/cap enforcement and route-inventory equality stay. No migration, live provider request,
production synthetic chat, hosting/credential change or live data rewrite.

Craig's picked layout replaces the native mobile conversation select with Recent chats and
New chat. Update that existing UI-control assertion to the selected controls while retaining
its complete stored-history/follow-up assertions. The existing card-race, Yes/No write and
allowance enforcement assertions remain; clarify the allowance label without weakening them.
If a unit fake closes with no terminal frame, make it follow the actual done/confirm protocol
and add a separate premature-close recovery assertion, rather than accepting silent closure.

Proof covers both roles, landing examples, draft preservation, known/unknown availability,
call/spend limits and reset text, history failure/reload and delete confirmation, streamed
chat isolation (including URL changes), stale-read cards, partial/lost replies and recovery,
safe answer text, and reader-controlled following. Browser cases cover 320/375 px, short
heights and desktop, themes, exact-film cards, and the existing full app journeys. Save
actual built-app fixture captures and inspect them; these are not production/physical phones.

Run all ten local batch-verify commands from a clean commit on disposable Postgres, with
zero database-backed API skips; run the full available local browser/jobs suite and E2E
typecheck. WebKit remains CI-only on this Mac. Run one AA9 PR through all seven jobs, merge
with a merge commit, await exact-SHA main CI and exact API/web SHA/full readiness, then close
out the ledger/architecture/status docs and verify their final head. Report all repairs,
remaining owner checks and any infrastructure restart. Do not start sitting 6.

Working estimate remains 3–6 agent hours plus CI/deployment waiting; recovery and browser
failures can extend it. The build's acceptance is the selected layout and all shared
corrections demonstrated above, not a cosmetic match while the error states remain broken.
