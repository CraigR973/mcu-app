import { test, type BrowserContext, type Page, type Request, type Response } from '@playwright/test'

/**
 * A page is left only once it has finished loading (DECISIONS.md #367).
 *
 * WebKit cancels everything a page still has in flight the moment a navigation starts; Chromium
 * and Firefox let it finish until the next document takes over. The page's script is still
 * running, so it meets each cancelled load as a failure. On 10 Nov CI met all three ways that
 * goes wrong: a save cancelled before it reached the server (AC6's reload), a lazy chunk
 * cancelled, which the app answers by reloading itself over the case's own navigation (the
 * cinemas case), and twice WebKit's loader failing the navigation itself, "WebKit encountered an
 * internal error", with 12 and 16 loads cancelled under it (the sign-out and Needs you cases).
 *
 * So every goto and reload a case starts first waits until the page has nothing in flight and has
 * started nothing for half a second, Playwright's own measure of a quiet network. goBack and
 * goForward are left alone: in this app they move within the page, which cancels nothing, and
 * AA9's case goes Back with an answer still on its way on purpose.
 *
 * A fetch counts as done once its answer arrives, the body not awaited. Chromium reports a fetch
 * finished only when the page reads its body, and a page that only looks at the status never does
 * (a profile photo's 404), so that fetch would otherwise stay open for ever; and an event stream
 * stays open for as long as its screen does (movie night's, the assistant's). The server has
 * answered by then, so a save has landed. An answer from the service worker's cache counts once it
 * arrives too: there is nothing left to fetch.
 */
const QUIET_MS = 500
/** Long enough for the slowest screen; a page still busy after this is reported, not left. */
const CEILING_MS = 15_000
const POLL_MS = 50

const methods = ['goto', 'reload'] as const
/** The resource types whose answer, once it arrives, is all the page was waiting for. */
const ANSWERED_AT_HEADERS = new Set(['fetch', 'xhr', 'eventsource'])
type Leaving = (typeof methods)[number]
type Navigate = (...args: unknown[]) => Promise<Response | null>

class Traffic {
  private readonly open = new Set<Request>()
  /** When the page last started or finished a request; 0 until it has made one. */
  private lastMoved = 0

  constructor(page: Page) {
    page.on('request', (request) => {
      // data: and blob: URLs never reach a network to be cancelled.
      if (!/^https?:/.test(request.url())) return
      this.open.add(request)
      this.lastMoved = Date.now()
    })
    page.on('requestfinished', (request) => this.done(request))
    page.on('requestfailed', (request) => this.done(request))
    page.on('response', (response) => {
      const request = response.request()
      if (ANSWERED_AT_HEADERS.has(request.resourceType()) || response.fromServiceWorker()) this.done(request)
    })
  }

  private done(request: Request): void {
    if (this.open.delete(request)) this.lastMoved = Date.now()
  }

  /** Resolves once nothing is in flight and nothing has moved for QUIET_MS. */
  async settled(): Promise<void> {
    const deadline = Date.now() + CEILING_MS
    for (;;) {
      const quietFor = Date.now() - this.lastMoved
      if (this.open.size === 0 && quietFor >= QUIET_MS) return
      if (Date.now() > deadline) {
        const still = [...this.open].map((request) => `${request.method()} ${request.url()}`)
        throw new Error(
          `the page was still loading ${CEILING_MS / 1000} s later, so it was not left: ` +
            (still.length ? still.join(', ') : `a request started or ended within the last ${QUIET_MS} ms`),
        )
      }
      await new Promise((resolve) => setTimeout(resolve, this.open.size ? POLL_MS : QUIET_MS - quietFor))
    }
  }
}

const settling = new WeakSet<Page>()

/** Make this page's navigations wait for it to finish loading. Safe to call twice. */
export function settleBeforeLeaving(page: Page): void {
  if (settling.has(page)) return
  settling.add(page)
  const traffic = new Traffic(page)
  const own = page as unknown as Record<Leaving, Navigate>
  const originals = {} as Record<Leaving, Navigate>
  for (const method of methods) originals[method] = own[method].bind(page)
  for (const method of methods) {
    // Awaited, and boxed, so a failure is reported at the case's own line as a bare call's would
    // be, not at this file's. Called as `originals[method]` so Playwright still names the call
    // page.goto or page.reload: it names a call by how the caller spelled it.
    own[method] = async (...args) =>
      await test.step(
        `${method}${typeof args[0] === 'string' ? ` ${args[0]}` : ''}, once the page has settled`,
        async () => {
          await traffic.settled()
          return await originals[method](...args)
        },
        { box: true },
      )
  }
}

/** Every page this context opens, now or later, waits for itself to settle before it is left. */
export function settleEveryPage(context: BrowserContext): void {
  for (const page of context.pages()) settleBeforeLeaving(page)
  context.on('page', settleBeforeLeaving)
}
