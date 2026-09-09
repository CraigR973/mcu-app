import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Tv } from 'lucide-react'

import {
  fetchStreaming,
  OFFER_KIND_LABELS,
  providerLogoUrl,
  type OfferKind,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

const ORDER: OfferKind[] = ['flatrate', 'rent', 'buy']

/**
 * §7.1's watch providers, on the film's own page.
 *
 * **Nothing is cached.** Streaming rights move constantly — a film included in a
 * subscription this week is rent-only the next — so a stale answer is a *wrong* answer
 * with a confident face and no signal that it has gone off. Contrast `completion_sets`,
 * which caches precisely because a filmography barely changes.
 *
 * TMDB's own "where to watch" link is shown alongside, which their terms require when
 * their availability data is displayed — and which is the only honest place to send
 * someone for prices, since the API gives none.
 */
export function StreamingPanel({ movieId }: { movieId: string }) {
  const streamingQuery = useQuery({
    queryKey: ['streaming', movieId],
    queryFn: () => fetchStreaming(movieId),
    // Long enough not to re-ask on every tab switch, short enough that a deal change is
    // not carried around for the session.
    staleTime: 10 * 60 * 1000,
  })
  const data = streamingQuery.data
  const state = listState(streamingQuery, (data?.offers.length ?? 0) === 0)

  if (state === 'loading') {
    return <p className="text-sm text-muted-foreground">Checking where to watch…</p>
  }
  if (state === 'offline') {
    return (
      <p className="text-sm text-muted-foreground">
        Waiting for the network — streaming options could not be checked.
      </p>
    )
  }
  if (state === 'error' || !data) {
    return (
      <p className="text-sm text-muted-foreground">
        {queryErrorMessage(streamingQuery.error, 'Streaming options are unavailable.')}
      </p>
    )
  }

  // Three different empty states, because they mean three different things and a single
  // "nothing found" would be wrong for two of them.
  if (data.unidentified) {
    return (
      <p className="text-sm text-muted-foreground">
        This film has not been identified yet, so there is nothing to look up.
      </p>
    )
  }
  if (data.unavailable) {
    return (
      <p className="text-sm text-muted-foreground">
        TMDB could not be reached, so availability is unknown right now. Your connection is
        fine — try again shortly.
      </p>
    )
  }
  if (data.offers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Not streaming, renting or selling in {data.region} right now.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {ORDER.map((kind) => {
        const offers = data.offers.filter((offer) => offer.kind === kind)
        if (offers.length === 0) return null
        return (
          <div key={kind} className="space-y-1.5">
            <p className="text-xs font-semibold text-foreground">
              {OFFER_KIND_LABELS[kind]}
            </p>
            <ul className="flex flex-wrap gap-2">
              {offers.map((offer) => (
                <li
                  key={`${kind}-${String(offer.providerId)}`}
                  className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2 py-1"
                >
                  <img
                    src={providerLogoUrl(offer.logoPath)}
                    alt=""
                    loading="lazy"
                    className="h-5 w-5 rounded"
                  />
                  <span className="text-xs text-foreground">{offer.providerName}</span>
                </li>
              ))}
            </ul>
          </div>
        )
      })}
      <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
        <Tv className="h-3 w-3" />
        Availability in {data.region} via TMDB.
        {data.link ? (
          <a
            href={data.link}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-0.5 text-primary hover:underline"
          >
            Prices and links <ExternalLink className="h-3 w-3" />
          </a>
        ) : null}
      </p>
    </div>
  )
}
