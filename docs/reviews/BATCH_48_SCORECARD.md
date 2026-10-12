# Batch 48 — The two-person scorecard (wave 1, pass R6)

**Never published.** Kept in the repo only. Reviewed SHA `527522d`, judged on what each person met on
11 Oct 2026, from the walk in `BATCH_48_UX_LIVE_APP_REVIEW.md` and the five other passes. Grades A–F per
job; a grade is about the job getting done for that person, not about the code.

## 1. By job

| Job | Craig (owner and operator) | Mark (viewer, Android) |
|---|---|---|
| Find a disc and its shelf | **B.** One search sheet gives shelf, format and "Seen" with the date. Fails for about 30 misidentified copies ("goodfellas": no owned films) and offline (UX48-01) | **B.** The same sheet; he can add and correct a match himself |
| Who has a disc | **Not yet used.** 0 loans ever; Lend and Borrow on both sides (W3); "Every disc is home" | **Not yet used.** Same |
| What to watch tonight | **B−.** Movie night worked end to end on 11 Oct: start, shortlist, a match, a push to both. Reopened, the night shows no match; a shortlist title can be stale ("Exorcist, the"). The assistant answers once, then fails (AI45-01) | **C.** His first notification ever was that match. His "seen it" stops at 14 Sep: no Letterboxd username, never synced (UX48-04). His one assistant follow-up failed (21 Sep) |
| What to buy | **D.** The eBay scan blind since 9 Oct behind "Last check 19:20"; about 1 in 4 deal pushes named the wrong disc (MK47-01); shop prices never shown (MK47-05); Deals shows 11-day-old prices, undated | **D−.** His 66 deal pushes never reached him; his eBay never connected (T8b); an empty Deals page would tell him "Craig has not run a deals scrape yet" |
| What it is worth | **C−.** Honestly labelled "asking prices", but on new copies (about 1.4–1.8× used, MK47-03); the top "most valuable" line is a DVD TV box set at £138.99 | **C−.** The same screen |
| Being told when something happens | **D.** Pushes died silently from 8 to 11 Oct; no job failure reaches him (DS44-01); the scan's one status line reads healthy (UX48-02) | **F, until 11 Oct.** 1 delivered of 104 ever; nothing outside Settings' foot said so; Settings could say "on" above "no devices" |
| Running the app | **C.** 165 films to identify and 525 discs on Disc specs wait on him; at phone size Audit runs 61 screens, Disc specs 43, Identify 26; no "needs attention" row. Undo and refusal wording are good | — |

**Overall: Craig C, Mark D+.** The browsing half of the app serves both well. Everything that is meant to
reach out to them (alerts, deals, the scan, the history sync) has failed quietly at least once, and Mark
has borne most of it without knowing.

**Mark's own voice: none recorded.** All 41 snags are Craig's. Mark's side reaches the app only through
Craig (his 4 scanner adds on 10 Oct, two of them one barcode; his 2 assistant chats; his 972 imported
watches). A one-line "Tell Craig" from the You page, landing in Craig's attention row, would give him one.

## 2. Craig's words: the 41 snags, and where each stands on 11 Oct

Statuses: fixed (seen in the walk or read in the code), partly, shipped but misleading, built and never
used, not possible, overcorrected. "OA" is `OWNER-ACTIONS.md`.

