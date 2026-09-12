# STATUS — MCU App

## Now

**Batch 28 shipped — eBay is integrated, and one acceptance criterion is deliberately
left open for you.** Merged as `b2a6c27`, CI green across all five jobs, production
`/api/v1/health` serving that SHA with `db: ok`.

**⚠️ Production reports `ebay: not_configured`, and that is the batch's first finding.**
`EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` are **not set in Railway** — they exist only in
`apps/api/.env.local`, and `.railway/railway.ts` declares neither. So every eBay surface in
the deployed app answers 503 until you set them. The new `ebay` field on
`/api/v1/health/ready` is what makes that visible at all: it was added for exactly the
reason `AGENTS.md` records about the TMDB outage — a value living only in a hosting
variable has nothing testing it — and it caught one on its first deploy. **Setting them is
a hosting change and therefore yours** (`OWNER-ACTIONS.md`).

**What shipped.** A new `src/ebay/` package modelled on `src/tmdb/` — Browse client with a
cached application token, the match filter, the segmented median, and Phase 4.3's
pre-filled listing URL. Two endpoints, both admin-authed and rate limited because each
spends a unit of a 5,000-a-day production quota:
`POST /api/v1/ebay/price-estimate` and `POST /api/v1/ebay/listing-url`. On the web, a
**Value and resale** panel inside every owned copy on a film's page, which fetches nothing
until asked.

