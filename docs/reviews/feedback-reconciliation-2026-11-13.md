# Craig's 8 snags of 13 Nov, reconciled against the code

**Read-only.** Code read at `c7b460c` (main). Live data read with the read-only database role,
14:00–14:30 GMT on 13 Nov. Nothing was changed, committed, pushed or deployed. The layout
points (3 and 7) are judged from the layout code, not seen on a phone: production needs Craig's
sign-in.

**Update, 13 Nov, 18:20 GMT.** Craig answered the decisions (#372). Decision 1 took the
alternative: "it will always be Mark that puts it back", so every put-back is Mark's, whoever
borrowed the disc. Decisions 2–4 took the recommendations, and he said "all good to plan the
other batches". The plan is Group AF in `docs/phase-batches.md`, with a phone copy in
`docs/reviews/group-af-plan-2026-11-13.md`; it waits for his go. Since this report was written,
PR 152 (`73e825e`, #371) changed only the Python lock files, none of the code read here.

Sizes are agent time for the change and its tests. Each batch also needs the full gate, the
seven CI jobs and the production check: about 30–60 minutes more.

## Summary

| Snag | Today | Fix size |
|---|---|---|
| 1. Needs you says "You" on discs given back | By design: every put-back is each person's own | ~1 h |
| 2. Needs you and Needs attention: both? | Two cards; Needs attention is Craig's alone, 1 item | 2–3 h to merge |
| 3. Closest to complete messy; Add to Wanted bunched | Buttons wider than their columns on a phone | 2–3 h |
| 4. Back returns to where you had scrolled | Nothing remembers scroll position | 3–4 h |
| 5. Home's cinema strip: older films first | Widest-showing first; older films fall off the end | ~45 min |
| 6. At the cinema opens on All films, All days | Opens on today | ~45 min |
| 7. A film's page: the same day strip | Every day stacked down the page | ~2 h |
| 8. "See what's on" opens the same default | Same address as every way in | in 6 |

**Total: about 12–15 hours of agent work**, plus the gate per batch.

## Risks

- **Snags 1, 2, 3 and 6 each overrule a choice already shipped:** AE8's "a shelf job is each
  keeper's own" (#363), Needs attention as its own row (Batch X2), AE3's buttons on Home (#355)
  and AE5's "opens on today" (#360). Each gets a new decision that supersedes the old one.
- **End-to-end cases encode the old behaviour** and change with Craig's decisions, never as a
  route to green: "opens on today" (AE5, AC4, AC5), "Needs attention" by name (AB1, AC1, Tell
  Craig) and Doesn't count clicked on Home (AE3).
- **Snag 4 cannot be proved on a phone by CI.** CI runs Playwright's WebKit, not iOS Safari.
- **This report is saved, not committed**, as 8 Nov's was. It is committed with Craig's answers
  and the batch plan, before any batch starts, because a batch needs a clean tree.

## Needs you

### 1. "You" against Halloween and The Silence of the Lambs after Craig gave them back

- **Live:** Craig borrowed both on 18 Oct and recorded them returned on 12 Nov at 22:39 GMT.
  Neither is shelved yet, so each shows as "Put back …".
- **Now:** every put-back is labelled "You" for both people. That is AE8's rule (#363): a shelf
  job (put back, hand over, chase an overdue loan) is each keeper's own.
- **It is Mark's in practice.** The same happened before: Craig returned Pulp Fiction and
  Rosemary's Baby on 28 Oct, and Mark shelved them on 5 Nov. All 4 loans ever were Craig's.
- **Fix:** when one keeper borrowed the disc, putting it back is the other keeper's. That
  matches how a request already works (#363: a disc Craig asked for is Mark's to hand over).
  - Craig sees "Mark to put back Halloween · Returned 12 Nov · goes to Back 5th shelf",
    labelled Mark, after his own items.
  - Mark sees "Put back Halloween", labelled You.
  - A loan to someone outside the app stays each keeper's own.
- **No data change.** Both discs relabel on the next read once the fix deploys.
- **Size:** ~1 h: the API's rule, the wording, tests.
- **Decision 1** below.

### 2. Do we need both Needs you and Needs attention?

- **Needs you** (top of Home, both people): things a person does, such as loans, cinema-trip
  replies and Mark's reviews. Shared between the two of you, each labelled with whose it is.
- **Needs attention** (under it, Craig only): what the app's 08:00 daily check found wrong,
  such as a stopped job, failing push, a PIN lockout or films in doubt, plus any "Tell Craig"
  line from Mark. Mark never sees it.
- **Live today:** Needs attention holds 1 item, "1 identified film has a disc page or review
  for another year", since 6 Nov, linking to the films in doubt. Tell Craig has never been used.
- **Answer: one is enough.** Fold Needs attention into Needs you, for Craig only:
  - each app problem becomes a row labelled **App**, in amber, opening where it opens now;
  - a line from Mark becomes a row labelled Mark, with Clear;
  - order: Craig's own items, then App, then Mark's;
  - the count includes them, and "See all" lists them.
- **Mark's Home does not change.** The daily check and its "the check has not run" warning are
  untouched: this is web only.
- **Size:** 2–3 h, including the three end-to-end cases that look for "Needs attention".
- **Decision 2** below.

## Home and Completion

### 3. Closest to complete is messy, and Add to Wanted is bunched

**On Home:**

- 3 sets, each naming up to 3 missing films. Each film is one line holding its title and two
  buttons, Want and Doesn't count.
- On a 390 px phone the card is about 326 px wide inside. The buttons take about 210 px, so a
  title gets about 110 px, and most are cut off after about 14 characters.
- With up to 9 such lines and 3 "+N more" links, the card can run to about 700 px.

**On a set's page (tap a set):**

- Missing films sit in a poster grid, 3 across. Each card stacks title, year, a TMDB link,
  "Add to Wanted" and "Doesn't count".
- The page is padded twice on a phone (the page's 16 px and the panel's own 16 px, each side),
  so each column is about 100 px wide.
- "Add to Wanted" is about 146 px wide and "Doesn't count" about 120 px, and buttons never wrap.
  Both spill into the next column: **that is the bunching.**

**Fix:**

- **Home:** each set becomes one tidy block: name, count and bar, then one line naming what is
  missing (for example "Missing: Piano Blues +3"). No buttons; tap the set to act.
- **Set page:** padded once. Missing films become a list: a small poster, title and year on top
  (wrapping, never cut), then Want and Doesn't count side by side beneath, each with room. TMDB
  becomes a small link. "Add all N to Wanted" moves under the Missing heading. On the shelf stays
  a poster grid.
- **Size:** 2–3 h, web only. AE3's end-to-end case moves its Doesn't count click to the set page.
- **Decision 3** below.

### 5. Home's At the cinema strip: older films first

- **Now:** up to 12 of this week's films, widest first (most cinemas, then most showings),
  leaving out any film already elsewhere on Home.
- **Why older films vanish:** an older film (the app's "Older films" run, badged Rerun) usually
  shows at one cinema, so it sorts behind the new releases and falls off the end.
- **Live this week:** 7 older films, each at one cinema with 1–4 showings: The Polar Express,
  Cliffhanger, Rocky, Elf, Prisoners, Almost Famous (25th anniversary) and Marie Antoinette
  (20th anniversary, listed twice, once in 4K). Against them, about 140 new-release listings.
- **Fix:** older films lead, soonest showing first (most are one-off screenings), then the new
  releases as now, ending with a "See all" tile that opens At the cinema.
- **Size:** ~45 min, web only.
- **Decision 4** below.

## At the cinema

### 6. Open on All films, All days

- **Now:** it opens on today. AE5 chose that (#360): today needs nothing in the address, and
  every day at once is "?day=all".
- "All films" is already the default, for both the view and the run. Only the day differs.
- **Fix:** nothing in the address means All days: This week, then Coming up, then listings and
  events. A chosen day, today included, goes in the address. Old "?day=all" links still work.
  The day strip stays pinned at the top.
- **Size:** ~45 min, plus the three end-to-end cases that expect today.

### 7. A film's page: the same day-by-day strip

- **Now:** every day is stacked down the page, each with its cinemas and time chips.
- **Fix:** the main page's strip, made one shared piece: the days this film is on, scrolling
  sideways, plus All days. Pick a day to see that day's cinemas and times. The day is kept in the
  address, so Back returns to it.
- **Opens on** the day picked on the main page, or otherwise the film's first day. A choice made
  for Craig, open to overrule (All days instead).
- **Size:** ~2 h, web only.

### 8. "See what's on" from Movie night's Plan a cinema trip

- **Now:** it opens the bare At the cinema address, so it lands on today. Every other way in uses
  the same address: Home's strip, Movie night's At the cinema tab, the menu, and a film page's
  "See what is on".
- **Fix:** none of its own. Snag 6 makes every way in open on All films, All days; one test pins
  this link.

## Everywhere

### 4. Back returns to where you had scrolled

- **Now:** nothing remembers scroll position. The app scrolls inside its own panel, not the
  browser window, so the browser's built-in restore never applies. That panel is reused from page
  to page, so Back lands wherever it happens to be, usually not where you were.
- The Archive's grid and list scroll in a box of their own, inside that panel.
- **Fix:** remember each page's position for each step in history.
  - Back (the phone's back arrow, a page's own back button, or the browser's) returns you to where
    you were, once the page is drawn.
  - A newly opened page starts at the top.
  - Changing a filter keeps your place.
  - It covers the Archive's own box, and a completion set opened from Home.
- **Size:** 3–4 h, with an end-to-end case in all three browsers: Archive → film → Back; Home →
  set → Back; At the cinema → film → Back.
- **Unproven on a phone** until Craig tries it: CI's WebKit is not iOS Safari.

## Decisions

1. **Who puts a disc back.** Recommend: the other keeper, only when a keeper borrowed it. It is
   what Craig asked, and how a request already works. Alternative: every put-back is Mark's (the
   shelves are his); identical today, since all 4 loans were Craig's.
2. **Needs attention.** Recommend: fold it into Needs you, for Craig only, as App rows: one card at
   the top of Home, Mark's unchanged. Alternative: keep both.
3. **Closest to complete on Home.** Recommend: names only, with the buttons on the set page. Home
   stays a glance and the buttons get room. It reverses AE3's buttons on Home. Alternative: keep
   them, stacked under each title (a taller card).
4. **Home's cinema strip.** Recommend: older films first, then the rest, then a See all tile.
   Alternative: older films only, with a tile for the others.
5. **The plan: Group AF** (the next group after AE), four batches, one branch and PR each,
   automatic close-out (#24), in one sitting:

| Batch | Snags | Claude Code |
|---|---|---|
| AF1 Needs you | 1, 2 | Opus 5.5 `high` |
| AF2 Closest to complete | 3 | Opus 5.5 `high` |
| AF3 At the cinema | 5, 6, 7, 8 | Opus 5.5 `high` |
| AF4 Back keeps your place | 4 | Opus 5.5 `xhigh` |

About 12–15 h of agent work, plus four gates (2–4 h). On Craig's answers, the plan goes into
`docs/phase-batches.md` with a superseding decision per overruled choice, and waits for his go.
