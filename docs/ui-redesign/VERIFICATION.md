# Redesign verification — live pass

**Branch:** `feat/comprehensive-ui-redesign`  **Date:** 2026-09-10
**Exercised against:** the live Neon catalogue through the local API — **1,843 films
across 1,857 physical and digital items**, signed in as Craig (admin).

This records what was *measured*, not what was intended. `AUDIT.md` holds the audit and
the design direction; this file holds the foundation decisions taken during verification,
the defects the live pass found, and the results.

---

## 1. What the live pass changed

The audit left three claims unproven — contrast, touch sizing and theme integrity. All
three turned out to be partly false, and the fixes below are the substance of this pass.

### 1.1 Tone colours now use two scales, not one

A tone serves two jobs with incompatible contrast rules: a **filled surface**
(`bg-destructive` under white) and a **status word on a page or card**
(`text-destructive` in an error). One value cannot satisfy both.

Measured on the pre-existing tokens:

| Pairing | Was | Needs |
|---|---|---|
| `text-destructive` on a dark card | **3.13:1** | 4.5:1 |
| `text-destructive` on the dark page | **3.35:1** | 4.5:1 |
| `text-accent` (champagne) on cream | **1.92:1** | 4.5:1 |
| `text-warning` on cream card | **4.39:1** | 4.5:1 |
| `--warning-foreground` on `--warning`, light | **4.40:1** | 4.5:1 |
| `text-quality-hdr` over its own tint, light | **3.59:1** | 4.5:1 |
| `text-quality-bluray` over its own tint, dark | **4.01:1** | 4.5:1 |
| `--input` boundary vs page, light | **2.86:1** | 3:1 |

`text-destructive` is the app's error-message colour in ~30 places, most carrying
`role="alert"`. It was the least legible text in the product.

**The fix is a token split, not a repaint.** `theme/tokens.ts` gains a `--<tone>-text`
variant for all six semantic tones in both themes, and `tailwind.config.ts` points
Tailwind's separate `textColor` scale at them. `text-*` therefore reads the text-safe
value while `bg-*`, `border-*` and `ring-*` keep the surface value — **no call site
changed.** `foreground` is re-declared on each tone so `text-primary-foreground` and its
siblings survive the override. `fill` is overridden for `accent` alone, so the rating star
never renders a champagne body with a bronze rim in light mode.

Values were solved for the nearest passing lightness rather than eyeballed, then rounded
in the safe direction. Four `--quality-*` values and `--input` were corrected in place
(they are surface-and-text in one use), and light `--warning` moved 38% → 37% so its
near-white chip label clears 4.5:1.

### 1.2 `touch-target` never worked

`.touch-target` (the coarse-pointer 44px floor) was declared in `@layer components`.
Tailwind emits `components` **before** `utilities`, and `.touch-target` and `.min-h-8`
carry identical specificity — so the smaller value simply came later and won. Every
control that appeared to opt in was silently unchanged: filter chips stayed 32px, small
buttons 36px.

Moved to `@layer utilities`, where it is emitted after the generated classes. Verified:
the removable filter chip is **32px on a fine pointer and 44px on a coarse one**, so
desktop density is untouched.

A companion `.touch-hit` utility grows only the *hit area* via a centred, transparent
pseudo-element, for controls whose drawn size carries meaning — a 24px switch track reads
as a switch, a 44px one reads as a bar.

### 1.3 Theme integrity was overstated

The audit claimed the palette had been unified. A repo sweep found **~60 raw Tailwind
palette classes still in place**, including `fill-yellow-400` rating stars and a
`NotificationSettingsPage` written almost entirely in `neutral-*`/`amber-*`/`emerald-*`
with hand-written `dark:` pairs. All are now on semantic tokens; the hand-written `dark:`
variants were deleted as dead weight, since the tokens already carry both themes.

`SpecBadges` moved onto the media-quality vocabulary that already existed for exactly its
three tones (`quality-4k` / `quality-hdr` / `quality-audio`). `FORMAT_COLORS` in
`lib/api.ts` — a second, unused format-colour vocabulary competing with `FormatBadge` —
was removed.

A repo-wide sweep for raw palette classes now returns nothing.

### 1.4 Two components fought over the tab title

`App.tsx`'s `RouteTitle` and `AppLayout` both wrote `document.title`. They could disagree
(`Page not found` against `Film archive`), and the archive root rendered
"The Real MCU · The Real MCU". `RouteTitle` is now the single owner; `AppLayout` keeps
`routeLabel` for the mobile header only.

### 1.5 The gate now enforces contrast

