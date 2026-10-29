# AB2 build plan — 28 Oct

Craig approved Summary cards and its shown wording, plus the exact one-field stats contract,
in chat on 28 Oct before this plan or product implementation. Sitting 1 only. Clean main
86e7d56 was green (all seven jobs, 40759704615); existing review branch preserves c2a6784.
The review contains the alternatives, screenshots, cost allowance and live examples.

## Batch goal and acceptance criteria (verbatim)

### AB2 — Collection descriptions, watched coverage and visible breakdown

- **Checkpoint before build:** present phone-size layout/wording alternatives; stop for
  Craig's pick. Recommendation: short descriptions, owned-watched coverage, small visible
  breakdown preview and expandable full charts. Existing five meanings stay available.
- Watched becomes the signed-in person's distinct watched currently owned titles against
  current owned titles. Rewatches/extra copies count once; downloads count; sold/donated/
  binned copies follow the canonical ownership rule. Preserve the diary and account privacy.
- Propose additive `ownedWatchedMovies` in existing stats/shared-zod contracts, preserving
  `watchedMovies` as the whole-diary metric. Obtain exact API approval with layout picks;
  old/cached responses cannot invent zero when the new field is absent.
- Explain titles/copies, overlapping formats, value coverage and matching. Keep identified
  meaning intact. Record a scoped supersession of #299 for watched and chosen presentation.
  Preserve format/location/genre/decade data and missing-spend caveats, without re-pricing.
- Regress both counts after watches and collection changes, account isolation, old responses
  and chosen design at 375 px/both themes. Full gate/E2E, exact-head CI and production
  readback; live snapshot numbers are examples, not pinned expected counts. No data rewrite.


## Approved mechanism

Authenticated person + distinct active watches → current owned-title intersection →
ownedWatchedMovies / totalMovies → Home Summary cards.

1. Add required non-negative integer ownedWatchedMovies to StatsResponse and OpenAPI.
   Count distinct WatchLog.movie_id for the current user, active watch and active Movie,
   using owned_film(). Downloads/listed-for-sale count; departed/trashed copies do not.
   Preserve watchedMovies query exactly and all other stats/AI diary consumers.
2. Add optional non-negative integer to shared statsSchema, without a zero default.
   Home displays Unavailable and the approved saved-response message when absent.
3. Apply approved Summary cards labels/descriptions; watched numerator and owned denominator
   appear together. Keep match semantics, existing value coverage and complete caveats.
   Add visible overlapping format bars; preserve all existing expandable full charts,
   recorded/missing spending explanations and Browse the archive navigation.
4. Add successful-write stats invalidation centrally (inspection found watches/copy edits
   did not invalidate this five-minute cache), key Home stats by profile id to isolate its personal numerator, invalidate stats after
   automatic replay as well, and prove
   watch changes, extra copies, copy departure/restoration, downloads, account isolation,
   deletion and genuine zero versus older-response absence. Extend regressions; scoped
   supersession of #299 authorises the obsolete diary-label/copy-label expectations only.
5. Run focused checks, inspect actual Home at 375 px in both themes for both people, then
   commit and run all ten batch-verify checks from clean tree plus local Chromium/Firefox/
   cron E2E. WebKit requires CI on this Mac. Review the diff, PR exact-head seven-job CI,
   merge, exact main CI, API/web SHA + full readiness and read-only live owned-watch comparison.
   Record all failures/repairs, acceptance evidence and limitations in the verification report.

## Decisions and boundaries

Summary cards is Craig's choice; Plain rows is rejected because grouped comparison and
visible breakdown suit this Home section. One existing endpoint field is approved; a new
endpoint, diary rewrite, inferred zero or re-price would change the agreed contract.
A wrong join could double-count rewatches/copies or leak another person's history; distinct
intersection and two-account regressions guard those failures. No migration, hosting,
credentials, provider/model request, production collection/history write or price refresh.
No sitting 2/AB3 or AA10c. Existing phone and AA10b final-total owner checks remain open.
Verification allowance remains roughly one hour plus build and repair time, not a promise.
