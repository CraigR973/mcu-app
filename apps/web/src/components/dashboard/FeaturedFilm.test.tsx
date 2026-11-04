// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ dealLuckyFilm: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import { FeaturedFilm } from './FeaturedFilm'
import type { FeaturedPick } from '@/lib/home-films'

const PICK: FeaturedPick = {
  movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401',
  title: 'The Suspect',
  posterPath: null,
  eyebrow: 'Worth a rewatch',
  detail: 'You gave it ★ 5 and last saw it on 20 Jan 2024.',
}

const DEALT = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3402',
  title: 'Gentle Monster',
  year: 2025,
  runtimeMinutes: 104,
  posterPath: null,
  lastWatchedAt: null,
  locations: [{ label: 'Front 2nd' }],
}

function renderCard(pick: FeaturedPick | null, homeLayoutPending = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FeaturedFilm pick={pick} homeLayoutPending={homeLayoutPending} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.dealLuckyFilm.mockResolvedValue({ film: DEALT })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('FeaturedFilm — AC2, Feeling lucky inside it (#337)', () => {
  it('leads with the film Home picked, and opening it is the choice', () => {
    renderCard(PICK)
    expect(screen.getByRole('heading', { name: 'The Suspect' })).not.toBeNull()
    expect(screen.getByText('Worth a rewatch')).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Open the film' }).getAttribute('href')).toBe(`/movies/${PICK.movieId}`)
  })

  it('deals another film, never the one on screen, with the unwatched-only switch', async () => {
    renderCard(PICK)
    const lucky = within(screen.getByRole('group', { name: 'Feeling lucky' }))
    fireEvent.click(lucky.getByRole('checkbox', { name: 'Only films I haven’t watched' }))
    fireEvent.click(lucky.getByRole('button', { name: 'Deal another' }))
    await waitFor(() => expect(api.dealLuckyFilm).toHaveBeenCalledWith({ excludedIds: [PICK.movieId], unwatchedOnly: true, sessionId: undefined }))
    expect(await screen.findByRole('heading', { name: 'Gentle Monster' })).not.toBeNull()
    expect(screen.getByText('From the Archive')).not.toBeNull()
    expect(screen.getByText('2025 · 104 min. No watch logged by you. Front 2nd')).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Open the film' }).getAttribute('href')).toBe(`/movies/${DEALT.id}`)
    // The run has started: the switch holds, and the run can start again.
    expect((screen.getByRole('checkbox', { name: 'Only films I haven’t watched' }) as HTMLInputElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Deal another' }))
    await waitFor(() => expect(api.dealLuckyFilm).toHaveBeenLastCalledWith({ excludedIds: [PICK.movieId, DEALT.id], unwatchedOnly: true, sessionId: undefined }))
  })

  it('says so at the end of a run, and starts again from the picked film', async () => {
    api.dealLuckyFilm.mockResolvedValue({ film: null })
    renderCard(PICK)
    fireEvent.click(screen.getByRole('button', { name: 'Deal another' }))
    expect(await screen.findByText('No more films for this run. Start again to deal a fresh run.')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Deal another' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Start again' }))
    expect(screen.getByRole('heading', { name: 'The Suspect' })).not.toBeNull()
  })

  it('takes no tap while Home\'s first layout arrives — AB7', () => {
    renderCard(PICK, true)
    const lucky = within(screen.getByRole('group', { name: 'Feeling lucky' }))
    expect((lucky.getByRole('button', { name: 'Deal another' }) as HTMLButtonElement).disabled).toBe(true)
    expect((lucky.getByRole('checkbox', { name: 'Only films I haven’t watched' }) as HTMLInputElement).disabled).toBe(true)
    expect(lucky.getByRole('status').textContent).toBe('Loading Home…')
  })

  it('invites a first deal when Home has nothing to feature', () => {
    renderCard(null)
    expect(screen.getByRole('heading', { name: 'Let the Archive choose' })).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Deal a film' })).not.toBeNull()
    expect(screen.queryByRole('link', { name: 'Open the film' })).toBeNull()
  })
})
