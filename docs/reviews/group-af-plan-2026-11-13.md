# Group AF: the plan for your 13 Nov snags

**Done 13 Nov: all four batches are live** (AF1 `057086f`, AF2 `06eb330`, AF3 `aeb2dbb`, AF4
`c2f080e`; #373–#376). What is left is trying them on your phone (`OWNER-ACTIONS.md`). Drafted
13 Nov from your 8 snags and your answers (#372). Four batches
in one sitting, one after another. Each runs the full checks, then merges and deploys on its own,
as Group AE did. The full plan is Group AF in `docs/phase-batches.md`.

| Batch | What changes | Size |
|---|---|---|
| AF1 | Needs you: Mark puts every disc back; Needs attention folded in | 3–4 h |
| AF2 | Closest to complete: names on Home, a tidy set page | 2–3 h |
| AF3 | At the cinema: All days first; older films first on Home; a film's day strip | ~3.5 h |
| AF4 | Back keeps your place | 3–4 h |

About 12–15 h of agent work, plus 2–4 h of checks across the four.

## What you will see

**AF1**

- Halloween and The Silence of the Lambs read "Mark to put back …", labelled Mark.
- Mark sees "Put back …", labelled You.
- One card at the top of your Home: your items, then the app's problems labelled App, then
  Mark's.
- Mark's Home does not change.

**AF2**

- Home: each set is one block, with one line naming what is missing. No buttons.
- A set's page: missing films as a list, with Want and Doesn't count side by side and room for
  both.

**AF3**

- At the cinema opens on All films, All days, from every way in, "See what's on" included.
- Home's strip starts with the week's older films, soonest first, then the rest, then See all.
- A film's page has the same side-scrolling day strip.

**AF4**

- Back puts you where you were: the phone's back arrow, a page's back button, the browser's Back.
- A newly opened page starts at the top.

## Choices made for you (say to change any)

- Handing a disc over stays as now: Mark's when you asked for it.
- Loans does not change: either of you can still confirm a disc shelved there.
- App rows go after your own items and before Mark's.
- A film's page opens on the day you picked on the main page, or otherwise its first day.
- A picked cinema day goes in the address; old "All days" links still work.
- Back remembers your place until you close the app.

## Risks

- Four changes undo choices already shipped (three from 10 Nov, one from October). Their tests
  change with your answers, never just to pass.
- CI cannot prove AF4 on your iPhone. A check on your phone goes on your list after AF4.

## What the go means

- I push this plan, then run AF1 to AF4 in order, each to production.
- A batch whose checks fail stops and reports, rather than closing out.