`src/theme/contrast.test.ts` — 42 assertions — computes WCAG ratios from the token source
the way a browser composites them, **including the translucent tints that badges and state
panels paint under their own text**. A future palette tweak fails the gate rather than
shipping. Suite went from 171 to 213 web tests.

---

## 2. Verification results

| Check | Result |
|---|---|
| `pnpm -r test` | **213 web + 79 shared, all passing** |
| `pnpm --filter @mcu/web lint` | **0 errors** (5 pre-existing `react-refresh` warnings) |
| `pnpm --filter @mcu/web typecheck` | **clean** |
| `pnpm --filter @mcu/web build` | **succeeds**, PWA service worker emitted |
| Contrast, both themes | **42/42 assertions pass** at AA |
| Horizontal overflow, 18 routes @ 320px | **none** — `scrollWidth === clientWidth` everywhere |
| Horizontal overflow, 18 routes @ 375px | **none** |
| Touch targets @ 375px, coarse pointer | **0 violations** across 10 sampled routes (was 11) |
| Desktop density | filter chip **32px** on fine pointer — unchanged |
| Heading order | exactly **one `h1` per route**, **no level skips**, 18 routes |
| Accessible names | **0 unnamed interactive controls** on the collection route |
| Tab order | skip-link first, **no positive `tabindex`**, 39 focusables in logical order |
| Focus ring | `:focus-visible`, 2px solid burgundy, 3px offset, **8.89:1** against the page |
| Reduced motion | global `prefers-reduced-motion` rule zeroes animation/transition, forces `scroll-behavior: auto` |
| Offline | live region announces "You're offline. You can still browse, and any changes are saved on this device." |
| Admin gating | every admin route wrapped in `AdminShell` → `ProtectedRoute` → `/unauthorized`, independent of nav visibility |

### Virtualisation held at scale

The single most important performance property survived. On the full 1,843-film grid:

- initial render — **881 DOM nodes / 36 cards**
- scrolled to **67,056px of 111,775px** (deep into the "P"s) — **1,421 nodes / 66 cards**

Bounded, not 1,843. List view renders 13 rows / 632 nodes; compact renders 19 rows at 52px
/ 610 nodes.

### Journeys confirmed against real data

- **Search** — `/` focuses a `role="combobox"` with `aria-autocomplete="list"`; typing
  "werewolf" returned *An American Werewolf in London* answering **✓ Owned · 4K UHD ·
  2 copies · Back 1st · Lounge** with the match highlighted. Arrow keys move a real
  `aria-activedescendant`; `aria-expanded` and `aria-controls` are correctly wired on the
  visible instance. (The second, hidden instance is `display:none` and out of the
  accessibility tree.)
- **Ownership** — the multi-copy record shows copy 1 as Blu-ray on *Back 1st Shelf* and
  copy 2 as 4K UHD, **Collector edition "Arrow"**, in the *Lounge Cabinet*. "Owned copies"
  is the first and default tab, so the ownership answer is not behind "Overview".
- **Filtering** — Lounge + 4K UHD narrowed 1,843 → **61 films**, with both constraints
  shown as individually removable chips plus "Clear all". Filters survive a reload.
- **Data coherence** — 1,829 films with one copy and **14 with two**, which is exactly the
  1,857 − 1,843 difference.

---

## 3. Open — needs Craig's judgement

1. **The floating assistant button covers a control on mobile.** Reproduced at 375px on
   `/settings/notifications`: the FAB (fixed, 48×48, `z-index: 20`) overlaps the
   "Upcoming releases" switch, so taps on the switch's right portion open the assistant
   instead. Any right-aligned control can fall under it at some scroll position. Fixing it
   properly is an information-architecture decision — make the assistant a sixth mobile
   tab, hide the FAB on routes with edge-aligned controls, or reserve a right gutter at
   the cost of ~64px on a 375px screen — so it is left for you rather than chosen here.

2. **Edition is still invisible while browsing.** Unchanged from the audit: the list
   contract has no edition field, and fetching copies per film would be an N+1 across
   1,843 rows. Making it visible needs an additive list field (an array of distinct
   edition labels), which is an API-contract change.

3. **`/debug` remains production-reachable.** Whether it should be development-only is a
   deployment decision.

---

## 4. Incomplete deliverable

**Before/after screenshots are only partially captured.** `screenshots/before/` holds the
nine baseline captures and `screenshots/after/` holds three work-in-progress ones. The
remaining after-shots could not be captured automatically in this session:

- Driving a headless Chrome needs the session token moved out of the browser, which was
  correctly refused by the permission guardrail — and typing the PIN is not something an
  agent should do.
