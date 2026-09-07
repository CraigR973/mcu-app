# batch-verify

Turn the batch's acceptance criteria into a checklist, then prove each one.

Run all of these, from the repo root, with absolute paths:

```
apps/api/.venv/bin/ruff check apps/api
apps/api/.venv/bin/ruff format --check apps/api
PYTHONPATH=apps/api apps/api/.venv/bin/mypy apps/api/src
apps/api/.venv/bin/python3.12 -m pytest apps/api/tests
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm -r test
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web lint
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web typecheck
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web build
```

**Know what this proves.** Without `DATABASE_URL` set, the 13 tests in
`test_derived_field_triggers.py` skip silently — and CI has no Postgres service, so they
have never run there. For any change near migration `0015`, export `DATABASE_URL` from
`apps/api/.env.local` and re-run pytest, then say in the report that you did.

`pnpm -r test`, not `--filter @mcu/web test` — the filtered form never runs
`packages/shared`.

For frontend-visible batches, open the app and record what you actually looked at.

Report pass/fail **by acceptance criterion**, with the exact remaining gaps. Do not merge,
deploy, or tick anything — `phase-closeout` does that, only after the user asks.
