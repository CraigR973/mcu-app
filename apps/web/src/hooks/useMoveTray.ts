import { useCallback, useSyncExternalStore } from 'react'

import type { CollectionCopy } from '@/lib/api'

/**
 * A disc waiting to be moved — Batch Y2 (`DECISIONS.md` #265).
 *
 * Carries what the tray shows and what the move needs: `updatedAt` is the version it was
 * picked at, so a disc changed on the other phone meanwhile is reported rather than
 * overwritten, and the place it was in is what "Move them back" restores.
 */
export interface TrayDisc {
  itemId: string
  movieId: string
  title: string
  formats: string[]
  edition: string | null
  location: string | null
  section: string | null
  shelf: string | null
  updatedAt: string
}

const STORAGE_KEY = 'mcu-move-tray'
const listeners = new Set<() => void>()
let cache: TrayDisc[] | null = null

function isTrayDisc(value: unknown): value is TrayDisc {
  if (!value || typeof value !== 'object') return false
  const disc = value as Record<string, unknown>
  return typeof disc.itemId === 'string' && typeof disc.movieId === 'string'
    && typeof disc.title === 'string' && typeof disc.updatedAt === 'string'
    && Array.isArray(disc.formats)
}

function read(): TrayDisc[] {
  if (cache) return cache
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    cache = Array.isArray(value) ? value.filter(isTrayDisc) : []
  } catch {
    // The tray is a convenience on this phone: unreadable storage is an empty tray.
    cache = []
  }
  return cache
}

function write(next: TrayDisc[]): void {
  cache = next
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // Still works for this visit when storage is unavailable.
  }
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** A copy as the read surface returns it, as the tray holds it. */
export function trayDiscFrom(copy: CollectionCopy, movieId: string, title: string): TrayDisc {
  return {
    itemId: copy.id,
    movieId,
    title,
    formats: copy.formats,
    edition: copy.edition,
    location: copy.location,
    section: copy.section,
    shelf: copy.shelf,
    updatedAt: copy.updatedAt,
  }
}

/** The discs picked for a move, kept on this phone across searches and visits. */
export function useMoveTray() {
  const discs = useSyncExternalStore(subscribe, read, () => [] as TrayDisc[])

  const add = useCallback((disc: TrayDisc) => {
    // Re-adding a disc refreshes it, so a newer version replaces the one picked earlier.
    write([...read().filter((held) => held.itemId !== disc.itemId), disc])
  }, [])
  const remove = useCallback((itemId: string) => {
    write(read().filter((held) => held.itemId !== itemId))
  }, [])
  const replace = useCallback((next: TrayDisc[]) => write(next), [])
  const clear = useCallback(() => write([]), [])
  const has = useCallback((itemId: string) => discs.some((held) => held.itemId === itemId), [discs])

  return { discs, add, remove, replace, clear, has }
}

/** Tests only: forget the module's copy so each test reads storage afresh. */
export function resetMoveTrayForTests(): void {
  cache = null
}
