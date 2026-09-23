# Owner snags — 23 Sep 2026, reconciled against the code

Craig raised 14 snags on 23 Sep 2026. The same day, each one was checked against the code
at `7ea6140`, the live database (read-only queries), live TMDB and eBay's developer docs.

**Status: reconciled, and Craig answered the same day (below).** The sign-in fix has
shipped (`aa112bd`). The other batches are Group T in `docs/phase-batches.md`: proposed, not
approved.

## Craig's answers, 23 Sep

| Question | Answer | Recorded |
|---|---|---|
| Fix the sign-in bug now? | Yes, as a fix, not a batch | Shipped `aa112bd`, #200 |
| Five-tab navigation? | Yes | #201, T3 |
| Blu-ray.com: A, B or C? | A, the full backfill | #202, T7 |
| eBay with alerts, no auto-buy? | A hybrid of alert and auto-buy | #203, T8 |
| Find out why the scheduled jobs never run? | Yes | See below |

**Why the scheduled jobs never run.** From the read-only Railway logs: both jobs fire on
time and crash on start-up. They refuse to run in production without the sign-in secrets and
the web address, and neither job has been given them, though neither job uses them. A
code-only fix is proposed; it needs no Railway change.

**What the eBay hybrid can be.** eBay lets only approved partners buy or bid through its
API. So:

- **Buy It Now:** an alert and one tap to buy.
- **Auctions:** the alert sets the target as a maximum bid on eBay, and eBay's own bidding
  then bids automatically.
- **Full auto-buy:** only if eBay ever grants access.
- **Never:** a bot using Mark's password.

**Not checked:** anything behind sign-in on the deployed app, because an agent can't enter
a PIN. Descriptions of signed-in screens come from the source code.

---

## Four things to know first

1. **The sign-in bug.** The app can never renew a session, so every sign-in lasts exactly
   24 hours and then asks for the PIN again. Live data: **30 sign-ins since 8 Sep, zero
   renewals.** The renewal step reads the wrong part of the token and never recognises one
   the app issued. Sign-out has the same flaw and has never cancelled a token on the
   server. No test ever tried a renewal. **Fixed on 23 Sep (`aa112bd`)** (snag 5).
2. **Nothing scheduled has ever run.** The only price check on record is a manual one on
   10 Sep. The nightly job has produced no runs in 13 days. Everything automatic proposed
   below (calendar refresh, eBay alerts, deal scans and valuation refresh) depends on
   fixing that first. **The cause was found on 23 Sep:** both jobs crash at start-up because
   they lack web-only secrets they never use. A code-only fix is proposed and needs no
   hosting change.
3. **The releases calendar was last refreshed on 9 Sep and holds no disc dates.** Its
   cinema dates stop at 6 Oct. Disc dates are looked up in the wrong place (snag 9). Asked
   directly, TMDB lists 28 UK disc releases between now and 31 Dec.
4. **No disc has Blu-ray.com specs (0 of 1,880).** So the Archive's Dolby Vision, Dolby
   Atmos and Region-free filters always return nothing.

---

## At a glance

| # | Snag | Today |
|---|---|---|
| 1 | Archive controls too tall | Confirmed: three bands above the first poster |
| 2 | Runtime filter | Not built. 81% of films have a runtime |
| 3 | Blu-ray.com specs | Not added. 0 of 1,880 items have specs |
| 4 | Search shows "seen it", and when | The server knows "seen" but not when. The screen shows neither |
| 5 | PIN asked too often | Bug: sessions can't renew |
| 6 | Search stays open after picking a film | Bug confirmed |
| 7 | What the collection is worth | Not built. A one-disc eBay estimate exists |
| 8 | Mark's eBay | Watch list and selling list are possible. Auto-buy isn't |
| 9 | 4K, Blu-ray and cinema releases | Last refreshed 9 Sep, no disc dates |
| 10 | Movie night (5 parts) | 1 of the 5 is already built |
| 11 | Share a movie night by notification | Not built. Push notifications themselves work |
| 12–13 | Bottom bar and side menu | See "My opinion" below |
| 14 | Search films you don't own | Not in the main search. The pieces exist |

