# AA3 — collection summary verification

27 Oct · implementation verification in progress; not a shipment claim.

Craig approved Compact summary, corrections, both personal/match numbers retained with
clearer definitions, and the two additive stats fields before implementation (#299).
The build plan and owner-picked preview are the acceptance source.

## Behaviour under test

Five metrics stay readable without sideways navigation. Physical copies and copies also
carrying downloads are direct counts from one aggregate query; multiple physical formats
never count a copy twice. Existing stats fields retain their meanings. Missing new fields
on an older API stay unavailable rather than becoming zero or being inferred from value.
The other Home shelves remain sideways. Charts expand in place; place names wrap and
monthly recorded spending can be read without hover. Both people retain their whole-diary
watch count and identified-owned-title count, with their limits written beside them.

## Failures and repairs

- Initial web lint found two unused variables in the new old-API test fixture. Removed
  the unused bindings; no lint exception was added.
- Initial web unit run: 704 passed, one failed. The existing Archive-link assertion caught
  a real regression: moving the link into the stats-loaded body hid it during loading and
  failure. The link is now outside the async body, available in every state. The existing
  assertion is unchanged.
- Review caught two additional edge cases before the final gate: missing offline value
  must say unavailable rather than loading forever, and dated recorded spending must name
  the number of dated purchases rather than all copies with prices.
- The first disposable-Postgres full run passed 2,482 tests but skipped nine collection-
  replacement cases because they require a localhost TCP URL rather than a Unix socket.
  Enabled loopback-only TCP for this disposable server so the clean gate can exercise them.
  The restart caller initially waited on the daemon's inherited output pipe; interrupted
  that caller, verified the running server and updated only ignored local test URLs.
- The first Chromium run passed the mixed-format API assertion but both new UI cases
  could not locate the physical/download line exactly: it shared a DOM text container
  with the overlap line. Each line now has its own span, preserving all exact expected
  values and assertions. Focused dashboard tests passed after this markup correction.
- Before the browser run, review caught that the new fixture would change the import
  journey's pinned 70-title baseline. Its own copy is now removed through the app API in
  `finally`; the import journey's existing expected count remains unchanged.
- Image inspection caught that the Archive action was content-width rather than the
  chosen full-width action. Added explicit full width and an exact browser width assertion.
  Component captures use a taller viewport to keep the fixed navigation out of the crop;
  functional checks still run at the normal 844 px height. The passing in-progress browser
  run was stopped for this visual correction; the complete final suite is required again.

The only changed existing layout expectation is Craig's approved collection-only exception
to the “every Home section is sideways” rule; every other shelf assertion stays. API route
inventory and access assertions are untouched. OpenAPI snapshot changes only the two
approved fields and their required-field entries; its exact comparison stays.

## Evidence pending

Focused API/stat/OpenAPI checks passed: 22 tests on disposable Postgres.
All ten standard local checks passed from clean commit `c164226`: API 2,491 passed with
zero skips; shared 157 and web 708 passed; lint/typechecks/builds passed. All 16 derived-field
trigger cases ran. A subsequent E2E-only fixture-cleanup commit changed no tested app source.
The final markup correction receives a fresh clean gate and browser run before close-out.
The second clean gate also passed all ten checks on `c1be577` (API 2,491, shared 157,
web 708, no API skips). Both new AA3 cases then passed in Chromium and Firefox; the final
full-width action correction receives another clean verification before shipment.
Browser screenshots, seven-job PR/main CI and exact production SHA/readiness proof remain
pending. Local WebKit is unavailable on macOS 13; CI must run it.
Real-phone observations remain owner-only. No live provider call, valuation start, data write
or synthetic production account/session is authorised or performed.
