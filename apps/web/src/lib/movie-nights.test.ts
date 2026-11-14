import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ fetchMovieNights: vi.fn() }))
vi.mock('./api', () => api)

import { nightForFilm, withNewNight } from './movie-nights'

const night = (id: string, status = 'open') => ({ id, status, createdAt: '2026-11-13T20:00:00Z', plannedStart: null }) as never

afterEach(() => vi.clearAllMocks())

describe('nightForFilm — the night a film page adds to', () => {
  it('keeps the night the person picked, asking nothing', async () => {
    expect(await nightForFilm(new QueryClient(), 'picked')).toBe('picked')
    expect(api.fetchMovieNights).not.toHaveBeenCalled()
  })

  it('reads the newest open night as it is now, not the list already on the phone', async () => {
    const client = new QueryClient()
    // The list read before the night was started: only an older night is open.
    client.setQueryData(['movie-nights'], { items: [night('older')], people: [] })
    api.fetchMovieNights.mockResolvedValue({ items: [night('just-started'), night('older'), night('done', 'ended')], people: [] })
    expect(await nightForFilm(client, '')).toBe('just-started')
    expect(api.fetchMovieNights).toHaveBeenCalledTimes(1)
  })

  it('says so when no night is open', async () => {
    api.fetchMovieNights.mockResolvedValue({ items: [night('done', 'ended')], people: [] })
    await expect(nightForFilm(new QueryClient(), '')).rejects.toThrow('There is no open movie night to add it to.')
  })
})

describe('withNewNight — a night just started', () => {
  it('goes at the top of the list on the phone, once', () => {
    const started = night('new')
    expect(withNewNight({ items: [night('older'), started], people: [] } as never, started)?.items.map((item) => item.id)).toEqual(['new', 'older'])
    expect(withNewNight(undefined, started)).toBeUndefined()
  })
})
