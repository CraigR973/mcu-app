// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ fetchStreaming: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchStreaming: mocks.fetchStreaming,
}))

import { StreamingPanel } from './StreamingPanel'

const MOVIE_ID = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'

beforeEach(() => {
  mocks.fetchStreaming.mockReset()
})
afterEach(() => {
  cleanup()
})

describe('StreamingPanel — the JustWatch credit (Batch X12c, CT46-06)', () => {
  it('credits JustWatch under the providers it lists', async () => {
    mocks.fetchStreaming.mockResolvedValue({
      movieId: MOVIE_ID,
      region: 'GB',
      link: 'https://www.themoviedb.org/movie/1/watch?locale=GB',
      offers: [{ kind: 'flatrate', providerId: 8, providerName: 'Netflix', logoPath: '/n.jpg' }],
      unidentified: false,
      unavailable: false,
    })
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <StreamingPanel movieId={MOVIE_ID} />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('Netflix')).not.toBeNull()
    expect(screen.getByText(/via TMDB, data from JustWatch/)).not.toBeNull()
  })
})
