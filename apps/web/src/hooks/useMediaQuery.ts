import { useEffect, useState } from 'react'

/**
 * Track a CSS media query from React.
 *
 * The initial value is read **synchronously**, not in an effect. That matters wherever the
 * query decides which artwork to request: an effect-initialised hook renders the mobile
 * asset first and swaps it a frame later, which is a visible flash of the wrong logo and a
 * wasted request. `matchMedia` is synchronous and available before first paint, so the
 * first render is already correct.
 *
 * Returns `false` where `matchMedia` does not exist — a non-browser test environment —
 * which is the narrow branch of every call site here.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
    return window.matchMedia(query).matches
  })

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const media = window.matchMedia(query)
    const apply = () => setMatches(media.matches)
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [query])

  return matches
}
