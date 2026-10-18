// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MobileTabBar } from './MobileTabBar'

afterEach(() => {
  cleanup()
})

function renderBar(onOpenSearch = vi.fn()) {
  render(
    <MemoryRouter initialEntries={['/movies']}>
      <MobileTabBar onOpenSearch={onOpenSearch} />
    </MemoryRouter>,
  )
  return within(screen.getByRole('navigation', { name: 'Primary mobile navigation' }))
}

describe('MobileTabBar — Batch T3', () => {
  it('is five slots in the agreed order, with no "More"', () => {
    const bar = renderBar()
    const slots = [...bar.getAllByRole('link'), ...bar.getAllByRole('button')]
    expect(slots).toHaveLength(5)
    const labels = Array.from(screen.getByRole('navigation').children).map((slot) => slot.textContent)
    expect(labels).toEqual(['Home', 'Archive', 'Add', 'Movie night', 'Search'])
    expect(bar.queryByText('More')).toBeNull()
  })

  it('uses labels no smaller than 12px (Batch X12b raised the floor from 11px)', () => {
    const bar = renderBar()
    for (const slot of [...bar.getAllByRole('link'), ...bar.getAllByRole('button')]) {
      expect(slot.className).toContain('text-xs')
      expect(slot.className).not.toContain('text-[0.6875rem]')
    }
  })

  it('opens search from its slot', () => {
    const onOpenSearch = vi.fn()
    const bar = renderBar(onOpenSearch)
    fireEvent.click(bar.getByRole('button', { name: 'Search the archive' }))
    expect(onOpenSearch).toHaveBeenCalledOnce()
  })

  it('marks the page you are on', () => {
    const bar = renderBar()
    expect(bar.getByRole('link', { name: 'Archive' }).getAttribute('aria-current')).toBe('page')
  })
})
