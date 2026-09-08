/**
 * When an unusable response should end the session, and when it should not.
 *
 * Extracted from `AuthProvider` so the rule is stated once and can be tested without a
 * DOM — and because getting it wrong is not a cosmetic bug: the previous behaviour
 * cleared the tokens for *any* non-ok response, so the first time the app was opened
 * without signal it signed the person out and destroyed the session their queued offline
 * writes were made under (`DECISIONS.md` #48).
 */
export function shouldEndSession(status: number): boolean {
  // Only these mean the credentials were examined and refused. A 5xx, a 408, a 429 or
  // anything from a gateway means nobody looked at them, and the session is still good.
  return status === 401 || status === 403
}
