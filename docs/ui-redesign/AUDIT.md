# UI/UX audit

**Baseline:** commit `942e1b1`, reviewed before the redesign branch changed the interface.  
**Evidence:** route and component inspection in `apps/web`, shared response schemas in
`packages/shared`, selected API response models, the repository decisions and house
standard, and baseline browser captures in `screenshots/before/`.

This is an audit of a working product, not a proposal to simplify it. The catalogue,
virtualisation, permissions, API contracts, offline queue, aliases and every existing
workflow are constraints of the redesign. “Addressed” below means code exists on this
branch; it does not substitute for the separate browser and automated verification gate.

## What was already strong

- The product models the real collection rather than a generic media library: multiple
  copies, format and technical specifications, shelf locations, wanted preferences,
  watch history, loans, box sets, smart collections, gift links and movie-night voting all
  have real routes and APIs.
- Grid, list and compact collection views already use `@tanstack/react-virtual`; the
  interface can request the full catalogue while keeping the DOM bounded. That behaviour
  is essential at 1,857 items and must remain intact.
- API responses are fetched as unknown data and parsed with shared Zod schemas. The
  frontend therefore has an explicit contract rather than silently trusting JSON.
- The query-state helper distinguishes loading, offline, error, empty and populated list
  states, and the query client deliberately attempts requests while offline so a service
  worker can answer from cache.
- Administrative routes are gated in React and the API remains the final authority.
  Viewer-readable pages generally hide write controls rather than waiting for a 403.
- Sign-in has no public registration path, watch data and smart collections are
  caller-scoped, and public gift capability URLs use a deliberately narrow response.
- The durable write queue, stale-edit timestamp and queue clearing on sign-out show careful
  attention to offline correctness, not merely an “offline” badge.
- Per-device collection-view preferences, useful poster fallbacks, image lazy loading and
  semantic labels on many forms provided a sound base to improve rather than replace.

## Severity model

- **P0:** can expose another profile’s data, present a destructive or permissioned action
  incorrectly, state a false collection fact, or make a core workflow inoperable.
- **P1:** materially slows or confuses a high-frequency job, excludes keyboard/touch users,
  or makes a principal route unreliable on mobile.
- **P2:** consistency, finish and maintainability debt that compounds across the product.

## P0 findings

| Finding | Evidence in the baseline | User impact | Branch disposition |
|---|---|---|---|
| Authenticated API cache was shared between profiles | `sw.ts` cached same-origin authenticated GET responses in one URL-keyed `mcu-api` cache. A Craig and Mark session on the same installed device used the same cache key. | An offline response created under one profile could be replayed to the other after a session change. | Addressed with a profile-partitioned cache key and deletion of the legacy cache; verification remains required across a real Craig → sign-out → Mark sequence. |
| A temporary profile request failure looked like sign-out | `context/auth.tsx` preserved tokens after a failed `/auth/me`, but set `profile` to `null`; `ProtectedRoute` interpreted that as unauthenticated and redirected to login. | Opening the installed app without a connection could strand a valid user at sign-in instead of the cached archive. | Addressed with a validated last-profile cache and an explicit “session unavailable” state; offline browser verification remains required. |
| Network sign-in could remain busy forever | The raw login `fetch` could reject, while `LoginPage.handleSubmit` had neither a catch nor a finally block. | A failed connection left the primary sign-in action stuck at “Signing in…” with no recovery message. | Addressed defensively in both auth transport and page submission; covered by an added auth test, pending full-suite confirmation. |
| Dense collection rows were pointer-only | `MovieListView` and `MovieCompactView` navigated from clickable `div` elements with no link semantics, tab stop or keyboard handler. | Keyboard and switch users could not open films from two of the three collection views. | Addressed by rendering virtualised rows as real links and preserving the same virtualisers. |
| Detail subqueries turned failures into false facts | A failed copies query rendered “No live copies”; watch-log failures looked like “not logged”; a failed active-loan query could offer “Lend”; photo-query failure looked like no photos. | The interface could confidently give the wrong answer to “do we own it?”, “have I watched it?” or “is this disc already out?”. | Addressed with explicit loading/offline/error branches and guarded actions; targeted tests were added for the highest-risk detail states. |
| Movie-night shortcuts could cast an unintended vote | The global left/right handler did not ignore inputs, selects, textareas or editable content; candidate-load failure was folded into an exhausted deck. | Editing a field while a session was open could vote, and a network failure could be mistaken for “nothing left”. | Addressed with editable-target guards and distinct deck/realtime failure states; targeted tests were added. |
| A trash preview could authorise the wrong visible table | `PurgePanel` retained its armed preview while the surrounding trash-table tab changed. | A user could preview one category, switch category and act with stale confirmation context. | Addressed by remounting the purge panel per table and announcing restore/purge failures. |
| Viewer UI exposed an administrator-only bulk action | Completion insights rendered “Add missing to wanted” for both roles, although the write endpoint is admin-only. | Mark was invited into a workflow that could only end in refusal; the UI contradicted the permission model. | Addressed by showing the bulk action only to Craig while leaving insights readable to both people. |

