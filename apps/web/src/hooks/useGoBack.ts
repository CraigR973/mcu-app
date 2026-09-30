import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

/**
 * Back through history when the app has some, and otherwise to `fallback` — Batch V1.
 *
 * React Router gives the first page of a visit the key `default`: a page opened from a
 * notification or a shared link has nothing in the app behind it, and `navigate(-1)` there
 * would leave the app altogether. The phone's top bar and the film page share this, so the
 * two back controls cannot disagree about where "back" is.
 */
export function useGoBack(fallback: string): () => void {
  const { key } = useLocation()
  const navigate = useNavigate()
  return useCallback(() => {
    if (key === 'default') navigate(fallback)
    else navigate(-1)
  }, [key, navigate, fallback])
}
