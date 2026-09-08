import { describe, expect, it } from 'vitest'

import { shouldEndSession } from './session'

describe('shouldEndSession', () => {
  it('ends the session only when the credentials were actually refused', () => {
    expect(shouldEndSession(401)).toBe(true)
    expect(shouldEndSession(403)).toBe(true)
  })

  it('keeps the session through anything that is not an answer about the credentials', () => {
    // The regression: a 503 from a restarting container used to clear the tokens, so
    // opening the app without signal signed the person out — and took the session their
    // queued offline writes were made under with it.
    for (const status of [408, 429, 500, 502, 503, 504]) {
      expect(shouldEndSession(status)).toBe(false)
    }
  })

  it('does not end the session on a 404 or a 422 either', () => {
    // Neither is a statement about who you are.
    expect(shouldEndSession(404)).toBe(false)
    expect(shouldEndSession(422)).toBe(false)
  })
})
