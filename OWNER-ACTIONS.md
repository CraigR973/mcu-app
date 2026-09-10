# Owner actions — things only Craig can do

Everything here is blocked on a person, not on an agent: a credential, a live run against
someone else's website, a device, or a choice that isn't an agent's to make. Agents should
**read this and stop**, not work around anything on it.

Tick a box when it's done and say so in `STATUS.md`'s Log. Last reviewed **2026-09-09**,
after a session that cleared four of the nine items. *Numbers changed at that review; the
old ones are noted in brackets so an earlier conversation still maps onto this file.*

---

## ⛔ Blocking the batch queue

### 1. Two crons and one device — everything Batches 11 and 20 left for you

**Batch 20 shipped on 2026-09-10 and Group F is complete.** The scraper acceptance run was
done on 2026-09-09 (`DECISIONS.md` #111); the code that runs nightly, alerts on price drops
and rolls up old checks is now deployed.

What is left is a single Railway console visit and one tap on a phone. Both are yours because
an agent must not take them:

**Read this first — what changed on 2026-09-10.** Both of these used to say "point a cron
at this endpoint", and **that was not possible**: both endpoints are admin-authed and an
access token lives 24 hours, so a cron container had no way to call either one. `DECISIONS.md`
#119. Each is now a command, and **both services are already declared in
`.railway/railway.ts`** — so this is no longer a click-through. It is two commands:

```
PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" "$HOME/.nvm/versions/node/v20.20.2/bin/railway" config plan
```
```
PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" "$HOME/.nvm/versions/node/v20.20.2/bin/railway" config apply
```

**Both halves of that line are load-bearing** and neither is obvious: Node 22 because the
IaC engine needs it, and the CLI's **full path** because the CLI lives in Node *20*'s bin,
so putting 22 first on `PATH` makes `railway` itself vanish. See `.railway/README.md`.

`plan` is read-only; run it first and **check the last number on the `Plan:` line**. It
should read **`2 to add, 1 to change, 0 to destroy`**. If anything is to be destroyed, stop
— that is `DECISIONS.md` #124, which is how applying this file would once have deleted
`TMDB_READ_TOKEN` and `ANTHROPIC_API_KEY`.

`apply` is a hosting change and therefore yours, not an agent's.

- [ ] **Wire the overnight schedule.** Phase 5.5 wants *"first overnight run completes"*.
      A Railway cron is still a hosting change (`DECISIONS.md` #60), and an in-process
      scheduler would still be worse than nothing — it runs once per container, so scaling
      to two would silently double the scraping. The command is:

      ```
      python -m src.scripts.daily_scrape
      ```

      It scrapes, alerts, delivers and rolls up in one pass, and **exits non-zero if a
      retailer failed**, naming the shop and the reason — so a bad night shows up in
      Railway rather than looking like a good one. `scrape_runs` is empty today, which is
      the honest record that nothing has run it yet — check it the morning after, and
      `/retailers` renders the same thing with the criterion applied. Something around
      **03:00 UTC** is sensible. `POST /api/v1/scrapers/daily` still exists and still does
      the same work when you want to trigger it by hand from the app.
- [ ] **And while you are in there, a second cron for reminders.** This is *the whole
      scheduler* for sale seasons, upcoming releases and overdue loans — for the same #60
      reason, nothing runs it on a timer inside the process. The command is:

      ```
      python -m src.scripts.run_reminders
      ```

      Daily is right, **08:00 UTC** or so, and it is idempotent: every sender checks its
      `notified` flag before setting it and the outbox deduplicates, so a double fire sends
      nothing twice. If a day is missed, `--as-of YYYY-MM-DD` catches it up. Until this
      exists, every reminder in the app waits for someone to press a button.
- [ ] **Receive a price-drop push on a real device.** Phase 5.6's acceptance, and the last
      unmet part of Batch 20. Everything behind it is deployed: push reports `configured`,
      the alert fires when a scrape finds a price at or below a want's `max_price`, and the
      service worker shows it. What is missing is a subscribed device.

      **The exact sequence, all of it in the app:**
      1. Settings → Notifications → name the device → **"Turn on for this device"**, then
         press **Test** on the row that appears. If no notification arrives, stop — nothing
         after this can work either.
      2. `/wanted` → **Cross of Iron** → **"Set a limit"** → `14` → Save. It is £12.99 at
         Zavvi and that check was never alerted, so the next run reads as a genuine drop.
      3. `/retailers` → **The nightly run** → **"Run it now"**. That scrapes, alerts and
         delivers in one pass.

      **"Set a limit" only exists as of 2026-09-10** (`DECISIONS.md` #123). Until then the
      maximum price could be set on the add form and nowhere else, so there was no way to
      put a limit on a want you already had — and the same change fixed "Stop looking"
      silently wiping the format, edition, limit and notes of whatever it toggled.

      **Doing step 1 on a second device also closes §6.2**, Batch 11's remaining criterion.

**5.5's criterion was corrected before the batch was built** (`DECISIONS.md` #112). As written
it expected rows ≈ wanted items × enabled retailers; the run proved that wrong — 6 rows from 35
pairs, with all 29 gaps correct, because no shop stocks every film.

### 2. Ask the assistant one question *(new — Batch 30, 2026-09-10)*

- [ ] **Open Assistant in the sidebar and ask it anything.** That is Phase 9.1's whole
      acceptance: *"simple text prompt returns a response; tokens logged"*. The answer
      renders its own token count and cost underneath it, and the log row is written either
      way.

It is yours rather than an agent's for one reason: **it spends real money on your key**,
which lives only in Railway. `docs/phase-batches.md` says one call is enough and *"do not
loop"* — a test suite is a loop, so the suite stubs the transport. Production already
reports `ai: configured` on `/api/v1/health/ready`, so the key is genuinely there; what is
unproven is only that a real round trip works.

Your caps are on the same page and start at **50 messages and $2 a day** (owner,
2026-09-09). Both are editable, and a message cap of 0 turns the assistant off for you.

### 3. Say something to the assistant *(new — Batch 32, 2026-09-10)*

- [ ] **Tap the microphone in the chat, say a question, and check what appears in the box.**
      That is Phase 9.5's acceptance: *"tapping mic, speaking a query, sends correct
      transcription"*.

Dictation deliberately **fills the input rather than sending it** — the engine mishears, and
reading it back before pressing send is both the safety net and the only way "correct
transcription" is a thing anyone can confirm. Nothing is uploaded by the app; the browser's
own engine does the listening. It works in Chrome, Edge and Safari, and **not in Firefox**,
where the button is hidden rather than shown dead.

### 4. Run the Blu-ray.com spec fetch *(new — Batch 23, 2026-09-10)*

- [x] **Fetch specs for ten discs from ten exact Blu-ray.com release URLs.** **Done
      2026-09-10.** You accepted `#110`'s risk and asked for it to be run for you
      (`DECISIONS.md` #121). Phase 3.7's acceptance in full — *"scraper run against 10
      known **live** URLs persists correct specs to the matching `collection_items` rows;
      row counts verified — not just unit tests against fixture HTML"* — is met: **10 rows
      of 1,857, from 10 distinct release URLs**, no halt, and no currency symbol anywhere
      in a derived field.

      **The run found that the scraper did not work at all**, which is the reason the
      criterion insists on live URLs. The first pass fetched all ten pages and extracted
      **nothing**: the parser looked for `<strong>`-labelled rows and the site serves
      `<span class="subheading">` sections. `test_specs.py`'s fixture had been *invented to
      match the parser*, so eleven tests passed against markup the site has never served.
      Then the fix's own re-run stored **one** audio track for Blade Runner 2049 where the
      page lists six, because that page wraps its tracks in a `<span>` and Fight Club's does
      not. Both fixtures are captured pages now, and a test asserts they stay captured.
      `DECISIONS.md` #122.

      Nothing was lost while it was broken: `apply_specs` checks `is_empty` before touching
      a row, so a parser that stops matching the site writes nothing rather than blanking
      1,857 rows.

      *What you may want to look at:* the ten pages were matched by **title and format**,
      not by edition or region — `Kick-Ass` and `Up` came back Region A, the rest region
      free. Every row records `specs_source_url`, so a wrong edition is visible rather than
      silently merged, and `DELETE /api/v1/specs` removes the lot.

**Why an agent did not run it until you said so.** `DECISIONS.md` #110 is explicit that this
is a *risk acceptance*, not a permission: the site's Legal Notices prohibit automated reuse, and #108's
earlier claim that absence from `robots.txt` made it allowed was wrong. Accepting a stated
legal risk on your own behalf is yours to do; `docs/agent-commands/group-start.md` also puts
live third-party runs in your hands, which is how Batch 19's checkpoint worked.

**#110's bounds are enforced by the code, not left to whoever runs it.** A URL that is not
an exact release page is a 422 before anything leaves the building; requests go one at a
time, five seconds apart, with an honest user agent and no redirect following; a `403`,
`429` or `451` **halts the whole integration** and abandons the rest of the batch. That halt
is a database row and **nothing in the application can clear it** — resuming needs a
`DECISIONS.md` entry and a deliberate database change, which is what "requires a new owner
decision" has to mean.

**How to do it.** Gather ten release URLs from Blu-ray.com's browse pages (never its search
— those routes are refused), then `POST /api/v1/specs/fetch` with
`{"targets": [{"collectionItemId": ..., "sourceUrl": ...}, ...]}`. The response **lists
every URL fetched**, which the ledger asks for in the close-out. `GET /api/v1/specs/state`
shows the running count and whether anything halted it.

**And it is reversible.** `DELETE /api/v1/specs` removes every field derived from that site
— that is what `specs_source_url` and `specs_fetched_at_utc` on each row are for, and it
leaves any hand-typed spec alone.

### 5. eBay production API application *(was 4)*

- [x] Applied 2026-09-09
- [ ] Approval — eBay said at least one business day

**Unblocks:** Group I — Batch 28 (eBay integration) → Batch 29 (format upgrade + sale
tracking). **And Batch 24**, which is not obvious from the ledger: `DECISIONS.md` #16 fixes
that batch's UPC→title chain as *cached mapping → eBay Browse keyword search → manual
fallback*, so the barcode lookup depends on the same approval.

### 6. One design choice left

- [x] **Batch 25 — how big may a photo be? 300 KB — confirmed by owner 2026-09-10**
      (`DECISIONS.md` #120). *The reasoning below is kept because it explains why the
      number is a setting rather than a shape.*
      Storage is settled as **Neon** (owner, 2026-09-09) — photo bytes in Postgres. The
      spec's raw sizing, 5 photos × 5 MB × 1,857 items ≈ 46 GB, is not sensible in a
      database that measured **36 MB** on 2026-09-10.

      **Two in-repo docs disagreed about whether the number was confirmed**, and Batch 25
      had to pick one: this file said "proposed, not confirmed", while `STATUS.md`'s run
      plan and `docs/phase-batches.md` both listed *"~300 KB after server-side resize
      (owner, 2026-09-09)"* under "settled inputs, so no batch has to ask again". There is
      no `DECISIONS.md` entry either way. The batch shipped at **300 KB** — the number both
      docs name — and made the disagreement cheap instead of arguing it: the target is the
      `PHOTO_TARGET_KB` setting, so changing it is an environment variable and a re-upload,
      **not a migration**, and the database's own CHECK sits far above it so a larger value
      needs no schema change either. A phone's 4032×3024 photo currently stores at ~240 KB.

      Changing it later is still one variable — `PHOTO_TARGET_KB` — and a re-upload.
- [x] **Batch 35 — what provides realtime?** ~~The design says Supabase Realtime and there
      is no Supabase project any more.~~ **Settled and shipped.** `DECISIONS.md` #113 records
      this as an owner decision taken on 2026-09-09 — Postgres `LISTEN`/`NOTIFY` plus SSE, no
      new vendor and no new credential — and Batch 35 built it on 2026-09-10. *This item was
      already stale when it was read: #113 answered it the day before.*

Neither is a credential, so an agent *could* take them; both were recorded as owner choices
because they set a shape that is annoying to reverse once photos or sessions exist. **Both are
now resolved** — the realtime one by `DECISIONS.md` #113, and the photo one by making the
number a setting rather than a shape, which is what stops it being annoying to reverse.

---

## Deprioritised by owner decision — not blocking

### 7. Google + Microsoft OAuth app registration — **deprioritised 2026-09-09**

Group K (Batch 33 email accounts + OAuth → Batch 34 parsers + scanning) is off the queue
until this is wanted. The batches stay in the ledger; nothing is dropped.

### 8. Subscribe the `.ics` feed in Apple or Google Calendar

Batch 17 shipped and the feed's bytes are verified against RFC 5545. The in-app release
calendar is the primary experience; external subscription is an optional convenience. Do this
only if Craig or Mark wants it.

**The URL is a capability URL** — anyone holding it can read the feed. It's `noindex,
nofollow` and the token is rotatable, but treat it like a password.

---

## Done since the last review

| | What happened |
|---|---|
| **VAPID keys** *(was 2)* | Generated and set in Railway 2026-09-09. Verified: 87-char public key, 43-char private key, both base64url, **the pair mathematically matches**, and `VAPID_SUBJECT` carries a `mailto:`. **The names are now fixed by what is in Railway** — Batch 11 must read `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`. **`VITE_VAPID_PUBLIC_KEY` is not needed at all and should not be set** — Batch 11 serves the public key from the API, derived from the private half, so the two cannot drift and no Vercel change is required (`DECISIONS.md` #114). **Unblocked Batch 11, which shipped 2026-09-10** and whose deployment reports `push: configured` on `/api/v1/health/ready`. |
| **`ANTHROPIC_API_KEY`** *(was 3)* | Set in Railway 2026-09-09. **Unblocked Group J** (30 → 31), and Batch 32 behind them. |
| **Mark's PIN** *(was 8)* | Set 2026-09-09. He can sign in, which is what two-user acceptance criteria need — Batch 35's movie night and Batch 38's login flow. |
| **`TMDB_READ_TOKEN`** *(new — was never on this list)* | **It had never been set in Railway at all.** Every TMDB-backed feature in the deployed app was returning a 502 reading *"TMDB search is temporarily unavailable"* — the identify flow for 757 unidentified films, the add-form search, watch providers, recommendations, calendar refresh and completion-set rebuilds. Nothing was temporary about it: `config.py` defaults the token to `""`, so the API booted happily and sent `Authorization: Bearer ` on every call. Set 2026-09-09. |

**Why the TMDB one is worth remembering.** CI cannot catch it — it is configuration, not
code, and `AGENTS.md` already says the gate proves the code and not the infrastructure around
it. It was invisible until someone tried to add a film to the wanted list. Anything that
lives only in a Railway variable has no test.

---

## Housekeeping — not blocking anything

### 9. Revoke the April PAT at GitHub

- [ ] Revoke it

Classic PAT, 40 chars, `ghp_3gLc…`, committed **in full** in `0bfb672` (2026-04-25) and
referenced truncated in `4768da8`. It is dead (returns 401) but was never formally revoked.
**A history rewrite is not recommended** — the repo is private and the token is already
invalid, so a rewrite would cost more than it buys.

### 10. `VITE_API_URL` for Vercel preview deploys

- [ ] Add it in the Vercel dashboard — **only if you want preview deploys to work**

It's currently set for Production only. Production is fine; previews would white-screen.

---

## Consequences worth knowing

**Batch 32 (voice input) is not independent, despite the ledger calling it "solo".** Phase
9.5's acceptance is *"tapping mic, speaking a query, **sends correct transcription**"* — to
the chat input, which doesn't exist until Batch 31. It is grouped as solo because it shares no
*files* with Group J, not because the feature stands alone. Now unblocked at the credential
level by `ANTHROPIC_API_KEY`, but still gated on Batch 31 existing.

**Batch 38 (E2E suite) can only cover 4 of its 7 flows today.** Phase 13.10's acceptance names
login, import, search, add-via-scan, price alert, chat session and movie night. Login is newly
testable now Mark has a PIN; scan is Batch 24, price alert is Batch 20, chat is Batch 31 and
movie night is Batch 35.

**Batch 26 (shelf QR) was dropped**, 2026-09-09, `DECISIONS.md` #109 — Batch 6's location
filter already answers the question printed codes existed for.

**No queued batch can meet its acceptance criteria in full today.** That line used to name
Batch 36 as the exception; Batch 36 shipped on 2026-09-09.
