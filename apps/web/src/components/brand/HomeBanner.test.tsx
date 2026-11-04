// @vitest-environment happy-dom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const cache = vi.hoisted(() => ({
  bannerName: vi.fn(() => 'letters-v1-1125'),
  cachedBanner: vi.fn<(name: string) => string | null>(),
  loadBanner: vi.fn<(name: string) => Promise<string>>(),
}))
vi.mock('@/lib/banner-cache', () => cache)

import { HomeBanner } from './HomeBanner'

const ART = 'data:image/webp;base64,UklGRg=='

beforeEach(() => {
  cache.cachedBanner.mockReturnValue(null)
  cache.loadBanner.mockResolvedValue(ART)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('HomeBanner — AC2, treatment T1 (#337)', () => {
  it('names the brand once and sets the subtitle as real text', () => {
    render(<HomeBanner />)
    expect(screen.getByRole('img', { name: "MARK'S Cinematic Universe" })).not.toBeNull()
    expect(screen.getByText('Cinematic Universe')).not.toBeNull()
  })

  it('draws from the device when it has the artwork: no request, no grey box', () => {
    cache.cachedBanner.mockReturnValue(ART)
    const { container } = render(<HomeBanner />)
    expect(container.querySelector('img')?.getAttribute('src')).toBe(ART)
    expect(container.querySelector('.animate-pulse')).toBeNull()
    expect(cache.loadBanner).not.toHaveBeenCalled()
  })

  it('keeps the letters\' shape while the first load arrives, then shows them', async () => {
    const { container } = render(<HomeBanner />)
    const box = container.querySelector('[style*="aspect-ratio"]') as HTMLElement
    expect(box.style.aspectRatio).not.toBe('')
    expect(container.querySelector('.animate-pulse')).not.toBeNull()
    await waitFor(() => expect(container.querySelector('img')?.getAttribute('src')).toBe(ART))
    expect(cache.loadBanner).toHaveBeenCalledWith('letters-v1-1125')
  })

  it('leaves the reserved box, not a hole, when the artwork cannot be read', async () => {
    cache.loadBanner.mockRejectedValue(new Error('Brand artwork could not be loaded.'))
    const { container } = render(<HomeBanner />)
    await waitFor(() => expect(cache.loadBanner).toHaveBeenCalled())
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('[style*="aspect-ratio"]')).not.toBeNull()
  })
})
