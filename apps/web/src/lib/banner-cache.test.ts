// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const tokens = vi.hoisted(() => ({ authFetch: vi.fn() }))
vi.mock('./auth-tokens', () => tokens)

import { bannerName, cachedBanner, forgetBanners, loadBanner } from './banner-cache'

const PNG = new Uint8Array([0x52, 0x49, 0x46, 0x46])

beforeEach(() => {
  forgetBanners()
  localStorage.clear()
  tokens.authFetch.mockResolvedValue(new Response(new Blob([PNG], { type: 'image/webp' }), { status: 200 }))
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('banner cache — AC2', () => {
  it('asks for a phone\'s 3x width unless the screen needs more', () => {
    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(375)
    Object.defineProperty(window, 'devicePixelRatio', { value: 3, configurable: true })
    expect(bannerName()).toBe('letters-v1-1125')
    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(896)
    Object.defineProperty(window, 'devicePixelRatio', { value: 2, configurable: true })
    expect(bannerName()).toBe('letters-v1-1800')
  })

  it('fetches once with the person\'s token, then serves it from the device', async () => {
    expect(cachedBanner('letters-v1-1125')).toBeNull()
    const url = await loadBanner('letters-v1-1125')
    expect(tokens.authFetch).toHaveBeenCalledWith('/brand/heroes/letters-v1-1125')
    expect(url.startsWith('data:image/webp')).toBe(true)
    expect(localStorage.getItem('mcu.banner.letters-v1-1125')).toBe(url)
    expect(cachedBanner('letters-v1-1125')).toBe(url)
  })

  it('keeps only the newest artwork, and forgets it at sign-out', async () => {
    localStorage.setItem('mcu.banner.letters-v0-1125', 'data:image/webp;base64,old')
    await loadBanner('letters-v1-1125')
    expect(localStorage.getItem('mcu.banner.letters-v0-1125')).toBeNull()
    forgetBanners()
    expect(localStorage.getItem('mcu.banner.letters-v1-1125')).toBeNull()
    expect(cachedBanner('letters-v1-1125')).toBeNull()
  })

  it('refuses a refused answer rather than storing it', async () => {
    tokens.authFetch.mockResolvedValue(new Response('no', { status: 401 }))
    await expect(loadBanner('letters-v1-1125')).rejects.toThrow('Brand artwork could not be loaded.')
    expect(localStorage.getItem('mcu.banner.letters-v1-1125')).toBeNull()
  })
})
