# Owner snags — 5 Oct 2026, reconciled against the code

Craig raised 7 snags on 5 Oct 2026. Each was checked the same day against the code at
`b5258af`, the live database (`SELECT`s only, inside a read-only transaction) and a render of
the app shell at 375 px in both themes (local dev server, sign-in skipped, no API).

**Status: reconciled, and Craig answered the same day (below).** The plan is Group W in
`docs/phase-batches.md`, with each batch's criteria; his answers are `DECISIONS.md` #249.

## Craig's answers, 5 Oct

| Question | Answer | Recorded |
|---|---|---|
| Borrowing: both lend and borrow, or name only? | Both lend and borrow | #249, W3 |
| Home: the collection first, every section a row? | Collection first | #249, W2 |
| The bid trial: to Admin, or delete it? | Move to Admin | #249, W2 |
| Go for W1 → W2 → W3? | Go | #249, Group W |

**Still open:** the screenshot of the faded top bar, and light or dark (snag 5).

**Not checked:** anything only an iPhone shows. The browser used here is Chromium, so the
keyboard (snag 1) and the status bar (snag 5) are reasoned from the code and from how iOS is
documented to behave, not seen. Which theme Craig uses is not known.

---

## Three things to know first

1. **The search keyboard is an iPhone rule.** iOS raises the keyboard only when a box is
   focused while the tap is still being handled. The app focuses the search box one frame
   after the tap, so the box can take focus but the keyboard stays down.
2. **V1's top-bar fix was real, but it could not change how the bar looks.** Nothing scrolls
   under the top bar: the page scrolls in its own region below it. So the bar always showed
   the page's own colour, with or without its background. The 30 Sep diagnosis was right about
   the missing class and wrong about the bar's look. The faded look has another cause, not yet
   pinned down (snag 5).
3. **Only Craig can lend today. Mark cannot, and there is no Borrow.** The loans table
   has **0 rows**, so changing its shape costs nothing to migrate.

---

## At a glance

