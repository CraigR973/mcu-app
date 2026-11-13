import { useEffect, useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'

import { forget, remember, remembered, restore, scrollToHeading } from '@/lib/scroll-memory'

/**
 * Back keeps your place — AF4 (#372, snag 4). Mounted once, inside the app's layout.
 *
 * Each step in history has its own places: Back and Forward put every marked scroll region back
 * where it was, once its page is drawn; a newly opened page starts at the top, or at the heading
 * its link names; a filter that replaces the address keeps the place.
 */
export function ScrollMemory() {
  const location = useLocation()
  const type = useNavigationType()
  const current = useRef(location.key)
  const first = useRef(true)

  // Written as the reader scrolls, so the last place is never lost to a page already replaced.
  useEffect(() => {
    if ('scrollRestoration' in window.history) window.history.scrollRestoration = 'manual'
    const onScroll = (event: Event) => {
      const target = event.target
      if (!(target instanceof HTMLElement)) return
      const region = target.dataset.scrollMemory
      if (region) remember(current.current, region, target.scrollTop)
    }
    document.addEventListener('scroll', onScroll, { capture: true, passive: true })
    return () => document.removeEventListener('scroll', onScroll, { capture: true })
  }, [])

  useLayoutEffect(() => {
    current.current = location.key
    if (first.current) {
      first.current = false
      // A page opened afresh is history's "default" step, which an earlier visit to another page
      // may have used too: its places are not this page's. A reloaded step keeps its own key.
      if (location.key === 'default') {
        forget('default')
        return undefined
      }
    }
    if (type === 'POP') {
      const positions = remembered(location.key)
      return positions ? restore(positions) : undefined
    }
    if (type === 'PUSH') {
      if (location.hash) return scrollToHeading(location.hash.slice(1))
      const main = document.querySelector<HTMLElement>('[data-scroll-memory="main"]')
      if (main) main.scrollTop = 0
    }
    // REPLACE: a filter or a matched listing's new address. The reader stays where they are.
    return undefined
  }, [location.key, location.hash, type])

  return null
}
