// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import SearchBar from './SearchBar'

function renderSearchBar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SearchBar />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
})

describe('SearchBar', () => {
  it('focuses and selects its input on mcu:focus-search — the "/" shortcut now dispatches this rather than owning the keydown itself', () => {
    renderSearchBar()
    const input = screen.getByLabelText('Search films') as HTMLInputElement

    window.dispatchEvent(new Event('mcu:focus-search'))

    expect(document.activeElement).toBe(input)
  })

  it('still closes its own dropdown on Escape', () => {
    renderSearchBar()
    const input = screen.getByLabelText('Search films') as HTMLInputElement
    input.focus()

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(document.activeElement).not.toBe(input)
  })
})