**What the collection holds**, since several answers depend on it: 1,880 live items. That's
1,457 physical discs (363 4K, 887 Blu-ray, 207 DVD), 422 digital downloads and 1 item with
no format.

---

## The snags

### 1. Archive: filters and layout on one line

**Today, on a phone**, three bands sit above the first poster:

1. The top bar: a menu button and "The Real MCU".
2. A page header: "COLLECTION CATALOGUE", "The archive", "1,887 films across 1,880
   physical and digital items", with the grid/list/compact switch below it.
3. The filter band: a full-width Filters button, then "1,887 films" a second time.

On wider screens the filter band holds location, format, Filters, sort and the count. The
layout switch still sits in the header above.

**Proposed.** Remove the header block and use a single row:
`[Filters •2] [Sort] ··· 1,887 films [▦ ☰ ≡]`. The count stays in that row, because it's
how you see that a filter worked, and it appears only once.

**My view on the top bar: yes, on every page.** Put the page name ("Archive") in the top
bar, where "The Real MCU" sits today. Do it on every page on phones, not just the Archive.
Every page repeats the same kicker, title and description block, so changing one page
would make it the odd one out. It's a single change to the shared header component, not
edits to 25 pages. It also gives every sub-page a back arrow in the same place, which fixes
snag 10's missing back button everywhere at once. On desktop there's room for the large
titles, so keeping or slimming them there is a matter of taste.

### 2. Runtime filter

**Today.** The filters have no runtime option, and the server has no runtime parameter.

**Proposed.** Add "Runtime from … to … minutes" to the Filters panel, shown as a removable
chip such as "90–120 min". Filter on the server, so saved collections can use it too.

**Coverage.** 1,521 of 1,887 films have a runtime (81%). The other 366 are unidentified and
would drop out whenever a runtime filter is on, which is the rule the rating filter already
follows. Identifying those films fixes it.

### 3. Blu-ray.com specs: not added

