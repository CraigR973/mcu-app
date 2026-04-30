# Mark's Cinematic Universe (The Real MCU) — Architecture & Technical Design Document

**Version 2.1 — Final | April 2026**

*Mark's Cinematic Universe (The Real MCU) — a personal movie collection management, discovery, and tracking application for family use. Non-commercial, private deployment. Built as a Progressive Web App (PWA).*

---

## 1. Project Overview

Mark's Cinematic Universe is a personal web application that consolidates movie collection management, discovery, and tracking into a single platform. It replaces the current workflow of using a separate spreadsheet for physical media tracking, IMDB for movie information, and Letterboxd for social logging and reviews.

**Primary Users:** Two users — an admin (Dad) with full catalog management rights, and a viewer with browse/search/discovery access.

**Deployment:** Private, non-commercial. Initially runs locally, with the option to deploy to a cloud platform (Railway, Fly.io) later. Built as a PWA with offline support and native push notifications.

### 1.1 Core Objectives

- Import and manage a physical media catalog (1,866+ Blu-rays, DVDs, 4K UHDs, Downloads) with storage location tracking
- Enrich catalog entries with movie metadata from TMDB (posters, cast, crew, ratings, trailers, genres, runtime)
- Provide fast search and filtering by title, genre, format, runtime, location, actor, director, AV specs, and more
- Barcode scanning for quick addition of new purchases
- Track detailed audio/video specs per disc (Dolby Atmos, Dolby Vision, HDR10, DTS:X, etc.) with quality badges
- Maintain a wanted list with automated price tracking across configurable online retailers
- Push notifications (PWA) for price drop alerts, deals, and reminders — with per-category preferences and digest mode
- Daily deals feed for 4K Blu-rays and special editions across configurable retailers
- Automatic purchase detection by scanning connected email inboxes (Gmail, Outlook, iCloud, others)
- Format upgrade flow with automated eBay listing of the superseded disc at a suggested price
- Show streaming availability for unowned movies
- Smart discovery: natural language search, "feeling lucky" randomiser, and collaborative Movie Night mode
- AI assistant chatbot with voice input/output powered by the Claude API
- Completion insights — director, actor, franchise, award, decade, and format-upgrade tracking
- Link out to IMDB and Letterboxd for extended information and social features
- Track lending of physical discs with return reminders
- Offline access for browsing and searching the collection without internet
- Export collection as CSV, PDF, JSON, or printable HTML for insurance, sharing, or backup purposes
- Rewatch suggestions, "on this day" memories, and sale season awareness
- Gift mode and shareable wanted list for family members buying presents
- Optional photo uploads per item for steelbooks, slipcovers, and insurance documentation
- QR code shelf markers for instant physical-to-digital navigation

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React 18 + Tailwind CSS + Vite | Fast dev experience, component-based UI, utility-first styling |
| PWA | Service Worker + Web App Manifest | Offline access, push notifications, installable on mobile/desktop |
| Backend / API | Python 3.12 + FastAPI | Async-first, auto-generated OpenAPI docs, easy TMDB integration, natural fit for AI features |
| Database | PostgreSQL (via Supabase) | Managed hosting, built-in auth, free tier, REST API, real-time subscriptions |
| Full-Text Search | PostgreSQL tsvector + GIN index | Fast ranked search across title, overview, cast, genres — no extra service needed |
| Auth | Supabase Auth | Email/password login, role-based access (admin vs viewer), JWT tokens |
| Real-time | Supabase Realtime | Powers Movie Night collaborative feature and live activity feed |
| Movie Data | TMDB API (v3) | Free, comprehensive metadata, includes IMDB IDs for cross-linking |
| Barcode Lookup | quagga2 or zxing-js + UPC database | Browser camera API for scanning, cross-referenced with TMDB |
| Price Tracking | Web scraping + scheduled jobs | Python scripts with BeautifulSoup/Playwright for eBay, Amazon, CEX, HMV |
| Streaming Data | TMDB Watch Providers API | Built into TMDB, covers major UK/US streaming platforms, region-configurable (default: GB) |
| Task Scheduling | APScheduler | Lightweight in-process scheduler for daily price checks and TMDB refresh jobs |
| Notifications | Web Push (pywebpush + VAPID keys) | Native push notifications on mobile and desktop via service worker |
| Barcode Scanning | quagga2 / zxing-js | Client-side barcode reading via phone camera |
| eBay Integration | eBay Browse API + Sell API (or pre-filled listing URLs) | Suggested sell prices from sold listings; draft eBay listings for format upgrades |
| Email Integration | Gmail API, Microsoft Graph API, IMAP (iCloud, Yahoo, others) | Scan order confirmations across multiple providers to auto-detect wanted list purchases |
| AI Assistant | Claude API (Anthropic) | Conversational chatbot with tool use for natural language queries, actions, and insights |
| Voice I/O | Web Speech API (SpeechRecognition + SpeechSynthesis) | Browser-native speech-to-text for chatbot input and optional text-to-speech for responses |
| Deals Scraper | Python + BeautifulSoup/Playwright | Daily scan of Blu-ray.com, HMV, Amazon, Zavvi for 4K deals |
| AV Specs Source | Blu-ray.com scraping | Video/audio specs (Dolby Atmos, Dolby Vision, HDR10, DTS-HD MA, etc.) per physical release |
| QR Codes | qrcode.react (generation) + camera scanning via zxing-js | Printable shelf QR codes for physical-to-digital navigation |
| Image Storage | Supabase Storage | Optional photo uploads per collection item (steelbooks, slipcovers, insurance documentation) |
| Cache Layer | In-memory + Redis (optional) | Dashboard data caching with TTL for fast home page loads |
| Component Library | shadcn/ui + Radix primitives | Premium, accessible, composable UI components on Tailwind |
| Icons | Lucide React | Consistent, well-designed icon set |
| Forms | React Hook Form + Zod | Type-safe validation, minimal re-renders |
| State Management | TanStack Query + Zustand | Server state (Query) and local UI state (Zustand) |
| Animation | Framer Motion | Smooth transitions, page transitions, micro-interactions |
| Date/Time | date-fns + date-fns-tz | Lightweight, tree-shakeable, timezone-aware |
| Testing (Backend) | pytest + pytest-asyncio + httpx | Unit and integration tests with async support |
| Testing (Frontend) | Vitest + React Testing Library | Fast, Jest-compatible unit/component tests |
| E2E Testing | Playwright | Cross-browser end-to-end flow coverage |
| DB Migrations | Alembic | Version-controlled schema migrations for SQLAlchemy |
| Error Tracking | Sentry | Real-time error and performance monitoring (generous free tier) |
| Logging | structlog | Structured JSON logging with context propagation |
| Rate Limiting | slowapi | FastAPI rate limiting on public and abuse-prone endpoints |
| CI/CD | GitHub Actions | Automated tests, linting, type checking, deploys on every PR |
| Secrets | .env + Doppler (optional) | Environment variable management with `.env.example` for dev |

---

## 3. Data Model

The database schema is designed around the following core entities. All tables use UUID primary keys. Common conventions applied across all tables:

- **`created_at TIMESTAMP`** on every table (auto-set on insert via default `NOW()`)
- **`updated_at TIMESTAMP`** on all mutable tables, auto-updated by a Postgres trigger on every row update
- **`deleted_at TIMESTAMP NULL`** on critical tables (`collection_items`, `wanted_list`, `movies`, `watch_log`) for soft deletes — default queries filter `WHERE deleted_at IS NULL`; admins can view and restore deleted items via a "Trash" UI
- **GIN indexes** on JSONB columns and arrays used for filtering (specs, formats, genres)

### 3.1 profiles

Managed by Supabase Auth. Extended with a profiles table for app-specific data.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | From Supabase Auth |
| display_name | VARCHAR(100) | Shown in the app |
| role | ENUM(admin, viewer) | Admin = full catalog CRUD; Viewer = read-only on catalog |
| streaming_region | VARCHAR(2) | ISO 3166-1 code, default 'GB' |
| push_subscription | JSONB | Web Push subscription object for notifications |
| created_at | TIMESTAMP | Auto-set |

### 3.2 movies

The central movie entity. One row per unique film. Populated initially from the spreadsheet import and enriched via TMDB.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| tmdb_id | INTEGER (UNIQUE) | TMDB movie ID for API lookups |
| imdb_id | VARCHAR(20) | e.g. tt0111161 — used for IMDB link |
| title | VARCHAR(500) | Primary title |
| original_title | VARCHAR(500) | Original language title if different |
| year | INTEGER | Release year |
| runtime_minutes | INTEGER | Film length in minutes |
| overview | TEXT | Plot synopsis from TMDB |
| poster_path | VARCHAR(255) | TMDB poster image path |
| backdrop_path | VARCHAR(255) | TMDB backdrop image path |
| tmdb_rating | DECIMAL(3,1) | TMDB average vote (0–10) |
| tmdb_vote_count | INTEGER | Number of TMDB votes |
| genres | JSONB | Array of genre objects from TMDB (name + id) |
| genre_ids | INTEGER[] | Array of TMDB genre IDs, GIN-indexed for fast filtering |
| top_cast_summary | JSONB | Top 5 cast for quick card display (avoids join) |
| trailer_key | VARCHAR(50) | YouTube key for the official trailer |
| letterboxd_slug | VARCHAR(255) | For constructing Letterboxd URL (with search fallback) |
| media_type | VARCHAR(50) | film, tv_movie, documentary, tv_series, mini_series |
| is_tv | BOOLEAN | Quick flag for filtering TV vs film content |
| best_format_owned | VARCHAR(50) | Derived: highest quality format owned (4k_uhd > blu_ray > dvd > download) |
| best_hdr_owned | VARCHAR(50) | Derived: best HDR available across owned items (Dolby Vision > HDR10+ > HDR10 > none) |
| best_audio_owned | VARCHAR(50) | Derived: best audio format owned (Dolby Atmos > DTS:X > DTS-HD MA > others) |
| search_vector | TSVECTOR | Full-text search index (title + overview + cast + genres) |
| last_tmdb_sync | TIMESTAMP | When metadata was last refreshed |

*GIN index on `search_vector` for fast full-text search. Trigger-updated on insert/update. GIN index also on `genre_ids` for efficient genre filtering.*

*Derived fields (`best_format_owned`, `best_hdr_owned`, `best_audio_owned`) are recalculated by a Postgres trigger whenever a `collection_item` is added, modified, or deleted. They power the quality badges shown on cards and enable "show me everything I own in 4K Dolby Vision" style queries.*

*TV series (e.g. Band of Brothers, The Wire, Alfred Hitchcock Presents box sets) are treated as single entries — each complete series = one movie row with `is_tv = true`. No per-episode tracking, matching how the physical collection works.*

### 3.3 movie_credits

Normalised cast and crew for searchable lookups by actor, director, etc.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| movie_id | UUID (FK → movies) | The film |
| person_name | VARCHAR(255) | Actor/director name |
| tmdb_person_id | INTEGER | TMDB person ID (for linking to their profile) |
| role | VARCHAR(50) | cast, director, writer, producer, composer |
| character_name | VARCHAR(255) | Character played (for cast only) |
| display_order | INTEGER | Billing order |

*Indexed on `person_name` and `tmdb_person_id` for fast lookups.*

### 3.4 collection_items

Represents a physical (or digital) copy owned. A movie can appear multiple times if owned in multiple formats.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| movie_id | UUID (FK → movies) | Links to the movie entity |
| formats | JSONB | Array of formats, e.g. ["blu_ray", "download"] for combo packs. GIN-indexed for fast filtering |
| location | VARCHAR(255) | Storage location as entered (e.g. "Front 2nd shelf") |
| section | VARCHAR(100) | Normalised area (Front, Back, Lounge, Garage, Digital) |
| shelf | VARCHAR(50) | Normalised shelf identifier |
| sub_category | VARCHAR(255) | Box set / director collection info |
| notes | TEXT | Any additional notes |
| purchase_price | DECIMAL(8,2) | What was paid (null if unknown) |
| price_is_estimate | BOOLEAN | True if auto-looked-up during import, false if manually entered |
| purchase_source | VARCHAR(255) | Where bought (eBay, HMV, charity shop, etc.) |
| purchase_date | DATE | When purchased |
| condition | VARCHAR(50) | new, like_new, good, acceptable, damaged |
| condition_updated_at | TIMESTAMP | When condition was last assessed |
| has_playback_issues | BOOLEAN | Flag for discs with known playback problems |
| playback_notes | TEXT | Details of any issues (skips at X, disc rot, etc.) |
| suggest_exclude | BOOLEAN | If true, excluded from "Feeling Lucky" and other suggestions. Default false |
| photo_urls | JSONB | Array of Supabase Storage URLs for user-uploaded photos (steelbook front, spine, inserts, etc.) |
| barcode | VARCHAR(50) | EAN/UPC barcode if scanned |
| video_specs | JSONB | Video codec, resolution, HDR formats — e.g. {"resolution": "2160p", "hdr": ["Dolby Vision", "HDR10+"], "codec": "HEVC", "aspect_ratio": "2.39:1"} |
| audio_specs | JSONB | Audio tracks — e.g. [{"language": "English", "format": "Dolby Atmos", "channels": "7.1.4"}, {"language": "English", "format": "DTS-HD MA", "channels": "5.1"}] |
| special_features | JSONB | Array of special features / extras on the disc |
| region_code | VARCHAR(20) | Blu-ray region (A, B, C, Free, etc.) |
| release_label | VARCHAR(100) | Publisher/label (Arrow, Criterion, Warner, etc.) |
| specs_source | VARCHAR(50) | Where AV specs came from (bluray_com, manual, imported) |
| specs_last_synced | TIMESTAMP | When specs were last fetched/updated |
| listing_status | VARCHAR(30) | in_collection, listed_for_sale, sold, donated. Default: in_collection |
| ebay_listing_url | TEXT | Link to active eBay listing if listed for sale |
| listing_price | DECIMAL(8,2) | Price listed at on eBay (if applicable) |
| added_by | UUID (FK → profiles) | Who added it (admin only) |
| added_at | TIMESTAMP | When it was added to the collection |

### 3.5 wanted_list

Movies the admin wants to purchase. Drives the price tracking system.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| movie_id | UUID (FK → movies) | The desired film |
| preferred_format | VARCHAR(50) | Desired format (4k_uhd, blu_ray, etc.) |
| max_price | DECIMAL(8,2) | Price threshold for notifications |
| currency | VARCHAR(3) | Default 'GBP' |
| is_active | BOOLEAN | Whether still looking |
| added_by | UUID (FK → profiles) | Who added it |
| added_at | TIMESTAMP | When added to the wanted list |

### 3.6 price_checks

Log of every price found by the daily scraping job. A Postgres trigger runs after each insert to evaluate whether the price is below the linked `wanted_list.max_price` — if so, a push notification is queued (respecting the `notification_sent` flag to prevent duplicate alerts for the same listing URL).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| wanted_id | UUID (FK → wanted_list) | The wanted list entry |
| retailer_id | UUID (FK → retailers) | Which retailer the price came from |
| retailer_name_snapshot | VARCHAR(100) | Retailer name at time of check (preserved if retailer deleted) |
| price | DECIMAL(8,2) | Found price |
| condition | VARCHAR(50) | new, used, refurbished |
| listing_type | VARCHAR(50) | buy_it_now, auction, fixed_price |
| url | TEXT | Direct link to the listing |
| notification_sent | BOOLEAN | True if a price-drop alert was pushed for this check |
| checked_at | TIMESTAMP | When the price was found |

*Raw rows are aggregated into `price_history_daily` after 90 days (see section 9.3) to keep the table lean.*

### 3.7 watch_log

Personal watch history. Each user can log when they watched a film and leave a rating.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| movie_id | UUID (FK → movies) | The watched film |
| user_id | UUID (FK → profiles) | Who watched it |
| watched_at | DATE | When they watched it |
| is_rewatch | BOOLEAN | False = first watch, True = rewatch |
| personal_rating | DECIMAL(2,1) | Personal rating (0.5–5.0 scale) |
| review | TEXT | Optional personal notes/review |

### 3.8 loans

Tracks discs lent to friends/family.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| collection_item_id | UUID (FK → collection_items) | The specific disc lent |
| borrower_name | VARCHAR(255) | Who has it |
| lent_date | DATE | When it was lent |
| due_date | DATE | Optional expected return date |
| returned_date | DATE | Null until returned |
| reminder_sent | BOOLEAN | Whether a follow-up reminder has been sent |
| notes | TEXT | Any notes |

### 3.9 movie_night_sessions

Tracks collaborative "Movie Night" swipe sessions.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Session identifier |
| created_by | UUID (FK → profiles) | Who started the session |
| filters | JSONB | Genre, decade, runtime filters applied |
| status | VARCHAR(20) | active, matched, expired |
| matched_movie_id | UUID (FK → movies) | The movie both users agreed on (null until matched) |
| created_at | TIMESTAMP | When session started |

### 3.10 movie_night_votes

