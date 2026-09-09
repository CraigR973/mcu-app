# Owner actions — things only Craig can do

Everything here is blocked on a person, not on an agent: a credential, a live run against
someone else's website, a device, or a choice that isn't an agent's to make. Agents should
**read this and stop**, not work around anything on it.

Tick a box when it's done and say so in `STATUS.md`'s Log. Last reviewed **2026-09-09**.

---

## ⛔ Blocking the batch queue

### 1. Live scraper acceptance runs — Group F's formal checkpoint

- [ ] Press **Add missing defaults** on Retailers, then **Apply these selectors**
- [ ] Test the 5 supported retailers, one at a time, before enabling any
- [ ] Put at least one real film on the wanted list — the *Add a film* panel does this now
- [ ] **Preview live run**, then **Run and save prices**, and confirm ≥ 1 `price_checks` row
      per working scraper

**Where:** <https://mcu-app-fawn.vercel.app> → Retailers. Every step above is now a button on
that page. Or the API directly: `POST /api/v1/retailers/seed`,
`POST /api/v1/scrapers/apply-built-ins`, `POST /api/v1/scrapers/test`, then
`POST /api/v1/scrapers/run?dryRun=false`.

**Which shops this is now about — five, not six.** Live page-shape checks on 2026-09-09
settled the rest (`DECISIONS.md` #91):

| Supported — test these | Permanently unverified — do not test |
|---|---|
| Zavvi, Arrow (UK), 101 Films, Second Sight, Powerhouse/Indicator | HMV and CEX (search routes disallowed), Amazon UK (blocks automated access; its official API is unsuitable here), Blu-ray.com (a catalogue, third-party prices) |

The four on the right stay listed in the app, marked unverified with the reason, so nobody
re-derives the same four answers. **eBay takes the general-market role** once item 4's
application is approved. Arrow's seeded URL was the *US* storefront and returned USD, which
the shape guard rejected — **Apply these selectors** corrects it to `arrowfilms.com`.

**What "test" means here:** a green tick means *"this looks like a real price for this
film"*, not *"the page loaded"*. That distinction is the whole reason §5.4 exists. A
selector can still fail on a layout change; the tool prints the node it read and why it
rejected the result, which is usually enough to correct the CSS in *Retailers → edit*.

**Unblocks:** Batch 20 (price scraping + drop alerts) → Batch 21 (price history charts, which
then needs 7 real days of wall-clock data) → Group G (22 deals feed, 23 specs scraper).

### 2. VAPID keys for push notifications

- [ ] Generate a VAPID key pair
- [ ] Set them in Railway (a credential change — that's why it stops here)

**Unblocks:** Batch 11, and pays two debts already outstanding — Batch 15's *"overdue loan
triggers a push"* (§12.5, shipped without it) and Batch 19's price-drop notifications. Batch
20 will want it too.

### 3. `ANTHROPIC_API_KEY` in Railway

- [ ] Add a live Claude API key to the Railway `api` service

There is no key anywhere in the repo, in `.railway/railway.ts`, or in `apps/api/.env.local`,
so Batch 30 can't do anything real without one.

**Unblocks:** Group J — Batch 30 (AI assistant client + usage caps) → Batch 31 (tools + chat).
Batch 32 (voice input) sits behind these too; see the note at the bottom.

### 4. eBay production API application

- [x] Apply for eBay production API access — submitted 2026-09-09; eBay account approval is pending (at least one business day)

**Unblocks:** Group I — Batch 28 (eBay integration) → Batch 29 (format upgrade + sale tracking).

### 5. Google + Microsoft OAuth app registration

- [ ] Register the OAuth apps and set the credentials in Railway

**Unblocks:** Group K — Batch 33 (email accounts + OAuth) → Batch 34 (parsers + scanning).

---

## Finishing acceptance criteria on work that already shipped

### 6. Subscribe the `.ics` feed in Apple or Google Calendar — deprioritised

- [ ] Generate the feed URL (Calendar → Subscribe in the app, or `POST /api/v1/calendar/subscribe`)
- [ ] Subscribe to it and confirm the 32 release-calendar events render

Batch 17 shipped and the feed's bytes are verified against RFC 5545. The in-app release
calendar is the primary experience; external-calendar subscription is retained as an optional
convenience and is no longer a current owner action. Do this only if Craig or Mark wants it.

**The URL is a capability URL** — anyone holding it can read the feed. It's `noindex,
nofollow` and the token is rotatable, but treat it like a password.

---

## Housekeeping — not blocking anything

### 7. Revoke the April PAT at GitHub

- [ ] Revoke it

Classic PAT, 40 chars, `ghp_3gLc…`, committed **in full** in `0bfb672` (2026-04-25) and
referenced truncated in `4768da8`. It is dead (returns 401) but was never formally revoked.
**A history rewrite is not recommended** — the repo is private and the token is already
invalid, so a rewrite would cost more than it buys.

### 8. Set Mark's PIN

- [ ] Choose a PIN and set it

`profiles.pin_hash` is `NULL` for Mark, so he cannot sign in at all. Left to you because it's
his PIN to choose, not an agent's to invent.

```
DATABASE_URL='<neon url from apps/api/.env.local>' PYTHONPATH=apps/api \
  apps/api/.venv/bin/python3.12 -m src.scripts.set_pin Mark
```

### 9. `VITE_API_URL` for Vercel preview deploys

- [ ] Add it in the Vercel dashboard — **only if you want preview deploys to work**

It's currently set for Production only. Production is fine; previews would white-screen.

---

## Consequences worth knowing

**Batch 32 (voice input) is not independent, despite the ledger calling it "solo".** Phase
9.5's acceptance is *"tapping mic, speaking a query, **sends correct transcription**"* — sends
it to the chat input, which doesn't exist until Batch 31. Building it before Group J means a
microphone button wired to nothing. It's grouped as solo because it shares no *files* with
Group J, not because the feature stands alone. **Blocked by item 3.**

**Batch 38 (E2E suite) can only cover 3 of its 7 flows today.** Phase 13.10's acceptance names
login, import, search, add-via-scan, price alert, chat session and movie night. Four of those
seven features don't exist yet — scan is Batch 24, price alert is Batch 20 (item 1), chat is
Batch 31 (item 3), movie night is Batch 35. **Partially blocked by items 1 and 3.**

**Batch 36 (command palette + keyboard shortcuts) needs nothing from this file.** Phase 6.3
indexes films, pages, actions and recent items — all of which exist — and 6.4's shortcuts are
self-contained. It is the only queued batch that can meet its acceptance criteria in full
today.
