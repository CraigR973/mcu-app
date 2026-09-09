# Owner actions — things only Craig can do

Everything here is blocked on a person, not on an agent: a credential, a live run against
someone else's website, a device, or a choice that isn't an agent's to make. Agents should
**read this and stop**, not work around anything on it.

Tick a box when it's done and say so in `STATUS.md`'s Log. Last reviewed **2026-09-09**,
after a session that cleared four of the nine items. *Numbers changed at that review; the
old ones are noted in brackets so an earlier conversation still maps onto this file.*

---

## ⛔ Blocking the batch queue

### 1. Finish the live scraper acceptance run — Group F's checkpoint *(was 1)*

**The setup is done. The proof is not.**

- [x] **Add missing defaults** and **Apply these selectors** — pressed 2026-09-09. Arrow's
      `base_url` is now the UK `arrowfilms.com`, and exactly the five supported shops are
      enabled
- [x] Films on the wanted list — *Misery*, *Nope* and *Project Hail Mary*, all wanting 4K
- [x] A real run saved real rows — **2 `price_checks` rows exist**
- [ ] **≥ 1 row per working scraper**, which is what phase 5.3 actually asks for

What the run produced, and it is worth reading before repeating it:

| Shop | Result |
|---|---|
| **Arrow Video** | ✅ *Misery Limited Edition 4K UHD*, **£25.00**, exact 4K match, no substitution |
| **Zavvi** | ⚠️ *Nope* at £8.99 — the **Blu-ray**, because Zavvi has no 4K *Nope* at all. Correct behaviour under `DECISIONS.md` #102, reported as `substitutedFormat` |
| 101 Films · Powerhouse · Second Sight | "not stocked" — correct: none of them carries a Stephen King adaptation, a Universal blockbuster or an unreleased 2026 title |

**Add a title each boutique label actually sells before running again**, or the criterion
cannot be met: *Deep Red* for Arrow, *Don't Look Now* or *Near Dark* for Second Sight,
*Sorcerer* or a Columbia Noir for Powerhouse, something from 101's Black Label. Then one
unhurried run gives all five shops a fair test in a single pass.

**Space the runs out.** Zavvi succeeded at 17:06 and failed at 17:08 with "no price found"
having worked minutes earlier — that is throttling, not a broken selector. **It still carries
2 of the 3 strikes that auto-disable a shop.**

*A trap that already fired, now fixed.* The first run counted "this shop does not stock this
film" as a scraper failure and **switched 101 Films, Powerhouse and Second Sight off** after
three of them. They were re-enabled and the accounting was fixed the same day
(`DECISIONS.md` #107) — a shop that answers honestly no longer accrues a strike. Zavvi's
throttling failures still do, correctly.

**Where:** <https://mcu-app-fawn.vercel.app> → Retailers. Or the API directly:
`POST /api/v1/scrapers/test`, then `POST /api/v1/scrapers/run?dryRun=false`.

**Four shops stay permanently unverified — do not test them.** HMV and CEX disallow the
search routes this job needs; Amazon UK blocks automated access and its official API is
unsuitable for a private app this size; Blu-ray.com is a catalogue whose prices belong to
third parties (`DECISIONS.md` #91). **eBay takes the general-market role** once item 2 lands.

**Unblocks:** Batch 20 (price scraping + drop alerts) → Batch 21 (price history charts, which
then needs 7 real days of wall-clock data) → Group G (22 deals feed, 23 specs scraper).

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
| **VAPID keys** *(was 2)* | Generated and set in Railway 2026-09-09. Verified: 87-char public key, 43-char private key, both base64url, **the pair mathematically matches**, and `VAPID_SUBJECT` carries a `mailto:`. **The names are now fixed by what is in Railway** — Batch 11 must read `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`. `VITE_VAPID_PUBLIC_KEY` on Vercel is deliberately **not** set: it is a build-time Vite variable that does nothing until Batch 11 ships code that reads it. **Unblocked Batch 11.** |
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
