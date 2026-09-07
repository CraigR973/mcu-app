# MCU — Mark's Cinematic Universe

A private physical-film catalogue built with FastAPI, React 18, and Neon Postgres.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, async SQLAlchemy, Uvicorn |
| Database | Neon (PostgreSQL) |
| State | TanStack Query v5 |
| Router | React Router v6 |

## Monorepo Structure

```
mcu_app/
├── apps/
│   ├── api/          # FastAPI backend (Python 3.12) + Alembic migrations
│   └── web/          # React 18 frontend
├── packages/
│   └── shared/       # Shared zod schemas and inferred TypeScript types
└── docs/             # Project documentation
```

## Prerequisites

- Node.js 20.18.0+ (see `.nvmrc`)
- Python 3.12.3+ (see `.python-version`)
- pnpm 9+

## Getting Started

### Frontend

```bash
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm install
PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" pnpm --filter @mcu/web dev
```

### Backend

```bash
python3.12 -m venv apps/api/.venv
apps/api/.venv/bin/python3.12 -m pip install -e "apps/api[dev]"
# Copy apps/api/.env.example to apps/api/.env and fill in local values.
apps/api/.venv/bin/uvicorn src.main:app --app-dir apps/api --reload
```

## Environment Variables

See [`apps/api/.env.example`](apps/api/.env.example) for required API keys.
