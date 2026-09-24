// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SpecBackfill, SpecQueue } from '@/lib/api'

const { backfillMock, queueMock, acceptMock, skipMock, startMock } = vi.hoisted(() => ({
  backfillMock: vi.fn(),
  queueMock: vi.fn(),
  acceptMock: vi.fn(),
  skipMock: vi.fn(),
  startMock: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchSpecBackfill: backfillMock,
  fetchSpecQueue: queueMock,
  acceptSpecPage: acceptMock,
  skipSpecDisc: skipMock,
  startSpecBatch: startMock,
}))

import SpecsPage from './SpecsPage'

const LOOKUP = '00000000-0000-4000-8000-000000000011'

const BACKFILL: SpecBackfill = {
  searchConfigured: true,
  halted: false,
  haltedReason: null,
  coverage: { discs: 1250, withSpecs: 140, accepted: 12, needsYou: 55, noMatch: 5, skipped: 1, notSearched: 1037 },
  run: {
    id: '00000000-0000-4000-8000-000000000001',
    trigger: 'job',
    status: 'budget_spent',
    startedAt: '2026-09-25T02:00:00Z',
    finishedAt: '2026-09-25T02:16:00Z',
    searchBudget: 150,
    searches: 150,
    searched: 150,
    accepted: 88,
    queued: 55,
    noMatch: 5,
    restored: 2,
    fetchBudget: 150,
    fetched: 88,
    applied: 86,
    sentBack: 2,
    fetchFailed: 0,
    lastError: null,
  },
  searchesThisMonth: 150,
  monthlyCeiling: 1500,
  searchesPerRun: 150,
  fetchesPerRun: 150,
}

const QUEUE: SpecQueue = {
  total: 60,
  items: [
    {
      lookupId: LOOKUP,
      collectionItemId: '00000000-0000-4000-8000-000000000012',
      movieId: '00000000-0000-4000-8000-000000000013',
      filmTitle: 'Fight Club',
      year: 1999,
      formatCode: 'blu_ray',
      location: 'Front 4th shelf',
      status: 'needs_you',
      note: '3 UK editions match. Pick the one on the shelf.',
      searchQuery: 'site:blu-ray.com Fight Club Blu-ray United Kingdom',
      candidates: [
        {
          url: 'https://www.blu-ray.com/movies/Fight-Club-Blu-ray/114797/',
          title: 'Fight Club Blu-ray (MetalPak) (United Kingdom)',
          country: 'United Kingdom',
          edition: 'MetalPak',
          matches: true,
          origin: 'search',
        },
        {
          url: 'https://www.blu-ray.com/movies/Fight-Club-Blu-ray/5587/',
          title: 'The page the 10 Sep test used; its edition was not confirmed',
          country: null,
          edition: null,
          matches: false,
          origin: 'restored',
        },
      ],
    },
  ],
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SpecsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  backfillMock.mockReset().mockResolvedValue(BACKFILL)
  queueMock.mockReset().mockResolvedValue(QUEUE)
  acceptMock.mockReset().mockResolvedValue({ lookupId: LOOKUP, status: 'accepted', acceptedUrl: null, how: 'confirmed' })
  skipMock.mockReset().mockResolvedValue({ lookupId: LOOKUP, status: 'skipped', acceptedUrl: null, how: null })
  startMock.mockReset()
})

afterEach(() => {
  cleanup()
})

describe('SpecsPage — Batch T7', () => {
  it('reports coverage against the Blu-ray and 4K discs, and the month’s searches', async () => {
    renderPage()
    expect(await screen.findByText('140 of 1,250 discs have specs')).not.toBeNull()
    expect(screen.getByText(/Brave searches this month: 150 of 1,500/)).not.toBeNull()
    expect(screen.getByText(/2 restored from 10 Sep/)).not.toBeNull()
  })

  it('lists a disc waiting for Craig with its candidates, UK first, and the 10 Sep page flagged', async () => {
    renderPage()
    const card = within(await screen.findByRole('article', { name: 'Fight Club' }))
    expect(card.getByText('1999 · Blu-ray · Front 4th shelf')).not.toBeNull()
    expect(card.getByText('3 UK editions match. Pick the one on the shelf.')).not.toBeNull()
    expect(card.getByText('UK')).not.toBeNull()
    expect(card.getByText('Used on 10 Sep')).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Need you (60)' })).not.toBeNull()
  })

  it('uses the page Craig picks, and nothing more', async () => {
    renderPage()
    const card = within(await screen.findByRole('article', { name: 'Fight Club' }))
    fireEvent.click(card.getAllByRole('button', { name: /Use this page/ })[0])
    await vi.waitFor(() => expect(acceptMock).toHaveBeenCalledTimes(1))
    expect(acceptMock).toHaveBeenCalledWith(LOOKUP, 'https://www.blu-ray.com/movies/Fight-Club-Blu-ray/114797/')
    expect(startMock).not.toHaveBeenCalled()
  })

  it('takes a pasted link, or a skip', async () => {
    renderPage()
    const card = within(await screen.findByRole('article', { name: 'Fight Club' }))
    fireEvent.change(card.getByRole('textbox', { name: /Blu-ray.com link for Fight Club/ }), {
      target: { value: ' https://www.blu-ray.com/movies/Fight-Club-Blu-ray/6715/ ' },
    })
    fireEvent.click(card.getByRole('button', { name: 'Use link' }))
    await vi.waitFor(() =>
      expect(acceptMock).toHaveBeenCalledWith(LOOKUP, 'https://www.blu-ray.com/movies/Fight-Club-Blu-ray/6715/'),
    )
    fireEvent.click(card.getByRole('button', { name: /Skip this disc/ }))
    await vi.waitFor(() => expect(skipMock).toHaveBeenCalledWith(LOOKUP))
  })

  it('says when searching is not set up, and hides the button when halted', async () => {
    backfillMock.mockResolvedValue({ ...BACKFILL, searchConfigured: false, halted: true, haltedReason: 'Blu-ray.com answered 403' })
    renderPage()
    expect(await screen.findByText(/the Brave key is missing/)).not.toBeNull()
    expect(screen.getByRole('alert').textContent).toContain('Blu-ray.com answered 403')
    expect(screen.queryByRole('button', { name: /Run a batch now/ })).toBeNull()
  })

  it('reports a batch that could not start', async () => {
    startMock.mockResolvedValue({ outcome: 'nothing_due', run: null })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Run a batch now/ }))
    expect(await screen.findByText('Nothing to search for or fetch right now.')).not.toBeNull()
  })
})
