import { type ChildProcess, spawn, spawnSync } from 'node:child_process'
import { createHash, randomBytes } from 'node:crypto'
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync, createWriteStream } from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import {
  adminUrl,
  API_DIR,
  API_ORIGIN,
  API_PORT,
  E2E_DIR,
  REPO,
  RUN_DIR,
  RUN_DB,
  WEB_DIR,
  WEB_DIST,
  WEB_ORIGIN,
  WEB_PORT,
  WORLD_DIR,
  pythonBin,
} from './env.ts'

const DBTOOL = path.join(E2E_DIR, 'harness', 'dbtool.py')
const FAKES = path.join(E2E_DIR, 'fakes')

export function dbtool(...args: string[]): string {
  const result = spawnSync(pythonBin(), [DBTOOL, adminUrl(), ...args], { encoding: 'utf8' })
  if (result.status !== 0 && args[0] !== 'exists') {
    throw new Error(`dbtool ${args.join(' ')} failed: ${result.stderr || result.stdout}`)
  }
  return args[0] === 'exists' ? String(result.status) : result.stdout.trim()
}

export function databaseUrl(db: string): string {
  return dbtool('url', db)
}

/** Secrets for one run, made fresh: a push key and an eBay sealing key nobody else has. */
const secrets = {
  jwtAccess: randomBytes(32).toString('hex'),
  jwtRefresh: randomBytes(32).toString('hex'),
  vapid: randomBytes(32).toString('base64url'),
  ebayTokenKey: randomBytes(32).toString('base64'),
}

/**
 * The whole environment a Python process gets. Built from nothing, not from the caller's
 * environment, so a stray `DATABASE_URL` or a real API key in the shell cannot reach it.
 */
export function pythonEnv(db: string, extra: Record<string, string> = {}): Record<string, string> {
  const url = databaseUrl(db)
  const env: Record<string, string> = {
    PATH: process.env.PATH ?? '/usr/bin:/bin',
    HOME: process.env.HOME ?? '/tmp',
    DATABASE_URL: url,
    ENVIRONMENT: 'development',
    JWT_ACCESS_SECRET: secrets.jwtAccess,
    JWT_REFRESH_SECRET: secrets.jwtRefresh,
    FRONTEND_ORIGIN: WEB_ORIGIN,
    LOG_LEVEL: 'WARNING',
    PYTHONPATH: [API_DIR, FAKES].join(path.delimiter),
    PYTHONUNBUFFERED: '1',
    MCU_OUTSIDE_WORLD: '1',
    OUTSIDE_WORLD_DIR: WORLD_DIR,
    // Fake credentials, so each client takes the path it takes in production and the
    // fake world answers. None of these is real.
    TMDB_READ_TOKEN: 'e2e-fake-tmdb-token',
    EBAY_CLIENT_ID: 'e2e-fake-ebay-client',
    EBAY_CLIENT_SECRET: 'e2e-fake-ebay-secret',
    EBAY_RUNAME: 'e2e-fake-runame',
    EBAY_TOKEN_KEY: secrets.ebayTokenKey,
    BRAVE_SEARCH_API_KEY: 'e2e-fake-brave-key',
    ANTHROPIC_API_KEY: 'e2e-fake-anthropic-key',
    VAPID_PRIVATE_KEY: secrets.vapid,
    VAPID_SUBJECT: 'mailto:e2e@example.invalid',
    ...extra,
  }
  return env
}

export function runPython(
  args: string[],
  db: string,
  extra: Record<string, string> = {},
  label = args.join(' '),
): { status: number; output: string } {
  mkdirSync(RUN_DIR, { recursive: true })
  const result = spawnSync(pythonBin(), args, {
    cwd: RUN_DIR,
    env: pythonEnv(db, extra),
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  })
  const output = `${result.stdout ?? ''}${result.stderr ?? ''}`
  if (process.env.E2E_VERBOSE) console.log(`[python ${label}]\n${output}`)
  return { status: result.status ?? 1, output }
}

function waitFor(url: string, ready: (body: string, status: number) => boolean, seconds: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + seconds * 1000
    const attempt = () => {
      http
        .get(url, (res) => {
          let body = ''
          res.on('data', (c) => (body += c))
          res.on('end', () => {
            if (ready(body, res.statusCode ?? 0)) resolve()
            else retry()
          })
        })
        .on('error', retry)
    }
    const retry = () => {
      if (Date.now() > deadline) reject(new Error(`${url} was not ready after ${seconds}s`))
      else setTimeout(attempt, 300)
    }
    attempt()
  })
}