Individual votes within a Movie Night session.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| session_id | UUID (FK → movie_night_sessions) | The session |
| user_id | UUID (FK → profiles) | Who voted |
| movie_id | UUID (FK → movies) | The movie being voted on |
| vote | BOOLEAN | True = like, False = skip |
| voted_at | TIMESTAMP | When they voted |

*Unique constraint on (session_id, user_id, movie_id) to prevent double-voting.*

### 3.11 email_accounts

Connected email inboxes to scan for purchase confirmations. Admin can connect multiple accounts across providers.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| user_id | UUID (FK → profiles) | Who owns the account (admin only) |
| provider | VARCHAR(50) | gmail, outlook, icloud, yahoo, generic_imap |
| email_address | VARCHAR(255) | The address being scanned |
| auth_type | VARCHAR(30) | oauth, app_password |
| oauth_tokens | JSONB | Encrypted OAuth refresh/access tokens (for Gmail, Outlook) |
| imap_config | JSONB | Encrypted IMAP host/port/username/password (for iCloud, Yahoo, generic IMAP) |
| scan_frequency | VARCHAR(20) | daily, hourly, manual |
| is_enabled | BOOLEAN | Whether scanning is active |
| last_scan_at | TIMESTAMP | When last scanned |
| last_scan_status | VARCHAR(50) | success, auth_error, connection_error |
| added_at | TIMESTAMP | When connected |

*All credentials are encrypted at rest using Supabase Vault or a dedicated encryption key. Only read access is requested — no email is ever sent.*

### 3.12 purchase_candidates

Tracks potential wanted-list purchases detected via email scanning.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| wanted_id | UUID (FK → wanted_list) | The matched wanted item |
| email_account_id | UUID (FK → email_accounts) | Which email account detected it |
| retailer_name | VARCHAR(100) | eBay, Amazon, HMV, etc. — inferred from email sender |
| detected_price | DECIMAL(8,2) | Price from the order confirmation |
| order_date | DATE | When the order was placed |
| email_message_id | VARCHAR(255) | Provider-specific message ID for reference |
| status | VARCHAR(30) | pending_review, confirmed, dismissed |
| detected_at | TIMESTAMP | When the candidate was created |
| reviewed_at | TIMESTAMP | When admin confirmed or dismissed |

*Admin sees pending candidates in a review queue. Confirming creates a collection_item and removes the wanted_list entry.*

### 3.13 chat_conversations

Chat history with the AI assistant.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Conversation identifier |
| user_id | UUID (FK → profiles) | Who started the conversation |
| title | VARCHAR(255) | Auto-generated summary |
| created_at | TIMESTAMP | When started |
| updated_at | TIMESTAMP | Last message timestamp |

### 3.14 chat_messages

Individual messages within a chat conversation.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Message identifier |
| conversation_id | UUID (FK → chat_conversations) | The conversation |
| role | VARCHAR(20) | user, assistant, tool |
| content | TEXT | Message text |
| tool_calls | JSONB | Tool/function calls made (for assistant messages) |
| tool_results | JSONB | Results from tool calls |
| input_method | VARCHAR(20) | text, voice — for user messages |
| input_tokens | INTEGER | Input tokens consumed (Claude API billing) |
| output_tokens | INTEGER | Output tokens generated |
| cost_cents | INTEGER | Estimated cost in cents, for per-user usage caps |
| created_at | TIMESTAMP | When sent |

### 3.15 completion_sets

Cached reference lists for completion tracking (Hitchcock filmography, Best Picture winners, franchises, box sets, etc.). Refreshed weekly.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| set_type | VARCHAR(50) | director, actor, franchise, box_set, award, curated_list |
| set_key | VARCHAR(255) | Identifier — e.g. tmdb_person_id, franchise slug, award name |
| set_name | VARCHAR(255) | Display name (e.g. "Alfred Hitchcock", "Best Picture Winners") |
| member_tmdb_ids | JSONB | Array of TMDB movie IDs in this set |
| metadata | JSONB | Extra info (e.g. award year, franchise poster) |
| last_refreshed | TIMESTAMP | When the set was last updated |

*Enables fast completion queries like "10 of 20 Hitchcock films owned" by intersecting member_tmdb_ids with the movies table.*

### 3.16 retailers

Configurable list of online retailers to scrape for deals and prices. Admin can add, edit, or disable retailers via the UI.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| name | VARCHAR(100) | Display name (e.g. HMV, Zavvi, Arrow Video) |
| base_url | TEXT | Root URL of the retailer |
| deals_url | TEXT | URL of their deals/sale page |
| search_url_template | TEXT | URL pattern for searching a title (e.g. `https://www.hmv.com/search?q={query}`) |
| scraper_type | VARCHAR(50) | built_in, generic_css, custom — determines scraping strategy |
| scraper_config | JSONB | Selectors for title, price, discount, URL (used by generic_css scraper) |
| scrape_frequency | VARCHAR(20) | daily, weekly, manual |
| enabled | BOOLEAN | Whether to include in scraping runs |
| currency | VARCHAR(3) | Default GBP |
| region | VARCHAR(2) | ISO country code, default GB |
| notes | TEXT | Admin notes |
| added_by | UUID (FK → profiles) | Who added it |
| added_at | TIMESTAMP | When added |
| last_scraped_at | TIMESTAMP | When last successfully scraped |
| last_scrape_status | VARCHAR(50) | success, error, blocked |
| last_scrape_error | TEXT | Error message if last run failed |

*Seeded with default retailers (HMV, Zavvi, Amazon UK, Blu-ray.com, Arrow Video, Criterion). Admin can add more via the Settings UI.*

### 3.17 deals

Scraped 4K/Blu-ray deals from various retailers. Refreshed daily.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| movie_id | UUID (FK → movies) | Matched movie (null if unmatched) |
| title_raw | VARCHAR(500) | Title as scraped |
| format | VARCHAR(50) | 4k_uhd, blu_ray, etc. |
| retailer_id | UUID (FK → retailers) | Which retailer the deal came from |
| retailer_name | VARCHAR(100) | Denormalised for easy display |
| current_price | DECIMAL(8,2) | Sale price |
| original_price | DECIMAL(8,2) | RRP or previous price |
| discount_percent | INTEGER | Calculated % off |
| url | TEXT | Direct link to the deal |
| already_owned | BOOLEAN | True if in collection (skip in notifications) |
| dismissed | BOOLEAN | User dismissed this deal |
| found_at | TIMESTAMP | When scraped |
| expires_at | TIMESTAMP | Estimated deal end if available |

### 3.18 price_history_daily

Aggregated daily price summaries, populated by a nightly job that rolls up `price_checks` older than 90 days into min/max/avg/count per day per retailer, then deletes the raw rows. Keeps the database lean while preserving trend data for charts.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| wanted_id | UUID (FK → wanted_list) | The wanted item |
| retailer_id | UUID (FK → retailers) | Retailer |
| date | DATE | Day of aggregation |
| min_price | DECIMAL(8,2) | Lowest price seen that day |
| max_price | DECIMAL(8,2) | Highest price seen that day |
| avg_price | DECIMAL(8,2) | Average price |
| check_count | INTEGER | Number of checks aggregated |

### 3.19 notification_preferences

Per-user notification settings for granular control over push alerts.

| Column | Type | Notes |
|--------|------|-------|
| user_id | UUID (PK, FK → profiles) | Owner |
| price_drops | BOOLEAN | Notify on wanted list price drops |
| deals | BOOLEAN | Notify on new deals matching interests |
| new_releases | BOOLEAN | Notify on upcoming releases in collected genres |
| loan_reminders | BOOLEAN | Notify when loaned items are overdue |
| purchase_candidates | BOOLEAN | Notify when email scan detects a purchase |
| on_this_day | BOOLEAN | Notify with "on this day you watched..." memories |
| digest_mode | VARCHAR(20) | realtime, daily, weekly |
| digest_send_time | TIME | When to send daily/weekly digest (e.g. 09:00) |
| quiet_hours_start | TIME | No notifications during quiet hours (e.g. 22:00) |
| quiet_hours_end | TIME | End of quiet hours (e.g. 08:00) |

### 3.20 admin_actions

Audit log of admin actions for accountability and "show me what changed this month" queries.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| user_id | UUID (FK → profiles) | Who performed the action |
| action_type | VARCHAR(50) | create, update, delete, restore, bulk_import, etc. |
| target_table | VARCHAR(50) | Which table was affected |
| target_id | UUID | Row ID affected |
| changes | JSONB | Diff of changes (old vs new values) |
| timestamp | TIMESTAMP | When it happened |

### 3.21 gift_links

Shareable public URLs for Dad's wanted list so family can see what to buy.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Public slug used in the URL |
| created_by | UUID (FK → profiles) | Admin who created the link |
| title | VARCHAR(255) | Display title (e.g. "Mark's Christmas List") |
| filter_config | JSONB | Optional filters (max price, genres, formats) |
| expires_at | TIMESTAMP | Optional expiry |
| view_count | INTEGER | Track how many times accessed |
| is_active | BOOLEAN | Can be deactivated without deleting |
| created_at | TIMESTAMP | When created |

*Public endpoint `/gift/{slug}` renders a simple read-only page showing Dad's wanted list, with retailer links for buyers.*

### 3.22 shelf_qr_codes

Maps QR codes to physical storage locations for instant navigation.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | QR code slug |
| section | VARCHAR(100) | Which area (Front, Back, Lounge, Garage) |
| shelf | VARCHAR(50) | Which shelf |
| label | VARCHAR(255) | Human-readable label printed on the QR |
| printed_at | TIMESTAMP | When printed/generated |

*Scanning a shelf's QR code in the app opens a filtered view showing all items at that location.*

### 3.23 smart_collections

User-defined dynamic filter sets that update as the collection changes (like iTunes smart playlists).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| user_id | UUID (FK → profiles) | Owner (private by default) |
| name | VARCHAR(255) | Display name (e.g. "Unwatched 4Ks from the 2010s") |
| icon | VARCHAR(50) | Lucide icon name for visual identity |
| filters | JSONB | Filter criteria — format, genre, decade, watched status, HDR, runtime, etc. |
| sort_by | VARCHAR(50) | Sort field |
| sort_order | VARCHAR(10) | asc, desc |
| is_pinned | BOOLEAN | Whether shown on home dashboard |
| display_order | INTEGER | Order in the sidebar |
| created_at | TIMESTAMP | When created |

*Evaluated at query time — no materialisation. Results update instantly as the collection changes.*

### 3.24 box_sets

Physical box sets and franchise collections that group multiple collection_items under one umbrella.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| name | VARCHAR(255) | e.g. "Kubrick Box Set", "Columbia Noir Vol 4", "Evil Dead Trilogy" |
| label | VARCHAR(100) | Publisher (Criterion, Arrow, Indicator, etc.) |
| volume_number | INTEGER | For series like "Columbia Noir #4" |
| series_id | UUID (self-FK) | Links to the parent series (e.g. all Columbia Noir vols) |
| expected_count | INTEGER | How many films should be in the set |
| poster_url | TEXT | Box artwork for display |
| notes | TEXT | Admin notes |
| created_at | TIMESTAMP | When added |

### 3.25 box_set_items

Junction between box_sets and collection_items.

| Column | Type | Notes |
|--------|------|-------|
| box_set_id | UUID (FK → box_sets) | The set |
| collection_item_id | UUID (FK → collection_items) | The film copy |
| disc_number | INTEGER | Position within the set |

*Composite PK on (box_set_id, collection_item_id).*

### 3.26 release_calendar

Upcoming film releases (physical and streaming) Dad cares about, populated from TMDB and curated sources.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Internal identifier |
| movie_id | UUID (FK → movies) | The film (nullable — upcoming films may not yet exist in TMDB) |
| title | VARCHAR(500) | Title if no TMDB match yet |
| release_type | VARCHAR(50) | 4k_uhd_release, blu_ray_release, streaming_release, theatrical, award_ceremony, sale_event |
| release_date | DATE | When |
| label | VARCHAR(100) | Publisher/distributor |
| region | VARCHAR(2) | ISO country code |
| url | TEXT | Source or pre-order link |
| is_wishlist_match | BOOLEAN | True if matches an active wanted_list item |
| notified | BOOLEAN | Whether user was already notified |
| added_at | TIMESTAMP | When added to calendar |

*Subscribable as an iCal feed at `/api/v1/calendar.ics` for Apple Calendar / Google Calendar integration.*

---

## 4. API Design

The backend exposes a versioned RESTful API. All endpoints are prefixed with **`/api/v1/`** to enable future breaking changes without disrupting clients. All endpoints return JSON with a consistent envelope:

```json
{
  "data": { ... },
  "meta": { "page": 1, "per_page": 20, "total": 1866 },
  "errors": null
}
```

Error responses follow a standard format:

```json
{
  "data": null,
  "errors": [{ "code": "NOT_FOUND", "message": "Movie not found", "field": null }]
}
```

Authentication is via JWT Bearer tokens from Supabase Auth. All list endpoints support pagination (`?page=1&per_page=20`) and sorting (`?sort_by=title&sort_order=asc`). Rate limits apply to public endpoints and abuse-prone paths.