**Phase 4.3's preferred option does not exist, and the fallback's parameter is not the
obvious one.** There is no eBay API that creates a Seller Hub *draft* — an Inventory API
offer is invisible until published, at which point it is a live listing with a buyer on the
other end. So Option B is primary (`DECISIONS.md` #142). `docs/phase-batches.md` flagged
that nobody had confirmed prefill still worked; checked in a browser on 2026-09-12, it
does — and `?keyword=`, `?q=` and `?sugKw=` all render the form with an **empty** box while
`?title=` fills it. The three names that look right are the three that fail silently.

**Phase 4.1 is built and its acceptance is not met — that is the owner's, by design.**
*"Querying 'Blade Runner 2049 Blu-ray' returns a reasonable UK median price"* needs a live
production call: eBay's sandbox has an empty GB catalogue, and
`docs/agent-commands/group-start.md` puts live third-party runs in your hands. The ledger's
own words are that it is *"not something an unattended agent signs off"*. **A green gate
does not imply it passed.**

**What was proven instead, and it is not nothing.** Two verbatim production payloads were
captured to `tests/fixtures/ebay_browse_*.json` (200 GB listings each, 2026-09-11) and the
filter is tested against them. Naive median over everything a keyword search returns:
**£24.74**. Matched plain-Blu-ray median: **£9.99 from 29 listings**. That is the same
shape as `DECISIONS.md` #129's £30.45 against £12.21, taken with a different method a day
later, and `test_ebay_pricing.py` re-takes the comparison on every run — because a filter
that silently degrades to "accept everything" leaves every other test green.

**Two guards were wrong on the first attempt and the captured fixtures caught both.**
Format words sat on the "a number here is a quantity" list, so "Jaws 3 Blu-Ray (2016)" and
"Jaws 2 - DVD" read as quantities and were priced as *Jaws* — nine wrong listings. And a
BBFC age rating is a bare number, so "Blade Runner 2049 [15] 4K UHD" was rejected as a
fifteenth instalment. Neither is findable against invented JSON, which is `DECISIONS.md`
#122's whole lesson restated. #143 records both, and the losses the filter knowingly
accepts: two real discs their sellers filed under "Audio Books" and "Other", and four where
an actor's name sits where a subtitle would.

**A pre-existing failure worth knowing about, which is not a red gate.** Running
`pytest apps/api/tests` with `DATABASE_URL` pointed at **live Neon** produces **22
failures** — in `test_ai_chat`, `test_movie_night`, `test_notifications_api`,
`test_price_alerts_and_history` and `test_wanted_and_retailers_api`. They are **not new**:
the identical 22 fail at `5237050` in a clean worktree (875 passed there, 943 on this
branch). They are tests written for an empty database being run against production data,
and CI is green because it runs against a fresh Postgres 17 service. The canonical gate in
`batch-verify.md` sets no `DATABASE_URL`, and that run is clean: **576 passed, 389
skipped**. Worth fixing so the live-database run means something, but it is its own job.

## Log

- **2026-09-12 (Batch 28 — eBay integration)** — Shipped `b2a6c27`. New `src/ebay/` package
  (Browse client with a cached application token, match filter, segmented median,
  pre-filled listing URL), two admin endpoints, an `ebay` field on `/health/ready`, and a
  **Value and resale** panel on each owned copy. **4.3 met** — Option A does not exist, so
  Option B is primary and prefill was confirmed in a browser: the parameter is `title`
  (`DECISIONS.md` #142). **4.1's acceptance NOT met — a live production call and the
  owner's.** Proven instead against two captured 200-listing payloads: naive £24.74 against
  a matched £9.99 from 29 plain Blu-rays. Two guards were wrong first time and the fixtures
  caught both (#143). **Production reports `ebay: not_configured` — the Railway keyset
  variables were never set** (`OWNER-ACTIONS.md`).

- **2026-09-11 (batch criteria recovery)** — Recovered acceptance criteria for the seven
  remaining planned batches — 21, 22, 24, 29, 33, 34, 38 — verbatim from §16 at
  `d94a6b8~1`, per `DECISIONS.md` #54, and wrote them into `docs/phase-batches.md` as a new
  section. All 69 quoted lines verified against the archived document programmatically; the
  one deliberate deviation is dropping the decayed `Sonnet 4.6` / `Opus` annotation while
  keeping the tier emoji, following Batch 11's precedent. Recorded three criteria the repo
  already contradicts (Recharts, Amazon, Supabase Vault) and corrected two stale ledger
  claims (the `cryptography` risk note, Group H's eBay block on Batch 24). `DECISIONS.md`
  #141.

  Also found, while checking Batch 21's data gate: **the nightly scrape cron has not fired.**
  Applied 2026-09-10 on `0 3 * * *`, it had produced no `scrape_runs` row by 22:26 UTC on
  2026-09-11, 19 hours past its first scheduled run. §5.5 is failing rather than pending and
  Batch 21 is blocked behind it. Recorded in `OWNER-ACTIONS.md` #1; not acted on, because
  hosting is an owner action.

  Gate green locally: 508 API tests passed, 239 web + 79 shared, ruff clean, mypy clean on
  118 files, web lint 0 errors, typecheck clean, production build passes. Docs-only change.

- **2026-09-11 (brand hierarchy correction)** — A rendered design review reversed the
  over-application of photographic identity artwork from `00414f5`. Navigation and loaders
  now use the compact vector mark; desktop sign-in uses the complete 440 px horizontal
  lockup in a restrained editorial panel; mobile sign-in no longer stretches its brand
  row; onboarding keeps the personalised poster as its sole 192 px reveal; and social
  metadata again names the rights-independent 1200×630 card. Added regression coverage for
  those boundaries and for responsive lockup proportions. PR #2 merged as `d961937` and
  main CI run `34578379338` passed all five jobs. Production was rendered from Vercel at
  1440×900 and the mobile breakpoint; Railway reported that exact SHA and `db: ok`.

  One of two duplicate pre-merge CI runs hit the existing timing-sensitive SearchBar
  assertion; the identical push run was fully green and the failed job passed unchanged on
  rerun. No expectation or test was weakened.

- **2026-09-10 (evening, continued)** — **Personalised poster now visible in authenticated header and sidebar.** LoginPage mobile header simplified (removed hero photo backdrop). Sidebar and AppLayout header now display personalised-poster-icon-512.png instead of brand marks — all authenticated navigation surfaces feature the real poster stack with stills from Mark's collection (Jaws, Double Indemnity, An American Werewolf in London). Gate green: 235 web + 79 shared tests, 508 API tests, all lint/typecheck/build clean. Commit `00414f5` deployed to main; Vercel/Railway automatic deployment in progress.

- **2026-09-10 (evening)** — **Phase 1 display fixes deployed.** Photo hero logo sizing corrected on LoginPage (desktop: w-auto min-w-full preserves aspect ratio instead of stretching; overlay opacity strengthened for text contrast). Personalised poster visibility improved across all loaders (h-32 → h-40/h-48, w-auto for aspect ratio, shadow-md for separation, centered on onboarding with responsive srcset). Gate green: 235 web + 79 shared tests, 508 API tests, all lint/typecheck/build clean. Commit `fb6ecbd` deployed to main; Vercel/Railway automatic closure in progress.

- **2026-09-10** — **The approved identity is integrated into the app.** Placeholder icons
  deleted; 18 assets installed under `apps/web/public/brand/` from the untracked design
  system via the new tracked `scripts/brand-sync.mjs`. `BrandMark`/`BrandLockup` apply the
  responsive hierarchy and follow the theme without flashing. Builder extended for the 384 px
  PWA icon, a one-colour notification badge and a rights-independent share card. Fixed the
  `sw.ts` `/icons/` path that never existed, the placeholder blue in the manifest, and a
  28 px mark under its 32 px floor. 235 web + 79 shared tests, 0 lint errors, clean
  typecheck, build passing, CLS 0 on login. `DECISIONS.md` #133–#139.

  **Headless Chrome still aborts on this macOS build** (`_NSCGSTransaction dealloc`,
  reproduced) — but the **CDP route works**: a Chrome launched with
  `--remote-debugging-port` and driven over the protocol captured all 16 branded surfaces at
  2×, no credential involved. That is the mechanism `OWNER-ACTIONS.md` #14 proposes, now
  proven, and `.claude/launch.json` gained a `web-dist` entry that serves the built bundle
  so a session can verify the artefact that ships rather than the dev server.

- **2026-09-10** — **The redesign closed out, with one deliverable knowingly incomplete.**
  Gate green locally from a clean tree and green in CI (`34502543298`): ruff, 192 files
  formatted, mypy across 118 files, **508 API tests**, **213 web + 79 shared**, 0 lint
  errors, clean typecheck, build passing. Merged to `main` and deployed. **The before/after
  screenshots did not get finished** — nine before, three after — because headless Chrome
  aborts on this macOS build and the token-injection route was correctly refused; that is
  recorded as an open deliverable (`OWNER-ACTIONS.md` #14) rather than quietly dropped.
  Three design/deployment calls went to the owner as #11–#13.

  **And for the first time the deployed web bundle was actually run, not just built.**
  Gotcha 3 has always said a green web job is no evidence the app boots — Decision #22's
  white-screen is why. Post-merge, `mcu-app-fawn.vercel.app` was loaded live: the redesigned
  login page renders, **no console errors**, and `document.title` reads `Sign in · The Real
  MCU`, which is #132's single owner working in production. At **375px: zero horizontal
  overflow, one `h1`, zero controls under 44px** — so #131's `@layer utilities` fix is real
  in the shipped bundle and not only in the suite. Authenticated surfaces were not re-checked
  post-merge; they were measured live before it.

  **`docs/brand/` was deliberately not swept into the merge.** 189 files, 56 MB, untracked,
  built in a separate session that morning — and `source-images/` is third-party film
  stills gathered as reference. The committed `VERIFICATION.md` §5 already calls its
  `stack-family/` set "approved", so `main` now references a path the repo does not
  contain; closing that gap is `OWNER-ACTIONS.md` #15, because 56 MB of binaries in
  permanent history and a redistribution question are both the owner's call, not an
  agent's.
- **2026-09-10** — **The UI redesign's live pass, and three claims that did not survive it.**
  The branch's own audit recorded contrast, touch sizing and theme integrity as addressed;
  measuring them found error text at **3.13:1**, champagne on cream at **1.92:1**, and
  `.touch-target` silently inert because it was declared in `@layer components` — Tailwind
  emits that **before** `utilities`, so at equal specificity `min-h-8` simply came later and
  won. Every control that appeared to opt into a 44px floor had been unchanged. Fixed by
  splitting each tone into surface and text tokens across Tailwind's separate `textColor`
  scale (no call site touched), moving the floor to `utilities`, and rehoming ~60 raw
  palette classes. The gate now asserts all 42 contrast pairings (#130–#132).

- **2026-09-10** — **eBay connected, and the checkpoint that was supposed to gate it did not
  exist.** Research before the batch read eBay's own Buy API page — *"intended for eBay
  partners only"* — plus forum reports of small developers being rejected, and called
  production access roughly a coin toss. It is not: a self-service production keyset calls
  Browse at 5,000/day, and `q="Blade Runner 2049 Blu-ray"` on `EBAY_GB` returned **308 live
  listings**. Group I's checkpoint, `OWNER-ACTIONS.md` #5 and — less obviously — Batch 24
  are all unblocked (#126).

  **What was built:** `GET|POST /api/v1/ebay/account-deletion`, the app's **third**
  unauthenticated route, because eBay activates no production keyset until a developer
  either subscribes to account-deletion notifications or claims a "not persisting eBay data"
  exemption that carries account suspension if claimed wrongly (#127). It reads and writes
  nothing, carries **no rate limit** on purpose — eBay polls it and reads a 429 as an outage
  — and answers **503 rather than a wrong-but-plausible digest** when unconfigured. Verified
  end to end from eBay's own servers, not just our probes.

  **The endpoint URL is a literal in `.railway/railway.ts`, not `preserve()`** (#128): eBay
  hashes the URL *it* holds into every challenge, so a byte of drift fails validation with
  nothing to show for it. Both eBay variables were declared for #124's reason — undeclared,
  `apply` would have deleted them and returned the endpoint to 503.

  **And the measurement that will shape the batch** (#129): segmenting 310 live GB listings
  for one film gives **£30.45 across everything and £12.21 for the plain Blu-ray — a 149%
  overstatement**, because the query also returns 4K editions (£50.45 median), collector
  steelbooks (£105.61) and multi-film bundles. `condition` cannot fix it — it is a localised
  display string with 16 spellings for five conditions. `conditionId` can. **"We got a
  number" is not "we got the right number"** — the same lesson as `#122` and today's
  scrape-verdict bug, arriving a third time from a different direction.

  *Left for the owner:* `railway config apply` still shows one line of **pre-existing
  drift** — `deploy.restartPolicyType (null → "ON_FAILURE")`. The live `api` service has had
  **no restart policy since Batch 2** while this repo claimed otherwise; visible only because
  today was the first `config plan` run since that file was written.

- **2026-09-10** — **Checking the retailer selectors found four bugs, and the selectors were
  mostly fine.** The first unattended-shaped run logged 11 failures out of 17. Checked
  against the live sites, one at a time:

  **Eight were not failures.** Arrow answered *"Sorry We Couldn't Find Any Results"*, 101
  Films *"0 results found"*, Second Sight the same — they do not carry those films.
  `not_stocked` required `titled_cards > 0`, so it handled *"results returned, none
  matching"* and let *"no results returned"* fall through to the failure branch. Those feed
  auto-disable: **three quiet nights would have switched a working shop off**, unattended,
  and it had not bitten only because each shop happened to price one film that night.

  **Three were real, and the opposite kind of bug.** Zavvi renders two price markups on one
  page; the selector read only the variant-wrapped one, so a genuine **£16.99** on `Castle
  Freak` was fetched, parsed and discarded. Missed alerts rather than wrong ones.

  **A third, found while fixing the second.** `_select_one` used `select_one`, which for a
  comma list returns document order, not selector order — so Second Sight's
  `".price-item--sale, .price-item--regular"` never had the sale-first precedence it was
  plainly written for. Selector lists are tried in order now.

  **A fourth, found while making the first observable.** `/retailers` computed its
  denominator as `attempted - notStocked`, but `attempted` already excludes `notStocked`
  (`#107`). The real run — 17 attempted, 23 not stocked, six discs priced — rendered as
  *"Nothing to price — no shop had any of the wants"*. A docstring and the web tests both
  asserted the wrong contract, so two sources agreed with each other and disagreed with the
  producer.

  **`#125` supersedes one clause of `#107`, and it is named rather than dropped.** #107
  decided a page with no titled listing *"still takes a strike"*, so a redesign would
  eventually auto-disable the shop. Sound reasoning, wrong premise — it assumed zero
  listings means the site changed, and the measurement says it usually means the shop was
  asked a question. The redesign case survives one level up: it makes *every* want return
  nothing, which is what the new per-retailer flag says. Visibility over auto-disable, the
  owner's call.

  **CI caught what reading did not, twice.** A CHECK constraint rejected the new
  `no_results` status — Batch 16 doing its job, a new state has to be declared. And two API
  tests failed because I had changed expectations rather than fixed bugs: `attempted`'s
  meaning is #107's, not the docstring's. Both invisible locally (gotcha 15).

  Migration `027` is applied to production; 1,857 `collection_items` untouched.
  **Tonight's 03:00 cron is the verification** — and closes §5.5 in the same run.

- **2026-09-10** — **The owner applied the crons and closed three criteria; the live rows
  say which, and which are still open.** `cron-scrape` (`0 3 * * *`) and `cron-reminders`
  (`0 8 * * *`) exist in Railway, and `railway config plan` reads `0 to add, 0 to destroy`.

  **§5.6 met.** A manual nightly run attempted 17, wrote 6, and queued 2 alerts;
  *"Cross of Iron is £12.99"* was **sent and delivered** to a real iPhone. Mark's copy of
  the same alert is `suppressed` with reason `no_subscriptions` — the outbox behaving
  correctly, and the standing evidence that §6.2 is still open.

  **§9.1 met.** Two `claude-sonnet-5` calls in `ai_usage_log` with input and output tokens
  and cost recorded, no error on either.

  **§9.5 cannot be settled from data, and that is by design.** Recognition runs in the
  browser and dictation deliberately fills the input rather than sending it, so a spoken
  question and a typed one write identical rows. Only the owner can confirm it.

  **One thing to look at, not yet acted on.** That run recorded **11 failures out of 17
  attempted**, every one *"no price found — the selector matched nothing usable"*, against
  retailers where six other lookups succeeded in the same pass. 23 more were correctly
  `not_stocked`, and no retailer was auto-disabled. It is not a regression from today, but
  after `#122` — a parser that matched its own invented fixture and nothing the site
  served — "the selector matched nothing usable" is a sentence worth taking at face value
  rather than assuming it means the shop is out of stock.

  **A permanent, benign plan diff.** `api deploy.restartPolicyType` reports as changing on
  every plan: Railway stores it absent while `restartPolicyMaxRetries: 3` persists, so
  `ON_FAILURE` appears to be the default normalised to null. It was **not** removed from
  `railway.ts` — the default is undocumented, and changing a production restart policy on a
  guess is not worth a tidy plan. The number that matters is still `0 to destroy` (`#124`).

- **2026-09-10** — **`railway config apply` would have deleted two live credentials, and
  had been able to since the day they were set.** Found by running the read-only
  `railway config plan` before adding the cron services: it read `2 to add, 3 to change,
  **2 to destroy**`, and the two were `api.ANTHROPIC_API_KEY` and `api.TMDB_READ_TOKEN`.

  Both were set in the Railway console on 2026-09-09 and never declared in
  `.railway/railway.ts`. IaC removes what the file does not declare, so it read them as
  drift. Applying would have **recreated the TMDB outage of 2026-09-09 exactly** — every
  TMDB-backed feature answering 502 behind a fully green gate — and taken the assistant
  with it. The JWT secrets were a quieter version of the same thing: declared as generated
  values but sealed, so they cannot be read back to compare, so every plan reported them as
  changing and an apply would have signed both people out. `DECISIONS.md` #124.

  All ten API variables are now `preserve()` — which names a variable without putting its
  value in the repo — and the plan reads **`2 to add, 1 to change, 0 to destroy`**.

  **The two crons are declared rather than clicked.** `cron-scrape` and `cron-reminders`
  are services in `railway.ts` sharing the API's image at a different entry point, taking
  `DATABASE_URL` and the VAPID keys **by reference** from `api` so each secret has one copy.
  `restartPolicyType` is `NEVER`: they make live requests to real shops, and retrying a
  failed night automatically would turn one bad night into three. All that is left for the
  owner is `railway config apply`, which stays his because it is a hosting change.

  *What made the trap invisible:* `.railway/README.md` warned against running `apply`
  outside close-out, which reads as caution about changes you meant to make. The hazard was
  the opposite — a change nobody authored, produced by the file's silence. The README now
  says to read the destroy count first.

- **2026-09-10** — **Writing out the owner's remaining steps found a live data-loss bug.**
  §5.6 needs a want whose `max_price` sits above its current price, and there was no way to
  set one on a want you already had: the field existed on the add form and nowhere else.

  Adding that control meant reading the update path. `PUT /api/v1/wanted/{id}` **replaces
  the row** — every field on its request model defaults to `None` — and the web app's one
  call site sent `{isActive}` alone. **Every press of "Stop looking" or "Look again" also
  nulled the format, the edition, the maximum price and the notes**, silently, in
  production, with `admin_actions` recording it faithfully as a change nobody had asked
  for. `DECISIONS.md` #123.

  The endpoint is not the bug: `PUT` means replace. The client now sends the complete
  resource with only the changed field overridden, `updateWanted` takes the row's own
  `currency` instead of hard-coding `GBP` where no caller could override it, and two tests
  pin both halves — the toggle round-trips every preference, and the endpoint's
  full-replace contract is asserted so the next person reads it as the contract rather than
  patching the API to be lenient.

  **A verification note worth keeping.** Confirming the new control had deployed by
  comparing the local bundle hash against Vercel's was wrong twice over: Vercel injects
  `VITE_API_URL`, so the hashes can never match, and Vercel answers an unknown
  `/assets/*.js` with `index.html` at **200**, which reads as "the file is there". The
  reliable check is to read the deployed `sw.js` precache manifest, fetch what it names,
  and grep for a string only the new build contains.

- **2026-09-10** — **§3.7's live run found that Batch 23's scraper had never worked, and
  the fix's own re-run found a second bug.** The owner accepted `#110`'s risk and asked for
  the run (`#121`).

  **First pass: ten pages fetched, `200` on all ten, zero specs extracted.** The parser
  looked for `<div class="row"><strong>Codec:</strong>`; the site serves
  `<span class="subheading">Video</span><br>Codec: MPEG-4 AVC<br>` — section headings with
  bare `Label: value` lines and no `<strong>` anywhere. `_label_of` returned `""` for every
  node on every page.

  **The suite could never have caught it.** `test_specs.py`'s `PAGE` was hand-written to
  match the parser. Fixture and parser agreed with each other and neither had ever met the
  site; eleven extraction tests passed against markup that has never existed. This is the
  third time this project has had a green gate over a broken feature — the missing TMDB
  token, the scraper *test* button that saved nothing, and now this.

  **Second pass: one audio track where the page lists six.** With one captured fixture the
  parser passed, but `Blade-Runner-2049-4K/189774` wraps its tracks in a `<span title="…">`
  and Fight Club's page does not, so a `_lines` reading only top-level children flattened
  all six into one string — and gave that one track a channel count belonging to the line
  below it, which is worse than storing nothing. `_flatten` recurses now. **One real page is
  a sample of one**, so the 4K page is a second fixture, kept precisely because it disagrees
  with the first about its own markup. It also carried the only HDR block of the ten, which
  the flattened version was dropping too.

  **Third pass met the criterion:** 10 rows of 1,857, 10 distinct release URLs, no halt, no
  currency symbol in any derived field.

  **What held throughout.** Every one of `#110`'s bounds — sequential requests five seconds
  apart, honest user agent, no redirect following, exact release URLs, never a `403`. And
  `apply_specs` checks `is_empty` before touching a row, so two broken passes cost twenty
  wasted requests and **no data**: a parser that stops matching the site writes nothing
  rather than blanking 1,857 rows. `DECISIONS.md` #121, #122.

  **The guard that matters more than the fix.** `TestTheFixtureIsReal` asserts the fixtures
  stay captured — provenance line present, `<span class="subheading">` rather than
  `<strong>` rows, price cell still in place. A fixture written to match the parser is the
  bug; a test that says so is the guard.

- **2026-09-10** — **The two Railway crons had nothing to run.** Found while walking the
  owner through his remaining close-out steps: `OWNER-ACTIONS.md` told him to point a cron
  at `POST /api/v1/scrapers/daily` and `POST /api/v1/notifications/run-reminders`, but both
  are `AdminUser`-authed and an access token lives 24 hours. **A cron container has no
  browser, no login and nothing to refresh, so neither endpoint was callable by a scheduler
  at all** — the owner action could not have been completed as written. Batches 11 and 20
  each shipped the endpoint half and left the command half unbuilt.

  `src/scripts/daily_scrape.py` and `src/scripts/run_reminders.py` are those jobs as
  commands, matching the precedent `#60` set with `refresh_completion_sets.py` — whose whole
  point was that scheduling should be *"one console action rather than a piece of
  engineering"*. No new credential (the container already holds `DATABASE_URL` and the VAPID
  keys) and no second authentication path on the API; the endpoints are untouched. A shared
  secret was offered as the alternative and the owner chose the scripts. `DECISIONS.md` #119.

  **The exit code is the behaviour worth testing**, because it is the only thing a scheduler
  reads: a failed retailer exits 1 and names the shop and the reason, a shop that simply does
  not stock a film exits 0, and `--dry-run` is opt-in on the scrape — a nightly job that
  defaulted to writing nothing would be indistinguishable from one that works.

  **One seam moved.** `push_sender` left `routers/notifications.py` for
  `src/services/push_transport.py`, so a scheduled job does not import FastAPI and the whole
  route table to obtain a transport; the router re-exports it and a test asserts the two
  names are one object.

  **CI cannot prove the container runs these**, because it never builds the image — so
  `test_deployment_config.py` asserts the contract they depend on instead: `WORKDIR /app`,
  `PYTHONPATH=/app`, the whole `src/` tree copied, and the command line in `OWNER-ACTIONS.md`
  matching the module that exists. A moved `WORKDIR` would otherwise break both crons
  silently, and the first sign would be a scrape that never ran.

  **Also settled with the owner:** the 300 KB photo target is now a recorded decision rather
  than an inference two docs disagreed about (`#120`), and the owner accepted `#110`'s
  Blu-ray.com risk so §3.7's live run can proceed.

- **2026-09-10** — **Batch 23 built: the Blu-ray.com spec scraper, badges and filters.**
  The last of the overnight run's eight batches.

  **#110's bounds are enforced by the code rather than described by it.** Exact release URLs
  only, with the disallowed search routes refused by name; requests sequential and five
  seconds apart, with an honest user agent and no redirect following, because #110 forbids
  evasion; a `403`, `429` or `451` **halts the whole integration** and abandons the rest of
  the batch. The halt is a database row, not a variable — one held in memory lasts until the
  next deploy, and that is precisely the promise that must not break. **Nothing in the runner
  can clear it**, and a test asserts that, because #110 says resuming needs a new owner
  decision.

  **No price, rating or review is extracted, and the page carries all three in the same
  document.** #108 calls the temptation "unusually close to hand", so the parser reads an
  allow-list of labels, the forbidden ones are named, and a test proves the two sets
  disjoint. The fixture deliberately carries a list price, an Amazon price, a rating and a
  review so their absence is demonstrated rather than promised.

  Two more of #108's measured facts changed the code: **audio is rendered twice** behind the
  `(more)`/`(less)` toggle, so extraction targets DOM nodes and de-duplicates; and **Special
  Features was absent** from a real page, so it is nullable rather than assumed.

  §3.8's badges use three genuinely distinct colours — resolution, HDR and audio are three
  different claims, and a row of identical pills makes them one blur. A disc with no specs
  renders **nothing**, not a grey "unknown": the app does not know until it has asked, and a
  placeholder that looks like data is how a catalogue starts lying.

  **§3.7's acceptance is not done and is an owner action.** It needs a live run against ten
  real URLs on a site whose terms prohibit automated access; #110 is the owner's acceptance
  of that risk rather than a permission an agent inherits, and `group-start.md` puts live
  third-party runs in the owner's hands — which is how Batch 19's checkpoint worked too.
  Production reports **0 pages ever fetched**, and `DELETE /api/v1/specs` is there to make
  the whole thing reversible.

- **2026-09-10** — **Batch 25 shipped: photos of a disc.** Bytes in Postgres, resized before
  they get there.

  §3.10 says Supabase Storage and there is no Supabase project; the owner settled storage as
  Neon, so a photo is a `BYTEA` column served by the API — and a real `item_photos` table
  rather than §3.4's `photo_urls`, which designs a list of *external* URLs there is now
  nothing to point at.

  **The resize is why the batch is shaped like this.** §3.10's raw numbers are 5 MB × 5 ×
  1,857 ≈ 46 GB, in a database that measured **36 MB** live today. A phone's 4032×3024
  photo now stores at about 240 KB — measured in a test rather than asserted in a comment.

  **A disagreement between two in-repo docs, resolved by making it cheap.**
  `OWNER-ACTIONS.md` said the 300 KB cap was "proposed… not confirmed"; `STATUS.md`'s own
  run plan and the batch ledger both listed it as *"(owner, 2026-09-09)"* under "settled
  inputs, so no batch has to ask again". No `DECISIONS.md` entry exists either way. It
  shipped at 300 KB — the number both docs name — with the target as the `PHOTO_TARGET_KB`
  **setting**, so the thing that made it an owner choice ("annoying to reverse once photos
  exist") is no longer true: changing it is one variable and a re-upload.

  **Every upload is decoded and re-encoded.** EXIF orientation applied *then dropped* —
  dropping it without applying is how a gallery fills with sideways shelves; transparency
  composited onto white rather than the default black; and Pillow's pixel ceiling refuses a
  decompression bomb, which is a tiny upload that unpacks to gigabytes.

  **Two blockers turned out not to exist.** Group H said Batches 24 and 25 were "both
  blocked on the same two `vercel.json` fixes". Neither was needed: `camera=(self)` has been
  live since Batch 2, and the photos are served from the API origin `connect-src` already
  allows. **`authFetch` did need a fix** — it forced `application/json` onto every body,
  which for multipart omits the boundary and makes the server parse nothing out of a request
  that looks perfectly normal.

  **Nothing failed in CI.** Green on the first push, 21 new tests.

- **2026-09-10** — **Batch 35 shipped: movie night.** Sessions, an invite URL, a swipe deck
  and match detection over Postgres `LISTEN`/`NOTIFY`.

  **The net-new integration turned out not to be needed.** §8.4 names Supabase Realtime and
  the ledger tiered this batch 🔴 partly for it; `DECISIONS.md` #113 replaced it with
  `LISTEN`/`NOTIFY` and SSE the day before, so it shipped with no new service, credential or
  bill.

  **#113's warning shaped the whole realtime module.** `LISTEN` holds a connection for as
  long as it listens, and taking one from the request pool for a whole movie night exhausts
  the pool and reads as the entire app hanging — Batch 8's paused query in another costume.
  One dedicated connection is opened on the first watcher and closed with the last. Unlike
  #60's cron, two containers is *correct* here: both listen on the same channel.

  **A match is derived, never stored** (gotcha 1b), with `announced_at_utc` the only derived
  state kept so it is announced once. The rule is "everyone here" rather than "two" — free
  now, and the difference between a feature that grows and one with a 2 baked in. **The
  other person's votes are invisible**: the stream says only that *a* vote happened, and a
  card vanishing because they swiped it would leak which way.

  `asyncpg-stubs` went in as a dev dependency rather than a mypy override for the module,
  and immediately earned it: asyncpg's listener callback really takes `object`, not `str`,
  because a binary-mode connection delivers bytes.

  **A stale owner action closed on the way past.** `OWNER-ACTIONS.md` still asked "what
  provides realtime for Batch 35?" — a question #113 had answered as an owner decision the
  day before. Marked done rather than asked again.

  **Nothing failed in CI.** Green on the first push, 16 new tests. §8.4's notification
  *arriving on a device* is deferred with 6.2 and 5.6; the match and both notification rows
  are proved.

- **2026-09-10** — **Batch 32 shipped: voice input.** Stage 9 is complete apart from 9.6,
  which `DECISIONS.md` #16 dropped.

  On-device recognition — the browser's engine listens and nothing is uploaded by this app.
  `microphone=(self)` had been in `vercel.json` since Batch 2, so no hosting change.

  **Dictation fills the input and never sends.** The engine mishears; a button that
  submitted on the last word would put a wrong question to the assistant with no chance to
  correct it, and would also make the acceptance criterion uncheckable — "correct
  transcription" is something only the person can confirm, by reading it.

  **Two things that would have been silent bugs.** TypeScript's DOM library declares none
  of the Web Speech API, so the used surface is declared in-repo rather than casting
  `window` to `any` — which accepts a misspelled event name and yields a mic that listens
  and reports nothing. And interim results are reassembled rather than appended: the engine
  revises earlier entries in place, so concatenating each event produces "where where is
  where is Heat".

  **9.5's acceptance is deferred** — it needs a person speaking into a microphone.

- **2026-09-10** — **Batch 31 shipped: role-aware tools, streaming chat, and confirmation
  before any write.** `fe1db05`. Group J is complete.

  **The agent loop is manual and that is the whole design.** The SDK's tool runner drives
  the cycle in one process; §9.4 requires it to stop, hand a request to a browser, and
  resume when a person answers in a *later HTTP request*. So a pending write is a row, not
  an in-memory future — the latter loses every outstanding confirmation on the next deploy.

  **Every call in a turn gets a row, including the reads.** The API insists one
  `tool_result` message answers all of an assistant message's `tool_use` blocks, so a turn
  that both searches and writes cannot send half an answer while it waits. The read runs,
  its result is held, and both go back once the write is resolved. A cancelled call is kept
  and marked, with a result the model reads as a refusal — otherwise its next sentence
  cheerfully reports success.

  **`DECISIONS.md` #12 stays closed.** Tools dispatch to the same endpoint functions the web
  app calls, which are plain async functions taking `(user, db, ...)`, and results come back
  as the same pydantic models the browser parses. No envelope was needed and none was added.

  **"Write" and "admin-only" turned out to be different questions.** Watch history is
  personal — Batch 6 and Batch 37 both scope it to the caller — so `log_watch` writes and a
  viewer keeps it. One axis would have taken it from Mark for no reason.

  Messages store raw content blocks rather than text, because replaying only the text makes
  Claude answer as though a tool call never happened, silently. `sequence` orders them:
  `NOW()` is the transaction's start time and a turn writes several rows in one (gotcha 24).
  The browser parses SSE with `fetch` rather than `EventSource`, which cannot POST or carry
  an Authorization header, and buffers across chunk boundaries — a frame routinely arrives
  split across two reads, and a parser that assumes otherwise drops text with no error.

  **Nothing failed in CI.** Green on the first push, 34 new tests.

  **A stale number corrected while verifying.** The "what the live database holds" block has
  said 3 `wanted_list` rows since 2026-09-09. It is 11, 8 of them live — the three originals
  were soft-deleted and eight boutique titles added during that evening's acceptance run
  (#111). Confirmed that nothing this session wrote to production: 1,857 items untouched,
  8 `price_checks`, and `ai_usage_log` empty.

- **2026-09-10** — **Batch 30 shipped: the Claude client and the AI usage caps.**
  `ecb00dd`. Group J is half done.

  **The model id is config, validated at load.** `docs/phase-batches.md` warned "do not
  guess a model id" — the April spec predates the current lineup by two generations. The
  validator refuses an id this app has no price for, which catches the *worse* failure as
  well as the obvious one: a wrong id 404s loudly, an unpriced one works and silently logs
  every call as free, and a cost cap counting zeros never fires.

  Two more things the spec could not have known: `budget_tokens` returns a **400** on the
  Claude 5 family (adaptive thinking plus an `effort` level replaces it), and assistant
  prefill is gone, so response shaping lives in the system prompt.

  **§9.7 enforces two ceilings, before the call.** A message count alone does not bound
  spend — the same question costs more at the end of a long conversation. Checking after
  the call would still have spent the money, and a test asserts the model is never reached
  once the cap is hit. A refusal is a 200 carrying the sentence, not a 429. The day is the
  person's local day (gotcha 26), and `cost_usd` holds six decimal places because rounding
  a sub-penny call to cents records it as free.

  **Readiness now reports `ai` alongside `push` and `db`,** and live it says `configured` —
  so the Anthropic key really is in Railway, which is the one thing a green gate could not
  have told anyone.

  **Nothing failed in CI.** All five jobs green on the first push, 34 new tests.

  **§9.1's acceptance is deferred and is a one-minute job.** It needs a live call, which
  spends the owner's money on a key held only in Railway; there is no credential on this
  machine and the deployed endpoint needs a login. Open Assistant in the sidebar, ask one
  question — the token count and cost render underneath it.

- **2026-09-10** — **Batch 20 shipped: the nightly price job, drop alerts and the 90-day
  roll-up.** `464e495`. Group F is complete.

  **§5.6 as written could not be built.** *"Postgres trigger after price_check insert …
  queue push"* — a trigger runs inside the writing transaction and cannot make an HTTP
  request. Batch 11's outbox is the queue it would have needed, so detection lives in the
  scrape path and writes a `deals` notification. `price_checks.notification_sent`, the
  column §3.6 designed for the trigger, is still the flag.

  **Alerts fire on the transition, not the condition.** A price at or below `max_price`
  stays that way until the disc is bought; alerting on it nightly would train the owner to
  ignore the category. A substituted format or edition still alerts and **says so** —
  suppressing it hides a real find, sending it silently lets "Deep Red is £15" mean the
  Blu-ray when the want was the 4K.

  **`scrape_runs` is new, and #112's criterion is unverifiable without it.** The counts the
  corrected acceptance is stated in used to exist only inside one HTTP response. They are
  now a row, with every failure carrying its retailer and reason, and a run that dies
  halfway is visible as a run that died halfway rather than as no run at all.

  **One CI failure, and it was the test that was wrong.** The not-stocked fixture used a
  generic whole-page config to exercise `DECISIONS.md` #107's detection, which only exists
  on the card-by-card path — `extract` says so in its own docstring. Batch 19's conservative
  reading is left alone and the fixture is now card-shaped, which is what every enabled
  retailer is. **Recorded because the gap is real for a hand-configured generic retailer:**
  three correct refusals in a row would auto-disable it.

  Verified live: `021` applied, both new tables present, 8 `price_checks` untouched, the new
  endpoints auth-gated. `scrape_runs` is empty and correctly so — **nothing schedules the
  job**, which is why §5.5's *"first overnight run completes"* and §5.6's *"push on a test
  device"* are both deferred to the owner.

- **2026-09-10** — **Batch 11 shipped: notifications and Web Push.** `36d3efa`, plus
  `69d263e` for the readiness check. First of the eight-batch overnight run.

  §6.1's toggles, digest mode and quiet hours; §6.2's per-device subscriptions and test
  button; §5.11's seeded sale seasons and their pre-sale reminder. Web Push is implemented
  directly on `cryptography` against RFC 8291/8292 rather than pulling `pywebpush` and its
  two companions, so `tests/test_webpush.py` can derive the message keys from the
  **receiver** side — the browser's half of the algorithm — instead of proving only that a
  library agrees with itself (`DECISIONS.md` #115).

  **Everything routes through an outbox**, which is what makes §6.1 checkable rather than
  asserted: a disabled category leaves a `suppressed` row naming itself, an evening alert
  leaves a `queued` row due at 07:00, and digest mode leaves three sharing one push. Quiet
  hours carry an IANA timezone — the one place this app is deliberately not UTC, because a
  22:00 window read in UTC is an hour wrong for the seven months of BST (gotcha 26).

  **A hosting step was removed rather than performed** (#114). The plan had the owner
  setting `VITE_VAPID_PUBLIC_KEY` on Vercel; instead the API serves the public key derived
  from the private half, so the two cannot disagree and push works the moment the code
  deploys. And because the remaining key still lives only in a Railway variable — the TMDB
  shape — `/api/v1/health/ready` now reports `push: configured | not_configured | invalid`,
  loading the key rather than checking that a string is present.

  **Two debts paid.** §12.5's overdue-loan push, unmet since Batch 15, now writes that
  batch's unused `loans.reminder_sent`. Batch 9's dropped onboarding notifications step
  (`#50`) is back against real infrastructure: 7 steps for an admin, 6 for a viewer.

  **Three defects CI caught that the local gate could not.** A partial unique index is not
  an `ON CONFLICT` arbiter unless its predicate is repeated — that took down all seven
  deduplicated paths. `UUIDPrimaryKeyMixin`'s `default=` runs when SQLAlchemy builds the
  INSERT, so a hand-built one sent a NULL primary key. And two assertions read the whole
  `notifications` table, where migration `002`'s seeded profiles mean a reminder correctly
  writes more rows than the fixture creates. All three are gotcha 15: a green local run says
  nothing about SQL.

  **The dependency audit rejected `cryptography` 48.0.1** over PYSEC-2026-3552/3553/3554.
  The `<49` pin that produced it was mine, added so this laptop could install a wheel; it
  was removed rather than defended. The cost is that this machine now runs 48.0.1 while CI
  and Railway run 50.0.1 — recorded as gotcha 28 rather than hidden.

  Verified live, not merely green: `020` applied to Neon with all three tables present,
  every notification route `401` while a made-up sibling `404`s, and `push: configured`.
  **§6.2 is deferred to the owner — it needs two real devices.** A daily cron for
  `run-reminders` is a new owner action.

- **2026-09-09** — **An audit session, not a batch session. Three beliefs about what was
  blocking the queue turned out to be false, and one production outage had been invisible
  behind a green gate.**

  **`TMDB_READ_TOKEN` had never been set in Railway.** The *Add a film* panel reported "TMDB
  search is temporarily unavailable"; TMDB was fine, and both credentials in `.env.local`
  returned 200. `config.py:70` defaults the token to `""`, so the API booted happily and sent
  `Authorization: Bearer ` on every call, which TMDB answered 401 and the routers converted
  to a 502 whose wording claimed transience. The blast radius was every TMDB-backed feature in
  the deployed app. Set the same day, along with VAPID keys and `ANTHROPIC_API_KEY`; Mark's
  PIN was set too, so both profiles can now sign in.

  **The scraper acceptance run had never saved a row.** The setup steps had been done — Arrow
  corrected to `arrowfilms.com`, five shops enabled — but `price_checks` and `wanted_list`
  were both empty, so the criterion everyone believed was met had never been attempted. It has
  now produced its **first real price**: Arrow Video, *Misery Limited Edition 4K UHD*, £25.00,
  an exact 4K match with no substitution, verified independently against the live site.

  **A 4K want answered with a Blu-ray turned out to be correct.** Zavvi has no 4K *Nope* at
  all — searched with and without the format term, the only *Nope* disc on the site is
  `/p/blu-ray/nope/`. The fallback and its `substitutedFormat` flag behaved exactly as #102
  specifies. The bare-title search also returned seven Magic: The Gathering and Disney
  t-shirts, every one correctly refused: the Jaws beach towel case, caught.

  **Three working scrapers had been auto-disabled for telling the truth** (`DECISIONS.md`
  #107). 101 Films, Powerhouse and Second Sight each returned a real catalogue page for
  *Misery*, extraction parsed it correctly, and #96's title rule refused every listing because
  none of them was the film. Three correct refusals read as three failures and switched all
  three shops off. `ScrapeOutcome.not_stocked` now separates "the shop answered and has not
  got it" from "the scraper is broken", read from card counts rather than the rejection
  message — because `check_shape` stops at "no price found" before reaching its title rules,
  and Zavvi's real answer for `?q=Nope 4K` leads with a priceless *Cujo* that would otherwise
  have been filed as a broken selector. The three shops were re-enabled with their counters
  zeroed. **Zavvi still carries 2 strikes** from a genuine throttling failure.

  **Batch 23's source settled and Batch 26 dropped** (#108, #109). Specs are scraped from a
  URL supplied per film rather than from the site's search, which `robots.txt` disallows; a
  real page was measured and returns every field §3.7 asks for. **#108's reasoning that this
  therefore "stays inside what the site allows" was wrong**, and #110 — written earlier the
  same day by a parallel session — supersedes it: absence from `robots.txt` is not
  permission, and the access proceeds as an owner-accepted risk instead. Three constraints recorded: the page also carries
  third-party prices the scrape must ignore, `(more)`/`(less)` toggles duplicate the audio and
  subtitle blocks in the flattened text, and `Special Features` can be absent. Shelf QR is
  dropped — Batch 6's location filter already answers the question it existed for. Ledger
  arithmetic re-derived rather than decremented: **37 batches → 24 sessions**.

  *Storage for Batch 25 is settled as Neon* (owner), meaning photo bytes in Postgres. The
  per-photo cap and Batch 35's realtime provider are both proposed but unconfirmed, and sit in
  `OWNER-ACTIONS.md` rather than being taken silently.

- **2026-09-09** — **Batch 27's security review: no findings at its bar, four real defects anyway.**

  The review you asked for ran against `feat/27-gift-links` before the merge. It verified all
  six intended properties with file-and-line evidence and reported **no security findings at
  its confidence bar** — but it surfaced four real defects, all fixed on the branch before it
  merged:

  | Found | Fixed by |
  |---|---|
  | The retailer-link builder ran **inside** the per-film loop — 50 identical `retailers` queries for a 50-film page, on the unauthenticated endpoint | hoisted; a test asserts exactly one `FROM retailers` per page |
  | **The service worker cached `no-store` responses.** It matched any GET under `/api/v1/` by pathname alone, so a gift page a family member opened was stored for 24h in *their* browser — and the route's own comment claiming the API sets no `Cache-Control` had become false | same-origin only, both capability URLs excluded, comment corrected (`DECISIONS.md` #87) |
  | `Decimal("NaN")` **parses**, so the `<= 0` guard raised rather than being caught — a 500 on an admin field in **Batch 18's already-merged code** | `is_finite()`; tests cover NaN, Infinity and sNaN |
  | `view_count += 1` was a read-modify-write in Python | atomic `SET view_count = view_count + 1` |

  Two things it named as conscious trade-offs rather than defects: the slug is stored in
  plaintext (`DECISIONS.md` #84 — a gift link must be re-shareable, unlike Batch 17's hashed
  feed token), and it transits request logs the way any path parameter does.

  **One process failure worth keeping.** The first review attempt failed before doing any work
  (monthly spend limit) — and I had *already* written "Reviewed" into the ledger and the commit
  message. That claim was corrected in `247ee25` and the branch was held unmerged until a
  review genuinely ran. Nothing is a review until it returns findings.



- **2026-09-09** — **Batch 23's Blu-ray.com risk was accepted explicitly, not explained
  away by `robots.txt`.** The site's Legal Notices prohibit automated reuse even for
  private/internal calculations, which supersedes #108's claim that exact release-page
  fetching is allowed. The owner accepts the practical risk, including the one-time
  1,857-item backfill; #110 keeps exact public release URLs, no site search or authentication,
  sequential rate limiting, indefinite caching, provenance for reversible cleanup, and a
  hard stop on `403`, `429`, an objection or a hosting complaint. Written permission is
  preferable but no longer blocks Batch 23.

- **2026-09-09** — **A want can now name an edition, not just a format.** Arrow sells *Deep
  Red* on 4K three times — plain £25, Limited Edition £25, Arte Originale slipcover £35 —
  and page order decided which a `max_price` alert was about. `wanted_list` gained
  `preferred_edition` (migration `019`, free text, nullable; the table was empty).

  **Naming the edition is also what makes it findable.** #96's rule refuses a title with
  meaningful extra words, so the slipcover listing was being *rejected outright* — *arte*
  and *originale* read as another film. The wanted edition's words now join that item's
  allowed vocabulary. Verified live against Arrow: no edition → the plain £25 4K; "Arte
  Originale Slipcover" → the £35 disc; "Limited Edition" → the £25 LE; "Steelbook" (not
  stocked) → falls back to the plain 4K and reports `editionMatched: false`.

  **The edition never narrows the search.** Measured: edition terms promote Arrow's exact
  listing, but on Zavvi `?q=Alien Steelbook 4K` returns seven steelbooks and no Alien at
  all. It is a selection input, not a search input (`DECISIONS.md` #104–#106).

- **2026-09-09** — **A want for a format now means that format.** Asked how a want for a
  specific version of a film would behave. It mostly did — `preferred_format` picks 4K vs
  Blu-ray vs DVD — but three defects were found underneath it (`DECISIONS.md` #101–#103):

  1. **Every 4K disc also says "Blu-ray"**, and format preference matched on mention, so a
     £19.99 4K combo satisfied a want for the £9.99 Blu-ray whenever it ranked first. A
     listing is now the *highest* format it names, because that is what is in the box.
  2. **A fallback was silent.** When the wanted format was not on the shelf, a different one
     was priced with nothing said — and `max_price` compares against whatever was priced, so
     an alert was either missed or wrong with no way to tell which disc it meant. The run
     now reports the format actually priced and the UI says so.
  3. **A digital want priced a disc.** `download` had no search term, so it fell back to
     "Blu-ray". Worse, it counted as a retailer *failure* — and three consecutive failures
     auto-disables a shop, so a digital-only wanted list would have **switched off every
     enabled retailer in the app**. Digital wants are now skipped, reported separately, and
     never counted against a shop that was never asked.

- **2026-09-09** — **The Test button was sending shops an unfilled placeholder.** Reported
  from the app: *Jaws* on Zavvi returned **The Sheriff of Fractured Jaw (Dual Format
  Edition)**. The cause was the previous fix's own doing — `ScraperTester` built its search
  URL in the browser and replaced `{query}` alone, so the new `{format}` placeholder went
  to Zavvi as literal text and matched a dual-**format** western. An unfilled placeholder
  is worse than a broken URL: it is extra search terms a shop happily matches, so the
  failure arrives looking like a result.

  Fixed at the root (`DECISIONS.md` #99, #100): `apply_search_template` is now the only
  function that knows what a placeholder means, the client sends the **template**
  verbatim, and the server fills it with the same call the runner makes. The test endpoint
  also now passes the expected title, the preferred format and the retailer's host into
  `extract`/`check_shape` — it had been doing none of those, so it priced whichever card
  came first and never applied the same-site rule. **A test is now exactly as strict as the
  run it stands for.** The tester gained a format selector to match.

  Re-verified against the live shops through the fixed path: *Jaws* at Zavvi → the 4K disc
  at £19.99, all five supported shops return the right film, *Heat* still correctly refused.

- **2026-09-09** — **The scrapers now filter on films, not on names.** Reported from the
  app: searching Zavvi for *Jaws* returned **a beach towel**. It passed all five of #79's
  shape rules — the film's name in the title, £17.99, GBP, a zavvi.com URL — so the price
  of a towel was being written as the price of the film. Fixed, and two more found while
  fixing it (`DECISIONS.md` #95–#98):

  1. **Merchandise.** A listing must now name a disc format in its title or URL. Zavvi's
     first twelve results for *Jaws* were towels, jumpers, T-shirts and a resin statue.
  2. **The film the shop does not stock.** Zavvi has no Michael Mann *Heat*, so it returns
     *Heat and Dust*, *The Big Heat*, *Red Heat* and *Step Up 4: Miami Heat* — each sharing
     a significant word, each passing the generous title rule, each a different film. A
     title carrying meaningful extra words, once format and edition wording is removed, is
     now refused.
  3. **Page-wide selectors.** Each selector ran over the whole page independently, so a
     card with no price node paired its title with the *next* product's price. Extraction
     now reads product cards, which also makes `preferred_format` work for the first time:
     101 Films lists *Bad Lieutenant* on 4K and Blu-ray, and the want says which.

  **Verified against the live shops, not only fixtures.** *Jaws* at Zavvi now returns the
  4K disc at £19.99; Arrow, 101 Films, Second Sight and Powerhouse all return the right
  film; *Heat* at Zavvi and *Don't Look Now* at Second Sight are both refused with a
  legible reason. **Two built-in search templates changed** (`{format}`) and every verified
  built-in gained an `item` selector — so **"Apply these selectors" must be pressed again**
  before the next run, or the live retailer rows keep the old config.

- **2026-09-09** — **Supported retailer paths.** Live page-shape checks settled which of
  §5.3's shops can actually be scraped: **five pass** — Zavvi, Arrow (on `arrowfilms.com`,
  its UK storefront; the seeded `arrowvideo.com` is the US site and returned USD, which the
  shape guard correctly rejected), plus three UK boutique labels added as supported
  replacements — 101 Films, Second Sight and Powerhouse/Indicator. **Four are permanently
  unverified and stay listed with the reason**: HMV and CEX disallow the search routes,
  Amazon blocks automated access, Blu-ray.com is a catalogue (`DECISIONS.md` #91, #92).

  **Three real defects were found and fixed on the way, none of which a green gate would
  have caught.** (1) `_same_site` compared the last two labels, so **every `.co.uk` host was
  one shop** — a listing link off `secondsightfilms.co.uk` to any other `.co.uk` site passed
  the guard. Latent since Batch 19 because no `.co.uk` retailer had working selectors; the
  two new UK labels are the first to arm it (#93). (2) Retailer pages return **relative**
  product links, which failed `_write_check`'s `http(s)://` test — so it returned without a
  row while `written` was incremented anyway, and the same-site guard was skipped entirely
  because a relative URL has no hostname (#94). (3) A **dry run** claimed to have saved
  prices, because `written` was incremented outside the `if not dry_run` guard.

  The Retailers page now carries the whole owner checkpoint as buttons — *Add missing
  defaults*, *Apply these selectors*, *Preview live run*, *Run and save prices* — and Wanted
  gained an *Add a film* panel, because step 4 of the checkpoint previously had no UI at all.
  **The checkpoint itself is still open**: no live `dryRun=false` run has happened, and
  `price_checks` is still empty.

- **2026-09-09** — **External calendar subscription deprioritised.** The in-app release
  calendar remains primary; its RFC 5545 feed remains available as optional convenience, but
  Apple/Google device verification is no longer a current owner action (Decision #90).

- **2026-09-09** — **eBay production developer application submitted.** The owner received
  eBay's confirmation that account review is pending and takes at least one business day.
  The owner-side application action is complete; Group I remains blocked until eBay approves
  production access.

- **2026-09-09** — **Batch 37 shipped — on-this-day + rewatch** (`50a4828`). Phase 11.6:
  caller-scoped anniversary memories and high-rated, not-recently-watched suggestions are
  parsed through shared schemas and rendered on the dashboard. The acceptance is proved by a
  date-controlled Postgres test: a watch logged exactly one year earlier appears today; CI
  ran it against Postgres 17. `watch_log` remains empty in production, so the dashboard says
  why it has no memories yet rather than rendering a misleading empty card. The optional
  daily push is still Batch 11's VAPID-key-gated work.

  The first full local gate failed only because `test_health.py` deliberately pins every
  public route and needed the two new endpoints named; fixed without weakening it. The final
  local gate: 301 passed, 250 skipped (no local database URL); CI's five jobs passed,
  including Postgres-backed pytest. No hosting, credential or destructive operation. API
  production health reports the merged SHA with `db: ok`. Dashboard browser automation could
  not run: `agent-browser` is unavailable in this environment.

- **2026-09-09** — **Batch 36 shipped — command palette + keyboard shortcuts** (`1425f91`).
  Phases 6.3/6.4. A Cmd/Ctrl+K modal indexing every page, the admin-only write action, and
  films — reusing Batch 5's `/search` endpoint rather than re-implementing it — plus
  recently-viewed films in localStorage. Ten shortcuts (`g`-chords, `/`, `n`, `?`, Esc) and
  a help modal, centralized in one `useKeyboardShortcuts` hook; `SearchBar`'s pre-existing
  `/` handler now defers to it via a `mcu:focus-search` event instead of the two owning
  the same key.

  **§7.5's `.` shortcut and the palette's "recent AI-assistant conversations" index were
  dropped, not built wrong** — both depend on Batch 31's chat, which does not exist yet.
  Same treatment Batches 8/9 gave dead onboarding steps.

  **Verified live in a browser**: Ctrl+K open, the empty-query page index, fuzzy-filtering
  "wanted" to one result, Enter navigating and closing the palette, Escape closing it, and
  a `g s` chord landing on `/stats` — against the dev server with `VITE_SKIP_AUTH`, since
  the local API wasn't running (no Docker/local Postgres — gotcha 15 again, this time for
  the API itself rather than a migration). **`?` and `/` were not independently
  browser-verified** — confirmed via a raw event listener that this environment's browser
  automation tool cannot synthesize a real `key: '?'`/`key: '/'` keydown (both arrive as
  `key: ''`) — nor was "typing 'blade' surfaces Blade Runner films", for lack of a running
  search backend. All three rest on the batch's 27 new unit/integration tests, which
  dispatch real `KeyboardEvent`s and mock the search endpoint directly.

  No backend, hosting or credential changes; no destructive operation. 547 API tests and
  107 web + 65 shared tests, zero skips. Production serves the merged SHA with `db: ok`.

- **2026-09-09** — **Batch 27 closed out (`888dae7`), after its security review ran.** Gift
  links: a 128-bit slug rather than §3.21's UUID PK or §6.26's 32-bit example; four failure
  modes answering identically; a public response model deliberately unrelated to the admin
  one so no ownership, id, slug or count can leak. **The review found no security findings at
  its confidence bar and four real defects** — a per-film N+1 on the unauthenticated
  endpoint, a service worker caching `no-store` gift responses in a family member's browser,
  `Decimal("NaN")` slipping past a `<= 0` guard in Batch 18's *already-merged* code, and a
  non-atomic view counter. All four fixed with tests before the merge (`DECISIONS.md`
  #83–#87). CI green on `main` (all five jobs); production serves the merged SHA with
  `db: ok`.

  Also corrected here: nine rows of `ARCHITECTURE.md`'s §17 table still read "Not yet built"
  for work this session shipped (rows 5, 9, 12, 16, 19, 27, 42, 43, 44). The close-out step
  that would have caught it — "tick the phase line in the roadmap doc" — has been a no-op
  since Batch 10 removed §16, so eight close-outs in a row skipped it without noticing.

- **2026-09-09** — **Batch 27 built but not merged.** The security review the owner asked
  for was launched and **failed before doing any work** (monthly spend limit), so the branch
  was deliberately held — and a first version of the ledger entry claimed it had been
  reviewed, which was corrected in `247ee25`.

- **2026-09-09** — **Batch 19 shipped — scraper framework** (`bf1b4d5`), **and Group F
  stopped at its checkpoint.** Both of 5.3's and 5.4's acceptance criteria need live
  requests to real shops, which `group-start.md` reserves for the owner — so the framework
  is built and fixture-tested (33 tests) and the runs are handed over. The batch is shaped by
  its own risk note: `check_shape` asserts five properties of every result and discards
  anything that fails, because a wrong selector fetches fine and returns a plausible wrong
  number (`DECISIONS.md` #79). Every built-in reported `verified: false` at the time (#80;
  see #91 for what the live checks later settled). The fetcher
  refuses non-public addresses at every redirect hop — the app's first person-supplied URL
  (#81). CI went red because dependencies are locked with `--require-hashes` and
  `pyproject.toml` alone is not enough.

- **2026-09-09** — **Batch 18 shipped — wanted list and retailers** (`f85aa91`). §3.5 and
  §3.16 built, **paying four debts** from Batches 13, 15, 16 and 17. Two of them surfaced as
  tests that had asserted an absence and now assert the presence — which is exactly why they
  were written that way (`DECISIONS.md` #78). A wanted entry can name a film the collection
  has never seen (#75); `is_active` and `deleted_at` stay distinct (#76); the six seeded
  retailers ship with **no selectors** and say so, because a guessed selector persists a
  plausible wrong price rather than erroring (#77).

- **2026-09-09** — **Batch 17 shipped — release calendar and iCal, closing Group E**
  (`a09c172`). Live ingestion put **32 rows** in `release_calendar`; the re-run was
  idempotent. The `.ics` feed is the app's **first unauthenticated surface**, and its token
  is handled as a refresh token — hashed, rotated, one live per person, revoked-answers-like-
  never-existed (`DECISIONS.md` #71–72). **A security review found a real content-injection
  hole**: a URI property is not escaped, so a newline in `release_calendar.url` injected
  iCalendar properties. Not reachable today; **Batch 19's scrapers would have armed it**
  (#73). The first live ingestion also hit a duplicate-page defect a dry run could not reach
  — gotcha 16 again. **Apple Calendar verification is an owner action.**

- **2026-09-09** — **Batch 16 shipped — watch providers and recommendations** (`d2218ab`).
  Live: *North by Northwest* shows HBO Max plus 6 rent and 6 buy options in GB; 20
  recommendations with 7 flagged as already owned. §7.1 assumed a `streaming_region` column
  that did not exist (#70). **A defect found only in the browser, and it was mine**: a 502
  for a TMDB outage made the page say "waiting for the network" — the endpoint now answers
  200 with an `unavailable` flag, because a status code cannot carry "we are fine, they are
  not" (#68). CI went red on gotcha 21's unpinned-mypy trap and was fixed by needing no
  ignore.

- **2026-09-09** — **Batch 15 shipped — trash, audit UI and lending, closing Group D**
  (`20d1eff`). The permanent delete is the app's first irreversible operation; it gets past
  `003`'s soft-delete trigger with a transaction-scoped `SET LOCAL`, **not**
  `DISABLE TRIGGER`, which is global and would make every delete permanent if a process died
  mid-request (`DECISIONS.md` #64). Proved on live data by destroying Batch 12's leftover box
  set: row gone, cascade fired, audit trail outlived it, 1,857 discs untouched. **"Overdue
  triggers a push" is not met** — push is Batch 11 — and no fake toggle was shipped.

- **2026-09-09** — **Batch 14 shipped — stats, activity feed and export** (`20650b3`).
  Stats at 344 ms median (criterion <1s). **Two of five charts have no data** — `watch_log`
  is empty and no disc carries a price — so they say what they are waiting for rather than
  drawing zeros (`DECISIONS.md` #61). CSV/JSON/HTML export all 1,857 discs; **no
  server-side PDF renderer**, because every option needs system libraries in an image
  Railway builds and CI does not (#62). Downloads go through `fetch` into a blob so the
  token stays out of the URL (#63). Also caught and corrected a false claim in my own
  comment: the collection has **zero** non-ASCII titles.

- **2026-09-09** — **Batch 13 shipped — completion sets, closing Group C** (`22680de`).
  40 sets built live from TMDB, zero errors. Hitchcock 12 of 61, where TMDB returns 129
  crew credits and 65 director ones — the filters that get from 65 to 61 are the batch
  (`DECISIONS.md` #58), because "12 of 91" and "12 of 65" are both plausible wrong numbers
  nothing would flag. Sets are seeded from the collection's own `movie_credits`, so there
  is no name-matching step to get wrong (#57). Ownership is never stored (#59). **"Bulk add
  missing to wanted list" was dropped** — the wanted list does not exist and Batch 18 owns
  it. **"Weekly" is not scheduled**: a Railway cron is a hosting change (#60).

- **2026-09-09** — **Batch 12 shipped — box sets + smart collections** (`881f444`). Three
  tables, seven endpoints, 38 tests. The saved-filter blob is closed off twice: validated
  through a model whose fields are `GET /movies`' own parameters, and *evaluated* by the
  same function that serves `GET /movies`, so a saved collection cannot silently drift from
  the filter bar (`DECISIONS.md` #55). `isComplete` is three-valued — an unrecorded box size
  means unmeasured, not incomplete (#56). `sub_category` deliberately untouched. Driven in a
  browser against live Neon: "Unwatched 4Ks from the 2010s" listed 40 real films. CI caught
  one test of mine that assumed the local catalogue was present.

- **2026-09-09** — **`fix/date-guards-read-the-server-timezone` shipped.** A pre-existing
  red on `main` that no change caused: `date.today()` reads the *server's* timezone, so the
  watch-log default (computed in UTC) and its own future-guard (compared in local time)
  disagreed for the hour after midnight BST. Green in CI all day, red at 00:07 locally.
  Fixed at the root rather than in the assertion — `purchaseDate` carried the same guard,
  and comparing a person's calendar date against any single timezone's "today" is wrong in
  both directions. New `apps/api/src/clock.py`; the ceiling is now the latest date that is
  today anywhere on Earth (`DECISIONS.md` #53). `04bfd44`.

- **2026-09-08** — **`fix/pytest-local-live-data-collisions` shipped — the 4 pytest
  failures Batch 10 flagged are fixed, not just flagged.** Not a scheduled ledger batch;
  closed out on its own branch per the guardrail against folding a pre-existing red into a
  batch. All four were testing the wrong thing rather than merely lacking test isolation:
  one asserted current runtime state (`pin_hash IS NULL`) for a claim that's actually about
  a migration's static seed data, and was destined to fail forever the instant a real PIN
  was set — which happened, correctly, before this fix existed. Rewritten to check
  migration `002`'s seed columns directly, with the migration now exposing
  `SEEDED_PROFILE_COLUMNS` and asserting its `sa.table()` declaration matches it, so a
  future edit adding `pin_hash` to the seed fails loudly rather than silently. The other
  three assumed an empty `movies`/`collection_items` table when filtering by `section` or
  `watched`, and collided with real production rows (38 in "Top Big Cabinet", 413 in
  "Digital", ~1,843 counting as unwatched) the moment they ran against live Neon rather
  than CI's disposable Postgres. Fixed by giving each fixture a shared, implausible `year`
  and filtering on it too — the same narrow-filter-combination convention an existing,
  passing test in the same file already used, not a new pattern invented for the fix.

  All 338 `apps/api`, 26 `packages/shared` and 57 `apps/web` tests now pass locally against
  live Neon — the first time that's been true since these four tests were written. No
  schema change; migration `002` gained a runtime assertion and a renamed constant only.
  Production serves the merged SHA `959b1ca85058daee7b5c2bde5283cbe99d227423` with
  `db: ok`.

- **2026-09-08** — **Batch 10 shipped — the architecture doc is split and its decisions
  table is reconciled.** `MCU_Architecture_v2.1_FINAL.md` (2,639 lines) is now
  `ARCHITECTURE.md` plus an 18-line stub at the old path pointing to it; `§16 Build Phases`,
  an 86-phase plan that named a model ("Sonnet 4.6") which no longer exists, is replaced by
  a pointer to `docs/phase-batches.md` as the roadmap of record. `§17 Resolved Decisions`
  now carries a status verdict on all 50 rows rather than only its original April
  resolution — split into shipped, superseded (with the `DECISIONS.md` # that did it), or
  not yet built. `session-log.md.txt` is retired; its content was entirely superseded by
  the re-scaffold and already reconstructed into `DECISIONS.md` #1–8.

  **This batch had no written acceptance criteria anywhere in the repo when the session
  started** — every other batch has a `### Batch N` section in `docs/phase-batches.md`
  with a `**Goal:**`/`**Acceptance:**`; Batch 10 had only its one-line ledger title. Wrote
  the criteria into the ledger first, from `REVIEW_PLAN_2026-09-07.md` Part C's own words,
  with the owner's agreement, before touching any doc.

  **Two rows of the reconciliation were corrected by reading the code rather than trusting
  the batch log.** The working draft called Sentry, structlog and correlation-ID binding
  "not confirmed built" because no `STATUS.md`/`DECISIONS.md` entry claims them. All three
  are actually wired — `sentry_sdk` in `apps/api/src/main.py`, `@sentry/react` in
  `apps/web/src/instrument.ts`, and `structlog.contextvars` bound to `correlation_id` in
  `apps/api/src/middleware.py` — found by grepping the source before finalising those two
  rows. Web Vitals is genuinely absent, and stayed marked as such.

  **Four `apps/api` pytest tests fail locally against live Neon data** — real production
  rows they weren't written to tolerate (a real PIN where one asserts `None`, 1,857 real
  movies swamping a section-filter assertion). Confirmed unrelated to this batch: zero diff
  in `apps/`/`packages/` against `main`, and this batch's own CI run — against CI's
  disposable Postgres, not live Neon — was green. Left unfixed per the guardrail against
  folding a pre-existing red into a batch; flagged in "Next" as worth its own `fix/` batch.

  Production serves the merged SHA `d94a6b828d5e96879b5794d4d11bb308ac01803c` with
  `db: ok`. No migration, no hosting or credential change, nothing destructive.

- **2026-09-08** — **Batch 9 shipped, and Group B is complete.** Batches 7, 8 and 9 all
  landed today, which finishes the "build to first deployment" half of the ledger: the
  collection can be written to, it works with the network off, and a first-time user is
  shown a setup flow whose every step does something.

  **The wizard is rebuilt, not repaired.** Batch 3 had removed it because its completion
  flag was a Supabase column that no longer exists (`DECISIONS.md` #27), so there was
  nothing to repair — migration `010` gives it a real one and `ProtectedRoute` gates on it
  again, closing a TODO it has carried since Batch 3.

  **Half the batch definition's premise was wrong.** It says `StepInstallPWA` and
  `StepNotifications` "now have real infrastructure behind them". The install step does —
  Batch 8's manifest and service worker let `beforeinstallprompt` fire, and the new
  `usePwaInstall` catches it, preventing the default because Chromium gives no second
  chance. **The notifications step does not**: no VAPID key, no subscription, no endpoint,
  no `push_subscription` column, and six toggles for features that do not exist yet.
  Dropped rather than ported (`DECISIONS.md` #50); Batch 11 owns bringing it back with
  infrastructure first.

  **A fourth dead step that gotcha 5 never listed** — the catalogue step read
  `d?.meta?.total`, the envelope `DECISIONS.md` #6 deleted, so it rendered a loading
  skeleton for ever. A dead read can hide behind a plausible loading state indefinitely,
  which is why "no step reads a property nothing sets" was worth checking by grep rather
  than by looking.

  Verified by walking the production bundle in a browser: six steps for an admin, resuming
  at step 3 after a reload, and "Skip setup" landing on a usable `/movies`. 249 API tests
  and 83 web/shared tests, zero skips.

- **2026-09-08** — **Batch 8 shipped — the app works with the network off.** Service
  worker, manifest and icon set, an offline banner, and a durable IndexedDB write queue
  with the two states that make it safe: a write the browser never sent is re-sent
  automatically, and one that left without an answer is *read back*, never re-sent.
  Ported from `the-coupon`'s `usePickEditor` — its reasoning transfers even though its
  storage does not, and `DECISIONS.md` #44 records why this one persists where that one
  deliberately does not.

  **Two spec facts did not survive checking.** Phase 13.9 specifies last-write-wins, which
  is the exact opposite of this batch's own acceptance criterion — a queued edit flushed
  on reconnect *is* written last. Replaced by an optimistic-concurrency check (#42).
  Phase 6.5's acceptance names the wanted list, which is Batch 18 and does not exist.

  **Four defects, none visible to any green check, all found by driving the built app
  against an API that could be switched off.** React Query *pauses* mutations when it
  believes the app is offline, so `mutationFn` never ran and the queue inside it was
  unreachable — the offline write path was dead on arrival, behind a spinner that could
  not stop. The same pause stops a query issuing the fetch a service worker exists to
  answer, which is gotcha 19's empty-state lie seen from the other end. A 5xx on a write
  was treated as a refusal and the write discarded. A 5xx on the profile load signed the
  person out and destroyed the session the queued writes were made under. And
  `updated_at` used `NOW()` — transaction time — so the new concurrency token never
  advanced and the guard passed anything, which this batch's own CI tests caught failing
  *open*.

  **Criterion 3 is proved end to end in a browser**: the edit queued while offline, and on
  reconnect the server received exactly the queued body with its `baseUpdatedAt` attached.
  Criteria 1 and 2 need a phone — see gotcha 25.

  337 API tests and 77 web/shared tests in CI, zero skips. 1,857 items untouched.

- **2026-09-08** — **Batch 7 shipped — the collection stops being read-only.** Add, edit,
  soft-delete and restore, with duplicate detection and condition tracking, and an
  `admin_actions` row written in the same transaction as every change. Migration `008`
  creates the audit table, which **did not exist on the new spine** — gotcha 4's
  speculative-table warning running the other way.

  **The batch's headline criterion is proved by destroying a row.** "The audit log
  survives deletion of the target" cannot be shown by a soft delete, and
  `collection_items_soft_delete` rewrites every `DELETE` into one — so the test disables
  the trigger, genuinely deletes the item, and shows the entry still readable through
  `GET /admin/audit`. `target_id` is TEXT with no foreign key (`DECISIONS.md` #5, #38),
  which is where §3.20's schema table is wrong and the decision is right.

  **Three scope calls, all recorded** (`DECISIONS.md` #37–39): writes are admin-only, as
  §3.1's own acceptance criterion requires; optimistic UI is Batch 8's phase 6.5, not
  this batch's, because building rollback here would mean building what Batch 8 explicitly
  rejects; and the trash ships without permanent delete, leaving the one irreversible
  action with §13.5.

  **`UtcDatetime` was written for real** (#40). `AGENTS.md` has specified it since the
  re-scaffold and nothing implemented it — #14's warning found inside our own conventions
  file. It went unnoticed because Batch 7 is the **first batch to put an instant on the
  wire**: Batch 6's `watchedAt` is a `DATE`, which has no offset to get wrong.

  **Two defects that a green gate could not have caught, and how each surfaced.** A
  `field_validator` that never ran for an absent field turned a malformed body into a 500
  — caught in CI by this batch's own test, which is what those tests are for. And every
  list page claiming to be *empty* when its request had merely been paused — caught only
  by opening the pages in a browser, with the build, the types and 34 web tests all green
  (gotcha 19). The second is fixed app-wide and matters most for Batch 8.

  Also fixed on the way: two test clients sharing one actor, because
  `app.dependency_overrides` is global to the app and the admin and viewer fixtures
  overwrote each other — which would have made §3.1's "viewer immediately sees it" look
  tested without being tested.

  331 tests in CI, zero skips. 1,857 collection items untouched.

- **2026-09-08** — **Batch 6 shipped — the app finally answers "where is this disc?"**
  §6.2's promise has been in the architecture doc since April and unimplementable until
  Batch 4 added the columns; this batch is the first thing to query them. `section`,
  `shelf`, `decadeFrom`, `decadeTo`, `minRating` and `watched` on `GET /movies`, a
  facet endpoint serving the vocabularies from the data, and location on all three
  collection views. **Front 2nd shelf answers in 20 ms** including network — 0.4 ms
  execution on `ix_collection_items_section_shelf_live`, the index Batch 4 created for
  exactly this query and which nothing had used until today.

  **Two premises in the batch definition did not survive checking, and both were settled
  with the owner before any code was written.** "Watched status" was listed as a facet
  beside decade and rating as though the three cost the same. They did not: §3.7 designs
  `watch_log` and §6.5 lists its endpoints, but **no phase in §16 creates it** — checked
  against all 96 phase headings — while Batch 37 sat defined as "inert until `watch_log`
  has ~a year of history", waiting on a table nothing brought into existence. Built here
  (#35), which moved the batch 🟢 → 🟡 and unblocked Batch 37 as a side effect. And the
  124 unsectioned rows, which `STATUS.md` had flagged as this batch's open question,
  turned out to be four named cabinets covering 122 of them — now in the vocabulary and
  backfilled (#34), taking sectioned coverage from 1,733 to **1,855 of 1,857**.

  **Two real defects found on the way, neither of them in this batch's own code.** The
  shelf parser matched any bare digit, so `Top small cabinet (Arrow 4 Film Noir Classics
  Vol 2)` had been stored as shelf "4th" for four live discs — rows this batch's own
  shelf filter would have wrongly returned. `Back 6th Shelf (Arrow 4 Film Noir Classics
  Vol 1)` escaped only because `re.search` returns the leftmost match (#36, gotcha 17).
  And the year filter in `FilterBar` was generated from 1970 forward, so **517 of the
  1,085 dated films — 47.6% — could not be selected at all**; the decade range replaces
  it with bounds taken from the data.

  **The gate was green on the first CI run**, 296 API tests against Postgres 17 with zero
  skips, all five jobs passing. Because migration `007` writes to 126 live rows, close-out
  stopped for owner sign-off rather than deploying itself, per the protocol. Before asking,
  `007`'s own `WHERE` clauses were run as read-only `SELECT`s against live Neon and matched
  the parser exactly; the post-deploy counts then matched that prediction row for row —
  38 + 38 + 26 + 20 sectioned, 4 shelves cleared, 2 correctly left alone, 1,857 items and
  1,843 films unchanged. **CI cannot prove a backfill, because its migration job runs on an
  empty schema** (gotcha 18).

  **One acceptance criterion is proved indirectly, exactly as in Batch 5, and for a
  narrower reason.** The browse UI is covered by CI contract tests, by direct measurement
  against the production database, and by booting the built bundle with zero console
  errors — but **not by driving the production UI**, because that needs a PIN and an agent
  must not type one. Craig's PIN is now set, so this is a one-minute owner check; Mark's is
  still `NULL`.

- **2026-09-08** — **Batch 5 shipped — the collection is browsable, searchable, and every
  unidentified film can be settled from its own page.** List, detail, copies and tsvector
  search ship with camelCase DTOs and shared zod schemas the web app genuinely `.parse()`s
  — zero `as Promise<T>` casts. Migration `005` completes the search document that `003`
  deliberately left half-built, adding credited names and genres and re-firing when credits
  change, so a film identified in the app becomes searchable immediately.

  **The identify flow replaces the review CSV** (#33). `GET /movies/{id}/candidates` runs
  the existing `MatchingEngine` live against the stored spreadsheet title and returns the
  top five with posters, years and overviews; `POST /movies/{id}/identify` fills the §3.2
  columns and the credits. It needed no schema change — the unidentified set is exactly the
  757 movies with `tmdb_id IS NULL`, and all 757 still carry the title to search on. Either
  user can identify a film, and the same picker corrects the four wrong-sibling matches, so
  the matching ranking was left alone.

  **Measured against production, not asserted.** Search median **20 ms** and a 60-item list
  page **23 ms** against live Neon with network included — the <150 ms budget was never
  close. Zero of 1,843 movies are missing a `search_vector`. The metadata-only criterion was
  proved with **"Kubrick": 8 films returned, and the word appears in no title in the
  collection**, so the hit can only come from fetched credits; genres index too. Production
  serves the merged SHA with `db: ok` at migration 005.

  **Two failures on the way.** CI went red on run `34227781888` — the `search_vector`
  trigger could not expand `genres` when SQLAlchemy had serialised Python `None` as the
  JSON scalar `null`, which is not SQL NULL and cannot be treated as an array; `005` now
  guards on `jsonb_typeof(...) = 'array'`. Run `34228015029` was then green with 269 API
  tests and no skips, including the 16 derived-trigger tests. During close-out the local
  verification script also failed twice on its own errors — a `release_date` column that
  does not exist (it is `year`) and psycopg2 reading `%` in an `ILIKE` pattern as a
  parameter placeholder. Neither touched the app.

  **One acceptance criterion is proved indirectly, and it is worth naming.** Both profiles
  still have `pin_hash = NULL`, so nobody can log in and every read route requires
  `CurrentUser`. The deployed app boots and renders its login page with no console errors,
  but the browse grid, detail page and picker were verified by CI integration tests and by
  direct database measurement — **not** by driving the production UI. The 60fps figure in
  particular rests on all three views being virtualised with `@tanstack/react-virtual`,
  not on a frame-rate measurement. Setting the PINs closes it.

- **2026-09-08** — **Batch 4 shipped — 1,857 discs are in the database, with structured
  location, for the first time.** Migration `003` lands the §3.4 domain schema and `004`
  two fixes the live import forced. All four acceptance criteria proved against the live
  database: 1,857 `collection_items` with 1,857 distinct `import_source_row` and zero
  errors; 1,733 sectioned with zero values outside the §3.4 vocabulary; the dry run
  diffed against `matching_eval.csv`; and **14 derived-field trigger tests running in CI
  with zero skips** — the criterion Batches 2 and 3 could only defer. 1,843 movies and
  45,144 credits alongside, with `search_vector` and `best_format_owned` populated by
  trigger over real rows. 764 rows are catalogued but not yet identified and sit in a
  review queue that lists every tied candidate.

  Three decisions were taken with the owner before or during the work: §3.4's schema over
  the April one, which forced the trigger tests to be re-authored rather than resumed
  (#28); the collection is **1,857 items, not 1,866** — nine trailing spreadsheet rows are
  blank, so the number was wrong everywhere it appeared, Phase 1.5's acceptance included
  (#29); and an ambiguous match is catalogued but not enriched, which meant changing the
  matching engine against this batch's own "port `matching/` unchanged" instruction (#31).

  **Four defects, three of them invisible to a green gate.** Criterion 3 stopped the batch
  for a day when a fresh matching run against `matching_eval.csv` showed `Amistad`
  resolving to `Friendship (2023)`; a full scan found 652 rows (35%) whose film was chosen
  by TMDB popularity alone. Then the live write found three more that no test could have
  caught: the importer could not connect to any hosted database, a 300-character
  `character_name` overflowed its column and rolled back a whole item, and an idempotency
  key on item contents collapsed "French Connection" and "French Connection 2" into one
  disc. Gotcha 16 records the general lesson; #32 records the fixes.

- **2026-09-07** — **Batch 3 shipped — Craig and Mark can log in; nobody else can.**
  `main` `e89a9c6`, CI green, production serving that SHA and the deployed web app rendering
  for the first time. bcrypt PINs, HS256 access/refresh on separate secrets, rotated
  SHA-256-hashed refresh rows, durable Postgres lockout proved by 9 CI tests that dispose the
  engine between writes. Migration `002` seeds both profiles with `pin_hash = NULL`; the first
  PIN is set by `src/scripts/set_pin.py` from a hidden prompt (`DECISIONS.md` #25). Removed
  the sign-up page outright and the onboarding wizard with it (#27), and closed a hole where
  `VITE_SKIP_AUTH` was honoured in production builds (#26). Two CI failures on the way, both
  migration defects a green local gate could not see: the `user_role` enum created twice, then
  the seeded role sent as varchar to an enum column.
- **2026-09-07** — **Batch 2 shipped — the app is deployed for the first time.**
  `main` `d4190ac` pushed, CI green. Railway `api` live on the root Dockerfile; migrate-on-boot
  applied `001` to Neon; `/api/v1/health` returns the merged commit SHA and `/ready` reports
  `db: ok`. Public API `api-production-a8fe.up.railway.app`. Two failures on the way: the
  first deploy built `0419cb2` and failed on a missing Dockerfile because `main` had been
  merged locally but never pushed; the generated domain then returned 502 until repointed
  from port 8000 to Railway's injected 8080. Vercel git-connected; web ships without auth
  env vars and white-screens until Batch 3 — verified in a browser, the console throws the
  expected `Missing VITE_SUPABASE_URL` and nothing else. A third failure found during
  verification: `FRONTEND_ORIGIN` pointed at `mcu-app.vercel.app`, an unrelated third
  party's app, because Vercel had actually assigned `mcu-app-fawn.vercel.app`. CORS now
  allows the real origin and returns 400 to the stranger (`DECISIONS.md` #20–#23).
- **2026-09-07** — Batch 2 implementation prepared for review on
  `feat/2-deploy-spine-ci`: dedicated Neon Postgres connection verified; migrate-on-boot
  Dockerfile, Railway IaC, Vercel configuration, reversible `001`, commit/readiness health
  checks, Postgres-backed CI and hashed dependency gates added. Fresh-lock and disposable-
  Postgres verification green. No commit, project creation or deployment yet; those wait
  for explicit `/phase-closeout 2`.
- **2026-09-07** — Batch 1 New spine foundations shipped via PR #1 (`0910428`, `15ed148`). Async SQLAlchemy/asyncpg, fail-closed config, `models/` mixins, health-only API, async pytest harness and the first shared Zod response schema are on `main`. CI green after fixing a test that assumed pytest always started at the repo root.
- **2026-09-07** — Cross-project review complete, Parts A–E. Merged to `main` as `9084ec6`, CI green (API + Web). 38 batches in 11 groups defined; owner reinstated all Part D drops except 9.6 (`DECISIONS.md` #16). Repo confirmed **private**, which lowers the urgency on the PAT still in history.
- **2026-05-05** — Phase 3.1 Add to Collection (manual). Commits `13d5f6b`, `fe7e895`. CI green. Close-out docs were written but never committed until today.
- **2026-04-30** — Phases 2.7, 2.8 (movie detail tabs; onboarding wizard).
- **2026-04-29** — Phases 2.2–2.6 (frontend shell, collection grid, view toggle, search, detail page).
- **2026-04-25 → 04-27** — Stage 1 (Alembic schema, TMDB client, spreadsheet parser, matching engine, bulk import, derived-field triggers). The real collection import landed 2026-04-27.
- **2026-04-20 → 04-24** — Stage 0 (scaffolding, backend, frontend, Supabase auth, CI, error tracking).
