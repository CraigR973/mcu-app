// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import AddToCollectionPage from './AddToCollectionPage'

const BARCODE = '5051892211475'

afterEach(cleanup)

vi.mock('@/components/collection/BarcodeLookupPanel', () => ({
  default: ({
    onBarcodeChange,
    onManualSearch,
  }: {
    onBarcodeChange: (barcode: string | null) => void
    onManualSearch: (barcode: string) => void
  }) => (
    <div>
      <button type="button" onClick={() => onBarcodeChange(BARCODE)}>
        Simulate scan
      </button>
      <button type="button" onClick={() => onManualSearch(BARCODE)}>
        Simulate manual fallback
      </button>
    </div>
  ),
}))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AddToCollectionPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AddToCollectionPage barcode handoff', () => {
  it('treats an explicit title-tab switch as a fresh title-only add', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Simulate scan' }))
    fireEvent.click(screen.getByRole('tab', { name: 'Search title' }))

    expect(screen.queryByText(`Finding barcode ${BARCODE} manually`)).toBeNull()
  })

  it('retains the barcode when the lookup deliberately falls back to title search', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Simulate manual fallback' }))

    expect(screen.getByText(`Finding barcode ${BARCODE} manually`)).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Search title' }).getAttribute('aria-selected')).toBe(
      'true',
    )
  })
})