### 4.1 Key Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| **Collection** | | | |
| GET | /api/v1/movies | Any | Browse/search movies with filters (title, genre, runtime, format, year, actor, director) |
| GET | /api/v1/movies/{id} | Any | Full movie detail including TMDB data, collection items, watch history, recommendations |
| POST | /api/v1/collection | Admin | Add a new item to the physical collection |
| PUT | /api/v1/collection/{id} | Admin | Edit a collection item (location, format, notes) |
| DELETE | /api/v1/collection/{id} | Admin | Remove an item from the collection |
| GET | /api/v1/collection/search | Any | Search owned movies with location info |
| GET | /api/v1/collection/stats | Any | Collection statistics (value, format breakdown, genre breakdown, etc.) |
| GET | /api/v1/collection/export | Any | Export collection as CSV or PDF |
| GET | /api/v1/collection/{id}/specs | Any | Fetch AV specs (video/audio) for this item |
| POST | /api/v1/collection/{id}/specs/sync | Admin | Re-fetch specs from Blu-ray.com |
| PUT | /api/v1/collection/{id}/specs | Admin | Manually edit AV specs |
| GET | /api/v1/collection/filter/by-specs | Any | Filter collection by spec criteria (e.g. all Dolby Atmos discs, all Dolby Vision 4Ks) |
| **Barcode** | | | |
| POST | /api/v1/barcode/lookup | Admin | Look up a barcode → return TMDB match for quick add |
| **Format Upgrade & eBay Listing** | | | |
| POST | /api/v1/collection/{id}/upgrade | Admin | Flag old format as superseded, add new format, trigger eBay price suggestion |
| GET | /api/v1/collection/{id}/sell-price | Admin | Get suggested eBay sell price based on recent sold listings for title + format |
| POST | /api/v1/collection/{id}/list-on-ebay | Admin | Generate pre-filled eBay listing URL (or draft via eBay Sell API) with suggested/overridden price |
| PUT | /api/v1/collection/{id}/mark-sold | Admin | Mark a listed item as sold and optionally remove from collection |
| **Wanted List & Prices** | | | |
| POST | /api/v1/wanted | Admin | Add a movie to the wanted list with price threshold |
| GET | /api/v1/wanted | Any | View the wanted list with latest prices |
| DELETE | /api/v1/wanted/{id} | Admin | Remove from wanted list |
| GET | /api/v1/wanted/{id}/price-history | Any | Price check history for a wanted item |
| **Watch Log** | | | |
| POST | /api/v1/watch-log | Any | Log a watch with optional rating/review |
| GET | /api/v1/watch-log | Any | View personal watch history |
| **Lending** | | | |
| POST | /api/v1/loans | Admin | Mark a disc as lent |
| PUT | /api/v1/loans/{id}/return | Admin | Mark a disc as returned |
| GET | /api/v1/loans | Any | View active and past loans |
| **Discovery** | | | |
| GET | /api/v1/discover/random | Any | Get a random movie suggestion (filters optional) |
| POST | /api/v1/discover/smart | Any | Natural language query → filtered results |
| GET | /api/v1/discover/new-releases | Any | Upcoming/recent films in collected genres |
| GET | /api/v1/discover/recommendations/{movie_id} | Any | TMDB similar/recommended films, flagged as owned or not |
| **Movie Night** | | | |
| POST | /api/v1/movie-night | Any | Start a new Movie Night session |
| GET | /api/v1/movie-night/{id}/next | Any | Get next movie to vote on |
| POST | /api/v1/movie-night/{id}/vote | Any | Submit a vote (like/skip) |
| GET | /api/v1/movie-night/{id}/status | Any | Check for a match |
| **Streaming** | | | |
| GET | /api/v1/movies/{id}/streaming | Any | Where to stream this movie (region-aware) |
| **Import & Admin** | | | |
| POST | /api/v1/import/spreadsheet | Admin | Bulk import from spreadsheet file |
| POST | /api/v1/import/imdb | Admin | Import IMDB ratings/watchlist CSV |
| POST | /api/v1/admin/enrich-batch | Admin | Trigger background TMDB enrichment for un-enriched movies |
| GET | /api/v1/admin/enrich-status | Admin | Check progress of batch enrichment |
| GET | /api/v1/activity | Any | Recent activity feed (additions, watches, price alerts) |
| **Completion & Insights** | | | |
| GET | /api/v1/insights/completion | Any | All completion sets with progress (director, actor, franchise, awards, box sets) |
| GET | /api/v1/insights/completion/{set_id} | Any | Detailed view of one set — owned vs missing with poster thumbnails |
| POST | /api/v1/insights/completion/{set_id}/add-missing-to-wanted | Admin | Bulk-add all missing items from a set to the wanted list |
| GET | /api/v1/insights/format-upgrades | Any | Films where a higher format (4K) is available but not owned |
| GET | /api/v1/insights/decade-coverage | Any | Film count by decade |
| GET | /api/v1/insights/genre-depth | Any | Genre distribution and relative depth |
| **Deals** | | | |
| GET | /api/v1/deals | Any | Current 4K/Blu-ray deals, filtered to exclude owned items by default |
| POST | /api/v1/deals/{id}/dismiss | Admin | Dismiss a deal from the feed |
| POST | /api/v1/deals/{id}/add-to-wanted | Admin | Add the deal's film to the wanted list |
| **Retailers** | | | |
| GET | /api/v1/retailers | Admin | List all configured retailers |
| POST | /api/v1/retailers | Admin | Add a new retailer with scraper config |
| PUT | /api/v1/retailers/{id} | Admin | Edit retailer details or scraper selectors |
| DELETE | /api/v1/retailers/{id} | Admin | Remove a retailer |
| POST | /api/v1/retailers/{id}/test | Admin | Test scraper config against the retailer's page, return sample results |
| POST | /api/v1/retailers/{id}/scrape-now | Admin | Manually trigger a scrape run for this retailer |
| **Purchase Detection** | | | |
| GET | /api/v1/admin/email-accounts | Admin | List all connected email accounts |
| POST | /api/v1/admin/email-accounts/gmail/connect | Admin | Start Gmail OAuth flow |
| POST | /api/v1/admin/email-accounts/outlook/connect | Admin | Start Microsoft OAuth flow |
| POST | /api/v1/admin/email-accounts/imap | Admin | Connect via IMAP (iCloud, Yahoo, generic) with app password |
| PUT | /api/v1/admin/email-accounts/{id} | Admin | Update scan frequency or enable/disable an account |
| DELETE | /api/v1/admin/email-accounts/{id} | Admin | Disconnect and purge credentials |
| POST | /api/v1/admin/email-accounts/{id}/scan-now | Admin | Trigger a manual scan |
| GET | /api/v1/purchase-candidates | Admin | List detected purchase candidates awaiting review |
| POST | /api/v1/purchase-candidates/{id}/confirm | Admin | Confirm a candidate — creates collection_item, removes wanted entry |
| POST | /api/v1/purchase-candidates/{id}/dismiss | Admin | Dismiss a false-positive candidate |
| **Chat / AI Assistant** | | | |
| POST | /api/v1/chat/conversations | Any | Start a new chat conversation |
| GET | /api/v1/chat/conversations | Any | List previous conversations |
| GET | /api/v1/chat/conversations/{id} | Any | Get conversation history |
| POST | /api/v1/chat/conversations/{id}/messages | Any | Send a message, stream assistant response |
| DELETE | /api/v1/chat/conversations/{id} | Any | Delete a conversation |
| GET | /api/v1/chat/usage | Any | Current user's Claude API usage and remaining quota |
| **Notifications** | | | |
| GET | /api/v1/notifications/preferences | Any | Get current user's notification preferences |
| PUT | /api/v1/notifications/preferences | Any | Update notification preferences |
| POST | /api/v1/notifications/subscribe | Any | Register a Web Push subscription |
| POST | /api/v1/notifications/test | Any | Send a test push notification |
| **Photos** | | | |
| POST | /api/v1/collection/{id}/photos | Admin | Upload photo(s) for a collection item |
| DELETE | /api/v1/collection/{id}/photos/{photo_id} | Admin | Remove a photo |
| **Gift Links** | | | |
| GET | /api/v1/gift-links | Admin | List shareable gift links |
| POST | /api/v1/gift-links | Admin | Create a new shareable link |
| PUT | /api/v1/gift-links/{id} | Admin | Update a gift link (filters, expiry, active status) |
| DELETE | /api/v1/gift-links/{id} | Admin | Revoke a gift link |
| GET | /gift/{slug} | Public | Read-only gift list page (no auth required) |
| **QR Codes** | | | |
| GET | /api/v1/shelves/qr | Admin | List all shelf QR codes |
| POST | /api/v1/shelves/qr | Admin | Generate QR for a shelf location |
| GET | /api/v1/shelves/qr/{id}/print | Admin | Get printable QR code (PDF with label) |
| GET | /api/v1/shelves/qr/{id}/contents | Any | List items at the scanned shelf |
| **Memories & Suggestions** | | | |
| GET | /api/v1/memories/on-this-day | Any | What you watched on this date in previous years |
| GET | /api/v1/memories/rewatch-suggestions | Any | Films not watched in X months, worth revisiting |
| GET | /api/v1/calendar/sale-seasons | Any | Upcoming predictable sale events (Prime Day, Black Friday, Criterion Flash Sale) |
| **Trash / Soft Delete** | | | |
| GET | /api/v1/trash | Admin | View soft-deleted items across all tables |
| POST | /api/v1/trash/{table}/{id}/restore | Admin | Restore a soft-deleted row |
| DELETE | /api/v1/trash/{table}/{id}/permanent | Admin | Permanently delete |
| **Audit Log** | | | |
| GET | /api/v1/admin/audit | Admin | View admin action audit log with filters |
| **Smart Collections** | | | |
| GET | /api/v1/smart-collections | Any | List user's smart collections |
| POST | /api/v1/smart-collections | Any | Create a smart collection |
| PUT | /api/v1/smart-collections/{id} | Any | Update filters, name, pin status |
| DELETE | /api/v1/smart-collections/{id} | Any | Delete a smart collection |
| GET | /api/v1/smart-collections/{id}/results | Any | Current items matching the filters |
| **Box Sets** | | | |
| GET | /api/v1/box-sets | Any | List all box sets with completion status |
| POST | /api/v1/box-sets | Admin | Create a new box set grouping |
| PUT | /api/v1/box-sets/{id} | Admin | Edit a box set |
| POST | /api/v1/box-sets/{id}/items | Admin | Add a collection item to a box set |
| DELETE | /api/v1/box-sets/{id}/items/{item_id} | Admin | Remove from a box set |
| **Release Calendar** | | | |
| GET | /api/v1/calendar | Any | Upcoming releases and sale events |
| GET | /api/v1/calendar.ics | Any | iCal feed for Apple/Google Calendar |
| POST | /api/v1/calendar/subscribe/{event_id} | Any | Opt in to notifications for a specific event |
| **Backup & Restore** | | | |
| POST | /api/v1/admin/backup | Admin | Trigger an on-demand backup |
| GET | /api/v1/admin/backups | Admin | List available backups |
| GET | /api/v1/admin/backups/{id}/download | Admin | Download a backup archive |
| POST | /api/v1/admin/restore | Admin | Restore from an uploaded backup file |
| **Health** | | | |
| GET | /api/v1/health | Public | Liveness check |
| GET | /api/v1/health/ready | Public | Readiness check (DB, TMDB, email providers) |
| **Auth** | | | |
| POST | /api/v1/auth/login | Public | Login |
| POST | /api/v1/auth/register | Public | Register (invite-only or open, configurable) |
| GET | /api/v1/auth/me | Any | Current user profile |

---

## 5. External Integrations

### 5.1 TMDB API

TMDB is the primary source of movie metadata. The app uses `append_to_response` to bundle multiple requests into single API calls, reducing total calls by ~75%.

Key endpoints used:
- **Search** — `/search/movie` to match spreadsheet titles to TMDB entries during import
- **Details + Credits + Videos + Watch Providers** — `/movie/{id}?append_to_response=credits,videos,watch/providers` (single call for all enrichment data)
- **Discover** — `/discover/movie` for filtered browsing (genre, year, rating ranges, watch providers)
- **Recommendations** — `/movie/{id}/recommendations` for similar film suggestions
- **Upcoming** — `/movie/upcoming` for new releases feed

TMDB data is cached locally in the movies table and refreshed every 30 days (or on demand). Rate limiting is enforced at 3 requests/second with exponential backoff retry. The TMDB API key and read access token are stored as environment variables, never committed to source control.

### 5.2 IMDB Linking

Every TMDB movie record includes an `imdb_id` field. The app constructs IMDB links as: `https://www.imdb.com/title/{imdb_id}`. No IMDB API is used. Users can also do a one-time import of their IMDB ratings/watchlist CSV export.

### 5.3 Letterboxd Linking

Letterboxd does not offer a public API. The app first attempts a slug-based URL (`https://letterboxd.com/film/{slug}`), falling back to a search URL (`https://letterboxd.com/search/{encoded_title}`) if the slug cannot be determined. Letterboxd remains the primary platform for social logging and reviews.

### 5.4 Price Tracking

A scheduled job runs daily (via APScheduler) to check prices for items on the wanted list. Sources:

- **eBay UK** — scraping search results for used/new Blu-ray listings
- **Amazon UK** — product search via scraping
- **CEX** — used media retailer, scraping search results
- **HMV** — new media retailer

Each price check logs: price, condition (new/used/refurbished), listing type (buy it now/auction), and direct URL. When a price is found below the user-defined threshold, a push notification is sent via Web Push. All price checks are logged in the `price_checks` table for historical trend analysis.

During the initial spreadsheet bulk import, the system also attempts to look up current retail/resale prices for each item to provide estimated collection values. These are flagged as estimates (`price_is_estimate = true`).

### 5.5 Barcode Lookup

When a user scans a barcode via the PWA camera, the EAN/UPC is sent to the backend. The lookup flow:
1. Check a UPC-to-TMDB mapping cache (built over time)
2. If not cached, search eBay/Amazon for the UPC to find the movie title
3. Search TMDB with the resolved title
4. Return the matched movie for the user to confirm and add

### 5.6 eBay Sell Integration

Used when upgrading a format and listing the old disc for sale. Two approaches available:

**Option A — eBay Sell API (preferred):** Requires registering as an eBay developer and obtaining OAuth tokens. Allows creating draft listings programmatically with title, condition, price, category, and images. The admin reviews and publishes from the eBay app/site.

**Option B — Pre-filled listing URL (fallback):** If the Sell API proves too complex to set up, eBay supports pre-populated listing URLs that open the eBay "Sell" form with fields already filled in. Less seamless but zero API setup required.

**Pricing data:** The eBay Browse API's "sold items" search provides recent completed sale prices. The app calculates the median sold price for the title + format + UK region and presents it as the suggested list price. The admin can override before listing.

### 5.7 Multi-Provider Email Purchase Detection

The admin can connect **multiple email accounts across different providers** to maximise purchase detection coverage. Supported providers:

- **Gmail** — OAuth 2.0 via Google API, read-only scope
- **Microsoft (Outlook, Hotmail, Live)** — OAuth 2.0 via Microsoft Graph API
- **iCloud** — IMAP with app-specific password (Apple requires this, no OAuth for third parties)
- **Yahoo** — IMAP with app-specific password
- **Generic IMAP** — any provider with IMAP access (BT, Virgin, custom domains)

**Connection flow per provider:**

- **OAuth providers (Gmail, Outlook):** One-tap authorisation flow redirects to the provider, admin grants read-only mail access, refresh token stored encrypted
- **IMAP providers (iCloud, Yahoo, generic):** Admin enters email, IMAP host/port, and an app-specific password (with instructions linked for how to generate one per provider). Credentials encrypted at rest using Supabase Vault

**Scanning process (unified across providers):**

1. A scheduled job runs per account at the configured frequency (daily by default)
2. Fetches new messages since last scan from the inbox
3. Filters to messages from known retailer senders (eBay, Amazon, HMV, Zavvi, etc.) — retailer sender patterns are stored as a curated list
4. Parses the email body to extract item title, price, and order date using retailer-specific templates where possible
5. Falls back to an LLM (Claude API) for flexible extraction from unfamiliar templates
6. Fuzzy-matches extracted title against active wanted_list entries
7. If a likely match is found, creates a `purchase_candidate` record
8. Sends a push notification: "Did you buy [Title] from [Retailer]? Tap to add to collection."

**Privacy & security:**

- Only read access is requested (no email is ever sent)
- Emails are never stored — only extracted metadata (retailer, price, date, message ID)
- Credentials are encrypted at rest
- Admin can disconnect any account at any time, which purges all stored credentials
- Failed auth triggers a push notification asking the admin to re-authenticate

### 5.8 Claude API — AI Assistant

The chatbot uses Anthropic's Claude API with tool use (function calling). Claude is given a set of tools that map to existing backend endpoints, allowing it to:

- Query the collection (search, filter, look up specific films)
- Fetch movie details and watch history
- Retrieve stats (spend, genre breakdown, etc.)
- Suggest what to watch based on available time, mood, or genre
- Identify gaps ("what directors am I missing?")
- Admin-only: modify the collection, add to wanted list, relocate items (all with explicit user confirmation before executing)

System prompt includes user role (admin vs viewer) so Claude knows which tools are available. All tool calls and responses are logged to `chat_messages` for auditing. A usage cap can be applied per user to control API costs.

Voice input is supported via the browser's Web Speech API — users can tap a mic button, speak their question, and have it transcribed and sent to Claude. Optional voice output uses SpeechSynthesis to read Claude's replies aloud (useful for hands-busy situations).

### 5.9 Deals Scraping

A daily scheduled job scans configured retailer sites for 4K Blu-ray and special-edition deals. The retailer list is **fully configurable** — admin can add, edit, or disable retailers via the Settings UI.

**Default seeded retailers:**
- **Blu-ray.com** — deals page and price drop alerts
- **HMV** — sale section and weekly deals
- **Amazon UK** — 4K deals with Lightning Deal detection
- **Zavvi** — 4K sales and steelbook releases
- **Arrow Video** — direct from the boutique label
- **Criterion UK retailers** — during sale periods

**Adding a new retailer:**
Admin provides the retailer name, deals page URL, and CSS selectors for title, price, original price, and deal link. The app offers three scraper types:

1. **built_in** — pre-coded scrapers for known retailers (robust, handles site quirks)
2. **generic_css** — admin provides CSS selectors; works for most retailer sites with standard HTML
3. **custom** — for complex sites, admin provides a Python scraper function (advanced)

Before activating, admin can hit "Test scraper" which runs the config against the live page and shows sample results — confirming selectors are correct before scheduling daily runs.

**For each deal found:**
1. Match the title to a TMDB film
2. Check if already owned (collection_items) — skip unless format upgrade
3. Check if already on wanted list — if so, link to existing entry
4. Store in `deals` table with discount %, retailer, expiry
5. Daily digest push notification: "5 new 4K deals matching your interests"

**Error handling:** If a scrape fails (site down, selectors broken, blocked), the error is logged on the retailer record and admin is notified so they can update the config. The scheduler skips failed retailers after 3 consecutive failures until admin re-enables.

The deals feed on the frontend is filterable by genre, discount %, format, and retailer. Dad can dismiss deals he's not interested in or add to wanted list with one tap.

### 5.10 Blu-ray.com AV Specs

Blu-ray.com maintains detailed technical specs for every physical disc release. The app scrapes this to populate the `video_specs`, `audio_specs`, `special_features`, `region_code`, and `release_label` fields on collection items.

**Flow for a new item:**
1. When a collection_item is added (via spreadsheet import, barcode scan, or manual add), the backend queues a spec lookup job
2. The job searches Blu-ray.com for the title + format + year
3. Extracts: video codec, resolution, HDR formats (Dolby Vision, HDR10, HDR10+), aspect ratio, audio tracks (Dolby Atmos, DTS:X, DTS-HD MA, etc.) with languages and channel counts, special features list, region code, and publisher/label
4. Saves to the collection_item's JSONB spec fields

**Matching:** Fuzzy match on title + year + format. If multiple editions exist (Standard, Steelbook, Limited Edition, Criterion), admin is prompted to choose the correct one. Once selected, the URL is cached for future re-syncs.

**Manual override:** Admin can edit any spec field manually if the auto-scrape is wrong or missing. Manual edits are preserved across future re-syncs (marked with `specs_source = "manual"`).

**Rate limiting:** Respectful scraping with delays between requests; specs are cached indefinitely once fetched and only re-synced on admin request or when the edition changes.

---

## 6. Key Features Detail

### 6.1 Spreadsheet Import

The initial import reads the existing Excel spreadsheet (1,866 entries) and performs the following steps:

