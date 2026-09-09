// @vitest-environment happy-dom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { useRecentItems, type RecentItem } from './useRecentItems'

function item(id: string): RecentItem {
  return { id, title: `Film ${id}`, year: 2020, posterPath: null }
}

afterEach(() => {
  cleanup()
  localStorage.clear()
})

describe('useRecentItems', () => {
  it('starts empty when nothing has been viewed yet', () => {
    const { result } = renderHook(() => useRecentItems())
    expect(result.current.recentItems).toEqual([])
  })

  it('adds the most recently viewed film to the front', () => {
    const { result } = renderHook(() => useRecentItems())

    act(() => result.current.addRecentItem(item('a')))
    act(() => result.current.addRecentItem(item('b')))

    expect(result.current.recentItems.map((i) => i.id)).toEqual(['b', 'a'])
  })

  it('moves a re-viewed film back to the front instead of duplicating it', () => {
    const { result } = renderHook(() => useRecentItems())

    act(() => result.current.addRecentItem(item('a')))
    act(() => result.current.addRecentItem(item('b')))
    act(() => result.current.addRecentItem(item('a')))

    expect(result.current.recentItems.map((i) => i.id)).toEqual(['a', 'b'])
  })

  it('caps the list at 8 films, dropping the oldest', () => {
    const { result } = renderHook(() => useRecentItems())

    for (let i = 0; i < 10; i++) {
      act(() => result.current.addRecentItem(item(String(i))))
    }

    expect(result.current.recentItems).toHaveLength(8)
    expect(result.current.recentItems[0].id).toBe('9')
    expect(result.current.recentItems.map((i) => i.id)).not.toContain('0')
    expect(result.current.recentItems.map((i) => i.id)).not.toContain('1')
  })

  it('persists across hook instances, the way a palette reopened after a page navigation needs', () => {
    const first = renderHook(() => useRecentItems())
    act(() => first.result.current.addRecentItem(item('a')))
    first.unmount()

    const second = renderHook(() => useRecentItems())
    expect(second.result.current.recentItems.map((i) => i.id)).toEqual(['a'])
  })
})
