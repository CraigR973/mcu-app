import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bookmark, Loader2, RotateCcw } from 'lucide-react'
import type { CompletionFilm } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { addWanted, countCompletionFilmAgain, excludeCompletionFilm } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/** After any change to a set's films: both completion reads, and Wanted, read again. */
function useRefresh(): () => void {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['completion-insights'] })
    void queryClient.invalidateQueries({ queryKey: ['completion-set'] })
    void queryClient.invalidateQueries({ queryKey: ['wanted'] })
    void queryClient.invalidateQueries({ queryKey: ['recommendations'] })
  }
}

/**
 * Want a missing film, through the existing Wanted path — AE3 (#355, point 3). Adding to
 * Wanted is Craig's (the route is admin-only), so `canAdd` is false for Mark, who still sees
 * that a film is wanted: Wanted is shared.
 */
export function WantFilm({ tmdbId, wanted, canAdd, label = 'Want' }: { tmdbId: number; wanted: boolean; canAdd: boolean; label?: string }) {
  const refresh = useRefresh()
  const add = useMutation({ mutationFn: () => addWanted({ tmdbId }), onSuccess: refresh })

  if (wanted || add.isSuccess) return <span className="shrink-0 text-xs font-semibold text-primary">Wanted</span>
  if (!canAdd) return null
  return (
    <span className="shrink-0">
      <Button type="button" size="sm" variant="outline" disabled={add.isPending} onClick={() => add.mutate()}>
        {add.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Bookmark className="h-4 w-4" aria-hidden />}
        {label}
      </Button>
      {add.isError ? <span role="alert" className="mt-1 block text-xs text-destructive">{queryErrorMessage(add.error, 'This film could not be added to Wanted.')}</span> : null}
    </span>
  )
}

/**
 * "Doesn't count": for a lost film, a TV episode or another version, in this set only — AE3.
 * Either person may; the server audits it. The film still counts in every other set.
 */
export function DoesNotCount({ setId, film }: { setId: string; film: CompletionFilm }) {
  const refresh = useRefresh()
  const exclude = useMutation({ mutationFn: () => excludeCompletionFilm(setId, film.tmdbId), onSuccess: refresh })
  return (
    <span className="shrink-0">
      <Button type="button" size="sm" variant="ghost" disabled={exclude.isPending} onClick={() => exclude.mutate()}>
        {exclude.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
        Doesn’t count
        <span className="sr-only"> toward this set: {film.title}</span>
      </Button>
      {exclude.isError ? <span role="alert" className="mt-1 block text-xs text-destructive">{queryErrorMessage(exclude.error, 'That could not be saved. Try again.')}</span> : null}
    </span>
  )
}

/** "Count it again" — undoes "Doesn't count" for this set. */
export function CountItAgain({ setId, film }: { setId: string; film: CompletionFilm }) {
  const refresh = useRefresh()
  const include = useMutation({ mutationFn: () => countCompletionFilmAgain(setId, film.tmdbId), onSuccess: refresh })
  return (
    <span className="shrink-0">
      <Button type="button" size="sm" variant="outline" disabled={include.isPending} onClick={() => include.mutate()}>
        {include.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <RotateCcw className="h-4 w-4" aria-hidden />}
        Count it again
        <span className="sr-only">: {film.title}</span>
      </Button>
      {include.isError ? <span role="alert" className="mt-1 block text-xs text-destructive">{queryErrorMessage(include.error, 'That could not be saved. Try again.')}</span> : null}
    </span>
  )
}
