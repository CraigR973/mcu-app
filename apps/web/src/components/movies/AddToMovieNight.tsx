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
  if (openNights.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      {openNights.length > 1 ? (
        <select className="select-control" aria-label="Which movie night" value={chosen} onChange={(event) => setNightId(event.target.value)}>
          {openNights.map((night) => (
            <option key={night.id} value={night.id}>
              {night.plannedStart ? `Planned ${formatDateTime(night.plannedStart)}` : `Started ${formatDateTime(night.createdAt)}`}
            </option>
          ))}
        </select>
      ) : null}
      <Button type="button" size="sm" variant="outline" disabled={add.isPending} onClick={() => add.mutate()}>
        <Popcorn aria-hidden /> Add to movie night
      </Button>
      {add.isError ? <p role="alert" className="w-full text-sm text-destructive">{queryErrorMessage(add.error, 'That film could not be added.')}</p> : null}
    </div>
  )
}
