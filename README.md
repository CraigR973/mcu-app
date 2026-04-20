# MCU — Mark's Cinematic Universe

A personal movie-tracking app built with FastAPI + React 18 + Supabase.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL) |
| State | TanStack Query v5 |
| Router | React Router v6 |

## Monorepo Structure

```
mcu_app/
├── apps/
│   ├── api/          # FastAPI backend (Python 3.12)
│   └── web/          # React 18 frontend
├── packages/
│   └── shared/       # Shared TypeScript types
├── migrations/       # Supabase SQL migrations
└── docs/             # Project documentation
```

## Prerequisites

- Node.js 20.18.0+ (see `.nvmrc`)
- Python 3.12.3+ (see `.python-version`)
- pnpm 9+

```bash
npm install -g pnpm
```

## Getting Started

### Frontend

```bash
pnpm install
pnpm --filter @mcu/web dev
```

### Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in your keys
uvicorn src.main:app --reload
```

## Environment Variables

See [`apps/api/.env.example`](apps/api/.env.example) for required API keys.