| Round · # | Craig asked | Now |
|---|---|---|
| 14 Sep · 1 | Less at the top of the Archive; search in the bottom bar | Fixed: a search tab; one row of controls |
| 14 Sep · 2 | One releases screen, led by 4K and Blu-ray | Fixed: Releases is "Coming to disc"; a Home row |
| 14 Sep · 3 | It zooms like a web page | Partly: no input under 16 px; his iPhone check is open (OA 1h) |
| 14 Sep · 4 | Remove gift links | Fixed: removed, table dropped |
| 14 Sep · 5 | Refine the menu | Overcorrected: hiding empty sections hid Loans (raised again 30 Sep, undone for Loans); still hides Deals when its source fails |
| 14 Sep · 6 | Movie night: suggestions, details, streaming, who has seen it | Fixed: suggestions by person, details, "seen by" |
| 14 Sep · 7 | Quick add on Home; offer to sell the old copy | Fixed differently: Add is the bar's centre; the sell offer follows an upgrade |
| 14 Sep · 8 | Some features for Mark and Craig only | Fixed (reframed): Mark can add and price (#155) |
| 14 Sep · 9 | Letterboxd links open the app | Partly: film links by IMDb id; his iPhone check is open (OA 1h) |
| 14 Sep · 10 | Sign in to Letterboxd; sync history | Partly: backfill plus a manual Sync now; Craig synced once, Mark never (UX48-04) |
| 14 Sep · 11 | Decide the opening screen and bar | Fixed: opens on Home; five tabs |
| 23 Sep · 1 | Archive controls too tall | Fixed: one row |
| 23 Sep · 2 | A runtime filter | Fixed: in Filters |
| 23 Sep · 3 | Blu-ray.com specs | Partly: 729 done; 525 wait on his picks |
| 23 Sep · 4 | Search shows "seen it", and when | Fixed: "Seen" with the date or "Not seen" |
| 23 Sep · 5 | PIN asked too often | Fixed: no PIN typed since 22 Sep |
| 23 Sep · 6 | Search stays open after a pick | Fixed (in code; not driven) |
| 23 Sep · 7 | What the collection is worth | Shipped but misleading: new copies' asking prices (MK47-03) |
| 23 Sep · 8 | Mark's eBay: lists, alerts, deals | Shipped but misleading: alerts blind since 9 Oct, 1 in 4 the wrong disc; his account never connected |
| 23 Sep · 9 | 4K, Blu-ray and cinema releases | Fixed: refreshed nightly |
| 23 Sep · 10 | Movie night: back, list, search, Add | Fixed |
| 23 Sep · 11 | Share a movie night by notification | Fixed: reached Mark on 11 Oct once he had a device |
| 23 Sep · 12 | The bottom bar | Fixed: five tabs |
| 23 Sep · 13 | The side menu | Fixed: the You page |
| 23 Sep · 14 | Search films we don't own | Fixed: "Not in the collection", streaming lines |
| 30 Sep · 1 | Where "usually £X" comes from | Shipped but misleading: the sources line is there; the figure mixes conditions and products (MK47-01, -06) |
| 30 Sep · 2 | Value from sold prices or bids | Not possible: sold prices closed; bids too thin (#237) |
| 30 Sep · 3 | The Loans section went missing | Fixed: always shown |
| 30 Sep · 4 | Movie night: swiping or the list | Fixed: the list |
| 30 Sep · 5 | Back buttons | Fixed: a back arrow on every page reached from You |
| 30 Sep · 6 | Craig's house as a location | Fixed |
| 30 Sep · 7 | The top bar looks faded | Partly: a raised panel since W1; light mode on his iPhone unchecked (OA 30) |
| 30 Sep · 8 | Reviews for wanted films | Fixed: links and scores; the "line" is mostly the page's release-date text |
| 30 Sep · 9 | Top reviews and highlights | Fixed: four Home rows |
| 5 Oct · 1 | Search needs a second tap for the keyboard | Partly: fixed in code; his iPhone check is open (OA 30) |
| 5 Oct · 2 | Lend and borrow, from Loans, with the scanner | Built, never used: 0 loans |
| 5 Oct · 3 | Home as rows, the collection first | Fixed |
| 5 Oct · 4 | Most watched duplicated | Fixed: removed |
| 5 Oct · 5 | The top bar is still faded | Partly: as 30 Sep · 7; his screenshot is still asked for |
| 5 Oct · 6 | Add a disc on Home | Fixed: removed as redundant |
| 5 Oct · 7 | The bid trial on Home | Fixed: moved to Admin |

**Tally:** 28 fixed, 7 partly (five wait on his iPhone), 3 shipped but misleading, 1 built and never used,
1 not possible, 1 overcorrected. The pattern: each round fixed what Craig could see; what failed later was
what nobody could see from a screen (a scan, a push, a sync), which is why UX48-02 matters more than any
single snag.
