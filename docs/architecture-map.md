# MCU App architecture map

`STATUS.md` says which commit is deployed. This map records the shipped structure through
AB2 on 29 Oct; the April design intent remains in
`ARCHITECTURE.md`.

```mermaid
flowchart TB
    Phone[Craig and Mark's PWA<br/>Vercel] --> API[FastAPI<br/>Railway]
    API --> DB[(Postgres<br/>Neon)]
    API --> Providers[TMDB · eBay · shops · model]
    API --> Artwork[Private MARKS artwork<br/>inside the API image]
    Jobs[Railway cron jobs] --> DB
    Jobs --> Providers
    Backup[GitHub weekly backup] --> DB
```

## AA8, shipped 23 Oct

```mermaid
flowchart TB
    Home[Signed-in Home] -- bearer fetch --> Route[Private artwork route]
    Route --> Files[MARKS photo assets<br/>inside the API image]
    Route -- image bytes --> Home
    Home -- object URL --> Banner[Five-image MARKS banner]
```

The original screen-print emblem remains a public, non-photo app asset and replaces the larger
in-app vector marks. The photo collages moved from Vercel's public directory into the Railway
image: an unauthenticated route request receives 401, and Home keeps the returned bytes only in
an in-memory browser object URL. The favicon and notification badge keep their 16 px vector mark.

## AA2, shipped 25 Oct

```mermaid
flowchart TB
    Home[Home] --> Attention[Needs attention]
    Attention --> Destinations[Repair screen or owner guidance]
    Home --> Highlights[Best discs: strongest score and detail]
    Home -. activity moved .-> You[You: Recent activity]
    Insights[Completion set] --> Missing[Missing films]
    Missing --> Wanted[Shared Wanted status or add action]
    Missing --> TMDB[TMDB film page]
```

The owner-authorised refresh ran on 25 Oct: it created one current set and removed one retired
set without error. It stores an optional TMDB person portrait for a new or changed set, but the
first run exposed that unchanged rows only advance their timestamp, not their metadata: 1 of 40
sets gained a portrait. Cards therefore keep initials until a narrow metadata fix and a newly
authorised re-run. The existing completion endpoint reads each missing film's shared Wanted state,
while the screen separates missing films from those on the shelf.

## AB1, shipped 28 Oct (`ad2c992`)

```mermaid
flowchart TB
    Home[Home attention read] --> Current[Current identification queues]
    Home --> Saved[Saved operational checks]
    Current --> Rules[Shared ownership and unresolved-state rules]
    Resolve[Resolution or collection change] --> Refresh[Invalidate attention]
    Refresh --> Home
    Daily[Real daily check] --> Saved
    Daily --> Push[Push once per new problem]
```

Identification warnings now reconcile the daily snapshot with the lists people can act on.
Reading Home neither writes a check nor sends a push. Historical lookup/spec/review evidence
stays intact. Settings actions select the eBay, Assistant or own-device tab; other people's
devices and Railway-only jobs receive owner guidance rather than a misleading repair link.

## AB2, shipped 29 Oct (`c187ed7`)

```mermaid
flowchart TB
    Change[Watch or copy change] --> Refresh[Invalidate profile stats]
    Refresh --> Request[Existing collection stats request]
    Request --> Count[Personal watched titles intersect current ownership]
    Count --> Home[Home coverage and Summary cards]
```

The existing endpoint adds ownedWatchedMovies; the whole-diary watchedMovies field stays
unchanged. Home shows owned coverage against totalMovies, or Unavailable for older answers.
Profile-scoped stats cache isolates each person's numerator. Visible overlapping format bars
preview the retained full breakdowns. No database shape, provider, service or history change.

## AA10a, shipped; first live pass read back 22 Oct

```mermaid
flowchart TB
    Owner[Admin starts first pass] --> Run[Used-sale run]
    Cron[Existing eBay cron] --> Run
    Run --> Search[Weekly used Buy It Now search]
    Search --> Store[(Item number, film, format,<br/>price, postage, condition, dates, status)]
    Run --> Missing[One item check when absent]
    Missing --> Store
    Store --> Median[Three observed sold listings<br/>in 90 days: postage-in median]
    Median --> Values[(Disc valuations)]
    Values --> Pages[Home · Admin · film page]
```

The store keeps no eBay title or image. A positive sold count on an out-of-stock listing
marks that listing sold; the figure uses its last advertised price, which can exceed an
accepted Best Offer. The run stops at 600 eBay calls per UTC day. Craig started the first
Admin pass on 22 Oct; the cron path now carries the remaining film-format pairs into later
daily budgets. AA10b is next.


## AA4, shipped 25 Oct (`6e9629d`)

