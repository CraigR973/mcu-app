# Batch 48 — Product and UX review of the live app (wave 1, pass R6)

**Pass R6** · reviewed SHA `527522d` · lens: product designer (UX) · read-only · paid calls: none.
Walked 11 Oct 2026 (19:50–21:45 UTC), written 11–12 Oct. The per-person scorecard and Craig's 41 snags
are in `BATCH_48_SCORECARD.md` (never published).

**How the app was seen.** The bundle built at `527522d`, served locally, driven headless in Chromium at
375×812 in both themes, as each person (Craig with an iPhone's agent, Mark with an Android's), with the
installed-app display mode. Behind it, the API's own code at `527522d` answering with production's data
on the read-only role, every connection read-only, every write refused (405), every outside call refused
in-process (the rig of #250). 244 page renders, plus 13 rendered failure states. Screens behind the three
credential tables (devices, eBay sign-ins, feed tokens) were given production's known state.

## 1. Summary

Grade **C**. The everyday screens are clear, quick and well worded; the moments when something has gone
wrong are not: they look fine, or they show the browser's own error text.

1. **Correct and safe:** mostly. Offline, the app promises browsing and shows nothing, because the worker
   has never kept an answer from the cross-origin API (UX48-01). A stale installed client loses whole
   pages to raw JSON (UX48-03).
2. **Honest:** no, at the edges. The one screen that reports the eBay scan calls it healthy while it is
   blind; Settings can say "Notifications are on" above "No devices are registered yet"; Home's counts use
   one word for two numbers (UX48-02, UX48-05).
3. **Doing its job:** on the happy path, yes: a search sheet answers "where is it, have I seen it" in one
   look; movie night worked end to end on 11 Oct. Buying and alerts fail (R5, R2), and Mark's history
   will lose its gap by mid-November (UX48-04).
4. **Noticed:** no. Nothing on Home ever says something stopped; the only words that admit a lost push sit
   three screens down in Settings (UX48-02).
5. **Cheap to change:** yes. Every finding here is a few hours of web work; most of the wording is given
   below.

## 2. Findings (7: 2 High, 3 Medium, 2 Low)

### UX48-01 — High — Offline, the app shows nothing it promised; the worker has never kept an API answer
- **Evidence:** `implemented` — the worker caches API reads only when `url.origin === self.location.origin`;
  production's bundle calls `https://api-production-a8fe.up.railway.app` (`observed`, R2's capture), a
  different origin from the Vercel page, so the rule never matches. `proved` — in the rig, which has the
  same cross-origin shape: with the worker in control, after reading Wanted, the Archive and a film online,
  the caches held 95 precached files, 4 page shells and **0 API answers**. Offline, the film page read "You're
  offline. You can still browse, and any changes are saved on this device." directly above "Could not open
  this film · Failed to fetch"; Wanted read "The wanted list could not be opened · Failed to fetch".
- **Why nobody saw it:** Batch 8's acceptance ("browses cached collection data with the network off") and
  #47 were verified locally, where the API answers on the page's own origin through Vite's proxy (dev and
  preview share `server.proxy`). Production sets `VITE_API_URL`, so the API is cross-origin there only.
- **What the person experiences:** in a shop, a garage or anywhere without signal, a reopened app shows no
  film, no shelf and no "do we own it?", under a banner saying browsing still works. Writes still queue.
