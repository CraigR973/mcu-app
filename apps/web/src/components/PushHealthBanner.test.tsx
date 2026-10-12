import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { PushStoppedNotice } from './PushHealthBanner'

function markup(devices: { items: never[]; total: number; stoppedAt: string | null }) {
  return renderToStaticMarkup(
    <MemoryRouter>
      <PushStoppedNotice devices={devices} />
    </MemoryRouter>,
  )
}

describe('PushStoppedNotice — Batch X3', () => {
  it('stays until notifications are on again, when the last device was refused', () => {
    const html = markup({ items: [], total: 0, stoppedAt: '2026-10-08T00:21:00Z' })
    expect(html).toContain('Notifications stopped reaching your phone on 8 Oct.')
    expect(html).toContain('href="/settings"')
  })

  it('is not there with a live device, or when nothing was ever refused', () => {
    expect(markup({ items: [], total: 0, stoppedAt: null })).toBe('')
    expect(markup({ items: [], total: 1, stoppedAt: null })).toBe('')
  })
})