| # | Snag | Today |
|---|---|---|
| 1 | Search needs a second tap for the keyboard | Bug: focus lands a frame after the tap |
| 2 | Craig borrows; lend and borrow from Loans with the scanner | Not built; lending is Craig-only |
| 3 | Home as carousels, the collection first | Only Highlights scrolls sideways |
| 4 | Most watched duplicated in Highlights | Yes: 8 of its 10 films are in Most rewatched |
| 5 | Top bar still faded | Background now built; bar is the page's exact colour |
| 6 | Add a disc on Home | Redundant at every width |
| 7 | The bid trial on Home | Left there on 1 Oct (#237); only Craig sees it |

---

## The snags

### 1. Search needs a second tap for the keyboard

**Today.** The bottom bar's Search opens a sheet over the page. The sheet is built after the
tap, and its box is focused by an event sent one animation frame later
(`requestAnimationFrame` in `AppLayout.tsx`).

**Cause.** iOS (Safari and home-screen apps alike) shows the keyboard for a programmatic focus
only inside the handler of the tap itself. A frame later is outside it: the box is focused, the
keyboard is not raised, and a second tap on the box raises it. Craig is on an iPhone; Mark's
Android is more lenient, which would explain it being Craig's snag (not checked).

**Proposed.** Build the sheet and focus the box inside the tap (React's `flushSync`), not a
frame later. A test proves the box has focus before the tap's handler returns; only an iPhone
proves the keyboard, so that check is Craig's.

### 2. Craig borrows; lend and borrow from Loans, with the scanner

**Today.**

- A loan is one specific disc (not a film), with the borrower as free text. The model's own
  comment says the two people "neither borrows from the other", which is no longer true.
- Lending and "Mark returned" are **admin-only** in the API and the screens. Mark (viewer) can
  read Loans and nothing more. There is no "borrow".
- The Loans page cannot start a loan. Its empty state says to lend from a film's page.
- Overdue reminders go to admins only, worded "<borrower> has had it since …".
- **Live: 0 loans ever recorded.**

**The scanner.** It exists on Add a disc: the camera (ZXing, loaded only when asked), a typed
fallback, and a lookup chain: remembered codes → a disc on the shelf with that code → eBay →
TMDB. **0 of 1,880 owned discs store a barcode** (the spreadsheet import has no barcode column)
and 1 code is
remembered. So on Loans, the first scan of each disc goes to eBay (one call of the shared 5,000
a day, at most 60 an hour per person), finds the film, and the person picks which copy (4K,
Blu-ray or DVD). Confirming it remembers the code, so the next scan of that disc is instant and
free.

**Proposed (decision 1, option A).**

- Both people can lend, borrow and mark returned, as #155 widened adding discs to Mark.
- **Borrow** is one tap: the borrower is you, stored as a link to your profile (one new,
  nullable column on the empty table), with your name kept as the text too.
- **Loans gets "Lend or borrow"**: scan, or search your own films → pick the copy → "I'm
  borrowing it" or "Lend to …", optional due date. Scanning a disc that is already out offers
  "Returned" instead.
- The film page gets **Borrow** beside **Lend**, for both people.
- Overdue reminders go to both people, each worded for them: "You've had *Heat* since 2 Oct"
  to the borrower, "Craig has had *Heat* since 2 Oct" to the other.

### 3. Home as carousels, the collection first

**Today, top to bottom on a phone (live, 5 Oct):**

1. Add a disc (button)
2. Coming to disc: a list of 5 (33 disc releases on the calendar from today)
3. On this day: your own viewings on this date in earlier years (4 logged for 5 Oct, across
   both diaries)
4. Worth a rewatch
5. Highlights: Top rated, Most rewatched, Most valuable discs, Best reviewed
6. What it's worth
7. Bid prices: a trial (Craig only)
8. The collection: 4 number tiles, 4 bar charts, Most watched
9. Completion: all 40 sets, as a list
10. Recent activity: 20 entries
11. Pinned collections: hidden while none

Only Highlights' rows scroll sideways. Everything else stacks, so the page is long, and the
collection's own numbers are eighth.

**Proposed (decision 2).** Every section becomes a titled row that scrolls sideways, as
Highlights' rows do, in this order:

1. **The collection:** number cards (films, discs, worth, watched, identified), then a row of
   chart cards (formats, where they live, genres, decades)
2. Coming to disc: poster cards with date and format
3. Top rated · Most rewatched · Most valuable · Best reviewed
4. On this day · Worth a rewatch
5. Completion: set cards, closest to complete first; "All 40" opens today's full view
6. Pinned collections (still hidden while none)
7. Recent activity: stays a short list at the foot, since a feed does not swipe well

This replaces Batch T5's criterion "Home opens with the next few disc releases".

### 4. Most watched duplicated in Highlights

**Yes.** "Most watched" (in The collection) is the 10 films with the most viewings, across both
diaries. Highlights' "Most rewatched" is up to 12 films watched twice or more, from the same
table in nearly the same order. **Live: 8 of the 10 Most watched films are also in Most
rewatched.** The diaries hold 1,566 viewings (Craig 594, Mark 972) of 1,112 films, 299 of them
watched twice or more.

**Proposed.** Drop Most watched. Most rewatched keeps the posters and the per-person counts.

### 5. Top bar still faded

**Measured at 375 px.**

| | Dark | Light |
|---|---|---|
| Top bar | page colour, 94% | page colour, 94% |
| Page | near-black | cream |
| Bottom bar | lighter panel + shadow | near-white panel |

V1's class is built and working. But the top bar sits above the page's scrolling region, not
over it, so 94% of the page's colour over the page's colour is the page's colour. The bottom bar
*does* float over scrolling content, which is where V1 made a visible difference.

**Likely causes, unconfirmed:**

- **(a) It does not read as a bar.** It is the page's own colour with grey icons (the back arrow
  and the assistant use the muted colour), while the bottom bar is a lighter panel with a shadow.
- **(b) In light mode, the iPhone draws the clock and battery in white.** The app asks iOS for a
  translucent status bar (`black-translucent`), whose text is always white, over a cream bar.

**Proposed.** Give the top bar the bottom bar's raised panel and full-strength icons, in both
themes. If (b) is the cause, also fix the status bar in light mode. **Needs from Craig:** a
screenshot of the faded bar, light or dark, and the installed app or Safari.

### 6. Add a disc on Home

**Redundant at every width.** Below 1,024 px the bottom bar's raised Add is always there; from
1,024 px the top bar has its own "Add a disc" button, shown to both people (#155).

**Proposed.** Remove Home's button. On a phone, Home's header then shows nothing.

### 7. The bid trial on Home

Craig ran it on 1 Oct: none of 100 films had enough bids for a price (#237). Values stay on
asking prices, V7 is shelved, and #237 left the trial on Home so it can be run again "if bids
ever look thicker". It is admin-only, so only Craig sees it.

**Proposed (decision 3).** Move it to Admin as a "Collection value" tool, with the "Update
values" button beside it, so Home only reads. The alternative is to delete it.

---

## Decisions for Craig

1. **Borrowing.** **A (recommended):** both lend, borrow and mark returned; Borrow links the loan
   to your profile; reminders to both. Cost: one nullable column on an empty table; Mark gains
   write access to loans. **B:** Borrow only types your name into today's text field; no
   migration; Mark still cannot lend; reminders stay Craig's only.
2. **Home's order:** the collection first, as above (recommended).
3. **The bid trial:** to Admin with "Update values" (recommended), or delete it.
4. **Go** for Group W below.

**Ask, not a decision:** a screenshot of the faded top bar, and light or dark.

---

## The plan — Group W (approved 5 Oct, #249)

| Batch | Covers | Claude Code | Codex |
|---|---|---|---|
| W1 | Snags 1 and 5: the search keyboard, the top bar | mid tier · high | mid tier · High |
| W2 | Snags 3, 4, 6 and 7: Home | mid tier · high | mid tier · High |
| W3 | Snag 2: lend and borrow, from Loans with the scanner | top tier · high | top tier · High |

- **One sitting, W1 → W2 → W3**, each its own pull request, closing out automatically after a
  green gate, which deploys (#24). W3 waits for decision 1.
- **Why W3 is top tier:** a migration (as V4 was), an auth widening (Mark writing loans) and
  the reminder job.
- **Each batch ends with a 375 px browser check** in light and dark. W1's keyboard and the top
  bar on an iPhone are Craig's checks, added to `OWNER-ACTIONS.md` when W1 ships.

## Choices made unless overruled

- The search fix keeps the existing focus event; it only moves it inside the tap.
- Recent activity stays a list, not a carousel.
- Each Home row keeps its own title; the outer "Highlights" heading goes, so every row is a peer.
- A loan scan never writes a barcode onto a disc. It only remembers the code against the film
  (the existing confirm step), so a wrong pick of copy cannot mislabel the catalogue.
- Reminders keep their once-only flag; a loan to a friend reminds both people, worded as today.
