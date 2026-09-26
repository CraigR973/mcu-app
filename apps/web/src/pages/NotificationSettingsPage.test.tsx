// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Toggle } from './NotificationSettingsPage'

afterEach(() => {
  cleanup()
})

/**
 * Found by Batch U3's browser check at 375 px: an absolute child of a `<button>` starts
 * where the button centres its content, so every switch that was on drew its knob past the
 * end of its track. There is no layout here to measure, so this pins the anchor the two
 * translations assume; the browser check measured the result.
 */
describe('Toggle', () => {
  it('anchors its knob to the left of the track, on and off', () => {
    for (const checked of [true, false]) {
      render(<Toggle checked={checked} onChange={vi.fn()} label="Upcoming releases" />)
      const knob = screen.getByRole('switch', { name: 'Upcoming releases' }).firstElementChild

      expect(knob?.className).toMatch(/(^|\s)left-0(\s|$)/)
      expect(knob?.className).toContain(checked ? 'translate-x-5' : 'translate-x-0.5')
      cleanup()
    }
  })

  it('reports the flipped value when pressed', () => {
    const onChange = vi.fn()
    render(<Toggle checked onChange={onChange} label="Deals" />)

    fireEvent.click(screen.getByRole('switch', { name: 'Deals' }))

    expect(onChange).toHaveBeenCalledWith(false)
  })
})