## P1 findings

| Area | Evidence and consequence | Branch disposition |
|---|---|---|
| Information architecture | The sidebar presented 14 personal/everyday destinations and 6 administrator destinations as one nearly flat run. Saved collections followed the admin tools, and AI settings was easy to miss. | Grouped archive, planning, discovery, personal and administration navigation; a five-destination mobile tab bar keeps frequent actions within reach. |
| Global search | Results showed title, year and best format, but omitted copy count and shelf; the widget had no combobox/listbox semantics, arrow-key selection, query-error state or offline state. It returned at most 20 results with no dedicated full-results route. | Results now answer owned, format, copy count and location with keyboard listbox behaviour and explicit states. There is still no `/search` route; that is recorded as a product decision rather than invented here. |
| Search scope copy | `GET /search` filters `Movie.search_vector`; format and shelf are response metadata, not query fields. | UI copy must promise title search only unless the backend search contract is expanded. |
| Filtering on a phone | The filter bar rendered up to eight selects plus three technical toggles in one wrapping 32px-high strip. Active constraints were not summarised as removable values. | Common location/format controls remain visible; secondary controls progressively expand and active filters render as individually removable chips. |
| Filter continuity | `/movies` kept filters only in component state, so a detail round trip or reload discarded a carefully narrowed result set. | The branch retains filters for the browser session. Filters still are not URL-addressable; shareable/bookmarkable searches require a separate product choice. |
| Edition visibility | The brief requires edition scanning, but the list/search contract has no edition field. See the explicit contract conflict below. | Detail and edit surfaces now call `subCategory` “Collector edition”; list views do not invent unavailable data. |
| Movie-detail hierarchy | A strong backdrop/poster start was undermined by small type, low-contrast metadata, tabs that hid the owned-copy answer and copy cards that did not name `subCategory` as an edition. | Reworked as an archive record with a clear ownership/copy summary, semantic tabs, resilient subquery states and scan-friendly format/edition/location panels. |
| Assistant continuity and mobile use | Desktop alone had conversation navigation. The render chose stored **or** live turns, so the earlier transcript could disappear after sending; stream/create/delete failures could escape, and the send icon lacked a useful name in its icon-only state. | Added a mobile conversation picker, merged stored and live turns safely, reduced-motion scrolling, explicit stream/mutation states and an accessible send action. |
| Onboarding recovery | Completion/skip failure produced no visible error and there was no sign-out escape from the full-screen gate. | Added announced save errors, retry-safe busy handling and sign-out access, while retaining every functional step. |
| Narrow administrative and utility rows | Wanted, loans, trash, notifications and several filter/action rows assumed horizontal space. Buttons could squeeze metadata or push beyond 320px. | Representative rows now stack intentionally; shared controls enforce touch sizing. Pages not structurally redesigned still inherit the shell and control foundation and must be checked during responsive verification. |
| Dialog and lightbox focus | Custom edit/dialog/photo overlays did not consistently trap focus, close on Escape and return focus to the invoker. | Shared dialog behaviour now provides focus containment, Escape, restoration and narrow-screen presentation; photo handling received explicit states. |

## P2 findings

