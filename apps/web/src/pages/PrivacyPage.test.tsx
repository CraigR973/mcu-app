// @vitest-environment happy-dom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import PrivacyPage from './PrivacyPage'

afterEach(cleanup)

describe('The privacy page eBay links to — Batch T8b', () => {
  it('says what Connect eBay keeps, who sees it, and how it ends', () => {
    render(
      <MemoryRouter>
        <PrivacyPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: 'Privacy' })).not.toBeNull()
    expect(screen.getByText(/never sees or stores your eBay password/)).not.toBeNull()
    expect(screen.getByText(/Only you see your eBay lists in the app/)).not.toBeNull()
    expect(screen.getByText(/does not buy, bid, sell, message or change anything on eBay/)).not.toBeNull()
    expect(screen.getByText(/deletes its copy of your eBay sign-in/)).not.toBeNull()
  })
})
