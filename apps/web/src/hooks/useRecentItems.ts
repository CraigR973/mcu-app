import { useCallback, useState } from 'react'

export interface RecentItem {
  id: string
  title: string
  year: number | null
  posterPath: string | null
}

const STORAGE_KEY = 'mcu:recent-items:v1'
const MAX_ITEMS = 8

function read(): RecentItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as RecentItem[]) : []
  } catch {
    return []
  }
}

function write(items: RecentItem[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  } catch {
    // Recent items are a convenience; private browsing can refuse local storage.
  }
}

/** Recently-viewed films for the command palette's empty-query state. Each instance
 *  re-reads localStorage on mount, so a palette that unmounts on close (see
 *  CommandPalette) always opens with what the last viewed film actually wrote. */
export function useRecentItems() {
  const [recentItems, setRecentItems] = useState<RecentItem[]>(() => read())

  const addRecentItem = useCallback((item: RecentItem) => {
    setRecentItems((prev) => {
      const next = [item, ...prev.filter((existing) => existing.id !== item.id)].slice(0, MAX_ITEMS)
      write(next)
      return next
    })
  }, [])

  return { recentItems, addRecentItem }
}
