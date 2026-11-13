import { useCallback, useLayoutEffect, useRef } from 'react'

import { holdPlace, mainPanel, restore } from '@/lib/scroll-memory'

/**
 * A panel shown in place of its page — a completion set on Home or on the list of sets — opens at
 * its top, and closing it puts the page back where it was: AF4 (#372, snag 4).
 *
 * The page's place is taken when the panel is asked for, before the panel replaces the page and
 * the panel's own height moves it. Pass `open` to the returned function in place of the panel's
 * own setter.
 */
export function useInPlaceScroll<T>(set: (value: T | null) => void, current: T | null): (value: T | null) => void {
  const place = useRef<number | null>(null)
  const was = useRef(current !== null)
  useLayoutEffect(() => {
    const open = current !== null
    if (open === was.current) return undefined
    was.current = open
    const main = mainPanel()
    if (open) {
      if (main) main.scrollTop = 0
      return undefined
    }
    holdPlace(null)
    const top = place.current
    place.current = null
    return top === null ? undefined : restore({ main: top })
  }, [current])
  // Let the page's place go if the page leaves while the panel is open.
  useLayoutEffect(() => () => holdPlace(null), [])
  return useCallback((value: T | null) => {
    if (value !== null && place.current === null) {
      place.current = mainPanel()?.scrollTop ?? 0
      holdPlace(place.current)
    }
    set(value)
  }, [set])
}
