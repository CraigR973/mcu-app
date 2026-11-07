import { useQuery } from '@tanstack/react-query'

import { useAuth } from '@/context/auth'
import { fetchCalendar, fetchCalendarMonth, fetchCinemaFilms, fetchNewReleases } from '@/lib/api'
import { CALENDAR_TYPES, DISC_WINDOW_DAYS, type ReleaseCalendar } from '@/lib/releases'

// The page observes the same queries as its sections: one cache entry and one in-flight
// request, with native controls held until the layout those answers produce has settled.
export function useCalendarMonthQuery(month: string, calendar: ReleaseCalendar) {
  return useQuery({
    queryKey: ['calendar-month', month, calendar],
    queryFn: () => fetchCalendarMonth(month, CALENDAR_TYPES[calendar]),
  })
}

export function useCinemaFilmsQuery(enabled: boolean) {
  const { profile } = useAuth()
  return useQuery({
    queryKey: ['cinema-films', profile?.id],
    queryFn: fetchCinemaFilms,
    enabled: enabled && Boolean(profile),
  })
}

export function useNewReleasesQuery(enabled: boolean) {
  return useQuery({
    queryKey: ['new-releases'],
    queryFn: fetchNewReleases,
    staleTime: 60 * 60 * 1000,
    enabled,
  })
}

export function useDiscReleasesQuery(enabled = true) {
  return useQuery({
    queryKey: ['calendar', DISC_WINDOW_DAYS],
    queryFn: () => fetchCalendar(DISC_WINDOW_DAYS),
    staleTime: 10 * 60 * 1000,
    enabled,
  })
}