```mermaid
flowchart TB
    Film[Owned or TMDB film page] --> Night[Choose an open night]
    Search[Suggest a film at top of night] --> Picks[Suggested: person and time]
    Night --> Picks
    Random[Archive random shortlist] -- person suggests a film --> Picks
    Picks --> Votes[Existing Add / Added votes and match]
    Plan[Optional local date and time] --> UTC[(One nullable UTC start)]
    UTC --> Local[List of nights and recipient-local invite push]
```

Moving a random pick to Suggested keeps its suggestion id and all existing votes. Existing
nights remain unplanned. Invite tokens remain withheld from the read-only and backup roles;
migration 066 grants only the new planned-start column.


## AA5, shipped 25 Oct (`8f47f39`)

```mermaid
flowchart TB
    Cron[Existing nightly spec/review job] --> File[Bounded IMDb ratings file]
    File --> Cache[(Scores for stored IMDb ids only)]
    Night[Film on a night] --> History[Each participant's watch and rating]
    Night --> Place[Owned-copy place, else streaming]
    Night --> Cache
    Night --> Snapshot[Runtime and IMDb identity on suggestion]
```

Night-only metadata stays on the existing suggestion; opening a night creates no catalogue
films or copies. IMDb cache identity and checked time prevent stale scores after an identity
correction. Failed refreshes keep previous scores and surface through the existing job check.

## AA6, shipped 25 Oct (`54dbc07`)

```mermaid
flowchart TB
    Person[Home or an open night] --> Run[Browser run: dealt film ids]
    Run --> Draw[Authenticated read-only draw]
    Draw --> Archive[(Current owned films)]
    Draw --> One[One film, excluding this run's ids]
    One -- Skip --> Run
    One -- Choose on Home --> Pick[Confirmed pick and film link]
    One -- Choose on a night --> Suggest[Existing suggestion action]
```

Home can deal only films unwatched by the current person. A night applies its filters;
a seeded random pick is promoted through AA4 without losing votes. A run creates no database
rows, provider calls or jobs. Existing API authentication and night membership guard the draw.

## AA7, shipped 26 Oct (`e6e5e16`)

```mermaid
flowchart TB
    You[You: choose photo or use initial] --> Write[Authenticated own-photo write]
    Write --> Resize[Existing resize and re-encode pipeline]
    Resize --> Store[(One photo per person in Postgres)]
    Screens[Top bar · You · night · activity] --> Read[Authenticated photo read]
    Read --> Store
    Read --> Avatar[In-memory object URL, else initial]
```

Pictures remain separate from credentials, with a 300 KiB database ceiling. Both read roles
can read the photo table but receive no new profile grants. Photo reads bypass the offline
API cache; removal returns each avatar to the initial. Activity carries the actor's stable
profile id, with a null fallback for older offline answers. No provider or new service is used.

## AA11, shipped 26 Oct (`b1075ec`)

```mermaid
flowchart TD
    Ask[Asked for: copy + needed-by] --> Out[Out: actual handover]
    Direct[Take directly] --> Out
    Out --> Back[Back, not shelved: either person]
    Back --> Shelf[Shelved: confirm or change home position]
    Ask --> Push[Durable request notification to other person]
    Shelf --> Location[Copy location and loan audit update together]
```

The same state and actions appear on Loans and the film's copy card. To put back lists only
current returned copies; reborrowing hides the old task without rewriting its history. Existing
NULL-state open loans read as Out, without a live backfill. Reminders apply only to Out copies.
Shelf confirmation remains available to both people, matching their existing copy-edit access;
Mark has the To put back list. No role, credential or hosting permission changes.


## AA9, shipped 28 Oct (`aecdf8d`)

```mermaid
flowchart TB
    Draft[Multiline draft per chat] --> Send[Explicit Send]
    Send --> API[Existing assistant stream API]
    API --> Origin[Transcript and exact-film card for origin chat]
    Origin --> Stored[(Existing stored conversation)]
    API --> Failure[Lost or failed answer: keep draft]
    Failure --> Reload[Reload stored conversation before another send]
    Reload --> Stored
```

The page keeps active stream state keyed by conversation, so browser Back cannot move a reply
or card into another chat. Controls lock during a request; the request still finishes if its
page is left. A saved question is read before a different question; an unsaved draft can be
sent only explicitly after a successful reload. Existing confirmation, server roles, caps,
model, endpoints and database shapes remain unchanged. Recent chats and named deletion use
the existing private history; deleting chat never undoes confirmed diary/Wanted actions.

A deletion finishing after page navigation refreshes shared history cache but cannot reopen
the assistant. No service, database shape or provider contract was added by AA9.