- **Fix and cost:** match the API's origin in the worker's rule (the build knows `VITE_API_URL`), keeping
  the per-person cache key; a test of the rule with a cross-origin `API_BASE`; Batch 38 runs the built
  bundle against a cross-origin API. About two hours. (A Vercel rewrite making `/api` same-origin would also
  work and remove CORS altogether, but it is a hosting change, so Craig's.)
- **Where it goes:** new small row in the roadmap's web group; the cross-origin check is a guard.

### UX48-02 — High — When alerts stop, the scan goes blind or a deal is old, every screen still looks fine
The screens' side of DS44-01, DS44-02, CR43-01 with MK47-02, and MK47-07.
- **Evidence (the eBay scan):** `proved` — Price alerts, the only screen that reports the scan, rendered
  with production's latest run: "Checked every two hours. Last check 11 Oct 2026, 19:20." Every run since
  02:21 UTC on 9 Oct ends "finished" having read 0 listings; the answer carries deals found and alerts
  checked, never listings read, so the page cannot tell. No other endpoint exposes the scan's runs
  (`implemented`).
- **Evidence (Deals):** `observed` — on 11 Oct evening Deals showed "7 deals.": six Zavvi prices found on
  30 Sep, undated, five labelled "Not matched to a film in the archive." (one is Goodfellas 4K, an upgrade
  on the Blu-ray on the shelf, which the app files under the 2016 *Good Fellas*, CT46-01). `implemented` —
  no card shows a date; when the last deal goes, Deals leaves the menu (#154, #165) and the empty state
  blames the wrong step: "The sale pages have not been scraped yet … start it from
  Retailers" (Mark: "Craig has not run a deals scrape yet."). The eBay scan has been the main source since
  T8a.
- **Evidence (push):** `proved` — Mark's Settings, rendered with the server's real list (0 devices) and a
  phone that still holds a subscription: "Notifications are on for this device. [Turn off here]" directly
  above "No devices are registered yet." The only words admitting a lost push are "Not sent — no devices
  are registered" under each row of Recent notifications, about three screens down. `observed`: Mark has had
  1 notification delivered of 104 ever, the first at 17:45 UTC on 11 Oct (a movie-night match, after he
  turned notifications on); Craig had none from 8 Oct 00:21 to 11 Oct 08:39.
- **What each person experiences:** Craig sees a scan "checked" every two hours, a Deals page thinning to
  eleven-day-old shop prices, and nothing on Home. Mark saw nothing at all for a month.
- **Fix and cost (words included):** (1) a "Needs attention" row at the top of Home, fed by DS44-01's daily
  check: "No eBay listings read since 9 Oct", "Mark's phone has had no notification since …"; (2) Price
  alerts: "Last check 19:20 · read 0 new listings (33 checks in a row)"; (3) "Seen 30 Sep" on every deal
  card, shop deals expiring two days after they were last seen (MK47-07); (4) Deals stays in the menu, its
  empty state saying when each source last answered; (5) Settings compares this phone's subscription with
  the server's list (DS44-02): "This phone stopped getting notifications on 8 Oct. Turn them on again."
  About two hours of words and lines on top of those rows' own costs.
- **Where it goes:** fold into DS44-01, DS44-02 and MK47-07; this pass owns the wording above.

### UX48-03 — Medium — When a read fails, the phone shows machine text, and a crash looks like no signal
- **Evidence:** `proved` (rig renders):
  - an unhandled API error: Starlette sends the 500 outside CORS, so the browser blocks it and the page reads
    "Could not open this film · Failed to fetch" (WebKit says "Load failed"), the same words as no signal;
  - a stale installed client meeting a newer API (CR43-04), one new review site on a film: the whole film
    page becomes "Could not open this film" plus raw JSON (`[ { "received": "dvdbeaver", "code":
    "invalid_enum_value", … } ]`); Wanted the same;
  - a page still running the previous build after a deploy, asking for a chunk the new deployment lacks
    (Vercel answers it with `index.html` at 200, STATUS 10 Sep): "Something went wrong · Failed to fetch
    dynamically imported module: …/assets/WantedPage-….js"; "Try again" fails the same way until a full
    reload. Nothing listens for a failed chunk.
  `implemented`: 129 call sites in 50 files show `error.message` as the explanation.
- **Near-optimal already:** "TMDB didn't answer, so only your own films are shown."; a handled 503 shows
  the API's own sentence; slow answers say "Counting the archive".
- **Fix and cost:** one `describeError()` behind `queryErrorMessage`: offline ("No signal — showing what's
  saved"), server fault ("The archive had a problem. Try again in a minute."), out of date ("This screen
  needs the newest version" with a Reload button); reload once on a failed chunk (`vite:preloadError`); CORS
  headers on error answers. About half a day. Guard: CR43-04's contract test, and one drift case in Batch 38.
- **Where it goes:** new row in the web group, beside CR43-04.

### UX48-04 — Medium — Mark's history will lose its gap by mid-November, and his screen does not say so
- **Evidence:** `observed` — Mark has no Letterboxd username stored (Craig has; he synced once, 18:59 UTC on
  11 Oct, 4 written). Mark's Watch history tab: an empty username box, "Never synced", "972 watches
  logged". `computed` (R4): his 50-entry feed stops reaching back to 15 Sep around 10–19 Nov; after that his
  viewings since the import are lost to the app for good (#161 never scrapes). `implemented`: the tab says
  nothing about the 50-entry window or how often to sync, and nothing schedules a sync.
- **What Mark experiences:** "seen it" on movie night, Search and the unwatched lists stays frozen at
  14 Sep, then silently loses the autumn.
- **Fix and cost:** now, Mark's username entered (the one Craig gave on 14 Sep) and one Sync now, both
  before ~10 Nov; then a weekly sync job (R4's guard) and one line on the tab: "Letterboxd's feed holds your
  last 50 diary entries. The app syncs weekly; last synced …". About two hours with the job.
- **Where it goes:** the dated ask joins `OWNER-ACTIONS.md` 1j; the job and line fold into the watch-history
  batch Craig chose on 11 Oct.

### UX48-05 — Medium — One fact, two numbers or two names
- **Evidence:** `observed` (walk, both people):
  - Home "Films 1,891" against the Archive's "1,869 films" (22 film rows with no copy: wants and leftovers);
    Home "Discs 1,889" (every copy, 422 downloads included) beside "1,304 of 1,466 discs priced"; "Digital
    556" (formats) beside "Digital 422" (where they live).
  - The "It's a match — Exorcist, the" push of 17:45 opens a night that shows no match: a match lives only
    in a live event and in the push (`implemented`: the session's answer carries none). The shortlist still
    reads "Exorcist, the", no year, no poster, after Craig identified *The Exorcist* (1973) at 18:30.
  - Dates in four forms on one phone: "11/10/2026" (Recent activity), "24 Sep 2026", "22 Sept" (movie
    night), "2026-09 – 2026-09" (Spend over time, from 3 priced discs).
  - Each copy prints its shelf twice ("Front 4th Shelf", then "Front · 4th shelf").
- **Fix and cost:** "Films owned 1,869" and "Copies 1,889 (1,466 discs, 422 downloads)"; one date helper
  ("11 Oct", "11 Oct 2026"); the shortlist reads title, year and poster from the film when shown; the
  session stores its match and the night page shows it; the shelf once. About half a day.
- **Where it goes:** new row: the UX polish batch, with UX48-06.

### UX48-06 — Low — Text and tap targets are small for a phone
- **Evidence:** `computed` (walk and axe-core 4.10, both themes): 10–11 px text on 32 of 34 screens (tile
  labels, badges, card details); no input under 16 px anywhere, so S2's zoom fix holds. Targets under 24 px,
  WCAG 2.2's minimum: Wanted 23 (title and review links 15–18 px tall), Trash 16, Home 11 (activity links
  15 px), Identify 9. Contrast passes in both themes except the dark theme's primary button (4.17:1 at
  14 px; AA asks 4.5), the 11 px format badge in the search sheet (3.85:1) and Retailers' dimmed rows
  (2.5–3.4:1).
- **Fix and cost:** a 12 px floor for labels and badges; padding to 44 px on list links; darken the dark
  primary button's fill. About two hours. **Where it goes:** the UX polish batch.

### UX48-07 — Low — The Archive waits for every film before showing one
- **Evidence:** `computed` (rig, cold, throttled, phone-sized): the Archive asks for all 1,891 films in one
  875 kB answer, sent uncompressed by the API (Neon reads 4.7 MB of rows for it, 2.7 MB of them a search
  column the list never shows). First films after 2.0 s on 4G, 7.8 s on a weak link (1.6 Mbps); Home 1.5 s
  and 3.9 s. The entry bundle is 207 kB compressed, which is fine.
- **Fix and cost:** compress JSON (one middleware), select only the columns the list shows, then load the
  first screen before the rest. About two hours. **Where it goes:** the UX polish batch; with DS44's egress
  hypothesis.

## 2b. One story across the six passes

What each person meets, in the order they would meet it. Each row is another pass's finding as it reaches
a screen; all but the push and the assistant's reply were seen in this walk. The fix is in that pass's row.

| Moment | What the screen says | Behind it |
|---|---|---|
| Opening "GoodFellas" from the shelf | an Iranian 2016 film's poster and cast, stated as fact; Search: "No owned films found for 'goodfellas'" | CT46-01 |
| A deal push for a film he owns | "Halloween on 4K: £9.68 … 66% under its usual" for another film's disc with no case | MK47-01 |
| Home's worth | "≈ £23,655 … at eBay asking prices", led by a DVD TV box set at £138.99 | MK47-03 |
| Asking the assistant a second thing | "The assistant could not answer that. Try rephrasing the question." | AI45-01 |
| Waiting for an eBay alert | Price alerts: "Last check 19:20"; no alert since 9 Oct | CR43-01, MK47-02, UX48-02 |
| Waiting for any notification | Mark: nothing for a month; Settings "on" above "no devices" | DS44-02, UX48-02 |
| "Have I seen it?" | right for most; 15 namesake watches count, and nothing after 14 Sep for Mark | CT46-02, UX48-04 |

**Seed answers.** Watch history stops at the import for Mark (Craig synced once on 11 Oct). The assistant's
screen offers its own example question, which R3 proved answers from 13 of 162 films. Box sets and
Collections are hidden while empty (#165 works); Loans and Price alerts stay, with clear empty states
("Every disc is home"); the photo panel and the eBay alert form sit on every film page, never used.

**Craig's own words** (41 snags in four rounds, 14 Sep to 5 Oct; table in the scorecard): 28 fixed, seen
fixed in this walk or in the code; 7 partly, five of them waiting on Craig's iPhone checks
(`OWNER-ACTIONS.md` 1h and 30); 3 shipped but misleading (the worth figure, "usually £X", the eBay alerts
he asked for on Mark's behalf); 1 built and never used (lending and borrowing); 1 answered "not possible"
(sold prices); 1 overcorrected, then half undone: hiding empty sections hid Loans (14 Sep, raised again
30 Sep), and it still hides Deals the moment its source fails. **Nothing is recorded in Mark's own
words**: every snag is Craig's, and the app has no way for Mark to raise one.

## 3. Follow-through corrections

| Row | Pack or pass says | Corrected to | Evidence |
|---|---|---|---|
| Panel, scope, brief | "Two people on iPhones" | Mark uses an Android phone (snags of 23 Sep and 5 Oct; `OWNER-ACTIONS.md`'s two-phone check) | `observed` in the docs |
| Fast lane (2) | No push since 8 Oct; Mark never | Fixed by hand on 11 Oct: Craig at 08:39, Mark between 17:26 and 17:45 (his first delivery ever, a match). The mechanism is unchanged | `observed` |
| R4 note 4, OA 1j | Each person presses Sync now before ~10 Nov | Mark has no username stored, so Sync now alone cannot work for him | `observed` |
| R5 note 6 | Home's most valuable list leads with Naked City, Labyrinth, BTTF | It leads with a DVD TV box set, "Alfred Hitchcock Hour, The [Complete Collection]", £138.99 from 5 listings | `observed` |
| R2 note 6 | Settings can say "on" above "no devices" | Confirmed by render with Mark's real device list | `proved` |
| R3 note 6 | The input stays enabled under a confirmation card | Confirmed in code (disabled only while streaming); not driven, the rig has no assistant key | `implemented` |
| LIVE | 1,884 copies, 1,890 films | 1,889 copies, 1,891 films at 20:15 UTC (11 Oct adds); Archive 1,869 owned films | `observed` |
| Identify queue | 0 of 166 decided since 25 Sep | 1 decided at 18:30 UTC on 11 Oct (*The Exorcist*, after it reached movie night under its sheet title) | `observed` |
| Scope finding 8 | Features with no use | Hidden: box sets, collections. Shown empty: loans, price alerts, photos, eBay accounts | `observed` |

## 4. Queued and parked items in this lens, re-verified

| Item | Verdict |
|---|---|
| Batch 38, the end-to-end suite | Accurate, and now the only place UX48-01 and UX48-03 can be caught: run the built bundle against a cross-origin API, one schema-drift case and one missing-chunk case. This pass's rig (`probes/` in scratch) is a ready start |
| `OWNER-ACTIONS.md` 30, the W1 and W3 iPhone checks | Open; a headless Chromium cannot see the iOS keyboard or status bar |
| `OWNER-ACTIONS.md` 16b, Mark's notifications and a two-phone movie night | Done in effect on 11 Oct (Mark's first delivery, a match at 17:45); Craig can close it |
| `OWNER-ACTIONS.md` 1j, Sync now | Craig's done (11 Oct); Mark's blocked on his username (UX48-04) |
| `OWNER-ACTIONS.md` 1h, Letterboxd links open the app | Open; the link is by IMDb id for identified films, a search for the 209 others |

## 5. For reconsideration · Hypotheses · Limitations · Probe log

**For reconsideration.** #154 and #165 (hide a section while its table is empty): new evidence that Deals
disappears exactly when its source fails, which turns a fault into silence; keep the rule for Box sets and
Collections, and show Deals with an honest status (UX48-02). #47 and Batch 8's offline acceptance were met
only where the API shares the page's origin (UX48-01); no decision is re-argued, the criterion simply never
held in production.

**Already near-optimal (keep):** the search sheet (poster, shelf, format, "Seen" with the date or "Not seen"
in one look); "TMDB didn't answer, so only your own films are shown."; "Not priced when checked on 24 Sep
2026: eBay had only 1 matching listing, and a price needs at least 3."; "AVForums does not allow apps to
read its pages, so its scores are not shown."; Loans' "Every disc is home"; the five-tab bar with a back
arrow on every page reached from You; no input under 16 px; both themes legible; Mark refused politely
on admin pages ("Access denied").

**Hypotheses.** (1) Whether Railway's edge compresses JSON is unverified: no unauthenticated endpoint is
large enough to show it. (2) How often the stale-chunk screen appears is unknown: it needs an installed app
left open across a deploy, and 44 pull requests, each a deploy, merged between 30 Sep and 11 Oct. (3)
WebKit may word failures differently from Chromium ("Load failed" is WebKit's usual text). (4) V9's
review "line" is the page's own description: 9 of 10 Blu-ray.com lines are "… Blu-ray Release Date …",
and AVForums' run to 300–600 characters, cut to two lines on screen.

**Limitations.** Chromium only (no WebKit installed), so nothing iOS-specific was seen: keyboard, status
bar, installed-app push. Writes were refused, so post-write screens were seen only as their error states.
TMDB-backed parts (streaming, films not owned, candidates) were seen only failing, by design. The assistant
was seen unconfigured (no key in the rig); R3 drove it. Devices, eBay sign-ins and feed tokens are withheld
from the read-only role, so their screens were given production's known state (no device, no account);
Craig's device from 08:39 on 11 Oct is not shown. One evening's data.

**Probe log** (11 Oct, UTC; scripts and logs in `scratchpad/wave-1/r6/`, never committed):
- Production database, read-only role (`live_sql`): 21 SELECTs (2 refused for a wrong column name, then
  re-run), each under 15 rows, no JSON, blob or credential column: row-size sums of `movies` (1 row);
  column grants on `profiles`, and the tables the role cannot read; 13 sample films; running runs in four
  job tables (0 each); notifications on 11 Oct by person and delivered-ever by person (no bodies); the
  matched shortlist row; identify decisions; films synced today; review lines classified by pattern
  (counts only); Letterboxd usernames set (booleans) and syncs by person; column lists for five tables.
- Production database through the API's own code (the rig): 216 uncached GETs, 2.6 MB of answers, on
  `mcu_readonly` with `default_transaction_read_only = on`; 1,675 requests in all (the rest from its cache),
  9 writes refused with 405. 40 TMDB calls attempted by the API's code, all refused in-process; none left
  the Mac. Four stale-run sweeps made no-ops (0 runs were running); `pin_hash` and `invite_token` read as
  stand-ins, never selected.
- Browser: 244 page renders (41 screens and 5 interactions, per person and theme where each applies, plus
  trials), 13 failure-state renders, 4 throttled first-open runs; 2,208 poster images from
  `image.tmdb.org` (public, no key); nothing else outside. One web build (the Sentry plugin's usual build
  telemetry; no token, nothing uploaded).
- Read: four snag rounds and the 14 Sep triage; the R1–R5 reports. Railway: none. eBay, Brave, shops:
  none. TMDB with the app's key: none (the 10 held back are unused). Paid calls: none.