export class ApiProcess {
  private child: ChildProcess | null = null
  constructor(private readonly db: string) {}

  async start(): Promise<void> {
    if (this.child) return
    mkdirSync(RUN_DIR, { recursive: true })
    const log = createWriteStream(path.join(RUN_DIR, 'api.log'), { flags: 'a' })
    // cwd is RUN_DIR: Settings reads `.env` from the working directory, and there is none.
    this.child = spawn(
      pythonBin(),
      ['-m', 'uvicorn', 'src.main:app', '--host', '127.0.0.1', '--port', String(API_PORT), '--log-level', 'warning'],
      { cwd: RUN_DIR, env: pythonEnv(this.db), stdio: ['ignore', 'pipe', 'pipe'] },
    )
    this.child.stdout?.pipe(log)
    this.child.stderr?.pipe(log)
    await waitFor(`${API_ORIGIN}/api/v1/health/ready`, (body) => body.includes('"db":"ok"'), 60)
  }

  async stop(): Promise<void> {
    const child = this.child
    if (!child) return
    this.child = null
    await new Promise<void>((resolve) => {
      child.once('exit', () => resolve())
      child.kill('SIGTERM')
      setTimeout(() => child.kill('SIGKILL'), 5000).unref()
    })
  }
}

export class WebProcess {
  private child: ChildProcess | null = null

  async start(): Promise<void> {
    const log = createWriteStream(path.join(RUN_DIR, 'web.log'), { flags: 'a' })
    this.child = spawn(
      'pnpm',
      ['--filter', '@mcu/web', 'exec', 'vite', 'preview', '--outDir', WEB_DIST, '--port', String(WEB_PORT), '--strictPort', '--host', 'localhost'],
      { cwd: REPO, env: { ...process.env }, stdio: ['ignore', 'pipe', 'pipe'] },
    )
    this.child.stdout?.pipe(log)
    this.child.stderr?.pipe(log)
    await waitFor(`${WEB_ORIGIN}/version.json`, (_body, status) => status === 200, 60)
  }

  async stop(): Promise<void> {
    const child = this.child
    if (!child) return
    this.child = null
    await new Promise<void>((resolve) => {
      child.once('exit', () => resolve())
      child.kill('SIGTERM')
      setTimeout(() => child.kill('SIGKILL'), 5000).unref()
    })
  }
}

/** Build the bundle the way production is built, pointed at the cross-origin API. */
export function buildWeb(): void {
  if (process.env.E2E_SKIP_BUILD && existsSync(path.join(WEB_DIST, 'index.html'))) return
  rmSync(WEB_DIST, { recursive: true, force: true })
  const result = spawnSync(
    'pnpm',
    ['--filter', '@mcu/web', 'exec', 'vite', 'build', '--outDir', WEB_DIST, '--emptyOutDir'],
    {
      cwd: REPO,
      env: { ...process.env, VITE_API_URL: API_ORIGIN },
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
    },
  )
  if (result.status !== 0) throw new Error(`web build failed:\n${result.stdout}\n${result.stderr}`)
}

/** A name that changes whenever the schema, the seed or the fake world does, so a stale
 * seeded template is never reused. */
export function templateName(): string {
  const hash = createHash('sha256')
  const add = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      if (entry.name === '__pycache__' || entry.name.endsWith('.pyc')) continue
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) add(full)
      else hash.update(entry.name).update(readFileSync(full))
    }
  }
  add(path.join(API_DIR, 'migrations'))
  add(path.join(API_DIR, 'tests', 'outside_world'))
  add(path.join(E2E_DIR, 'seed'))
  hash.update(readFileSync(path.join(REPO, 'apps', 'e2e', 'harness', 'stack.ts')))
  return `mcu_e2e_tpl_${hash.digest('hex').slice(0, 10)}`
}

export function resetWorld(): void {
  rmSync(WORLD_DIR, { recursive: true, force: true })
  mkdirSync(WORLD_DIR, { recursive: true })
  writeFileSync(path.join(WORLD_DIR, 'scenario.json'), '{}')
}

export { RUN_DB, WEB_DIR }