- Chrome 152 headless aborts on this macOS build (`_NSCGSTransaction dealloc` assertion),
  so the unauthenticated login page could not be captured either.

Every surface listed in §2 was verified live and measured; the gap is the saved image
files, not the verification. The cheapest way to close it: launch Chrome once with
`--remote-debugging-port=9222`, sign in yourself, and a short CDP script can then capture
all nine surfaces at both themes and both widths without ever handling the PIN.

---

## 5. Ready for the brand pass

The identity slots are reserved and marked with `data-logo-slot`, still holding plain-text
placeholders:

| Slot | Where | Currently |
|---|---|---|
| `desktop-horizontal` | `Sidebar.tsx` header | "M" mark + "The Real MCU / Private film archive" |
| `mobile-mark` | `AppLayout.tsx` header | 28px burgundy "M" square |
| `onboarding-stacked` | `OnboardingPage.tsx` | stacked wordmark + eyebrow |
| auth stacked | `LoginPage.tsx` left panel | circled film icon + stacked wordmark |

None of the approved assets under `docs/brand/logo-system/stack-family/` were touched.

---

## 6. Route-by-route summary

Change volume is `git diff --numstat` on this branch. "Verified live" means exercised in
the browser against the real catalogue during this pass; the rest were swept for overflow,
touch targets and heading order at 320px and 375px but not driven interactively.

### New shared building blocks

| File | Purpose |
|---|---|
| `theme/tokens.ts` | The single palette source — brand, semantic, `-text` and media-quality tokens for both themes |
| `theme/contrast.test.ts` | 42 gate-enforced WCAG assertions, tint-composited |
| `ui/page-header.tsx` | Eyebrow / display title / description / actions hierarchy |
| `ui/state-panel.tsx` | One loading / empty / error / offline treatment |
| `ui/badge.tsx` | Six semantic tones, icon-or-word paired so status never rests on colour |
| `movies/FormatBadge.tsx` | Format vocabulary on the media-quality tokens |
| `movies/Poster.tsx` | Fixed ratio, lazy loading, useful fallback and alt text |
| `layouts/MobileTabBar.tsx` | Five everyday destinations within thumb reach |

### Structurally redesigned

| Route | What changed | Live |
|---|---|---|
| `/login` | Split composition, stacked identity slot, offline/error states, network-failure recovery | ✅ |
| `/movies` | Archive header, three purposeful views, progressive filters, removable filter chips, virtualisation preserved | ✅ |
| `/movies/:id` | Ownership answered in the metadata row *and* as the first tab; per-copy format, **Collector edition**, shelf; explicit subquery states | ✅ |
| `/welcome` (onboarding) | Resumable editorial steps, announced errors, sign-out escape | – |
| `/assistant` | Mobile conversation picker, stored+live turns merged, stream/mutation states, named send action | ✅ (swept) |
| `/movie-night`, `/movie-night/:id` | Guarded keyboard shortcuts, distinct deck vs realtime failures | ✅ (swept) |
| `/box-sets`, `/box-sets/:id` | Shared header/state patterns, responsive rows | – |
| `/dashboard` | Shared panels and state treatment | – |
| Global shell | Grouped sidebar (archive / planning / explore / personal / administration), mobile header, global search, offline banner, floating assistant | ✅ |

### Rehomed onto tokens during this pass

| Route / component | Was |
|---|---|
| `/settings/notifications` | Almost entirely `neutral-*`/`amber-*`/`emerald-*` with hand-written `dark:` pairs; switch had a ~1.1:1 track and a ~1.3:1 knob |
| `/retailers` | `text-amber-500` ×7, `text-emerald-600` |
| `/trash` | 24px table tabs |
| `/insights`, `CompletionSetPanel` | `bg-amber-500` progress |
| `SpecBadges` | amber/violet/teal → the `quality-*` vocabulary that already named those tones |
| `WatchPanel` | `fill-yellow-400` rating stars |
| `IdentifyPanel`, `DuplicatePrompt`, `RecommendationsPanel` | amber panels and chips |
| `lib/api.ts` | `FORMAT_COLORS` — an unused second format vocabulary — removed |
| `main.tsx` | Crash fallback in `text-red-600` |

### Inherit the shell, tokens and controls without bespoke redesign

`/wanted`, `/collections`, `/collections/:id`, `/calendar`, `/discover`, `/loans`,
`/stats`, `/audit`, `/gift-links`, `/settings/ai`, `/admin`, `/unauthorized`, `/offline`,
`/gift/:token`. All were swept clean for overflow, touch targets and heading order.

**No route was removed, and no workflow lost.** The 18-route sweep resolves every path in
`navItems` and `adminNavItems`.
