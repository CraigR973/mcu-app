// @vitest-environment happy-dom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

// The four panels each read the API; this file is about the tabs around them.
vi.mock('@/components/settings/EbayAccountPanel', () => ({ EbayAccountPanel: () => <p>The eBay panel</p> }))
vi.mock('@/components/settings/WatchHistoryPanel', () => ({ WatchHistoryPanel: () => <p>The history panel</p> }))
vi.mock('./NotificationSettingsPage', () => ({ NotificationSettings: () => <p>The notifications panel</p> }))
vi.mock('./AiSettingsPage', () => ({ AiSettings: () => <p>The assistant panel</p> }))

import SettingsPage from './SettingsPage'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('Settings — Batch T8b', () => {
  it("opens on the tab a link names, eBay's included, and brings it into view on a phone", () => {
    const scrolled: Element[] = []
    vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(function (this: Element) {
      scrolled.push(this)
    })
    render(
      <MemoryRouter initialEntries={['/settings?tab=ebay']}>
        <SettingsPage />
      </MemoryRouter>,
    )

    const tab = screen.getByRole('tab', { name: 'eBay' })
    expect(tab.getAttribute('aria-selected')).toBe('true')
    expect(screen.getByText('The eBay panel')).not.toBeNull()
    expect(scrolled).toContain(tab)
  })
})