1. Parse the spreadsheet columns: Title, Format, Location, Category, Sub Category, Type
2. Normalise inconsistent data (casing, format names, location strings)
3. For each title, search TMDB to find the best match and retrieve the tmdb_id (rate-limited at 3 req/sec with exponential backoff)
4. Create a movie record enriched with TMDB metadata (using `append_to_response` for efficiency)
5. Create a collection_item record with the format(s) and location
6. Attempt price lookup for estimated collection value
7. Present unmatched titles for manual resolution via a review UI

The import is idempotent — running it again will not create duplicates. A match confidence score is calculated for each TMDB lookup, and low-confidence matches are flagged for review. Progress is reported via a websocket or polling endpoint so the UI can show a progress bar.

### 6.2 Collection Search & Location

Users can search the collection by title, genre, actor, director, format, or free text using PostgreSQL full-text search (`tsvector` with GIN index). Results display the movie poster, key info, and crucially the physical storage location. Location strings from the spreadsheet are normalised into structured fields (section, shelf) to enable filtering like "show me everything on the Front 2nd shelf."

All list results support pagination and sorting by title, year, rating, date added, or runtime.

### 6.3 Barcode Scanning

The PWA uses the browser camera API with quagga2 or zxing-js for client-side barcode reading. When a barcode is scanned:
1. The EAN/UPC is sent to the backend
2. The backend resolves it to a TMDB movie
3. The user sees the matched movie with poster and details
4. One tap to confirm and add to the collection
5. Duplicate detection warns if the movie is already owned (possibly in a different format)

### 6.4 Storage Location Suggestions

When adding a new purchase, the app analyses existing location patterns to suggest where to store it. The logic considers: genre groupings, director/actor collections, format (4K tends to be on Front 1st shelf), sub-category (box sets), and available space estimates based on item counts per shelf.

### 6.5 Duplicate Detection

When adding a new movie (via search or barcode scan), the app checks existing collection items and warns: "You already own this on DVD — add the 4K as well?" This prevents accidental double-buying and also helps track format upgrades.

### 6.6 Lending Tracker

Admin can mark any disc as "lent to [person]" with a date and optional due date. The loans page shows all active loans. If a due date passes, a push notification reminds the admin to follow up. Marking a loan as returned logs the return date.

### 6.7 Smart Discovery

Users can type natural language queries like "light-hearted comedy under 90 minutes" or "classic noir from the 1940s." The app translates these into structured filters using keyword extraction with predefined mappings (genre synonyms, decade shortcuts, runtime parsing). Results are drawn from the owned collection first, with an option to expand to the full TMDB catalog. Can be upgraded to LLM-powered (Claude API) in the future if the simple approach proves limiting.

### 6.8 Feeling Lucky

A randomiser that picks a movie from the collection (or full TMDB catalog). Users can optionally apply soft filters (genre, decade, max runtime) before hitting the button. If the suggestion is rejected, hitting the button again picks a new one. The algorithm avoids recently suggested titles within the same session.

### 6.9 Movie Night Mode

A collaborative feature for deciding what to watch together:
1. One user starts a Movie Night session, optionally setting genre/runtime filters
2. Both users are shown movies from the collection one at a time
3. Each user swipes or taps like/skip
4. When both users like the same movie, it's a match — notification sent to both
5. Powered by Supabase Realtime for live sync between users

### 6.10 New Releases Feed

A feed showing upcoming and recently released films in genres your dad collects, powered by TMDB's `/movie/upcoming` and `/discover/movie` with date and genre filters. Each entry has a one-tap "add to wanted list" button.

### 6.11 Similar Movie Recommendations

On each movie detail page, TMDB's `/movie/{id}/recommendations` powers a "You might also enjoy..." section. Movies are flagged as "Owned," "On Wanted List," or "Not Owned" — making it easy to discover gaps in the collection.

### 6.12 Collection Statistics Dashboard

A visual stats page showing:
- Total number of items and estimated collection value
- Breakdown by format (pie chart)
- Breakdown by genre (bar chart)
- Breakdown by decade (bar chart)
- Most-watched films
- Average personal rating
- Collection growth over time (line chart)
- Storage utilisation by shelf/section
- Top directors and actors in the collection

### 6.13 Activity Feed

The home page shows a timeline of recent activity: new additions, watch logs, price drop alerts, wanted list changes, loan activity. Example: "Dad added 3 new Blu-rays this week" or "Price drop: Shawshank Redemption 4K now £8.99 on eBay."

### 6.14 Collection Export

Export the full collection as CSV (for spreadsheet use) or PDF (for insurance/sharing). The export includes: title, year, format, location, purchase price, condition, and IMDB/TMDB IDs.

### 6.15 Offline Access

The service worker caches collection data, movie metadata, and poster images for offline browsing. Users can search and browse the collection, view movie details, and check storage locations without internet. Write operations (adding, editing) are queued and synced when connectivity returns.

### 6.16 Format Upgrade & eBay Listing

When Dad upgrades a film from one format to another (e.g. Blu-ray → 4K UHD), the app streamlines the entire process:

1. Dad adds the new 4K via scan or search
2. Duplicate detection triggers: "You already own this on Blu-ray — is this an upgrade?"
3. He confirms the upgrade
4. The old Blu-ray entry is flagged as superseded
5. The app looks up recent eBay sold listings for that title + old format to suggest a sell price
6. Dad can accept or override the suggested price
7. One tap generates a pre-filled eBay listing (via eBay Sell API or a pre-populated eBay listing URL with title, condition, price, and category)
8. The old collection item is marked as "listed_for_sale" with the eBay URL stored
9. Once sold, Dad marks it as "sold" — the item is archived or removed from the active collection

The suggested price is based on the median of recent completed eBay sales for the same title and format, filtered to UK listings. If no sold data is found, the app falls back to current active listing prices with a note that the estimate is less reliable.

### 6.17 Automatic Purchase Detection

The app can automatically detect when Dad purchases a film from his wanted list by scanning his email inbox:

1. Dad connects his Gmail account once via OAuth (read-only access)
2. A daily background job scans for order confirmation emails from retailers (eBay, Amazon, HMV, Zavvi, etc.)
3. When a purchase is detected that matches a wanted list entry, a purchase candidate is created
4. A push notification asks: "Did you buy [Title]? Tap to add to collection."
5. Dad reviews in a queue and confirms — the item is added to the collection with a suggested storage location, and the wanted entry is removed
6. False positives can be dismissed in one tap

Email parsing uses retailer-specific templates where possible, with an LLM fallback for flexible extraction from unfamiliar formats. No emails are ever sent — only read access is used.

### 6.18 AI Assistant (Chatbot)

An always-available conversational interface powered by the Claude API. Accessible from any page via a floating chat button. The assistant can:

**Query & Insight:**
- "What Kubrick films do I own?"
- "Show me everything under 90 minutes in comedy"
- "Which directors am I missing films from?"
- "How much have I spent on 4Ks this year?"
- "What's on the Back 3rd shelf?"

**Recommendations:**
- "We have 2 hours, suggest something we haven't seen recently"
- "I liked Dune — what similar films do I own?"
- "What should we watch for a rainy Sunday?"

**Admin Actions (with confirmation):**
- "Add The Batman (2022) 4K to my wanted list with a max price of £15"
- "Mark Shawshank Redemption as watched today with 5 stars"
- "Move all Hitchcock films to the Top Big Cabinet"

The chatbot uses tool use (function calling) to access the same backend endpoints as the UI. All actions that modify data require explicit confirmation in chat before execution. Conversation history is preserved so the admin can refer back to past queries. A per-user monthly API usage cap keeps costs controlled.

The chatbot effectively becomes a universal interface to the app — replacing the need to navigate menus for many tasks.

**Voice input:** Tap the mic icon to speak your question. The browser's Web Speech API transcribes it and sends it to Claude. Works on mobile (iOS Safari, Chrome Android) and desktop browsers. Optional voice output reads Claude's text replies aloud — useful while driving or doing chores.

### 6.19 Completion Insights

A dedicated Insights page surfaces completion tracking across multiple dimensions. Each set shows a progress bar, owned count, missing count, and a one-tap "Add all missing to wanted list" button.

**Completion set types:**
- **Director filmography** — "You own 10 of 20 Hitchcock films. Missing: Rear Window, Vertigo, ..."
- **Actor filmography** — "Clint Eastwood: 45 films. You own 28."
- **Franchise** — "James Bond: 27 films. You own 25." (auto-detected via TMDB collections)
- **Box set / label** — "Criterion Collection Noir Vol 1: 4 films. You own 3." (from existing sub_category data)
- **Award winners** — "Best Picture Oscars: 96 winners. You own 40."
- **Curated lists** — BFI Top 100, IMDb Top 250, Sight & Sound polls
- **Decade coverage** — "1940s: 200 films. 2020s: 15 films." — highlights under-represented eras
- **Genre depth** — "Film Noir: 180 owned (deep). Western: 12 owned (shallow)."
- **Format upgrades available** — "47 of your Blu-rays have 4K versions available. Consider upgrading: [list]"

Sets are refreshed weekly from TMDB and curated external sources. The Insights page is designed to feel rewarding — visual progress bars, "X% complete" badges, and milestone notifications when a set is completed.

### 6.20 4K / Blu-ray Deals Feed

A daily-refreshed feed of deals on 4K Blu-rays, special editions, and boutique releases from major UK retailers. Deals are:

