import { test as base, expect, type BrowserContext, type Page } from '@playwright/test'
import { CONTROL_ORIGIN, PINS, RUN_DB, type Person } from '../harness/env.ts'
import { dbtool } from '../harness/stack.ts'
import { Api, login, type Tokens } from './api.ts'
import { world } from './world.ts'

const tokenCache = new Map<Person, Tokens>()

async function tokensFor(person: Person): Promise<Tokens> {
  const cached = tokenCache.get(person)
  if (cached) return cached
  const fresh = await login(person)
  tokenCache.set(person, fresh)
  return fresh
}

export interface Session {
  context: BrowserContext
  page: Page
}

interface Fixtures {
  /** A new browser context already signed in as that person (no login form). */
  signedIn: (person: Person, options?: { worker?: boolean }) => Promise<Session>
  /** The app's own API as that person, from the test process. */
  api: (person: Person) => Promise<Api>
  /** Stop or start the API process (the one the browser talks to). */
  apiProcess: { stop(): Promise<void>; start(): Promise<void> }
  db: { sql(statement: string): void; scalar(statement: string): string }
  noLeaks: void
  cleanWorld: void
}

export const test = base.extend<Fixtures>({
  signedIn: async ({ browser }, use) => {
    const opened: BrowserContext[] = []
    await use(async (person, options) => {
      const tokens = await tokensFor(person)
      // The service worker installs on a page's first load and then takes the page over, which
      // reloads it. A case that is not about the worker does not want that mid-click, so it runs
      // without one; the offline cases ask for it.
      const context = await browser.newContext({ serviceWorkers: options?.worker ? 'allow' : 'block' })
      opened.push(context)
      await context.addInitScript((t) => {
        try {
          localStorage.setItem('mcu.accessToken', t.accessToken)
          localStorage.setItem('mcu.refreshToken', t.refreshToken)
        } catch {
          /* a context with storage off signs in through the form instead */
        }
      }, tokens)
      return { context, page: await context.newPage() }
    })
    await Promise.all(opened.map((context) => context.close()))
  },

  api: async ({}, use) => {
    await use(async (person) => new Api((await tokensFor(person)).accessToken))
  },

  apiProcess: async ({}, use) => {
    const post = (action: string) => fetch(`${CONTROL_ORIGIN}/api/${action}`, { method: 'POST' }).then((r) => {
      if (!r.ok) throw new Error(`control /api/${action} answered ${r.status}`)
    })
    await use({ stop: () => post('stop'), start: () => post('start') })
    // Whatever a case did, the next one finds the API running.
    await post('start')
  },

  db: async ({}, use) => {
    await use({
      sql: (statement) => void dbtool('sql', RUN_DB, statement),
      scalar: (statement) => dbtool('scalar', RUN_DB, statement),
    })
  },

  // What the fake world was told by the last case is not for this one.
  cleanWorld: [
    async ({}, use) => {
      world.clearScenario()
      await use()
    },
    { auto: true },
  ],

  // Nothing may have tried to leave: an unfaked host, or a path on a faked host nobody wrote,
  // fails the case that caused it.
  noLeaks: [
    async ({}, use) => {
      const since = Date.now() / 1000
      await use()
      const leaks = world.leaks(since)
      expect(leaks, `the app reached for something the fake world does not know: ${JSON.stringify(leaks)}`).toEqual([])
    },
    { auto: true },
  ],
})

export { expect, PINS }
export type { Person }
