// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { PersonPage as Person } from '@mcu/shared'

const api = vi.hoisted(() => ({ fetchPerson: vi.fn(), fetchProfilePhoto: vi.fn() }))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: 'p-craig', displayName: 'Craig', role: 'admin' } }) }))
vi.mock('@/lib/api', async (original) => ({ ...(await original<typeof import('@/lib/api')>()), ...api }))
import { ApiError } from '@/lib/api'
import PersonPage from './PersonPage'

const MARK = '00000000-0000-4000-8000-0000000000aa'
const FILM = '00000000-0000-4000-8000-0000000000bb'
const page: Person = {
  profileId: MARK, displayName: 'Mark', isYou: false, watchedThisYear: 41, watchedTotal: 972,
  diary: [{ movieId: FILM, title: 'Alien', year: 1979, posterPath: null, watchedOn: '2025-11-08', rating: 4.5, rewatch: true }],
  recentlyAdded: [{ copyId: '00000000-0000-4000-8000-0000000000cc', movieId: FILM, title: 'Alien', posterPath: null, formats: ['blu_ray', '4k_uhd'], addedOn: '2025-11-05' }],
  wants: [{ movieId: FILM, title: 'Heat', year: 1995, posterPath: null }], wantsTotal: 23,
  loans: [{ loanId: '00000000-0000-4000-8000-0000000000dd', movieId: FILM, title: 'Jaws', posterPath: null, state: 'asked_for', lentDate: null, dueDate: null, neededBy: '2025-11-12' }],
}

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/people/:profileId" element={<PersonPage />} />
          <Route path="/you" element={<p>Your page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => { api.fetchPerson.mockResolvedValue(page); api.fetchProfilePhoto.mockRejectedValue(new Error('no photo')) })
afterEach(() => { cleanup(); vi.resetAllMocks() })

it('reads another person’s diary, shelves, wants and loans, and nothing else (AE9)', async () => {
  show(`/people/${MARK}`)
  expect(await screen.findByRole('heading', { level: 1, name: 'Mark' })).not.toBeNull()
  expect(screen.getByText('41 films watched this year · 972 films in all')).not.toBeNull()
  const diary = screen.getByRole('region', { name: 'Lately in the diary' })
  expect(within(diary).getByRole('link').getAttribute('href')).toBe(`/movies/${FILM}`)
  expect(within(diary).getByRole('link').textContent).toContain('rated 4.5 · rewatch')
  expect(within(screen.getByRole('region', { name: 'Added lately' })).getByRole('link').textContent).toContain('4K UHD + Blu-ray')
  expect(screen.getByRole('heading', { name: 'Wants · 23' })).not.toBeNull()
  expect(screen.getByText('And 22 more on Wanted.')).not.toBeNull()
  expect(within(screen.getByRole('region', { name: 'Has now' })).getByRole('link').textContent).toContain('Asked for · needed by 12 Nov 2025')
  expect(api.fetchPerson).toHaveBeenCalledWith(MARK)
  // Nothing from Settings is asked for or shown.
  expect(screen.queryByText(/PIN|notification|session|eBay/i)).toBeNull()
})

it('opens You for the reader’s own page, without asking for it', async () => {
  show('/people/p-craig')
  expect(await screen.findByText('Your page')).not.toBeNull()
  expect(api.fetchPerson).not.toHaveBeenCalled()
})

it('says when there is no such person', async () => {
  api.fetchPerson.mockRejectedValue(new ApiError('No such person', 404))
  show(`/people/${MARK}`)
  expect(await screen.findByText('No such person')).not.toBeNull()
})

it('says what is empty, section by section, for a person with no diary', async () => {
  api.fetchPerson.mockResolvedValue({ ...page, watchedThisYear: 0, watchedTotal: 0, diary: [], recentlyAdded: [], wants: [], wantsTotal: 0, loans: [] })
  show(`/people/${MARK}`)
  expect(await screen.findByText('Nothing in Mark’s diary yet.')).not.toBeNull()
  expect(screen.getByText('0 films watched this year · 0 films in all')).not.toBeNull()
  expect(screen.getByText('Mark has no discs out.')).not.toBeNull()
})
