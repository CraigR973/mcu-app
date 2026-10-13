/**
 * What a person reads when something fails — one describer for every screen (Batch X8,
 * UX48-03).
 *
 * Screens used to show `error.message`, and three of the messages that reach a phone are
 * machine text: `fetch` rejecting ("Failed to fetch", "Load failed"), a newer API's value
 * refused by an older build (raw zod JSON), and a chunk a deploy removed ("Failed to fetch
 * dynamically imported module"). A crash read as no signal, because its 500 had no CORS
 * headers (fixed in the API's `UnhandledErrorMiddleware`). Each now has one sentence.
 *
 * A refusal the server explains in words (a 409, a handled 503 such as "TMDB didn't answer")
 * still shows the server's own sentence, and so does an error this app raised with a
 * sentence of its own.
 */
export const NO_SIGNAL = "No signal — showing what's saved."
export const SERVER_FAULT = 'The archive had a problem. Try again in a minute.'
export const OUT_OF_DATE = 'This screen needs the newest version.'

export type ErrorKind = 'offline' | 'server' | 'outdated' | 'explained'

const CHUNK_FAILURE =
  /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS/i

/** The API's own words for a fault it could not explain, or no words at all. */
const GENERIC_SERVER_TEXT = /^(HTTP 5\d\d|Internal Server Error|The server did not answer\.)$/

function statusOf(error: Error): number | undefined {
  const status = (error as { status?: unknown }).status
  return typeof status === 'number' ? status : undefined
}

export function isChunkFailure(error: unknown): boolean {
  return error instanceof Error && CHUNK_FAILURE.test(error.message)
}

export function classifyError(error: unknown): ErrorKind {
  if (!(error instanceof Error)) return 'explained'
  if (error.name === 'ZodError' || isChunkFailure(error)) return 'outdated'
  const status = statusOf(error)
  if (status !== undefined && status >= 500) {
    return GENERIC_SERVER_TEXT.test(error.message) ? 'server' : 'explained'
  }
  // A body that was not JSON: a proxy's or an edge's page, not the API.
  if (error.name === 'SyntaxError') return 'server'
  if (error.name === 'TypeError' || error.name === 'NetworkError') return 'offline'
  return 'explained'
}

/** The sentence for ``error``; ``fallback`` when it carries none. */
export function describeError(error: unknown, fallback: string): string {
  switch (classifyError(error)) {
    case 'offline':
      return NO_SIGNAL
    case 'server':
      return SERVER_FAULT
    case 'outdated':
      return OUT_OF_DATE
    default:
      return error instanceof Error && error.message ? error.message : fallback
  }
}

/** Raised on `window` when a screen meets an API newer than this build; the banner listens. */
export const OUT_OF_DATE_EVENT = 'mcu:out-of-date'

export function reportIfOutOfDate(error: unknown): void {
  if (typeof window !== 'undefined' && classifyError(error) === 'outdated') {
    window.dispatchEvent(new Event(OUT_OF_DATE_EVENT))
  }
}

const RELOADED_AT = 'mcu.chunkReloadAt'

/**
 * Reload once after a chunk failed to load: a deploy replaced the build this page is
 * running, and only a full reload fetches the new one. Once — if the reload did not help
 * within a minute, reloading again would loop; the screen says it needs the newest version
 * instead. Returns whether it reloaded.
 */
export function reloadOnceForNewBuild(now: number = Date.now()): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOADED_AT) ?? 0)
    if (now - last < 60_000) return false
    sessionStorage.setItem(RELOADED_AT, String(now))
  } catch {
    return false
  }
  window.location.reload()
  return true
}
