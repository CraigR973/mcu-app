// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'

import { ApiError, NetworkError } from './api'
import {
  NO_SIGNAL,
  OUT_OF_DATE,
  SERVER_FAULT,
  describeError,
  reloadOnceForNewBuild,
} from './describe-error'

/** Batch X8 (UX48-03): one sentence for each failure a phone meets, never machine text. */
describe('describeError', () => {
  it('says no signal when fetch itself failed', () => {
    expect(describeError(new TypeError('Failed to fetch'), 'x')).toBe(NO_SIGNAL)
    expect(describeError(new TypeError('Load failed'), 'x')).toBe(NO_SIGNAL)
    expect(describeError(new NetworkError('Could not reach the server.', true), 'x')).toBe(NO_SIGNAL)
  })

  it('says the archive had a problem for a 5xx with no words of its own', () => {
    expect(describeError(new ApiError('HTTP 500', 500), 'x')).toBe(SERVER_FAULT)
    expect(describeError(new NetworkError('The server did not answer.', true, { status: 502 }), 'x')).toBe(SERVER_FAULT)
  })

  it("keeps a handled 503's own sentence", () => {
    const tmdb = "TMDB didn't answer. Try again in a moment."
    expect(describeError(new ApiError(tmdb, 503), 'x')).toBe(tmdb)
  })

  it('says the screen needs the newest version for a value this build cannot read', () => {
    const drift = z.enum(['blu_ray_com']).safeParse('dvdbeaver')
    expect(drift.success).toBe(false)
    if (!drift.success) expect(describeError(drift.error, 'x')).toBe(OUT_OF_DATE)
  })

  it('says so for a chunk a deploy removed', () => {
    const chunk = new TypeError(
      'Failed to fetch dynamically imported module: https://x/assets/WantedPage-abc.js',
    )
    expect(describeError(chunk, 'x')).toBe(OUT_OF_DATE)
  })

  // Batch 38: Safari (WebKit) words a removed chunk differently. Vercel answers an unknown
  // /assets/*.js with index.html, and WebKit refuses that for its MIME type, in these words;
  // the classifier did not know them, so an iPhone met "Something went wrong" instead.
  it("says so for a removed chunk in Safari's words as well as Chrome's and Firefox's", () => {
    for (const words of [
      "'text/html' is not a valid JavaScript MIME type.",
      'Importing a module script failed.',
      'error loading dynamically imported module: https://x/assets/WantedPage-abc.js',
    ]) {
      expect(describeError(new TypeError(words), 'x'), words).toBe(OUT_OF_DATE)
    }
  })

  it("keeps a refusal's own words, and falls back when there are none", () => {
    expect(describeError(new ApiError('That film is already wanted.', 409), 'x')).toBe(
      'That film is already wanted.',
    )
    expect(describeError('not an error', 'The fallback.')).toBe('The fallback.')
  })
})

describe('reloadOnceForNewBuild', () => {
  afterEach(() => {
    sessionStorage.clear()
    vi.unstubAllGlobals()
  })

  it('reloads once a minute at most, so a missing chunk cannot loop', () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { ...window.location, reload })

    expect(reloadOnceForNewBuild(1_000_000)).toBe(true)
    expect(reloadOnceForNewBuild(1_030_000)).toBe(false)
    expect(reloadOnceForNewBuild(1_070_000)).toBe(true)
    expect(reload).toHaveBeenCalledTimes(2)
  })
})
