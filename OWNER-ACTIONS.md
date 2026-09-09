# Owner actions — things only Craig can do

Everything here is blocked on a person, not on an agent: a credential, a live run against
someone else's website, a device, or a choice that isn't an agent's to make. Agents should
**read this and stop**, not work around anything on it.

Tick a box when it's done and say so in `STATUS.md`'s Log. Last reviewed **2026-09-09**,
after a session that cleared four of the nine items. *Numbers changed at that review; the
old ones are noted in brackets so an earlier conversation still maps onto this file.*

---

## ⛔ Blocking the batch queue

### 1. Settle Batch 20's remaining two steps *(was 1 — the scraper run itself is **done**)*

**The acceptance run is complete.** 2026-09-09, 21:55–21:56: all five shops `success`, zero
failures, six new `price_checks` rows, one or more per shop (`DECISIONS.md` #111). Group F's
checkpoint is cleared and Batch 20 is open.

Two steps remain, and both are yours because an agent must not take them:

- [ ] **Wire the overnight schedule.** Phase 5.5 wants *"first overnight run completes"*. A
      Railway cron is a hosting change (`DECISIONS.md` #60), and an in-process scheduler would
      be worse than nothing — it runs once per container, so scaling to two would silently
      double the scraping. Batch 20 leaves the job and its endpoint ready so this is one
      console action.
- [ ] **And while you are in there, a second cron for reminders.** Batch 11 shipped
      `POST /api/v1/notifications/run-reminders`, which is *the whole scheduler* for sale
      seasons, upcoming releases and overdue loans — for the same #60 reason, nothing runs
      it on a timer inside the process. Daily is right; the endpoint is idempotent, so a
      double fire sends nothing twice. Until this exists, every reminder in the app waits
      for someone to press a button.
- [ ] **Receive a price-drop push on a real device.** Phase 5.6's acceptance. **Batch 11's
      push has now shipped** and production reports `push: configured`, so what remains is a
      device: open the app, Notifications, "Turn on for this device".

**5.5's criterion was corrected before the batch was built** (`DECISIONS.md` #112). As written
it expected rows ≈ wanted items × enabled retailers; the run proved that wrong — 6 rows from 35
pairs, with all 29 gaps correct, because no shop stocks every film.

### 2. eBay production API application *(was 4)*

- [x] Applied 2026-09-09
- [ ] Approval — eBay said at least one business day

**Unblocks:** Group I — Batch 28 (eBay integration) → Batch 29 (format upgrade + sale
tracking). **And Batch 24**, which is not obvious from the ledger: `DECISIONS.md` #16 fixes
that batch's UPC→title chain as *cached mapping → eBay Browse keyword search → manual
fallback*, so the barcode lookup depends on the same approval.

### 3. Two design choices nobody has made

- [ ] **Batch 25 — how big may a photo be?** Storage is settled as **Neon** (owner,
      2026-09-09), which means photo bytes in Postgres rather than an object store. The
      spec's raw sizing — 5 photos × 5 MB × 1,857 items ≈ 46 GB — is not sensible in any
      Postgres; the database is 35 MB today. An agent proposed server-side resize to
      ~300 KB per photo (worst case ~2.8 GB, realistic case under 200 MB) but **that has not
      been confirmed**, so it is recorded here rather than acted on.
- [ ] **Batch 35 — what provides realtime?** The design says Supabase Realtime and there is
      no Supabase project any more (`DECISIONS.md` #17). An agent proposed Postgres
      `LISTEN`/`NOTIFY` plus SSE over the existing FastAPI service — no new vendor, no new
      credential — but **that has not been confirmed either.**

Neither is a credential, so an agent *could* take them; both are recorded as owner choices
because they set a shape that is annoying to reverse once photos or sessions exist.

---

## Deprioritised by owner decision — not blocking

### 4. Google + Microsoft OAuth app registration *(was 5)* — **deprioritised 2026-09-09**

Group K (Batch 33 email accounts + OAuth → Batch 34 parsers + scanning) is off the queue
until this is wanted. The batches stay in the ledger; nothing is dropped.

### 5. Subscribe the `.ics` feed in Apple or Google Calendar *(was 6)*

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

### 6. Revoke the April PAT at GitHub *(was 7)*

- [ ] Revoke it

Classic PAT, 40 chars, `ghp_3gLc…`, committed **in full** in `0bfb672` (2026-04-25) and
referenced truncated in `4768da8`. It is dead (returns 401) but was never formally revoked.
**A history rewrite is not recommended** — the repo is private and the token is already
invalid, so a rewrite would cost more than it buys.

### 7. `VITE_API_URL` for Vercel preview deploys *(was 9)*

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
