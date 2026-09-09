// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ShortcutsHelpModal from './ShortcutsHelpModal'

afterEach(() => {
  cleanup()
})

describe('ShortcutsHelpModal', () => {
  it('renders nothing when closed', () => {
    render(<ShortcutsHelpModal open={false} onClose={() => {}} isAdmin={false} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('lists every documented shortcut for an admin', () => {
    render(<ShortcutsHelpModal open onClose={() => {}} isAdmin />)

    expect(screen.getByText('Open command palette')).not.toBeNull()
    expect(screen.getByText('Focus search')).not.toBeNull()
    expect(screen.getByText('Show all shortcuts')).not.toBeNull()
    expect(screen.getByText('Go to home')).not.toBeNull()
    expect(screen.getByText('Go to collection')).not.toBeNull()
    expect(screen.getByText('Go to wanted list')).not.toBeNull()
    expect(screen.getByText('Go to stats')).not.toBeNull()
    expect(screen.getByText('Add new item')).not.toBeNull()
    expect(screen.getByText('Close modal / clear search')).not.toBeNull()
  })

  it('hides the admin-only "add new item" row for a viewer', () => {
    render(<ShortcutsHelpModal open onClose={() => {}} isAdmin={false} />)
    expect(screen.queryByText('Add new item')).toBeNull()
  })

  it('does not list opening AI-assistant chat — Batch 31 has not shipped it', () => {
    render(<ShortcutsHelpModal open onClose={() => {}} isAdmin />)
    expect(screen.queryByText(/assistant/i)).toBeNull()
  })

  it('closes on Escape', () => {
    const onClose = vi.fn()
    render(<ShortcutsHelpModal open onClose={onClose} isAdmin={false} />)

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
