import { useCallback, useEffect, useState } from 'react'

/**
 * The time a saved cinema programme is judged against — AB7, shared since AC4 by At the cinema
 * and the film page.
 *
 * A page left open keeps its listing, so a ticket link must lapse as its showing starts or its
 * check grows stale without waiting for a new answer: the clock moves every 30 seconds, and at
 * once when the page regains focus or the connection changes. `tick` moves it on demand.
 */
export function useProgrammeClock(): [number, () => void] {
  const [now, setNow] = useState(Date.now)
  const tick = useCallback(() => setNow(Date.now()), [])
  useEffect(() => {
    const timer = window.setInterval(tick, 30_000)
    window.addEventListener('focus', tick)
    window.addEventListener('online', tick)
    window.addEventListener('offline', tick)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', tick)
      window.removeEventListener('online', tick)
      window.removeEventListener('offline', tick)
    }
  }, [tick])
  return [now, tick]
}