| Area | Baseline evidence | Direction taken |
|---|---|---|
| Visual identity | Deep navy plus bright amber, generic sans typography and repeated equal cards made the application resemble a starter dashboard more than a private archive. | Warm near-black/off-white surfaces, burgundy action colour, champagne accent, an editorial display face from local system fonts and quieter archive dividers. |
| Theme integrity | List and compact views contained hard-coded `zinc-*`, `amber-*` and `emerald-*` classes, bypassing semantic theme variables. | Brand, semantic and media-quality tokens are separated; shared badges and states consume semantic colours in both themes. |
| Contrast | Baseline token calculation put primary on the light background at about 1.95:1; destructive text was about 3.44:1 in light and 2.75:1 in dark, below 4.5:1 for normal text. | Semantic text/surface pairings were redesigned. Both themes still require automated and visual contrast verification before acceptance. |
| Type scale | A repository scan found 217 `text-xs`/9–11px occurrences, including operational metadata and actions rather than captions alone. | Core metadata now follows a deliberate label/value pattern; tiny type remains only where genuinely secondary and must be sampled at mobile widths. |
| Touch sizing | Search, filter, view, close and row actions frequently used 32–36px controls. | Shared buttons and inputs default to 44px, coarse-pointer fallbacks enforce minimum targets, and safe-area padding is included. |
| State consistency | Only a handful of baseline surfaces used alert/live-region semantics; many pages rendered one-line “Loading…” or visually identical error/empty text. | A reusable state panel covers loading, empty, error and offline treatment without turning every content section into a card. |
| Motion | There was no global reduced-motion policy, while chat auto-scroll and several transitions always animated. | Global reduced-motion rules and a chat-specific scroll preference were added; routine navigation remains largely static. |
| Page identity | Routes did not update the document title, and heading/action placement varied by page. | Route-aware titles and a shared page-header hierarchy were introduced. |
| Test surface | The baseline had only nine UI-level page/component test files; most coverage exercised schemas and library functions. | Regression tests were added around search keyboard behaviour, authentication transport, movie detail, assistant transcript and movie-night keyboard/error handling. Full results belong in the verification report. |
| Stale/dead-end copy | `/admin` was a placeholder, `/debug` exposed a production-reachable “Break the world” control, and a few comments/captions described already-shipped work as future. | `/admin` is now a real route index and stale product copy was corrected where touched. Whether `/debug` should be development-only remains a deployment/product decision. |

## Cross-discipline assessment

- **Hierarchy and typography:** the baseline prioritised route names weakly and rendered
  most content at one small sans-serif level. Posters sometimes dominated while the
  ownership answer remained typographically quiet. The new hierarchy reserves display
  typography for record/page titles, uses sans text for operations, and treats location,
  edition and status as labelled archive metadata.
- **Spacing and layout:** page widths, outer padding, card padding and section separation
  varied route by route. Shared page shells, a spacing rhythm and restrained divider/panel
  patterns replace one-off wrappers without forcing every feature into the same card.
- **Forms and validation:** most fields had labels, but busy/error presentation and narrow
  layouts were inconsistent. Shared 44px controls, field labels/hints, `aria-invalid`,
  associated errors and mobile stacking establish the expected pattern.
- **Colour and status:** direct utility colours weakened light mode and several statuses
  relied on hue. Semantic tones now pair icons/words with colour; format colour is a
  separate quality vocabulary rather than a success/error signal.
- **Responsive behaviour:** the old mobile strategy was mainly a hidden sidebar plus a
  wrapping desktop page. The redesign adds a compact identity/header, mobile tabs,
  safe-area spacing, progressive filters, bottom-sheet dialogs and deliberate row/form
  stacking. Horizontal-overflow testing is still required at 320px and with long titles.
- **Keyboard and touch:** global `/` and command shortcuts were a good start, but virtual
  rows and swipe interactions were incomplete keyboard experiences. Links, listbox arrow
  navigation, guarded movie-night shortcuts, focus-visible styling and larger targets
  close the most serious gaps.
- **Administrator versus viewer:** API enforcement was generally sound. The principal UI
  defect was presenting viewer actions that only Craig could complete; the redesigned
  navigation and completion actions now reflect role, while read access stays shared.

## The ten highest-value journeys

