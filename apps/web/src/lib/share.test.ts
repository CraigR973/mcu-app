// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from 'vitest'

import { shareLink } from './share'

const LINK = { title: 'Movie night', url: 'https://example.com/movie-night/join/token' }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('shareLink — Batch T4', () => {
  it('uses the share sheet where there is one', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share, clipboard: { writeText: vi.fn() } })
    await expect(shareLink(LINK)).resolves.toBe('shared')
    expect(share).toHaveBeenCalledWith(LINK)
  })

  it('treats closing the share sheet as nothing having gone wrong', async () => {
    const share = vi.fn().mockRejectedValue(new DOMException('closed', 'AbortError'))
    const writeText = vi.fn()
    vi.stubGlobal('navigator', { share, clipboard: { writeText } })
    await expect(shareLink(LINK)).resolves.toBe('cancelled')
    expect(writeText).not.toHaveBeenCalled()
  })

  it('copies the link where there is no share sheet', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    await expect(shareLink(LINK)).resolves.toBe('copied')
    expect(writeText).toHaveBeenCalledWith(LINK.url)
  })
})
