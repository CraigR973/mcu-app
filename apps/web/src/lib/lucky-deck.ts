import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { dealLuckyFilm, type MovieListItem } from './api'

/**
 * AA6's deal: one film at a time from the Archive, never the same twice in a run.
 *
 * Shared by Feeling lucky and Home's featured film (AC2, #337). `alsoExclude` keeps a film
 * already on screen out of the first deal, so "Deal another" means another.
 */
export function useLuckyDeck({ sessionId, alsoExclude = [] }: { sessionId?: string; alsoExclude?: readonly string[] }) {
  const [unwatchedOnly, setUnwatchedOnly] = useState(false)
  const [started, setStarted] = useState(false)
  const [seen, setSeen] = useState<string[]>([])
  const [film, setFilm] = useState<MovieListItem | null>(null)
  const [exhausted, setExhausted] = useState(false)
  const draw = useMutation({
    mutationFn: (excludedIds: string[]) => dealLuckyFilm({ excludedIds, unwatchedOnly, sessionId }),
    onSuccess: ({ film: next }) => {
      setFilm(next)
      setExhausted(next === null)
      if (next) setSeen((ids) => [...ids, next.id])
    },
  })
  const deal = () => {
    setStarted(true)
    draw.mutate([...new Set([...alsoExclude, ...seen])])
  }
  const reset = () => {
    setStarted(false)
    setSeen([])
    setFilm(null)
    setExhausted(false)
    draw.reset()
  }
  return { unwatchedOnly, setUnwatchedOnly, started, film, exhausted, draw, deal, reset }
}