| Journey | Baseline assessment | Design response / remaining limit |
|---|---|---|
| 1. Sign in and first-time onboarding | Functionally small, visually generic and vulnerable to raw network rejection. The wizard could silently fail and offered no sign-out exit. | A reserved stacked-identity composition, clear private-access form, visible offline/error states, resumable editorial setup and sign-out escape. No public sign-up was added. |
| 2. Search and establish ownership | Fast to invoke with `/`, but the result did not make “owned” explicit or show shelf/copy count, and keyboard semantics were incomplete. | Search now explicitly says Owned and shows format, copies and location. It remains a title search and still has no dedicated results route. |
| 3. Find format, edition, location and shelf | Format and location existed but were visually inconsistent; edition appeared only as ambiguously named `subCategory`. | Shared format badges and location metadata improve scanning; copy detail and forms say Collector edition. Edition cannot appear truthfully in list/search results under the current contract. |
| 4. Browse and filter the collection | Virtualisation was strong, but two views were pointer-only and the mobile filter strip was dense. | All three purposes remain: visual grid, metadata list and rapid compact index. Rows are links; filters disclose progressively and active filters stay visible. |
| 5. Open a film and understand all copies | Rich metadata existed, but copy-query failure could state that nothing was owned and edition/location hierarchy was weak. | Ownership and every copy are presented as a catalogue record with explicit query states and progressive technical detail. |
| 6. Add or edit a disc | The workflow worked and supported offline/stale-edit logic, but felt like loosely connected forms and used unclear edition naming. | A numbered, responsive catalogue-entry flow and shared copy editor preserve validation, duplicate checking, queueing and API payloads. |
| 7. Manage wanted titles | Buying preferences were capable, but rows/forms compressed poorly and several errors were quiet. | Clear wanted counts, responsive rows, labelled format/edition/price preferences and announced search/write states; Craig-only writes remain enforced. |
| 8. Record a watch or loan | Copy-specific lending was conceptually correct, but loading errors could expose the wrong action; watch errors looked like absence. | Distinct state handling, clearer copy context, responsive loan register and announced mutations. Watch records remain per user and loan writes remain admin-only. |
| 9. Use collections, movie night and assistant | The feature set was unusually complete, but visual patterns diverged; movie-night shortcuts and assistant transcript/mobile navigation had correctness gaps. | Shared headers/states plus targeted interaction fixes. Smart collections remain caller-scoped; movie night remains shared; assistant limits remain personal. |
| 10. Use administrative and notification tools | Six admin links were mixed into routine navigation and `/admin` was a dead placeholder. Utility pages used inconsistent layout/state patterns. | A separate administration group and useful admin index improve wayfinding. Audit/trash received targeted fixes; retailers, gift links and notification settings currently receive the shared shell/tokens rather than a claimed bespoke redesign. |

## Explicit contract conflict: collection editions

The requested collection-browsing answer includes **edition**, but the current list
contract cannot provide it:

- `movieListItemSchema` / `MovieListItemResponse` contains `bestFormatOwned`, technical
  bests, `copyCount` and aggregated `locations`; it has no edition field.
- `/movies` and `/search` both return that same list item shape.
- Edition-like data exists only per copy as `CollectionCopyResponse.subCategory`, returned
  by `/movies/{id}/copies`. The database and import/export vocabulary still calls it
  `sub_category`.

Fetching every film’s copies from a 1,857-item list would create an unacceptable N+1
request pattern, and guessing an edition from title/format would be false data. This pass
therefore makes the existing field legible as **Collector edition** on add, edit and movie
detail surfaces, while list/search views show only what their contract proves.

If edition must be visible while browsing, the recommended follow-up is an additive,
schema-validated list field containing distinct edition labels per film (an array avoids
inventing a subjective “best edition”). That is an API-contract decision requiring
Craig’s approval, not a styling change.

## Design direction

**A maintained private film archive with the cadence of a repertory programme:** warm
paper and near-black rooms, burgundy for deliberate action, champagne for identity and
fine rules, editorial titles paired with efficient catalogue text, and poster art treated
as collection evidence rather than streaming entertainment. The system favours scan speed,
truthful metadata and quiet progressive disclosure over spectacle.**

The approved logo files are intentionally untouched. The shell and authentication flow
reserve semantic desktop-horizontal, mobile-mark and auth-stacked identity slots for the
subsequent brand-integration pass.
