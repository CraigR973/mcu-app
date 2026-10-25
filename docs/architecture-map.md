# MCU App architecture map

`STATUS.md` says which commit is deployed. This map shows the running structure through AA4,
deployed on 25 Oct; the April design intent remains in `ARCHITECTURE.md`.

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


## AA5, implementation ready for deployment

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
