# MCU App architecture map

`STATUS.md` says which branch is deployed. This map shows the running structure and the
AA10a change pending merge; the April design intent remains in `ARCHITECTURE.md`.

```mermaid
flowchart TB
    Phone[Craig and Mark's PWA<br/>Vercel] --> API[FastAPI<br/>Railway]
    API --> DB[(Postgres<br/>Neon)]
    API --> Providers[TMDB · eBay · shops · model]
    Jobs[Railway cron jobs] --> DB
    Jobs --> Providers
    Backup[GitHub weekly backup] --> DB
```

## AA10a, pending close-out on 21 Oct

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
accepted Best Offer. The run stops at 600 eBay calls per UTC day, and the cron path stays
inactive until the first Admin pass. AA10b has not started.
