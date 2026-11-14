import type { QueryClient } from '@tanstack/react-query'
import type { MovieNightSession, MovieNightSessionList } from '@mcu/shared'

import { fetchMovieNights } from './api'

/**
 * The night a film page adds a film to: the one the person picked, or else the newest open
 * night, read from the API as they tap rather than from the list already on the phone.
 *
 * That list can predate the newest night. On 13 Nov a film page opened seconds after "Start
 * movie night" still held the list read before the night existed, so "Add to movie night" put
 * the film on an older open night and opened that night instead (the end-to-end case that
 * failed twice on `main`). Reading the list again costs one small request on a tap.
 */
export async function nightForFilm(queryClient: QueryClient, picked: string): Promise<string> {
  if (picked) return picked
  const list = await queryClient.fetchQuery({ queryKey: ['movie-nights'], queryFn: fetchMovieNights, staleTime: 0 })
  const newest = list.items.find((night) => night.status === 'open')
  if (!newest) throw new Error('There is no open movie night to add it to.')
  return newest.id
}

/** A night just started goes at the top of the list on the phone at once, as the API orders
 *  it (newest first), so nothing reads the list without it while it is read again. */
export function withNewNight(list: MovieNightSessionList | undefined, night: MovieNightSession): MovieNightSessionList | undefined {
  return list ? { ...list, items: [night, ...list.items.filter((item) => item.id !== night.id)] } : list
}