- Automatically filtered to exclude items Dad already owns (unless it's a format upgrade opportunity)
- Ranked by discount percentage
- Tagged with genre and director for easy filtering
- One-tap to add to wanted list or dismiss

A daily push notification summarises the top deals: "5 new 4K deals today — best: Heat 4K for £12 (40% off)." Dad can opt into push alerts for specific triggers (e.g. "Notify me if any Hitchcock 4K goes below £15").

### 6.21 Custom Retailer Management

Admin can extend the deals scraper by adding new retailers through the Settings UI. The flow:

1. Admin enters retailer name, deals page URL, and search URL template
2. Chooses scraper type (built-in for known sites, generic CSS for new sites, or custom Python for complex ones)
3. For generic CSS: provides selectors for the product container, title, current price, original price, and link
4. Hits "Test scraper" — the app fetches the page, runs the selectors, and shows the first 5 extracted items for review
5. Once confirmed, saves and enables scraping on the chosen frequency (daily/weekly/manual)

The retailer management page shows each retailer's status, last scrape result, number of active deals found, and any errors. Failed retailers are flagged clearly so admin can fix selectors when sites change their layout.

This makes the deals feature future-proof — if Dad discovers a new boutique label or specialist retailer, he can add it himself without waiting for code changes.

### 6.22 Audio & Video Specs

Each collection item can store detailed technical specifications, automatically fetched from Blu-ray.com:

**Video:**
- Resolution (2160p for 4K, 1080p for Blu-ray, 480p for DVD)
- Codec (HEVC, AVC, etc.)
- HDR formats (Dolby Vision, HDR10, HDR10+, HLG)
- Aspect ratio

**Audio:**
- Per-track format (Dolby Atmos, DTS:X, Dolby TrueHD, DTS-HD Master Audio, Dolby Digital, etc.)
- Language
- Channel count (7.1.4, 5.1, 2.0 stereo, etc.)

**Other:**
- Special features list (commentaries, deleted scenes, featurettes)
- Region code (A, B, C, Free)
- Publisher/label (Arrow, Criterion, Warner, 4K Ultra HD Collection, etc.)

**Display:**
On the movie detail page, specs are shown as badges for quick scanning — a small "Dolby Atmos" chip, a "Dolby Vision" chip, etc. Dad can see at a glance that his 4K of *Blade Runner 2049* has Dolby Vision + Dolby Atmos without opening the case.

**Filter & Search:**
The collection can be filtered by spec criteria via a new filter panel:
- "Show me all Dolby Atmos discs"
- "All Dolby Vision 4Ks"
- "Everything with DTS:X audio"
- "Region-free imports"
- "All Arrow Video releases"

**Upgrade decisions:**
When Dad considers buying a 4K upgrade of something he owns on Blu-ray, the detail page shows a comparison: current disc specs vs the 4K version specs from Blu-ray.com — making the value of upgrading clear (e.g. "Blu-ray: 1080p, DTS-HD MA 5.1 → 4K: 2160p Dolby Vision, Dolby Atmos 7.1.4").

**Manual entry:**
For rare editions or items Blu-ray.com doesn't cover, Dad can enter specs manually. The edit form uses dropdowns for standard values (codec, HDR format) and free text for anything custom.

### 6.23 Quality Badges & "Best Format Owned"

Each movie row shows visual badges indicating the best version Dad owns:

- **Resolution badge** — "4K UHD" (teal), "Blu-ray" (blue), "DVD" (grey), "Digital" (gold outline)
- **HDR badge** — "Dolby Vision" (gold), "HDR10+" (dark blue), "HDR10" (light blue), none (hidden)
- **Audio badge** — "Atmos" (gold), "DTS:X" (dark red), "DTS-HD MA" (red), lower formats hidden

Badges appear on:
- Collection grid cards (compact pill style)
- Movie detail page (full badges with spec tooltip on hover/tap)
- Search results
- Movie Night card swipes

Derived from the `best_format_owned`, `best_hdr_owned`, and `best_audio_owned` fields on movies (auto-updated by Postgres trigger when collection items change). A quick filter "Show my best discs" surfaces items with top-tier specs across all three dimensions.

### 6.24 Rewatch & "On This Day" Memories

Drawing from the watch_log table:

- **On this day** — "You watched [Film] on this date X years ago. Watch again?" Appears on the home dashboard and as optional daily push notification
- **Rewatch suggestions** — "You haven't watched any Billy Wilder films in 6 months. Here are 3 from your collection"
- **Forgotten favourites** — Films Dad rated highly but hasn't watched since
- **Anniversary reminders** — Favourite films that just had a milestone release anniversary (20 years, 50 years, etc.)

### 6.25 Sale Season Awareness

The app tracks predictable annual sale events:

- **Prime Day** (July) — Amazon UK deals
- **Black Friday / Cyber Monday** (late November) — across all retailers
- **Boxing Day sales** (26 Dec onwards)
- **Criterion Flash Sale** (typically July and November)
- **Arrow Video / Vinegar Syndrome seasonal sales**
- **HMV sales** (various throughout year)

Two weeks before a known sale period, Dad gets a push notification: "Criterion Flash Sale expected in 2 weeks — review your wanted list and set max prices." The app also scans more aggressively during these windows.

### 6.26 Gift Mode & Shareable Wanted List

Dad can generate a **public shareable link** of his wanted list for family members to browse when buying him gifts:

1. Dad goes to the gift link creator, optionally applies filters (e.g. max £30, 4K only) and names the list ("Mark's Christmas 2026")
2. Shares the generated link (e.g. `/gift/a8f3b2c1`) via text, email, WhatsApp
3. Family see a read-only page with movie posters, formats, and direct retailer links
4. No login required for viewers
5. Dad can track view count, set expiry, or revoke the link anytime

Family can filter by "items under £20," "4K only," etc. to find gifts in their budget. This removes the awkward "what do you want?" conversation while keeping the wanted list private from general view.

### 6.27 Photo Uploads

Each collection item supports optional photo uploads stored in Supabase Storage:

- Steelbook front / back / spine
- Slipcover variations
- Inserts (booklets, postcards, posters)
- Condition documentation (for insurance)

Photos are displayed in a gallery on the collection item detail page. Useful for:
- Distinguishing visually similar editions
- Insurance documentation (paired with the PDF export)
- Pride of place for beloved boutique releases

Upload limited to 5 photos per item, max 5MB each. Uses the browser's camera for quick mobile capture or file picker for existing photos.

### 6.28 Shelf QR Codes

Dad can generate printable QR codes for each physical shelf/location:

1. In the admin UI, select "Generate QR for [Front 2nd Shelf]"
2. App generates a QR code and a print-ready PDF with a label (e.g. "Front 2nd Shelf — Scan to view contents")
3. Dad prints and attaches to the physical shelf
4. Scanning the QR in the app (via the scanner) instantly opens a filtered view of items at that location

Also works in reverse: when holding a disc, scan its barcode then the shelf's QR to instantly update the item's location in the database — great for reorganising.

### 6.29 Notification Preferences & Digest Mode

A granular preferences page lets each user control push notifications:

- **Per-category toggles:** price drops, deals, new releases, loan reminders, purchase candidates, on-this-day memories
- **Digest mode:** real-time (each event sent immediately), daily summary (one push at configured time), or weekly
- **Quiet hours:** no notifications between specified times (default 22:00–08:00)
- **Per-device:** subscriptions tracked per device so Dad can silence his phone while keeping desktop active

### 6.30 Trash & Audit Log

**Trash (soft delete):** Deleted collection items, wanted entries, watch logs, and movies move to Trash rather than being permanently removed. From the Trash UI, admin can:
- Restore individual items
- Permanently delete
- Empty trash (with confirmation)

Items older than 90 days are auto-purged.

**Audit log:** Every admin action (create, update, delete, restore, bulk import) is logged with who/what/when/diff. Searchable and filterable. Gives peace of mind that changes are traceable and recoverable.

### 6.31 Smart Collections

User-defined dynamic filter sets — save any combination of filters as a named collection that updates as the catalog changes. Inspired by iTunes smart playlists.

**Examples:**
- "Unwatched 4Ks from the 2010s"
- "Dolby Vision + Atmos films under 2 hours"
- "Films owned over 5 years, never watched"
- "Everything Arrow Video"
- "Box sets I haven't completed"

Smart collections appear in the sidebar with custom icons, can be pinned to the home dashboard, and support all the same sort/view options as the main collection view.

### 6.32 Box Sets & Franchise Tracking

Physical box sets are first-class entities. From the spreadsheet we already see many — Kubrick Box Set, Columbia Noir Vol 4, Evil Dead Trilogy, Sherlock Holmes Definitive Collection — currently captured only as a sub_category string.

**Features:**
- Group multiple collection_items under one box set
- **Completion tracking** per set — "You have 3 of 4 discs in Columbia Noir Vol 4"
- **Series awareness** — know when new volumes in a series are released
- **Dedicated box set view** with box artwork
- **Search by set** — "everything in my Criterion sets"
- **Box set value** aggregated from component prices for insurance

### 6.33 Release Calendar

A calendar view of upcoming releases Dad cares about, with iCal export so it syncs to Apple Calendar, Google Calendar, or any calendar app.

**Event types:**
- **New 4K UHD / Blu-ray releases** in collected genres or from favourite directors
- **Criterion announcements** and release dates
- **Boutique label releases** (Arrow, Indicator, Radiance, Vinegar Syndrome)
- **Streaming premieres** for unowned films on Dad's wishlist
- **Award ceremonies** (Oscars, BAFTAs, Cannes)
- **Known sale events** (Prime Day, Black Friday, Criterion Flash Sale)

**Features:**
- Monthly/weekly calendar view
- Filter by event type
- Opt-in to push notifications for specific events
- "Add to wanted list" for upcoming releases
- iCal feed at `/api/v1/calendar.ics` — subscribe once in Apple/Google Calendar, always up to date

---

## 7. Frontend Architecture & Design System

### 7.1 Design Principles

The app is designed to feel **premium, cinematic, and effortless**. Every interaction is considered. Every state (loading, empty, error) is intentional. Nothing is improvised.

**Inspirations:** Letterboxd's typography and restraint, Linear's keyboard-first flow and command palette, Arc/Raycast's fluid animations, Criterion's aesthetic restraint and film-forward presentation.

**Core tenets:**
- **Content first** — posters and film art take centre stage; chrome stays out of the way
- **Fast** — perceived performance > raw performance (skeleton loaders, optimistic UI, prefetching)
- **Keyboard-equal** — every primary action reachable without a mouse
- **Accessible** — WCAG 2.1 AA minimum, keyboard nav, screen reader support
- **Touch-first on mobile** — gestures, haptics, large tap targets

### 7.2 Design System

**Framework:** shadcn/ui components on Tailwind CSS with Radix UI primitives underneath.

**Colour Palette**

| Token | Light Mode | Dark Mode | Usage |
|-------|-----------|-----------|-------|
| background | #FAFAF9 | #0A0A0B | Page background |
| surface | #FFFFFF | #141416 | Cards, modals |
| surface-elevated | #FFFFFF | #1C1C1F | Popovers, dropdowns |
| border | #E7E5E4 | #27272A | Dividers, card borders |
| text-primary | #18181B | #FAFAFA | Headings, body |
| text-secondary | #52525B | #A1A1AA | Metadata, captions |
| text-tertiary | #71717A | #71717A | Placeholder, disabled |
| primary | #C8A86B (warm gold) | #D4AF7F | Primary actions, brand |
| accent | #B8475E (crimson) | #C95A73 | Highlights, call-outs |
| success | #16A34A | #22C55E | Confirmations |
| warning | #D97706 | #F59E0B | Cautions |
| error | #DC2626 | #EF4444 | Errors |
| quality-4k | #C8A86B (gold) | — | 4K UHD badges |
| quality-dolby-vision | #FFC24C | — | Dolby Vision badge |
| quality-hdr10 | #5B8DEF | — | HDR10 badge |
| quality-atmos | #8B6DBE (purple) | — | Dolby Atmos badge |
| quality-dts-x | #C4403E (red) | — | DTS:X badge |

**Typography**

- **Display / Headings:** Instrument Serif or Playfair Display (cinematic, editorial)
- **Body / UI:** Inter (clean, highly legible at all sizes)
- **Mono:** JetBrains Mono (for technical specs like codecs, region codes)

**Type scale:** 12 / 14 / 16 / 18 / 20 / 24 / 32 / 48 / 64 px. Line heights 1.2 for headings, 1.5 for body. Letter spacing tightened on large display sizes.

**Spacing scale:** 4px base grid — 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 px. No arbitrary values.

**Radii:** 4px (tight), 8px (default), 12px (cards), 16px (modals), 9999px (pills).

**Elevation:** subtle, layered shadows in light mode; luminosity shifts in dark mode (darker shadows don't work on dark backgrounds).

**Motion:** Framer Motion. Standard easings: `easeOut` for entries, `easeInOut` for transitions. Durations: 150ms (micro), 250ms (standard), 400ms (page), 600ms (hero reveal). Respect `prefers-reduced-motion`.

**Iconography:** Lucide React throughout. 16/20/24 px sizes. Icons always accompanied by a label (or aria-label on icon-only buttons).

### 7.3 Dark Mode & Theming

Dark mode is the **default** (appropriate for a film app used in the evening) with a light mode option. Theme preference stored per-user in profile and in localStorage for instant load.

**Optional additional themes:**
- **Cinema mode** — near-black background, minimal colour, large poster emphasis. One-tap toggle for when actually watching
- **High contrast** — accessibility variant meeting WCAG AAA

Themes controlled via CSS custom properties and `[data-theme]` attribute on `<html>`.

### 7.4 Component Patterns

**Cards:** movie cards come in three density variants (grid, list, compact) — user-toggleable globally. Hover state on desktop reveals quick actions; long-press on mobile.

**Skeleton loaders** for every async boundary — content-shaped placeholders, not generic spinners. Pulse animation at 1.5s cycle.

**Empty states:** every list has a purposeful empty state with icon, explanation, and primary CTA (e.g. wanted list empty → "Nothing on your wanted list. Browse the collection or search to add films.").

**Error states:** graceful degradation. If TMDB is down, show cached data with a subtle banner. If a scraper fails, show the deals feed with a "some retailers unavailable" note.

**Toasts** for transient feedback (added, removed, saved) — bottom-right, auto-dismiss at 4s, with undo where applicable.

**Modals and sheets:** modals for focused tasks (confirm delete, add to collection), bottom sheets on mobile for better ergonomics, side drawers for secondary content.

### 7.5 Keyboard Shortcuts & Command Palette

**Command palette (`⌘K` / `Ctrl K`)** — the single most powerful feature of the UI. One modal, fuzzy search across:
- Films in the collection
- Every page and setting
- Actions (add to wanted list, mark watched, log watch, etc.)
- Recent conversations with the AI assistant

**Global shortcuts:**

| Shortcut | Action |
|----------|--------|
| `⌘ K` / `Ctrl K` | Open command palette |
| `/` | Focus search |
| `?` | Show all shortcuts |
| `g` then `h` | Go to home |
| `g` then `c` | Go to collection |
| `g` then `w` | Go to wanted list |
| `g` then `s` | Go to stats |
| `n` | Add new item (admin) |
| `.` | Open chat with AI assistant |
| `Esc` | Close modal / clear search |

### 7.6 Optimistic UI & Perceived Performance

- Actions update the UI immediately, reconcile with the server in the background
- Failed operations rollback with a toast notification
- Prefetch on hover: hovering a movie card triggers metadata prefetch before click
- Service worker pre-caches the collection on first load for instant repeat visits

### 7.7 Mobile Gestures & Haptics

On touch devices:
- **Swipe right** on a film card → quick action (mark watched)
- **Swipe left** on a film card → remove / archive
- **Long press** → contextual menu
- **Pull to refresh** on lists
- **Pinch to zoom** on posters and photos
- **Haptic feedback** on key actions (add to wanted list, match found in Movie Night, successful scan)

### 7.8 Accessibility Commitment

**Target: WCAG 2.1 AA compliance.** Specifically:

- All interactive elements keyboard-reachable
- Visible focus indicators on every focusable element
- ARIA labels on all icon-only buttons
- Live regions for async updates (toasts, search results)
- Colour contrast ≥ 4.5:1 for normal text, ≥ 3:1 for large text and UI components
- `prefers-reduced-motion` respected — all animations replaced with instant transitions
- Screen reader tested on NVDA and VoiceOver before each release

### 7.9 Internationalisation & Localisation

Though the app is English-only initially, data is handled properly from day one:

- All timestamps stored in **UTC**, rendered in the user's **local timezone**
- Dates formatted via `Intl.DateTimeFormat` (e.g. `en-GB` → "16/04/2026")
- Currencies formatted via `Intl.NumberFormat` with the correct symbol (£1,299.00)
- Numbers formatted with correct separators (1,866 not 1866)
- Strings wrapped in an `i18n()` helper using `react-intl`, even if only one locale exists — makes future translation trivial

### 7.10 Pages & Routes

| Page | Route | Description |
|------|-------|-------------|
| Home / Dashboard | / | Activity feed, quick stats, random suggestion widget, collection highlights, on-this-day |
| Browse Collection | /collection | Filterable, sortable, paginated grid — supports grid / list / compact view modes |
| Movie Detail | /movie/:id | Hero backdrop, tabs (Overview / Cast & Crew / Your Copies / Watch History / Streaming / Recommendations), quality badges, IMDB/Letterboxd links |
| Search | /search | Full-text and smart search across collection and TMDB |
| Scan | /scan | Camera-based barcode scanner for quick add (Admin) |
| Wanted List | /wanted | Wanted movies with price tracking, history charts, and alerts |
| Movie Night | /movie-night | Collaborative swipe-to-match movie picker |
| Loans | /loans | Active and past lending log (Admin) |
| Stats | /stats | Collection statistics dashboard with charts |
| Add to Collection | /collection/add | Admin-only form to add a new purchase (manual or post-scan) |
| Import | /import | Admin-only spreadsheet and IMDB import tools with progress tracking |
| Settings | /settings | Profile, streaming region, theme, email connections |
| Chat | /chat | AI assistant chat interface with conversation history and voice input (also via floating button globally) |
| Purchase Review | /purchases | Admin-only queue of detected purchase candidates |
| Insights | /insights | Completion tracking — directors, actors, franchises, awards, decades, format upgrades |
| Deals | /deals | Daily-refreshed feed of 4K/Blu-ray deals |
| Smart Collections | /collections | User-saved dynamic filter sets ("Unwatched 4Ks from the 2010s", "Dolby Vision under 2hrs") |
| Box Sets | /box-sets | Dedicated view of physical box sets and franchise boxes |
| Calendar | /calendar | Upcoming releases, award ceremonies, known sale events (syncable to external calendars) |
| Memories | /memories | On-this-day, rewatch suggestions, forgotten favourites |
| Retailers | /settings/retailers | Admin-only — manage scraped retailers |
| Email Accounts | /settings/email | Admin-only — connect Gmail, Outlook, iCloud, Yahoo, IMAP |
| Notifications | /settings/notifications | Per-user preferences, digest mode, quiet hours |
| Gift Links | /settings/gift-links | Admin-only — manage shareable wanted list links |
| Public Gift Page | /gift/:slug | Public read-only gift list (no auth) |
| Shelf QR Codes | /settings/shelves | Admin-only — generate and print shelf QR codes |
| Backup & Restore | /settings/backup | Admin-only — trigger manual backups, download archives, restore |
| Trash | /trash | Admin-only — restore soft-deleted items |
| Audit Log | /admin/audit | Admin-only — view action history |
| Onboarding | /welcome | First-run guided setup (import, email connect, install PWA, notifications) |

### 7.11 Onboarding Flow

First-time admin login triggers a guided setup:

1. **Welcome** — brief intro, "Mark's Cinematic Universe is ready to ingest your collection"
2. **Import** — upload spreadsheet, live progress bar showing TMDB matching, unmatched items flagged for review
3. **Connect email** (optional) — for automatic purchase detection
4. **Install PWA** — prompt to add to home screen
5. **Enable notifications** — request push permission
6. **Pick theme** — dark (default) / light / cinema
7. **Quick tour** — 4-card carousel highlighting search, scan, chat, wanted list
8. **Done** — land on a pre-populated home dashboard

Viewer first-run is simpler: welcome, theme pick, done.

### 7.12 State & Data Strategy

- **TanStack Query** manages all server state (caching, refetching, optimistic updates, pagination)
- **Zustand** for local UI state (modals, filters, theme)
- **localStorage** for persistent user preferences (theme, view mode)
- **IndexedDB** for offline cache (collection data, pending offline writes)

### 7.13 Forms

All forms use **React Hook Form + Zod** for schema-driven validation. Shared Zod schemas between frontend and backend (via a `packages/shared` workspace) eliminate drift.

---

## 8. Authentication & Security

### 8.1 Authentication

- Supabase Auth handles user registration and login via email/password
- JWT tokens passed in the Authorization header for all API calls
- Role-based access enforced at the API level: Admin endpoints check role before processing
- Row Level Security (RLS) policies in Supabase provide an additional database-layer protection
- Registration can be set to invite-only to prevent unauthorised sign-ups

### 8.2 Secrets Management

- All secrets stored as environment variables — never committed to source control
- `.env.example` file documents all required variables (with dummy values)
- Doppler (or similar) recommended for team secret sync; single-dev setup can use local `.env`
- Per-environment secrets (dev, staging, production) — no shared keys across environments
- Third-party API keys rotated annually; notification issued 30 days before rotation

### 8.3 Rate Limiting

Applied via `slowapi` on:

- **Login endpoint** — 5 attempts per 15 minutes per IP
- **Registration** — 3 per hour per IP
- **Public gift page** — 60 requests per hour per IP
- **Chat / AI endpoints** — per-user daily message cap (configurable, default 100/day)
- **Barcode lookup** — 30 per minute per user (prevent abuse of UPC lookup)

### 8.4 Data Protection

- CORS configured to allow only the frontend origin
- TMDB, VAPID, Supabase, Claude API credentials in environment variables
- Email OAuth tokens and IMAP passwords encrypted at rest via Supabase Vault
- Photo uploads validated for type and size; virus scanning via ClamAV-as-a-service (optional)
- All user-uploaded content stored in Supabase Storage with signed URLs

### 8.5 Input Validation

- All request bodies validated via Pydantic models (backend)
- All forms validated via Zod schemas (frontend)
- Shared schema package ensures parity between client and server validation
- SQL injection prevented via SQLAlchemy parameterised queries
- XSS prevented via React's default escaping + DOMPurify for any raw HTML rendering

---

## 9. Reliability & Operations

### 9.1 TMDB Rate Limiting

TMDB allows ~40 requests per 10 seconds. The app enforces a client-side rate limit of 3 requests/second with exponential backoff retry (max 3 retries). Failed lookups are logged for manual retry via the admin UI.

### 9.2 Offline Sync

Write operations made offline (if any) are queued in IndexedDB and synced to the server when connectivity returns. Conflict resolution uses last-write-wins for simplicity.

### 9.3 Data Retention

- **`price_checks`** — raw rows aggregated into `price_history_daily` after 90 days, raw rows then deleted. Keeps the table lean while preserving trend charts
- **`admin_actions` (audit log)** — retained for 2 years by default, then archived to cold storage
- **`chat_messages`** — retained indefinitely unless the conversation is deleted by the user; usage stats kept for cost tracking
- **Soft-deleted items** — moved to "Trash" and auto-purged after 90 days if not restored
- **`purchase_candidates`** dismissed or confirmed — kept for 1 year as a record, then deleted

### 9.4 Dashboard Caching

The home dashboard aggregates data from multiple sources (activity feed, stats, suggestions, memories). To avoid a slow page load:

- Dashboard payload cached per-user in memory with a 5-minute TTL
- Cache invalidated on relevant writes (new collection item added, new watch logged, etc.)
- Optional Redis layer if deploying to production at scale (free in-process cache sufficient for two-user app)

### 9.5 Testing Strategy

**Each phase ships with tests — no phase is considered done without them.**

**Backend (pytest):**
- Unit tests for all business logic (importers, parsers, match algorithms)
- Integration tests for every API endpoint (happy path + error cases)
- Minimum 80% line coverage target
- Separate test database with transactional rollback per test

**Frontend (Vitest + React Testing Library):**
- Component tests for non-trivial components (forms, cards, filters)
- Hook tests for custom hooks
- Snapshot tests for layout stability (used sparingly)

**End-to-end (Playwright):**
- Critical flows only — login, import, add to collection, barcode scan, price drop alert, chat session
- Runs on every PR in CI
- Records video on failure for debugging

**Visual regression (optional):**
- Chromatic or Percy for key screens
- Catches unintended design drift

### 9.6 Observability

**Error tracking (Sentry):**
- Captures exceptions on both frontend and backend
- Source maps uploaded on deploy for readable stack traces
- Environment tagging (dev/staging/prod)
- Alert rules for error rate spikes

**Structured logging (structlog):**
- JSON logs with consistent schema
- Correlation IDs propagate through request lifecycle
- Log levels: debug / info / warn / error / critical
- PII scrubbing — no emails, passwords, or tokens logged

**Performance monitoring:**
- Web Vitals (LCP, FID, CLS) reported to Sentry
- API response time percentiles tracked
- Slow query log enabled on Postgres

**Health checks:**
- `/api/health` — simple liveness
- `/api/health/ready` — checks DB, TMDB, email providers, Supabase
- Used by uptime monitoring service (e.g. UptimeRobot free tier)

### 9.7 Database Migrations

**Alembic** manages all schema changes:

- Every schema change starts with an Alembic migration
- Migrations reviewed in PRs before merge
- Naming convention: `YYYY_MM_DD_HHMM_description.py`
- Rollback (downgrade) function required for every migration
- CI verifies migrations run cleanly forward and backward on a fresh DB
- Seed data (retailers, completion sets, known sale events) applied via dedicated seed scripts

### 9.8 CI/CD

**GitHub Actions** pipeline per PR:

1. **Lint** — ruff (Python) + ESLint (TS/JS) + Prettier
2. **Type check** — mypy (Python) + TypeScript
3. **Test** — backend + frontend + E2E
4. **Build** — frontend production bundle, backend Docker image
5. **Migration check** — verify Alembic migrations apply cleanly
6. **Security scan** — dependabot + Snyk for known vulnerabilities

On merge to `main`:
- Auto-deploy to staging
- Manual promotion to production (or auto with green E2E)

### 9.9 Backups

A weekly automated `pg_dump` via Supabase CLI exports the full database. Additionally:

- On-demand backups via admin UI
- Backup archives (compressed) stored in Supabase Storage with 90-day retention
- Monthly offsite backup to an external cloud (e.g. Backblaze B2) for disaster recovery
- Restore flow tested quarterly

---

---

## 10. Non-Functional Requirements

Targets that define "good enough" for the app to feel premium.

### 10.1 Performance

| Metric | Target |
|--------|--------|
| First Contentful Paint (LCP) | < 1.5s on 4G |
| Time to Interactive | < 2.5s on 4G |
| API response (P50) | < 100ms |
| API response (P95) | < 400ms |
| API response (P99) | < 1s |
| Search response | < 150ms for collection-only, < 500ms including TMDB |
| Collection grid render | 60fps during scroll with 2000+ items (virtualised) |
| Service worker offline load | < 500ms |

### 10.2 Availability & Reliability

- **Target uptime:** 99.5% (acceptable for a private app; allows ~3.5h downtime/month)
- **TMDB dependency:** graceful degradation — cached data shown when TMDB unreachable
- **Scraper resilience:** individual scraper failures don't break the app; disabled after 3 consecutive fails
- **Data durability:** zero data loss from crashes (write-ahead log, atomic transactions)

### 10.3 Scalability

- Designed for 2 users but scales to 10–20 without architectural change
- Database sized for 10,000 collection items (5x current)
- Beyond that, would need pgvector/dedicated search, read replicas, CDN for posters — out of scope for v1

### 10.4 Security & Privacy

- No PII beyond email addresses and movie watch history
- No tracking, no analytics by default (optional Plausible for usage stats, privacy-friendly)
- No data sold, shared, or exported except via explicit user action
- OWASP Top 10 considered throughout (XSS, SQL injection, broken auth, etc.)

### 10.5 Usability

- First-run to first-successful-search: < 5 minutes including import of 1866 items
- Add-to-collection via barcode scan: < 10 seconds end-to-end
- Onboarding completion rate: target 90%+ (admin) given motivation

### 10.6 Maintainability

- Type coverage: 100% in new code (mypy strict, TypeScript strict)
- Lint-clean (ruff, ESLint) on every commit
- Documentation-as-code: architecture doc updated with each significant change
- Runbook for common operational tasks (restoring a backup, adding a retailer, rotating secrets)

---

## 11. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| 1 | Retailer ToS violations via scraping | Medium | Medium | Respectful scraping (rate limits, user-agent), use official APIs where available, admin accepts risk. Fallback to manual price entry if blocked. |
| 2 | TMDB API quota exhaustion (limits ~40 req/10s) | Low | Medium | Rate limiter at 3 req/s, exponential backoff, cache aggressively (30-day TTL) |
| 3 | Scraper breakage when retailer sites change layout | High | Low | Configurable selectors via UI, "test scraper" tool, auto-disable after 3 failures, admin alert |
| 4 | Claude API costs spiral from chat usage | Medium | Medium | Per-user daily message cap + spend cap, token/cost logged per message, usage dashboard |
| 5 | Supabase free-tier limits hit | Low | Low | Monitor usage monthly; free tier generous for 2 users; fallback is £25/mo Pro plan |
| 6 | OAuth tokens expire or get revoked | Medium | Low | Refresh flow handled gracefully, admin notified via push when re-auth needed |
| 7 | Email scanning false positives | Medium | Low | Manual review queue — nothing is auto-added without admin confirmation |
| 8 | Barcode lookup fails (UPC not in any DB) | Medium | Low | Fallback to manual title search, user correction feeds UPC-TMDB cache for next time |
| 9 | eBay Sell API complexity | Medium | Low | Pre-filled listing URL fallback implemented in parallel; admin chooses |
| 10 | Data loss from user error | Low | High | Soft delete (trash UI), audit log, weekly backups, quarterly restore test |
| 11 | Security breach exposing collection/email data | Low | High | Encryption at rest, Supabase Vault for secrets, no PII beyond email, audit log for forensics |
| 12 | PWA push notifications unreliable on iOS | Medium | Low | Email fallback for critical alerts, user education in onboarding about iOS Add-to-Home-Screen requirement |
| 13 | Gmail/Outlook API policy changes | Low | Medium | Multiple providers supported; IMAP fallback works for almost any inbox |
| 14 | Single developer (bus factor) | High | High | Comprehensive docs, tests, deployment automation — project can be picked up by anyone |

---

## 12. Cost Estimate

Monthly operating costs at steady-state (2 users, 1,866-item collection, moderate usage).

| Service | Tier | Est. Monthly Cost (GBP) |
|---------|------|-------------------------|
| Supabase | Free tier (500MB DB, 1GB Storage, 2GB bandwidth) | £0 |
| TMDB API | Free (unlimited for personal use) | £0 |
| Claude API (Anthropic) | Pay-as-you-go, ~100 messages/day | £5–15 |
| Sentry | Free tier (5k errors/month) | £0 |
| Web hosting (frontend) | Vercel free tier | £0 |
| Backend hosting (Railway) | Hobby plan ($5/mo) | £4 |
| Domain name | Annual ~£12 | £1 |
| Push notifications | Free via VAPID | £0 |
| eBay API | Free (developer account) | £0 |
| UptimeRobot | Free tier | £0 |
| Email provider | Free via OAuth (Gmail, Outlook) | £0 |
| **Total (typical)** | | **£10–20/month** |

**Paid upgrades to consider if scaling:**
- Supabase Pro — £20/mo (if DB > 500MB or need higher limits)
- Railway Pro — £18/mo (for guaranteed resources)
- Claude API heavy usage — variable

**One-off costs:**
- Custom domain: ~£12/year
- Design assets (fonts, icons) — mostly free (Inter, Lucide), optional Instrument Serif from Google Fonts

---

## 13. Conventions

Consistency is non-negotiable. All contributors follow these.

### 13.1 Naming

| Context | Convention | Example |
|---------|-----------|---------|
| Database tables | snake_case plural | `collection_items` |
| Database columns | snake_case | `purchase_price` |
| Python (backend) | snake_case | `def add_to_collection()` |
| TypeScript vars/funcs | camelCase | `addToCollection()` |
| TypeScript components | PascalCase | `MovieCard.tsx` |
| JSON API fields | camelCase | `"purchasePrice": 19.99` |
| Environment variables | SCREAMING_SNAKE | `TMDB_API_KEY` |
| Git branches | kebab-case with prefix | `feat/barcode-scanning` |

### 13.2 API Response Shapes

**Success (single resource):**
```json
{ "data": { "id": "...", "title": "..." }, "meta": null, "errors": null }
```

**Success (list):**
```json
{ "data": [...], "meta": { "page": 1, "per_page": 20, "total": 1866 }, "errors": null }
```

**Error:**
```json
{ "data": null, "meta": null, "errors": [{ "code": "NOT_FOUND", "message": "...", "field": null }] }
```

### 13.3 Git Workflow

- **Main branch:** `main` — always deployable
- **Feature branches:** `feat/<description>` branched from main
- **Bug fixes:** `fix/<description>`
- **Chores:** `chore/<description>`
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) format — `feat:`, `fix:`, `chore:`, `docs:`, `test:`
- **PRs:** require passing CI + self-review checklist (tests, docs, migration if needed)
- **Squash merge** into main for clean history

### 13.4 Code Organisation

```
/
├── apps/
│   ├── api/              # FastAPI backend
│   └── web/              # React frontend (Vite)
├── packages/
│   └── shared/           # Shared Zod schemas, TS types, constants
├── migrations/           # Alembic migrations
├── docs/                 # Architecture, runbooks, ADRs
└── .github/workflows/    # CI/CD
```

### 13.5 Architecture Decision Records (ADRs)

Every significant technical decision captured as an ADR in `docs/adr/`. Format: number, title, status (proposed/accepted/superseded), context, decision, consequences. Referenced from code comments where relevant.

---

## 14. Entity Relationships & Glossary

### 14.1 Entity Relationship Overview

Core relationships (simplified):

```
profiles ──────────────────┐
  │                        │
  │ 1:N                    │ 1:N
  ▼                        ▼
collection_items ◄──── M:1 ──── movies ──── 1:N ──── movie_credits
  │                        │
  │ 1:N                    │ 1:N
  ▼                        ▼
loans, photos       wanted_list
                         │
                         │ 1:N
                         ▼
                    price_checks ──── N:1 ──── retailers
                         │
                         ▼
                    price_history_daily (aggregated)

profiles ──── 1:1 ──── notification_preferences
profiles ──── 1:N ──── email_accounts ──── 1:N ──── purchase_candidates
profiles ──── 1:N ──── chat_conversations ──── 1:N ──── chat_messages
profiles ──── 1:N ──── smart_collections
profiles ──── 1:N ──── gift_links

movies ──── 1:N ──── collection_items ──── N:M ──── box_sets (via box_set_items)
movies ──── N:M ──── completion_sets (via member_tmdb_ids)
movies ──── 1:N ──── watch_log ──── N:1 ──── profiles

retailers ──── 1:N ──── deals ──── N:1 ──── movies
shelf_qr_codes → maps to (section, shelf) on collection_items
```

A full ERD will be generated via SchemaSpy or similar as part of Phase 1a deliverables.

### 14.2 Glossary

| Term | Definition |
|------|-----------|
| **Admin** | User role with full CRUD permissions on the catalog — Dad (Mark) |
| **Viewer** | User role with read-only access to the catalog plus personal watch log and chat |
| **Movie** | Conceptual film entity — TMDB-matched, one per unique film |
| **Collection item** | A physical or digital copy owned — many can link to one movie |
| **Format** | Physical or digital type — 4k_uhd, blu_ray, dvd, download |
| **Wanted list** | Movies the admin wants to acquire |
| **Watch log** | Per-user history of films watched with optional ratings |
| **Loan** | Record of a collection item lent to someone |
| **Deal** | A price drop or sale detected by the daily scraper |
| **Retailer** | An online store scraped for prices/deals, configurable |
| **Purchase candidate** | A potential wanted-list purchase detected via email scanning, pending admin confirmation |
| **Completion set** | A curated list used for tracking progress (director filmography, award winners, etc.) |
| **Box set** | A physical set containing multiple discs/films (Columbia Noir, Kubrick Box, etc.) |
| **Smart collection** | User-saved dynamic filter set (like iTunes smart playlists) |
| **Gift link** | Public shareable URL of the wanted list for family members buying presents |
| **Quality badge** | Visual indicator of a movie's best-owned format, HDR, or audio spec |
| **Movie Night** | Collaborative swipe-to-match feature for choosing what to watch together |
| **Feeling Lucky** | Randomiser that suggests a movie from the collection |

---

## 15. Deployment Strategy

The app is built to run locally first, with a clear path to cloud deployment when ready.

### 15.1 Local Development

- Frontend: Vite dev server on port 5173
- Backend: Uvicorn (FastAPI) on port 8000
- Database: Supabase cloud (free tier) — no local DB setup needed

### 15.2 Production Options

| Option | Frontend | Backend | Cost |
|--------|----------|---------|------|
| Railway | Static hosting | Docker container | Free tier available, ~£5/mo after |
| Vercel + Railway | Vercel (free) | Railway container | Mostly free |
| Fly.io | Static files served by backend | Docker container | Free tier for small apps |
| Self-hosted | Nginx | Systemd service | Cost of hardware only |

---

## 16. Build Phases

The project is broken into **small, session-sized phases**. Each phase:

- Has **one focused goal** (achievable in a single working session)
- Ships with **automated tests** proving it works
- Has **explicit acceptance criteria** — the phase isn't done until these all pass
- Is **independently deployable** — the app still works after each phase

**Convention:** Phase IDs like `1.2` mean "stage 1, phase 2". Stages group related phases thematically.

---

### Session Protocol

**At the start of every session, print:**

```
=== PHASE [ID]: [NAME] ===
Model: [Sonnet 4.6 / Opus]
Status: [ ] Not started / [~] In progress / [✅] Complete

ACCEPTANCE CRITERIA:
- [ ] [criterion 1]
- [ ] [criterion 2]
...

Starting now.
```

**At the end of every session, print:**

```
=== PHASE [ID] COMPLETE ===
Date: [date]
All acceptance criteria passed: ✅
Notes: [any deviations or follow-ups]
Next phase: [ID] — [name]
```

A phase is **not complete** until every acceptance criterion is checked off. If a session runs out of tool calls mid-phase, note the last completed step and resume cleanly next session.

---

### Model Guide

| Tag | When to use |
|-----|-------------|
| 🟢 **Sonnet 4.6** | Straightforward implementation — CRUD, components, migrations, tests, API wiring. The default. |
| 🔴 **Opus** | Complex reasoning — matching algorithms, architecture decisions, tricky integrations, debugging gnarly failures, anything where the doc turns out to be wrong mid-build. |

Default to **Sonnet 4.6**. Switch to **Opus** only for phases tagged 🔴 or when genuinely stuck.

---

### Stage 0 — Foundations

**Phase 0.1: Repository Scaffolding** 🟢 Sonnet 4.6 ✅ 2026-04-20
- Monorepo structure (`apps/api`, `apps/web`, `packages/shared`, `migrations`, `docs`)
- Git initialised, `.gitignore`, README, LICENSE
- Node + Python versions pinned, `pnpm` workspace configured
- **Acceptance:** `pnpm install` works; repo structure matches spec

**Phase 0.2: Backend Skeleton** 🟢 Sonnet 4.6 ✅ 2026-04-20
- FastAPI app with `/api/v1/health` endpoint
- Pydantic settings loader with `.env.example`
- Uvicorn dev server, Dockerfile
- Ruff + mypy configured
- **Acceptance:** `uvicorn` starts, `/health` returns 200, lint passes

**Phase 0.3: Frontend Skeleton** 🟢 Sonnet 4.6 ✅ 2026-04-21
- Vite + React 18 + TypeScript, strict mode
- Tailwind configured with full design token CSS variables (Section 7.2 colours, spacing, typography)
- shadcn/ui initialised with a sample Button
- Dark mode default, theme toggle
- **Acceptance:** `pnpm dev` starts, design tokens applied, dark/light toggle works

**Phase 0.4: Supabase Setup & Auth** 🟢 Sonnet 4.6 ✅ 2026-04-22
- Supabase project created, credentials in `.env.example`
- `profiles` table + RLS policies
- Login/signup pages with email/password
- Protected routes (admin, viewer)
- **Acceptance:** Can register, log in, see role-appropriate routes; viewers blocked from admin endpoints

**Phase 0.5: CI Pipeline** 🟢 Sonnet 4.6 ✅ 2026-04-23
- GitHub Actions: lint, typecheck, unit test, build
- Runs on every PR
- **Acceptance:** PR shows green checks; failing lint or test blocks merge

**Phase 0.6: Error Tracking & Logging** 🟢 Sonnet 4.6 ✅ 2026-04-24
- Sentry integrated (frontend + backend)
- structlog with correlation IDs
- **Acceptance:** Thrown test error appears in Sentry dashboard; logs include correlation IDs

---

### Stage 1 — Data & Import

**Phase 1.1: Alembic + Core Schema (movies, movie_credits)** 🟢 Sonnet 4.6 ✅ 2026-04-25
- Alembic initialised
- Migration for `movies` (with tsvector + genre_ids GIN indexes)
- Migration for `movie_credits`
- `updated_at` trigger helper
- **Acceptance:** Migrations apply and rollback cleanly; indexes verified via `EXPLAIN`

**Phase 1.2: Alembic Migration — Collections & Wanted** ✅ COMPLETE — commit `bcbf96b` — Sonnet 4.6
- Migration for `collection_items` (all fields including AV specs, photos, listing status)
- Migration for `wanted_list`, `price_checks`, `price_history_daily`
- Soft delete triggers
- **Acceptance:** All tables exist with correct FKs and indexes; test data insertable

**Phase 1.3: Alembic Migration — Remaining Tables** 🟢 Sonnet 4.6 ✅ 2026-04-26
- `watch_log`, `loans`, `movie_night_*`, `email_accounts`, `purchase_candidates`
- `chat_conversations`, `chat_messages`, `completion_sets`, `retailers`, `deals`
- `notification_preferences`, `admin_actions`, `gift_links`, `shelf_qr_codes`
- `smart_collections`, `box_sets`, `box_set_items`, `release_calendar`
- **Acceptance:** Full schema deployed; all tables documented in code comments

**Phase 1.4: TMDB Client** 🟢 Sonnet 4.6 ✅ 2026-04-26
- Python TMDB API wrapper with `append_to_response` support
- Rate limiter (3 req/s) and exponential backoff
- Typed Pydantic models for TMDB responses
- Unit tests with mocked responses
- **Acceptance:** Can fetch a movie by ID with credits, videos, watch providers in one call

**Phase 1.5: Spreadsheet Parser** 🟢 Sonnet 4.6 ✅ 2026-04-26
- Read `.xlsx`, normalise format strings, casing, locations
- Extract section/shelf from location text
- Output a structured list of import candidates
- Unit tests with sample spreadsheet rows
- **Acceptance:** Given the real spreadsheet, parser produces 1,866 structured entries with no data loss

**Phase 1.6: TMDB Matching Engine** 🔴 Opus ✅ 2026-04-26
- For each parsed title, search TMDB and return top N matches with confidence scores
- Handle year disambiguation (e.g. "20,000 Leagues Under the Sea (1954)")
- Cache results to avoid re-querying
- **Acceptance:** On 100 sample titles, ≥90% match the correct film; unmatched flagged clearly

**Phase 1.7: Bulk Import Script** 🟢 Sonnet 4.6 ✅ 2026-04-26 (real import committed 2026-04-27)
- CLI tool that runs end-to-end import: parse → match → enrich → insert
- Progress reporting
- Idempotent (safe to re-run)
- Generates a review file for low-confidence matches
- **Acceptance:** Real spreadsheet committed to live DB (no `--dry-run`); row counts in `movies`, `collection_items`, and `movie_credits` verified > 0; review file lists ambiguous matches. (See Rule 6 in §Phase Count & Guidance — tools must be exercised, not just built.)

**Phase 1.8: Derived Field Triggers** 🔴 Opus ✅ 2026-04-26
- Postgres trigger to update `movies.best_format_owned`, `best_hdr_owned`, `best_audio_owned` on collection_item changes
- Trigger to update `movies.search_vector`
- **Acceptance:** Adding/removing a collection_item updates derived fields within the same transaction

---

### Stage 2 — Basic UI

**Phase 2.1: API — List & Detail Movies** 🟢 Sonnet 4.6 ✅ 2026-04-27
- `GET /api/v1/movies` with pagination, sort, basic filters
- `GET /api/v1/movies/{id}` with full metadata
- Response envelope format
- Integration tests
- **Acceptance:** Endpoints return correct paginated data; filter by genre, year, format works

**Phase 2.2: Frontend Shell & Routing** 🟢 Sonnet 4.6 ✅ 2026-04-29
- App layout with sidebar nav
- Protected route component
- 404 and error boundaries
- **Acceptance:** All defined routes reachable; nav works; auth state persists on refresh

**Phase 2.3: Collection Grid (Grid View)** 🟢 Sonnet 4.6 ✅ 2026-04-29
- Virtualised grid (react-window or TanStack Virtual) for 2000+ items
- Skeleton loader during fetch
- Empty state
- Basic filter bar (genre, format, year)
- **Acceptance:** Grid renders 1,866 items smoothly (60fps scroll); filters update results instantly

**Phase 2.4: Collection Grid (List & Compact Views)** 🟢 Sonnet 4.6 ✅ 2026-04-29
- View mode toggle (grid / list / compact)
- List view with configurable columns
- Persistence of user's view preference
- **Acceptance:** Toggling views is instant; user's choice remembered across sessions

**Phase 2.5: Full-Text Search** 🟢 Sonnet 4.6 ✅ 2026-04-29
- `GET /api/v1/search` using tsvector
- Search bar in header, `/` shortcut to focus
- Debounced input, result highlighting
- **Acceptance:** Searching "Kubrick" returns all Kubrick films in < 150ms

**Phase 2.6: Movie Detail Page — Layout** 🟢 Sonnet 4.6 ✅ 2026-04-29
- Hero backdrop with gradient overlay
- Title, year, runtime, rating metadata row
- Overview tab content
- External link buttons (IMDB, Letterboxd)
- **Acceptance:** Detail page displays cleanly on mobile and desktop; external links open correct URLs

**Phase 2.7: Movie Detail — Cast, Crew, Your Copies Tabs** 🟢 Sonnet 4.6 ✅ 2026-04-30
- Cast carousel with photos
- Crew list
- "Your Copies" tab showing all collection_items for this movie with locations and formats
- **Acceptance:** Movie with multiple owned formats shows all copies clearly

**Phase 2.8: Onboarding Flow** 🟢 Sonnet 4.6 ✅ 2026-04-30
- 8-step wizard (welcome → import → email connect → install PWA → notifications → theme → tour → done)
- Skippable, resumable
- **Acceptance:** First-time admin completes all 8 steps; skipping still lands on a usable dashboard

---

### Stage 3 — Collection Management

**Phase 3.1: Add to Collection (Manual)** 🟢 Sonnet 4.6
- Admin-only form with movie search, format picker, location, purchase fields
- Duplicate warning before saving
- Optimistic UI
- **Acceptance:** Admin adds a movie; viewer immediately sees it; duplicate warning fires on re-add

**Phase 3.2: Edit & Delete Collection Items** 🟢 Sonnet 4.6
- Edit form (location, format, notes, condition, price)
- Soft delete (move to trash)
- admin_actions audit log entry
- **Acceptance:** Changes persist; deleted items appear in Trash UI; audit log shows the change

**Phase 3.3: Barcode Scanner UI** 🟢 Sonnet 4.6
- Camera access via `getUserMedia`
- quagga2 or zxing-js barcode reading
- Display scanned UPC, ready for lookup
- **Acceptance:** Scanning a real Blu-ray barcode on mobile returns a valid EAN in < 2 seconds

**Phase 3.4: Barcode → TMDB Lookup** 🔴 Opus
- `POST /api/v1/barcode/lookup` endpoint
- UPC-to-title resolution (try cached mapping, then eBay/Amazon UPC search, then TMDB)
- Confirmation UI before adding
- **Acceptance:** Scanning a common Blu-ray returns the correct movie; unknown UPCs prompt manual search

**Phase 3.5: Duplicate Detection** 🟢 Sonnet 4.6
- When adding, check for same movie_id in collection
- Show existing formats and locations
- Admin confirms "add another copy" or "this is an upgrade"
- **Acceptance:** Adding a 4K when Blu-ray exists triggers the upgrade prompt

**Phase 3.6: Storage Location Suggestions** 🔴 Opus
- Algorithm: analyse existing items by genre, director, format to suggest a shelf
- Shown as the default in the Add form
- Admin can override
- **Acceptance:** Adding a Kubrick film suggests the shelf where other Kubrick films live

**Phase 3.7: Blu-ray.com Specs Scraper** 🔴 Opus
- Scrape video_specs, audio_specs, special_features, region_code, release_label
- Handle multiple editions (prompt admin to pick)
- Cache URL for future re-syncs
- Unit tests with mocked Blu-ray.com HTML
- **Acceptance:** Scraper run against 10 known **live** Blu-ray.com URLs persists correct specs to the matching `collection_items` rows; row counts verified — not just unit tests against fixture HTML.

**Phase 3.8: Spec Display & Quality Badges** 🟢 Sonnet 4.6
- Badge components for resolution, HDR, audio
- Displayed on collection cards and detail page
- Hover/tap shows full spec list
- **Acceptance:** A 4K disc with Dolby Vision + Atmos shows three distinct coloured badges

**Phase 3.9: Spec-Based Filtering** 🟢 Sonnet 4.6
- Filter panel: "Dolby Atmos only", "Dolby Vision 4K only", "Arrow Video", "Region-free"
- URL-encoded so filters are bookmarkable
- **Acceptance:** Applying "Dolby Vision" filter reduces list to only DV-capable discs

**Phase 3.10: Photo Uploads** 🟢 Sonnet 4.6
- Upload to Supabase Storage (max 5 per item, 5MB each)
- Camera capture or file picker on mobile
- Gallery display on detail page
- **Acceptance:** Upload succeeds; photos appear in gallery; deletion works

**Phase 3.11: Condition Tracking** 🟢 Sonnet 4.6
- Condition field on edit form
- "Mark as damaged" quick action
- Playback issues notes
- Condition history visible on detail page
- **Acceptance:** Marking a disc as damaged updates UI and logs the change

---

### Stage 4 — Upgrades & eBay

**Phase 4.1: eBay API Integration** 🔴 Opus
- eBay Browse API client (OAuth app credentials)
- Search sold listings endpoint
- Median price calculation for title + format + UK
- **Acceptance:** Querying "Blade Runner 2049 Blu-ray" returns a reasonable UK median price

**Phase 4.2: Format Upgrade Flow** 🟢 Sonnet 4.6
- After duplicate detection "it's an upgrade" path
- Flag old format as superseded
- Show suggested sell price from 4.1
- Admin adjusts or accepts
- **Acceptance:** Upgrade path completes in ≤ 3 taps; old item marked `listed_for_sale`

**Phase 4.3: eBay Listing Creation** 🔴 Opus
- Option A (preferred): eBay Sell API draft listing creation
- Option B (fallback): pre-filled eBay listing URL
- Admin publishes from eBay
- **Acceptance:** A draft listing appears in admin's eBay account (or URL opens with prefilled fields)

**Phase 4.4: Listing Status Management** 🟢 Sonnet 4.6
- "Mark as sold" action on listed items
- Auto-archive from active collection
- **Acceptance:** Marking sold removes from active views, remains in audit/trash

---

### Stage 5 — Wanted List, Prices & Deals

**Phase 5.1: Wanted List CRUD** 🟢 Sonnet 4.6
- Add, edit, remove endpoints
- Wanted list page UI with cards
- Preferred format, max price, currency
- **Acceptance:** Adding to wanted list from detail page and listing it works both ways

**Phase 5.2: Retailer Management** 🟢 Sonnet 4.6
- `retailers` CRUD UI
- Admin adds retailer with base URL, deals URL, selectors
- Seeded default retailers
- **Acceptance:** Admin adds a new retailer; it's saved and enabled

**Phase 5.3: Scraper Framework** 🔴 Opus
- Generic CSS scraper that uses retailer config
- Built-in scrapers for HMV, Amazon UK, Blu-ray.com, Zavvi, Arrow, CEX
- Error handling with retry and auto-disable after 3 fails
- **Acceptance:** Each built-in scraper runs against the **live** retailer and persists ≥ 1 `price_checks` row per scraper for a real wanted item; total `price_checks` rows after the run verified > 0.

**Phase 5.4: Test Scraper Tool** 🟢 Sonnet 4.6
- "Test scraper" button in retailer UI
- Runs selectors against live page, displays sample results
- **Acceptance:** Admin validates a new retailer before enabling

**Phase 5.5: Daily Price Scraping Job** 🟢 Sonnet 4.6
- APScheduler job running daily
- Iterates through active wanted items × enabled retailers
- Inserts price_checks rows
- **Acceptance:** First overnight run completes; same-day `price_checks` row count ≈ (active wanted items × enabled retailers) within ≤ 10% failure margin; failures logged with retailer + reason.

**Phase 5.6: Price Drop Trigger & Push Notification** 🔴 Opus
- Postgres trigger after price_check insert: if price ≤ max_price and not notified, queue push
- Web Push via pywebpush with VAPID
- Service worker shows notification
- **Acceptance:** Setting max_price above current price and running scrape triggers a push on test device

**Phase 5.7: Price History Charts** 🟢 Sonnet 4.6
- Chart per wanted item showing price over time across retailers
- Recharts line chart
- **Acceptance:** After 7+ days of **real scheduled scrapes** (not back-dated fixtures), chart renders multi-retailer time-series for ≥ 3 wanted items.

**Phase 5.8: Daily Aggregation Job** 🟢 Sonnet 4.6
- Nightly job rolls price_checks > 90 days old into price_history_daily
- **Acceptance:** After backdating test data, rows > 90 days are aggregated and raw rows removed

**Phase 5.9: Deals Scraper & Feed** 🔴 Opus
- Scrape retailer deals pages (not just wanted items)
- Match to TMDB, store in `deals` table
- Skip already-owned
- **Acceptance:** Deals scraper run against live retailer pages populates the `deals` table with ≥ 20 rows from ≥ 3 retailers; UI renders them with posters; "skip already-owned" verified against the real `collection_items` table.

**Phase 5.10: Deal Filtering & Actions** 🟢 Sonnet 4.6
- Filters: genre, discount %, retailer, format
- One-tap dismiss / add to wanted list
- **Acceptance:** Admin can curate the deals feed; dismissed items don't reappear

**Phase 5.11: Sale Season Calendar Events** 🟢 Sonnet 4.6
- Seeded data for Prime Day, Black Friday, Boxing Day, Criterion Flash Sale, etc.
- Pre-sale push notifications
- **Acceptance:** Test date set 2 weeks before a seeded event triggers a reminder

---

### Stage 6 — Notifications & Polish

**Phase 6.1: Notification Preferences** 🟢 Sonnet 4.6
- Per-category toggles
- Digest mode and quiet hours
- **Acceptance:** Disabling "deals" stops deal pushes; quiet hours suppress evening alerts

**Phase 6.2: Multi-Device Push Subscriptions** 🟢 Sonnet 4.6
- Per-device subscription records
- Test notification button
- **Acceptance:** Admin connects phone + laptop; both receive pushes; removing one doesn't silence the other

**Phase 6.3: Command Palette (⌘K)** 🟢 Sonnet 4.6
- Modal with fuzzy search
- Indexes films, pages, actions, recent items
- Keyboard navigation
- **Acceptance:** ⌘K opens instantly; typing "blade" surfaces Blade Runner films; Enter navigates

**Phase 6.4: Keyboard Shortcuts** 🟢 Sonnet 4.6
- Global shortcuts (g+h, g+c, /, n, ., ?)
- Help modal listing all shortcuts (triggered with ?)
- **Acceptance:** All documented shortcuts work; help modal shows all

**Phase 6.5: Optimistic UI** 🟢 Sonnet 4.6
- TanStack Query optimistic updates on add/edit/delete
- Rollback on error with toast
- **Acceptance:** Adding to wanted list shows instantly; network failure rolls back with error toast

**Phase 6.6: Mobile Gestures & Haptics** 🟢 Sonnet 4.6
- Swipe actions on cards
- Long press menu
- Haptic feedback on key actions
- **Acceptance:** On iOS and Android PWA, swipe actions feel native; haptics fire on supported devices

---

### Stage 7 — Streaming, Recommendations & Calendar

**Phase 7.1: TMDB Watch Providers Integration** 🟢 Sonnet 4.6
- `GET /api/v1/movies/{id}/streaming`
- Region-aware (user's streaming_region)
- Display on detail page
- **Acceptance:** For a popular film, UK streaming options shown correctly

**Phase 7.2: Recommendations & New Releases** 🟢 Sonnet 4.6
- TMDB `/recommendations` on detail page
- Flag as owned / wanted / unowned
- New releases feed filtered by collected genres
- **Acceptance:** Detail page shows 10+ recommendations with correct ownership flags

**Phase 7.3: Release Calendar Data Source** 🟢 Sonnet 4.6
- Populate release_calendar from TMDB upcoming + curated sources
- Filter by genres of interest
- **Acceptance:** Live ingestion run populates `release_calendar` with ≥ 30 rows spanning the next 3 months (not seeded data); Calendar page renders them.

**Phase 7.4: Calendar UI & iCal Feed** 🟢 Sonnet 4.6
- Monthly calendar view
- `/api/v1/calendar.ics` endpoint
- Subscribe button with copy-link
- **Acceptance:** Subscribing in Apple Calendar successfully displays events

---

### Stage 8 — Discovery & Movie Night

**Phase 8.1: Smart Search (Natural Language)** 🔴 Opus
- Keyword extraction for genres, decades, runtime
- Maps "light-hearted comedy under 90 min" to structured filters
- **Acceptance:** Test queries like "noir 1940s", "short action" return sensible results

**Phase 8.2: Feeling Lucky** 🟢 Sonnet 4.6
- Random film from collection
- Respect `suggest_exclude` flag
- Session memory of recent suggestions
- **Acceptance:** Clicking Lucky 5 times gives 5 different films

**Phase 8.3: Movie Night Session Start** 🟢 Sonnet 4.6
- Session creation with filters
- Invite URL for second user
- **Acceptance:** Session created; second user joins via URL

**Phase 8.4: Movie Night Swipe & Match** 🔴 Opus
- Swipe-like UI (cards, left/right gestures)
- Real-time sync via Supabase Realtime
- Match detection, notification to both
- **Acceptance:** Both users swiping on the same film triggers a match notification

---

### Stage 9 — AI Assistant

**Phase 9.1: Claude API Client** 🟢 Sonnet 4.6
- Anthropic SDK integration
- System prompt scaffolding
- Token + cost logging per message
- **Acceptance:** Simple text prompt returns a response; tokens logged

**Phase 9.2: Tool Definitions** 🔴 Opus
- Tool schemas for major endpoints (search, add_wanted, log_watch, etc.)
- Role-aware tool filtering (admin vs viewer)
- **Acceptance:** Tool list differs correctly between admin and viewer

**Phase 9.3: Chat UI** 🟢 Sonnet 4.6
- Conversation list and detail
- Streaming response display
- Floating chat button on every page
- **Acceptance:** User sends message, streamed response renders progressively

**Phase 9.4: Tool Execution with Confirmation** 🟢 Sonnet 4.6
- When Claude calls a write tool, UI confirms before executing
- **Acceptance:** "Add X to wanted list" prompts confirmation; cancelling aborts

**Phase 9.5: Voice Input** 🟢 Sonnet 4.6
- Web Speech API integration
- Mic button, transcribes to text input
- **Acceptance:** Tapping mic, speaking a query, sends correct transcription

**Phase 9.6: Voice Output (TTS)** 🟢 Sonnet 4.6
- SpeechSynthesis integration
- Optional toggle
- **Acceptance:** Enable TTS; Claude's reply is read aloud

**Phase 9.7: Usage Caps** 🟢 Sonnet 4.6
- Per-user daily message / cost cap
- Graceful "limit reached" message
- **Acceptance:** Sending over the cap blocks with clear messaging; resets next day

---

### Stage 10 — Purchase Detection

**Phase 10.1: Email Account Model & Encryption** 🔴 Opus
- Supabase Vault or encryption-at-rest for credentials
- email_accounts CRUD endpoints
- **Acceptance:** Credentials round-trip through encryption; DB never stores plaintext

**Phase 10.2: Gmail OAuth Flow** 🔴 Opus
- Consent screen, read-only scope
- Token storage, refresh handling
- **Acceptance:** Admin connects Gmail; token refreshes automatically

**Phase 10.3: Outlook OAuth Flow** 🔴 Opus
- Microsoft Graph integration
- **Acceptance:** Admin connects Outlook successfully

**Phase 10.4: Generic IMAP Connector** 🟢 Sonnet 4.6
- IMAP client for iCloud, Yahoo, custom
- App-specific password input form
- Instructions linked per provider
- **Acceptance:** Admin connects an iCloud account using an app password

**Phase 10.5: Retailer Email Parsers** 🟢 Sonnet 4.6
- Templates for eBay, Amazon, HMV, Zavvi order confirmations
- Extract title, price, date
- **Acceptance:** Each parser passes against (a) a fixture sample email in unit tests AND (b) at least one **real received email** from the admin's connected mailbox, both producing correct structured output.

**Phase 10.6: LLM Fallback Parser** 🔴 Opus
- Claude API call to extract order fields from unfamiliar email templates
- **Acceptance:** A novel retailer's email is parsed into structured data

**Phase 10.7: Scheduled Scan Job** 🟢 Sonnet 4.6
- Per-account scheduled scan
- Fuzzy match to wanted_list
- purchase_candidate creation
- **Acceptance:** Scanning a mailbox with a known wanted item creates a candidate

**Phase 10.8: Candidate Review UI** 🟢 Sonnet 4.6
- Review queue with confirm/dismiss actions
- Confirm creates collection_item and removes wanted entry
- **Acceptance:** Admin reviews and processes candidates; state updates correctly

---

### Stage 11 — Insights, Box Sets & Memories

**Phase 11.1: Completion Sets Data & Refresh** 🔴 Opus
- Seed director, franchise, award sets
- Weekly refresh job from TMDB collections
- **Acceptance:** Refresh job runs live against TMDB and populates `completion_sets` with ≥ 20 sets (directors, franchises, awards); Hitchcock set lists every Hitchcock film TMDB returns; re-running after a TMDB change updates the affected rows.

**Phase 11.2: Completion Insights UI** 🟢 Sonnet 4.6
- Progress bars per set
- Missing films list with posters
- Bulk "add missing to wanted list"
- **Acceptance:** Opening Insights shows ≥ 20 sets with owned/missing counts

**Phase 11.3: Box Set CRUD** 🟢 Sonnet 4.6
- Admin creates a box set, adds collection_items
- Series linking
- **Acceptance:** Admin creates "Columbia Noir Vol 4" with 4 items

**Phase 11.4: Box Set Display & Completion** 🟢 Sonnet 4.6
- Box set grid view
- Per-set completion ("3 of 4")
- **Acceptance:** Browsing box sets shows all with status

**Phase 11.5: Smart Collections** 🔴 Opus
- Create/edit/delete smart collections
- Dynamic filter evaluation
- Pin to dashboard
- **Acceptance:** Creating "Unwatched 4Ks from 2010s" lists correct films and updates live

**Phase 11.6: On-This-Day & Rewatch Memories** 🟢 Sonnet 4.6
- On-this-day query from watch_log
- Rewatch suggestions (highly-rated, not recently watched)
- Optional daily push
- **Acceptance:** If a watch was logged a year ago, today's dashboard surfaces it

---

### Stage 12 — Sharing & Physical Integration

**Phase 12.1: Gift Link Creation** 🟢 Sonnet 4.6
- CRUD for gift_links
- Filter configuration
- Slug-based public URL
- **Acceptance:** Admin creates a link; visiting the slug renders public list

**Phase 12.2: Public Gift Page** 🟢 Sonnet 4.6
- Read-only rendering with posters and retailer links
- No auth required
- Basic filters visible to viewer
- **Acceptance:** Non-logged-in visitor can browse Dad's wanted list

**Phase 12.3: Shelf QR Code Generation** 🟢 Sonnet 4.6
- Generate QR for section/shelf
- Printable PDF with label
- **Acceptance:** Generating QR for "Front 2nd Shelf" produces a valid printable PDF

**Phase 12.4: QR Code Scanning in App** 🟢 Sonnet 4.6
- Scanner opens filtered view for scanned shelf
- "Update location" flow when scanning disc barcode then shelf QR
- **Acceptance:** Scanning a printed shelf QR opens the filtered collection view

**Phase 12.5: Lending Tracker** 🟢 Sonnet 4.6
- Mark as lent / returned
- Loans page
- Reminder notifications for overdue
- **Acceptance:** Lending a disc shows it in Loans; overdue triggers a push

---

### Stage 13 — Stats, Export & Resilience

**Phase 13.1: Stats Dashboard** 🟢 Sonnet 4.6
- Format breakdown pie
- Genre bar chart
- Decade distribution
- Most-watched
- Collection value over time
- **Acceptance:** Stats page loads in < 1s with all charts populated

**Phase 13.2: Activity Feed** 🟢 Sonnet 4.6
- Timeline of recent additions, watches, price drops, loans
- **Acceptance:** Home dashboard shows last 20 events across all users

**Phase 13.3: Collection Export (CSV, JSON)** 🟢 Sonnet 4.6
- Full collection export endpoints
- Download links
- **Acceptance:** CSV opens cleanly in Excel; JSON is valid

**Phase 13.4: Collection Export (PDF, HTML)** 🟢 Sonnet 4.6
- Printable PDF with posters
- "Coffee table" HTML style
- **Acceptance:** PDF looks presentation-ready; HTML prints well

**Phase 13.5: Trash & Restore UI** 🟢 Sonnet 4.6
- List soft-deleted items per table
- Restore / permanently delete actions
- **Acceptance:** Deleted item in Trash; restoring brings it back with full state

**Phase 13.6: Admin Audit Log UI** 🟢 Sonnet 4.6
- Filterable log of all admin actions
- **Acceptance:** Making 5 test changes shows 5 entries with correct diffs

**Phase 13.7: Backup & Restore** 🟢 Sonnet 4.6
- Manual backup trigger
- Download archive
- Restore from upload
- Weekly automated backup to Supabase Storage
- **Acceptance:** Admin backs up, nukes test data, restores, state matches

**Phase 13.8: Service Worker — Offline Caching** 🔴 Opus
- Cache collection data in IndexedDB
- Cache poster images
- Offline indicator
- **Acceptance:** Turning off network still allows browsing and searching the collection

**Phase 13.9: Offline Write Queue** 🔴 Opus
- Queue add/edit/delete in IndexedDB when offline
- Sync on reconnect
- Conflict resolution (last-write-wins)
- **Acceptance:** Adding offline syncs to server when back online

**Phase 13.10: Playwright E2E Tests** 🟢 Sonnet 4.6
- Critical flows: login, import, search, add via scan, price alert, chat session, movie night match
- Runs in CI
- **Acceptance:** All flows pass on CI in Chromium + Firefox + WebKit

**Phase 13.11: Visual Polish Pass** 🔴 Opus
- Empty states, error states, micro-animations
- Transition polish (page changes, modals)
- Accessibility audit (NVDA + VoiceOver)
- **Acceptance:** Lighthouse scores ≥ 90 across all categories; axe-core 0 violations on all pages

---

### Phase Count & Guidance

- **Total phases:** 86 (across 14 stages)
- **Estimated sessions per phase:** 1–2 working sessions
- **Suggested pace:** 1–3 phases per session depending on complexity

**Rules for the build:**
1. **Never skip acceptance criteria** — a phase isn't done until every bullet passes
2. **Ship tests with each phase** — no "I'll add tests later"
3. **Keep branches small** — one phase per PR, easier to review and roll back
4. **Document as you go** — if a phase changes design, update the architecture doc in the same PR
5. **If a phase starts feeling too big mid-session, split it** — it's better to land 0.3a today and 0.3b tomorrow than to leave a half-done phase overnight
6. **Tools must be exercised, not just built** — any phase whose deliverable is a tool, scraper, scheduled job, integration, migration, or data pipeline must include an explicit "run it for real" acceptance step with verifiable persisted state (row counts > 0, real network response logged, real device received notification, real email parsed). A green dry-run, mocked unit test, or fixture-driven pass is **not sufficient** to mark the phase complete. Origin: Phase 1.7 was closed out on a `--dry-run` only — the actual import was deferred without anyone flagging it, leaving Phase 1.8 to backfill an empty table.

---

## 17. Resolved Decisions

| # | Decision | Resolution |
|---|----------|------------|
| 1 | Price tracking approach | Accept scraping risk; use official APIs where available |
| 2 | Notification method | Web Push via PWA (pywebpush + VAPID keys) |
| 3 | Smart discovery approach | Start with keyword extraction; upgrade to LLM later if needed |
| 4 | Letterboxd linking | Slug-based URL with search fallback |
| 5 | Streaming region | UK (GB) default, user-configurable in settings |
| 6 | Mobile app | PWA sufficient, no native app needed |
| 7 | Barcode scanning | Include from Stage 3 (Phase 3.3–3.4) |
| 8 | Purchase price tracking | Yes; auto-estimate during bulk import, manual for new entries (Phase 3.1) |
| 9 | Lending tracker | Yes, included in Stage 12 (Phase 12.5) |
| 10 | Movie Night mode | Yes, included in Stage 8 (Phase 8.3–8.4) |
| 11 | Offline access | Yes, service worker caching in Stage 13 (Phase 13.8–13.9) |
| 12 | Collection export | Yes, CSV/PDF/JSON/HTML in Stage 13 (Phase 13.3–13.4) |
| 13 | Format upgrade eBay listing | Yes; suggest sell price from eBay sold data, one-tap listing, Stage 4 (Phase 4.1–4.3) |
| 14 | Automatic purchase detection | Yes — multi-provider (Gmail, Outlook, iCloud, Yahoo, IMAP), Stage 10 |
| 15 | AI chatbot assistant | Yes via Claude API with tool use, Stage 9 (Phase 9.1–9.7) |
| 16 | Completion insights | Yes — directors, actors, franchises, awards, decades, format upgrades, Stage 11 |
| 17 | General deals scraper | Yes — daily 4K/Blu-ray deals feed, Stage 5 (Phase 5.9–5.10) |
| 18 | Voice input for chatbot | Yes via Web Speech API, Phase 9.5–9.6 |
| 19 | Configurable retailers | Yes — admin can add/edit/test scrapers, Stage 5 (Phase 5.2–5.4) |
| 20 | Audio/Video specs per disc | Yes — auto-fetched from Blu-ray.com, with badges and filters, Stage 3 (Phase 3.7–3.9) |
| 21 | Multi-provider email support | Yes — Gmail, Outlook, iCloud, Yahoo, generic IMAP, Stage 10 (Phase 10.1–10.4) |
| 22 | Quality badges (best format/HDR/audio owned) | Yes — derived fields on movies, auto-updated by trigger, Phase 1.8 + Phase 3.8 |
| 23 | TV series handling | Single row per series (`is_tv = true`), no per-episode tracking |
| 24 | Disc condition tracking over time | Yes — `condition_updated_at`, `has_playback_issues`, `playback_notes` on collection_items |
| 25 | Rewatch / On-this-day memories | Yes — Phase 11.6 |
| 26 | Sale season awareness | Yes — seeded events with pre-sale alerts, Phase 5.11 |
| 27 | Gift mode (shareable wanted list) | Yes — public gift links with optional filters, Stage 12 (Phase 12.1–12.2) |
| 28 | Photo uploads per item | Yes — Supabase Storage, up to 5 photos/item, Phase 3.10 |
| 29 | Shelf QR codes | Yes — generation + printing + scan-to-locate, Stage 12 (Phase 12.3–12.4) |
| 30 | Notification preferences & digest | Yes — per-category toggles, digest mode, quiet hours, Stage 6 (Phase 6.1–6.2) |
| 31 | Soft delete / trash / audit log | Yes — 90-day trash retention, 2-year audit log, Stage 13 (Phase 13.5–13.6) |
| 32 | Data retention for price_checks | Aggregate into `price_history_daily` after 90 days, delete raw rows (Phase 5.8) |
| 33 | Dashboard caching | 5-min TTL per-user in-memory cache, invalidated on writes |
| 34 | Chat token/cost tracking | Stored per message for per-user usage caps, Phase 9.1 + 9.7 |
| 35 | Design system | shadcn/ui + Radix + Tailwind, dark-mode default with cinema mode, full token spec in Section 7.2 — Phase 0.3 |
| 36 | API versioning | All endpoints prefixed `/api/v1/`, standard response envelope — Phase 0.2 |
| 37 | Testing strategy | pytest + Vitest + Playwright; ≥80% coverage; tests ship with each phase — Phase 0.5 |
| 38 | Error tracking | Sentry on frontend and backend with source maps — Phase 0.6 |
| 39 | Database migrations | Alembic, reviewed in PRs, rollback-capable — Phase 1.1 |
| 40 | CI/CD | GitHub Actions — lint, type, test, build, migration check, security scan — Phase 0.5 |
| 41 | Command palette | ⌘K global fuzzy search across films, pages, actions — Phase 6.3 |
| 42 | Smart collections (iTunes-style) | User-saved dynamic filter sets, Phase 11.5 |
| 43 | Box set tracking | First-class entity with completion tracking, Phase 11.3–11.4 |
| 44 | Release calendar with iCal feed | Upcoming releases + sale events syncable to Apple/Google Calendar, Phase 7.3–7.4 |
| 45 | Accessibility target | WCAG 2.1 AA minimum, tested with NVDA and VoiceOver — Phase 13.11 |
| 46 | Internationalisation ready | All timestamps UTC, `Intl.*` for formatting, `i18n()` wrapper from day one — Phase 0.3 |
| 47 | Onboarding flow | 8-step guided setup for admin, 3-step for viewer — Phase 2.8 |
| 48 | Rate limiting | Via slowapi on auth, public pages, barcode lookup, chat — Phase 0.2 |
| 49 | Secrets management | `.env` + `.env.example`, optional Doppler, rotated annually — Phase 0.1 |
| 50 | Observability | Sentry + structlog with correlation IDs, Web Vitals, health checks — Phase 0.6 |

---

*This document supersedes all previous versions (v1.0 through v2.0). It is the authoritative design specification for implementation. Version 2.1 — final.*
