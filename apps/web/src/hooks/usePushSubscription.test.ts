// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'

import { base64UrlToBytes, guessDeviceLabel } from './usePushSubscription'

/**
 * The VAPID key conversion, which has no visible failure mode.
 *
 * `pushManager.subscribe` accepts any 65 bytes without complaint, the push service accepts
 * the resulting subscription, and every send answers `201`. Nothing arrives, and nothing
 * anywhere says why. That is the same silent shape as the encryption info strings in
 * `tests/test_webpush.py`, and it is why this tiny function has its own tests.
 */
describe('base64UrlToBytes', () => {
  it('decodes an unpadded base64url VAPID key to 65 bytes', () => {
    // A real uncompressed P-256 point: 0x04 then two 32-byte coordinates, 87 characters
    // of unpadded base64url — the exact shape `subscribe` is handed.
    const key =
      'BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8'

    const bytes = base64UrlToBytes(key)

    expect(bytes).toHaveLength(65)
    expect(bytes[0]).toBe(0x04)
  })

  it('translates the URL-safe alphabet rather than passing it through', () => {
    // `-` and `_` stand in for `+` and `/`. Decoding without the substitution throws or,
    // worse, silently yields different bytes.
    expect(Array.from(base64UrlToBytes('-_8'))).toEqual([0xfb, 0xff])
  })

  it('handles every padding remainder', () => {
    // Four base64 characters carry three bytes; two and three carry one and two. A VAPID
    // key is 87 characters — remainder 3 — so the unpadded case is the one in production.
    expect(base64UrlToBytes('AA')).toHaveLength(1)
    expect(base64UrlToBytes('AAA')).toHaveLength(2)
    expect(base64UrlToBytes('AAAA')).toHaveLength(3)
    expect(87 % 4).toBe(3)
  })

  it('returns bytes backed by a plain ArrayBuffer', () => {
    // `applicationServerKey` rejects a `SharedArrayBuffer`-backed view, and TypeScript
    // 5.7's inference makes that easy to reintroduce.
    expect(base64UrlToBytes('AAAA').buffer).toBeInstanceOf(ArrayBuffer)
  })
})

// happy-dom, for `navigator` and `atob`. The rest of the web suite runs in node; this
// file needs a browser global on both sides of the conversion it is testing.
describe('guessDeviceLabel', () => {
  it('names the device so the field is never empty on a phone', () => {
    // §6.2's criterion is about telling one device from another, and a list of two rows
    // both reading "Unnamed device" cannot demonstrate it.
    expect(guessDeviceLabel()).toBeTruthy()
  })
})
