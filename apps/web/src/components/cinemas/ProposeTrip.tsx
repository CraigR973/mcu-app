import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { CinemaFilmDetail } from '@mcu/shared'
import { Loader2, Send, Ticket, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { PeoplePicker, TripTimes } from '@/components/cinemas/TripPickers'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { useAuth } from '@/context/auth'
import { fetchInvitablePeople, proposeCinemaTrip } from '@/lib/api'
import { pickableTimes, TRIP_OFFLINE, tripErrorMessage, tripPath } from '@/lib/cinema-trips'
import { queryErrorMessage } from '@/lib/query-state'

/**
 * "Propose a trip" on a film's page — AC5 (#345 §6). A sheet: pick one of this page's
 * confirmed, still-to-start times, pick people (everyone you can invite, none ticked), then
 * "Send invitations". The trip opens once it is made.
 */
export function ProposeTrip({ detail, now, today, online }: {
  detail: CinemaFilmDetail; now: number; today: string; online: boolean
}) {
  const [open, setOpen] = useState(false)
  if (pickableTimes(detail, now).length === 0) return null
  return (
    <>
      <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={() => setOpen(true)}>
        <Ticket aria-hidden />Propose a trip
      </Button>
      {open ? <ProposeSheet detail={detail} now={now} today={today} online={online} onClose={() => setOpen(false)} /> : null}
    </>
  )
}

function ProposeSheet({ detail, now, today, online, onClose }: {
  detail: CinemaFilmDetail; now: number; today: string; online: boolean; onClose: () => void
}) {
  const { profile } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showingId, setShowingId] = useState<string | null>(null)
  const [chosen, setChosen] = useState<Set<string>>(new Set())
  // One id per choice of time and people: the same send again, its answer lost, returns the
  // same trip; a different choice is a different send.
  const ids = useRef(new Map<string, string>())
  const people = useQuery({
    queryKey: ['cinema-trip-people', profile?.id],
    queryFn: fetchInvitablePeople,
    enabled: Boolean(profile),
  })
  const send = useMutation({
    mutationFn: () => {
      const key = `${showingId ?? ''}|${[...chosen].sort().join(',')}`
      const clientRequestId = ids.current.get(key) ?? crypto.randomUUID()
      ids.current.set(key, clientRequestId)
      return proposeCinemaTrip({ clientRequestId, filmKey: detail.film.key, showingId: showingId ?? '', inviteeIds: [...chosen] })
    },
    onSuccess: (trip) => {
      queryClient.setQueryData(['cinema-trip', profile?.id, trip.id], trip)
      void queryClient.invalidateQueries({ queryKey: ['cinema-trips'] })
      navigate(tripPath(trip.id))
    },
  })
  const ready = showingId !== null && chosen.size > 0

  return (
    <Dialog open onClose={onClose} label="Propose a trip">
      <form
        className="space-y-5 p-4 sm:p-6"
        onSubmit={(event) => {
          event.preventDefault()
          if (ready && online) send.mutate()
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="section-heading">Propose a trip</h2>
            <p className="mt-1 text-sm text-muted-foreground">{detail.film.title}</p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X aria-hidden />
          </Button>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Pick a time</legend>
          <TripTimes days={pickableTimes(detail, now)} today={today} selected={showingId} onSelect={setShowingId} disabled={send.isPending} />
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Who to invite</legend>
          {people.data ? (
            <PeoplePicker people={people.data.people} chosen={chosen} onChange={setChosen} disabled={send.isPending} />
          ) : people.isError ? (
            <p role="alert" className="text-sm text-destructive">{queryErrorMessage(people.error, 'Could not load who you can invite.')}</p>
          ) : (
            <p className="text-sm text-muted-foreground">Loading who you can invite…</p>
          )}
        </fieldset>

        {!online ? <p role="status" className="text-sm font-semibold">{TRIP_OFFLINE}</p> : null}
        {send.isError ? (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {tripErrorMessage(send.error, 'The invitations could not be sent.')}
          </p>
        ) : null}

        <Button type="submit" className="w-full" disabled={!ready || !online || send.isPending}>
          {send.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
          Send invitations
        </Button>
      </form>
    </Dialog>
  )
}
