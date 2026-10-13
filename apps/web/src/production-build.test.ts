import { spawnSync } from 'node:child_process'
import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { afterAll, beforeAll, describe, expect, it } from 'vitest'

/**
 * What a production build leaves out — Batch U3, `DECISIONS.md` #221.
 *
 * Two things in the source must never reach the live site: `/debug`, whose button throws an
 * error on purpose, and `ProtectedRoute`'s `VITE_SKIP_AUTH` bypass, which would open the
 * whole collection. Both sit behind `import.meta.env.DEV`, which a production build compiles
 * to `false`. A comment saying the bundler drops them is not evidence, so this builds the
 * app as Vercel does and reads what comes out.
 *
 * **`NODE_ENV` is set, not inherited.** Vitest runs with `test`, and Vite takes `DEV` from
 * it, so an inherited value would build a development bundle — which contains both.
 *
 * **So is `VITE_SKIP_AUTH`: the build runs with it on**, as a stray variable on a deployment
 * would. Built without it, the bypass compiles away with or without its guard (its
 * condition becomes `undefined === 'true'`), and a check would prove nothing.
 */

const webRoot = fileURLToPath(new URL('..', import.meta.url))
const source = (path: string) => readFileSync(join(webRoot, 'src', path), 'utf8')
const outDir = mkdtempSync(join(tmpdir(), 'mcu-production-build-'))

let shipped = ''
let worker = ''
let version = ''

beforeAll(() => {
  // `VITE_API_URL` on another origin, as production's Railway API is to its Vercel page, so
  // the worker's cache rule can be read for it below (Batch X8).
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    NODE_ENV: 'production',
    VITE_SKIP_AUTH: 'true',
    VITE_API_URL: 'https://api.example.test',
  }
  const build = spawnSync(
    process.execPath,
    [join(webRoot, 'node_modules/vite/bin/vite.js'), 'build', '--outDir', outDir, '--emptyOutDir', '--logLevel', 'error'],
    { cwd: webRoot, env, encoding: 'utf8', timeout: 170_000 },
  )
  if (build.status !== 0) throw new Error(`vite build failed:\n${build.stderr || build.stdout || build.error}`)

  // Everything a browser can load. Not the hidden source maps: they hold the source text,
  // guards and all, and are neither referenced by the bundle nor served by Vercel.
  const scripts = readdirSync(join(outDir, 'assets'))
    .filter((name) => name.endsWith('.js'))
    .map((name) => readFileSync(join(outDir, 'assets', name), 'utf8'))
  worker = readFileSync(join(outDir, 'sw.js'), 'utf8')
  version = readFileSync(join(outDir, 'version.json'), 'utf8')
  shipped = [...scripts, worker, readFileSync(join(outDir, 'index.html'), 'utf8')].join('\n')
}, 180_000)

afterAll(() => {
  rmSync(outDir, { recursive: true, force: true })
})

describe('a production build', () => {
  it("gives the worker the API's own origin, so it keeps answers from a cross-origin API", () => {
    // Batch X8 (UX48-01): the rule matched only the page's origin, and production's API is
    // on another, so the worker never kept one answer. The guard for the rule itself is
    // `api-cache-route.test.ts`; this proves the built worker is handed the API's address.
    expect(worker).toContain('https://api.example.test')
    expect(worker).toContain('/api/v1/')
  })

  it('says which commit it was built from', () => {
    const parsed = JSON.parse(version) as { commit: string }
    expect(parsed.commit).toMatch(/^([0-9a-f]{40}|unknown)$/)
  })

  it('is the app as it stands, so an absence below means something', () => {
    expect(shipped).toContain('"/movies"')
    expect(shipped).toContain('Ask the assistant')
  })

  it('contains neither the /debug route nor its page', () => {
    // The markers are checked against the source first: a renamed button would otherwise
    // leave this test looking for words that no longer exist anywhere.
    const app = source('App.tsx')
    for (const marker of ['path="/debug"', 'Break the world', "'Debug tools'", 'This is your first error!']) {
      expect(app).toContain(marker)
    }

    expect(shipped).not.toContain('"/debug"')
    expect(shipped).not.toContain('Break the world')
    expect(shipped).not.toContain('Debug tools')
    expect(shipped).not.toContain('This is your first error!')
  })

  it('keeps the sign-in check, though it was built with VITE_SKIP_AUTH on', () => {
    const route = source('components/ProtectedRoute.tsx')
    expect(route).toContain("import.meta.env.VITE_SKIP_AUTH === 'true') return <>{children}</>")

    // Were the bypass compiled in, its `return` would come first and the bundler would drop
    // everything after it as unreachable: the session check's two panels among them.
    for (const panel of ['Confirming this device’s session…', 'Your session could not be confirmed']) {
      expect(route).toContain(panel)
      expect(shipped).toContain(panel)
    }
  })
})
