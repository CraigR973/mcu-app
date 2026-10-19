import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))

export const E2E_DIR = path.resolve(here, '..')
export const REPO = path.resolve(E2E_DIR, '..', '..')
export const API_DIR = path.join(REPO, 'apps', 'api')
export const WEB_DIR = path.join(REPO, 'apps', 'web')

/** Everything the run writes. Also the API's working directory: no `.env` lives here, so the
 * API cannot read the real database's URL from a file by accident. */
export const RUN_DIR = path.join(E2E_DIR, '.run')
export const WORLD_DIR = path.join(RUN_DIR, 'world')
export const WEB_DIST = path.join(RUN_DIR, 'web')

export const API_PORT = 8000
export const WEB_PORT = 4173
export const CONTROL_PORT = 8001

// The page is `localhost`, the API is `127.0.0.1`: two origins, as Vercel and Railway are.
export const WEB_ORIGIN = `http://localhost:${WEB_PORT}`
export const API_ORIGIN = `http://127.0.0.1:${API_PORT}`
export const CONTROL_ORIGIN = `http://127.0.0.1:${CONTROL_PORT}`

export const PINS = { Craig: '4827', Mark: '7391' } as const
export type Person = keyof typeof PINS

/** A throwaway Postgres server, as an admin URL. Never Neon, Railway or production: the
 * database tool refuses anything that does not look local. */
export function adminUrl(): string {
  const url = process.env.E2E_DATABASE_URL
  if (!url) {
    throw new Error(
      'E2E_DATABASE_URL is not set. Give it a throwaway Postgres, e.g. ' +
        'postgresql://postgres:postgres@localhost:5432/postgres (CI) or a pgserver socket URL.',
    )
  }
  return url
}

export function pythonBin(): string {
  if (process.env.E2E_PYTHON) return process.env.E2E_PYTHON
  const venv = path.join(API_DIR, '.venv', 'bin', 'python3.12')
  return existsSync(venv) ? venv : 'python3'
}

export const RUN_DB = 'mcu_e2e_run'
