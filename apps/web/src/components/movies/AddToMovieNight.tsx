import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Popcorn } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { fetchMovieNights, suggestMovieNightFilm } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { formatDateTime } from '@/lib/utils'

export function AddToMovieNight({ movieId }: { movieId: string }) {
  const [nightId, setNightId] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const nights = useQuery({ queryKey: ['movie-nights'], queryFn: fetchMovieNights })
  const openNights = (nights.data?.items ?? []).filter((night) => night.status === 'open')
  const chosen = openNights.find((night) => night.id === nightId)?.id ?? openNights[0]?.id ?? ''
  const add = useMutation({
    mutationFn: () => suggestMovieNightFilm(chosen, { movieId }),
    onSuccess: (list) => {
      queryClient.setQueryData(['movie-night-candidates', chosen], list)
      navigate(`/movie-night/${chosen}`)
    },
  })
  return (
    <div>
      {/* Keep one action row even while nights load or there are none. Inserting it
          later moves the film's other controls between pointer down and up. */}
      <div className="flex min-h-11 min-w-0 items-center gap-2">
        {openNights.length > 0 ? (
          <>
            {openNights.length > 1 ? (
              <select className="select-control min-w-0 max-w-xs flex-1" aria-label="Which movie night" value={chosen} onChange={(event) => setNightId(event.target.value)}>
                {openNights.map((night) => (
                  <option key={night.id} value={night.id}>
                    {night.plannedStart ? `Planned ${formatDateTime(night.plannedStart)}` : `Started ${formatDateTime(night.createdAt)}`}
                  </option>
                ))}
              </select>
            ) : null}
            <Button type="button" size="sm" variant="outline" className="shrink-0" disabled={add.isPending} onClick={() => add.mutate()}>
              <Popcorn aria-hidden /> Add to movie night
            </Button>
          </>
        ) : null}
      </div>
      {add.isError ? <p role="alert" className="w-full text-sm text-destructive">{queryErrorMessage(add.error, 'That film could not be added.')}</p> : null}
    </div>
  )
}