**Today.** None of the 1,880 current items has specs. Only 10 discs ever did, from the test
run on 10 Sep. When the collection was refreshed on 18 Sep, those specs stayed on the old
rows, which are now in Trash (accepted at the time, `DECISIONS.md` #195). They can be
restored until mid-December.

**Why it stopped at 10.** The fetcher works (fixed on 10 Sep, `DECISIONS.md` #122), but it
needs someone to supply the exact Blu-ray.com page for each disc. #110 rules out the site's
own search, so the real blocker is finding about 1,250 page addresses for the Blu-ray and 4K
discs. Fetching them is the easy part. The site's terms forbid automated collection. Craig
accepted that risk in #110, including a one-time backfill, with hard stop rules: a
403 or 429 response halts everything.

**Options.**

- **A. Full backfill (recommended).** Find each disc's page with a paid web-search API, not
  Blu-ray.com's own search. Strong matches on title, year, format and UK edition are
  accepted automatically. Doubtful ones go into a queue in the app, and you tap to confirm
  each. Pages are then fetched in nightly batches at #110's pace, about two hours of
  fetching in total. Costs: a small search-API bill (not yet priced), a confirm queue to
  work through, and #110's risk at full volume. An outside search engine is a new way of
  sourcing, so it needs a `DECISIONS.md` entry.
- **B. 4K first.** Option A for the 363 4K discs only, where HDR and Atmos matter most.
- **C. By hand.** Add a "Blu-ray.com link" box to each disc. Paste the link and the specs
  arrive. Free and low-risk, but slow.

With any option, first restore the 10 old specs onto the new rows. Also hide the three spec
filters until at least one disc has specs, under #154's hide-when-empty rule.

### 4. Search: "seen it", and when

**Today.** Each result shows the poster, title, year, "Owned", format, copies and shelf.
The server already works out whether *you* have seen each film, but the dropdown doesn't
show it, and the date isn't sent at all.

**Proposed.** Show "Seen 12 Mar 2025" or "Not seen" on each result, for the person signed
in. It's a small change: the server adds your last watch date and the dropdown displays it.

### 5. Asked for the PIN too often: a bug

- **Designed:** you sign in once, the session renews itself silently, and it lasts 30 days
  from your last use.
- **Actual:** every session ends 24 hours after sign-in.

**Why.** A session token is two parts joined by a dot, and the first part contains two dots
of its own. The renewal step splits at the *first* dot, so it never finds the token it
issued. The server refuses the renewal and the app signs you out. Re-running the exact
split confirmed it can never match. Sign-out splits the same way, so it has never cancelled
a token on the server either.

**Evidence.** Since 8 Sep, Craig has signed in 26 times and Mark 4 times. There have been
no renewals.

**Fix.**

- Read the last part of the token instead of the second.
- Add the missing tests: sign in, renew, renew again, and check that sign-out cancels the
  token.
- Stop the app signing you out when a renewal fails for a reason that isn't security, such
  as the server restarting during a deploy. The app already follows that rule elsewhere
  (#48).

After it ships you'll sign in one more time and then stay signed in. **It should go first,
on its own branch**, because it's a live production bug.

### 6. Search stays open after you pick a film

**Confirmed.** On a phone, search opens as a sheet over the page. Picking a result opens the
film, but nothing closes the sheet, so the film stays dimmed behind it until you press
Cancel. The fix is to close the sheet whenever the page changes. Small.

### 7. What the collection is worth

**Today.** A film's page can check eBay for one disc at a time. It gives the median of
current asking prices and how many listings that's based on. Nothing is stored, and none
of the 1,880 items has a purchase price.

**The limit.** Apps can't get sold prices any more. eBay closed its sold-price API to new
apps and put sold listings behind a sign-in in late August (`DECISIONS.md` #16, #126). Any
total is therefore "at current eBay asking prices", which usually run higher than what
things actually sell for.

**Proposed.** A valuation run that prices each of the 1,457 physical discs with the same
estimator. Downloads are left out because they can't be resold. The run stores each disc's
price, sample size and date. Home then shows a total such as "≈ £X at current eBay asking
prices, 1,3xx of 1,457 discs priced". That's about 1,460 eBay calls against a daily
allowance of 5,000, spread over two nights so the rest of the app still has room. After
that, a monthly refresh, which needs the scheduled jobs working. Rare titles and
unidentified films will price thinly or not at all, and the page will say so.

**Not recommended:** CeX trade-in prices. They would give a realistic floor, but there's no
official API, and matching needs barcodes, which the app doesn't store.

### 8. Mark's eBay

| He wants | Possible? | How |
|---|---|---|
| Connect his eBay account | Yes | "Sign in with eBay" consent |
| See his watch list | Yes | eBay's Trading API |
| See his selling list | Yes | Trading API, active and sold |
| Auto-buy at a target price | **No** | eBay only lets approved commercial partners buy or bid through its API |
| Scan for good deals | Yes | eBay search, which the app already uses |

**Instead of auto-buy.** Mark sets a price target on any item. The app checks it and sends
a push the moment it's at or under the target. One tap opens the listing in the eBay app,
and he presses Buy himself. For auctions, eBay's own maximum bid already bids for him up to
his limit.

**Deal scan.** The app looks for new 4K and Blu-ray listings on eBay UK priced well below
that film's usual asking price. Films on his Wanted list come first. Films he owns are
skipped unless the listing would be an upgrade. Finds arrive as push alerts and go onto the
existing Deals page.

**Costs and risks.**

- **A new kind of secret.** The app would store a long-lived token for his eBay account,
  encrypted. It has deliberately never held one before (`DECISIONS.md` #142). Its
  permissions should be read-only where possible.
- **Owner steps.** Craig would need to set a redirect address and sign-in settings in
  eBay's developer portal, and add an encryption key in Railway. These are hosting and
  credential changes.
- **Dependencies.** Alerts need the scheduled jobs working, and they use part of the
  5,000-a-day eBay allowance.

### 9. 4K, Blu-ray and cinema releases on the calendar

**What's in the live calendar:** 20 cinema dates in September, 10 in October up to 6 Oct,
plus Prime Day and Black Friday. **There are no disc dates.** It was last refreshed on
9 Sep.

There are four causes:

1. **It only refreshes when an admin presses "Refresh from TMDB".** Nothing runs it on a
   schedule, and nobody has pressed it since 9 Sep. It wasn't pressed when the disc-date
   change shipped on 15 Sep either, so disc dates have never been fetched in production.
   `STATUS.md`'s Group S table, which says S6 wrote "first physical rows ever written", is
   wrong: the live table has no row added or changed after 9 Sep.
2. **It looks for disc dates in the wrong place.** It only asks about films coming to
   cinemas in the next three months, and those almost never have a disc date yet (1 of 58
   when measured). Disc releases are mostly films that have already left cinemas, plus 4K
   re-issues of older films.
3. **Cinema coverage is capped.** It reads three pages of TMDB's list and keeps eight
   genres, which gives 30 films. TMDB has 146 UK cinema releases between now and 31 Dec.
4. **"Coming to disc" only lists the month you're viewing.** So it's empty unless a disc
   comes out in that month.

**Asking TMDB directly** (its discover search by release type, UK, 23 Sep to 31 Dec) returns
**28 disc releases**. They include *Frankenstein*, *KPop Demon Hunters* and *Coyote vs.
Acme*, and re-issues of *28 Days Later*, *Fargo* and *Evil Dead*. TMDB's data is
community-maintained, so the list is incomplete, but it's 28 against the 0 we have now.

**Proposed.**

- Fetch disc and cinema releases by release type, six months ahead.
- Make "Coming to disc" list the next releases, whichever month is on screen.
- Refresh nightly once the scheduled jobs work, and keep the button as a manual override.

**Optional second source** for boutique 4K releases: the label shops the price scraper
already reads (Arrow, Second Sight, 101 Films, Powerhouse and Zavvi) publish pre-order
dates.

### 10. Movie night

| Part | Today |
|---|---|
| a. Back button | Missing. Only the error screens have one |
| b. Show the suggested films on opening | One card at a time. The full list is loaded but never shown |
| c. Swipe a sample, and search | **Already built.** Each night starts with 30 random Archive films, and anyone can add any film |
| d. Live search results | You type, press Search, and get six results with no posters |
| e. Add and Skip instead of a cross and a heart | Icon-only buttons |

**Proposed.**

- Opening a night shows the shortlist: poster, title, who suggested it and your vote, with
  "Start swiping" above it.
- The buttons say "Skip" and "Add".
- Search becomes the same live search as the Archive (the snag 14 version), so it shows
  posters, whether a film is owned or streaming, and who has seen it.
- The back arrow comes from the top-bar change in snag 1.

**Assumed, overrule if wrong:** the other person's votes stay hidden until there's a match.
That's the current rule, because seeing their answer first changes the game.

### 11. Sharing a movie night by notification

**Today.** "Invite" copies a link, which you paste into a message yourself. Nothing notifies
the other person. The only movie-night notification is "It's a match", and tapping it
already opens that night. No match notification has been sent yet. Mark's phone has never
received a notification from the app: it has been registered since 16 Sep, but nothing has
been sent to it.

**Proposed.** A "Send to Mark" button. One tap adds him to the night and sends a push
("Craig started a movie night — 32 films to swipe") that opens that night. "Share link"
stays as the backup, using the phone's share sheet.

**A platform limit.** Craig uses an iPhone and Mark an Android phone. On an iPhone, a link
tapped in WhatsApp or Messages opens in Safari, not the installed app, because Apple
doesn't let web apps catch links. The link still lands on the right night, after a one-off
sign-in in Safari. Notifications don't have this problem. On Android, an installed web app
can usually catch its own links.

### 14. Search films you don't own

**Today.** Search only finds films you own, and says "No owned films found" otherwise. But
movie night's "Suggest a film" already searches all of TMDB, marks what's on the shelf and
shows streaming services for films you don't own. The pieces exist.

**Proposed.** One search, used in the search sheet, the desktop header and movie night:

- Owned films come first, with shelf, format, and whether and when you've seen them (snag 4).
- Then "Not in the collection", with where each film streams in the UK: subscription
  services first, then rent or buy.
- Tapping a film you don't own opens a card with the overview, where to watch, "Add to
  Wanted" and "Suggest for movie night".

**Cost.** TMDB calls while you type, which is already how movie night works, plus a
streaming lookup for the top few unowned results, cached.

---

## My opinion: the bottom bar and the side menu (12, 13)

**Today on a phone:**

- **Top bar:** a menu button, the logo and "The Real MCU".
- **Bottom bar, six slots:** Archive · Search · Add · Home · Movie night · More.
- **Menu:** "More" and the top-left menu button open the same slide-out menu. It lists
  Movies, Wanted, Movie night, Releases, Home, Assistant and Settings, plus six admin pages
  for Craig. Box sets, Collections, Deals and Loans are hidden while empty, and all four
  are empty today.

**The problems:**

- Six slots squeeze the labels down to 9px.
- Two buttons open the same menu.
- Releases and Wanted are two taps deep, and they're what a collector checks most after
  the Archive.
- The top bar spends its space on the app's name, then every page repeats its own title in
  a large block.

**Recommended: five tabs, and no side menu on phones.**

- **Bottom bar:** Home · Archive · (+) · Movie night · Search. Search stays in the bar, as
  you asked on 14 Sep.
- **Top bar:** a back arrow on sub-pages, the page title, and a button with your initial.
  That button opens a "You" page listing Wanted, Releases, Deals, Loans, Box sets,
  Collections, Assistant, Settings and Craig's admin pages. It's a full page, not a
  slide-out.
- **Home** opens with what's coming to disc and deals on Wanted films, so buying is one tap
  from the opening screen.
- **Desktop keeps its sidebar.** This change is for phones and tablets only.

**Alternatives.**

- **Cheapest:** keep the six tabs, remove the duplicate menu button and make "More" a full
  page. This doesn't fix the cramped labels.
- **Search in the top bar:** Home · Archive · (+) · Movie night · More, with search as a
  top-bar icon. This reverses your 14 Sep request.

**Not decided here:** the floating assistant button, which already covers controls on
phones (`OWNER-ACTIONS.md` item 11). It could move to the "You" page or the top bar.

---

## Proposed batches: for approval, not started

| Batch | Covers | Waits on |
|---|---|---|
| ~~T1 Session renewal fix~~ | 5 | **Shipped 23 Sep, `aa112bd`** |
| Scheduled jobs fix | Everything automatic | Craig's go (code only) |
| T2 One search | 4, 6, 14, 10d | Nothing |
| T3 Navigation and the Archive row | 1, 2, 12, 13, 10a | Craig choosing a navigation option |
| T4 Movie night | 10b, 10e, 11 | T2, T3 |
| T5 Releases | 9 | Scheduled jobs, for the nightly refresh |
| T6 Collection value | 7 | Scheduled jobs, for the monthly refresh |
| T7 Blu-ray.com backfill | 3 | Craig choosing A, B or C |
| T8 Mark's eBay | 8 | eBay portal setup, an encryption key, scheduled jobs |

**Craig's job before T5, T6 and T8** can run automatically: get the scheduled jobs working
(`OWNER-ACTIONS.md` item 1). Each batch's model and effort will be set when it's added to
`docs/phase-batches.md`.

---

## Sources

- [eBay Order API (checkout): Limited Release](https://developer.ebay.com/api-docs/buy/order/static/overview.html)
- [eBay Offer API (bidding): Limited Release](https://developer.ebay.com/api-docs/buy/offer/static/overview.html)
- [eBay Buy API requirements](https://developer.ebay.com/api-docs/buy/static/buy-requirements.html)
- [GetMyeBayBuying: the watch list](https://developer.ebay.com/devzone/xml/docs/reference/ebay/getmyebaybuying.html)
- [GetMyeBaySelling: active and sold listings](https://developer.ebay.com/devzone/xml/docs/reference/ebay/getmyebayselling.html)
- [Using OAuth with eBay's Trading API](https://developer.ebay.com/api-docs/static/oauth-trad-apis.html)
