import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Loader2, Tag, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { FormatBadge } from '@/components/movies/FormatBadge'
import { Poster } from '@/components/movies/Poster'
import { useAuth } from '@/context/auth'
import { dismissDeal, fetchDeals, FORMATS, type Deal, type DealFilters } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/** §5.10's discount filter, as thresholds rather than a slider — the question is
 *  "anything worth looking at?", not "exactly 37%". */
const DISCOUNT_STEPS = [10, 25, 50] as const

function DealCard({ deal }: { deal: Deal }) {
  const queryClient = useQueryClient()
  const { profile } = useAuth()
  const canEdit = profile?.role === 'admin'

  const dismiss = useMutation({
    mutationFn: () => dismissDeal(deal.id, true),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['deals'] })
    },
  })

  return (
    <article className="archive-panel flex gap-3 p-3 sm:p-4">
      <div className="w-16 shrink-0 sm:w-20">
        <Poster path={deal.posterPath} title={deal.title} className="w-full" />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-display text-base font-semibold text-foreground">
              {deal.movieId ? (
                <Link to={`/movies/${deal.movieId}`} className="hover:underline">
                  {deal.title}
                </Link>
              ) : (
                deal.title
              )}
            </h3>
            <p className="mt-0.5 text-xs text-muted-foreground">{deal.retailer}</p>
          </div>
          {deal.discountPercent ? (
            <Badge tone="success">−{deal.discountPercent}%</Badge>
          ) : null}
        </div>

        <div className="flex flex-wrap items-baseline gap-2">
          <span className="font-display text-xl font-semibold text-foreground">
            £{deal.price}
          </span>
          {deal.wasPrice ? (
            <span className="text-sm text-muted-foreground line-through">£{deal.wasPrice}</span>
          ) : null}
          {deal.formatCode ? <FormatBadge format={deal.formatCode} /> : null}
        </div>

        {/* An unmatched deal is shown rather than hidden — it is the evidence the matcher
            needs work, and hiding it would make a broken matcher look like a quiet sale. */}
        {!deal.movieId && (
          <p className="text-xs text-muted-foreground">Not matched to a film in the archive.</p>
        )}

        <div className="mt-auto flex flex-wrap gap-2 pt-1">
          <Button asChild size="sm" variant="secondary">
            <a href={deal.url} target="_blank" rel="noopener noreferrer">
              View at {deal.retailer} <ExternalLink aria-hidden />
            </a>
          </Button>
          {canEdit && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => dismiss.mutate()}
              disabled={dismiss.isPending}
            >
              {dismiss.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <X aria-hidden />}
              Not interested
            </Button>
          )}
        </div>

        {dismiss.isError && (
          <p role="alert" className="text-sm text-destructive-text">
            {queryErrorMessage(dismiss.error, 'Could not dismiss this deal.')}
          </p>
        )}
      </div>
    </article>
  )
}

/**
 * §5.9's feed and §5.10's curation.
 *
 * **The feed is empty until somebody runs a scrape, and that is the honest state.**
 * §5.9's acceptance requires a live run against real retailer sale pages, which
 * `docs/agent-commands/group-start.md` puts in the owner's hands — so the empty state
 * says who has to do what rather than implying there is simply nothing on offer.
 */
export default function DealsPage() {
  const [filters, setFilters] = useState<DealFilters>({})
  const { profile } = useAuth()
  const canEdit = profile?.role === 'admin'

  const dealsQuery = useQuery({
    queryKey: ['deals', filters],
    queryFn: () => fetchDeals(filters),
  })

  const data = dealsQuery.data
  const items = data?.items ?? []
  const state = listState(dealsQuery, items.length === 0)
  const filtered = Object.values(filters).some(Boolean)

  return (
    <div className="page-shell space-y-6">
      <PageHeader
        eyebrow="On offer"
        title="Deals"
        description="Discounted discs from the shops the archive watches. Anything you already own on the same format or better is filtered out."
      />

      {/* §5.10's four filters: retailer, genre, format, discount. Only values actually
          present in the feed are offered, so no filter can produce a guaranteed blank. */}
      {items.length > 0 || filtered ? (
        <section className="archive-panel space-y-3 p-4" aria-label="Filter the deals">
          <div className="flex flex-wrap gap-2">
            {DISCOUNT_STEPS.map((step) => (
              <Button
                key={step}
                type="button"
                size="sm"
                variant={filters.minDiscount === step ? 'default' : 'outline'}
                onClick={() =>
                  setFilters((current) => ({
                    ...current,
                    minDiscount: current.minDiscount === step ? null : step,
                  }))
                }
              >
                {step}% or more
              </Button>
            ))}
            {FORMATS.filter((format) => format.value !== 'download').map((format) => (
              <Button
                key={format.value}
                type="button"
                size="sm"
                variant={filters.formatCode === format.value ? 'default' : 'outline'}
                onClick={() =>
                  setFilters((current) => ({
                    ...current,
                    formatCode: current.formatCode === format.value ? null : format.value,
                  }))
                }
              >
                {format.label}
              </Button>
            ))}
          </div>

          {(data?.retailers.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-border pt-3">
              {data?.retailers.map((retailer) => (
                <Button
                  key={retailer}
                  type="button"
                  size="sm"
                  variant={filters.retailer === retailer ? 'default' : 'outline'}
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      retailer: current.retailer === retailer ? null : retailer,
                    }))
                  }
                >
                  {retailer}
                </Button>
              ))}
            </div>
          )}

          {(data?.genres.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-border pt-3">
              {data?.genres.map((genre) => (
                <Button
                  key={genre}
                  type="button"
                  size="sm"
                  variant={filters.genre === genre ? 'default' : 'outline'}
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      genre: current.genre === genre ? null : genre,
                    }))
                  }
                >
                  {genre}
                </Button>
              ))}
            </div>
          )}

          {filtered && (
            <Button type="button" size="sm" variant="ghost" onClick={() => setFilters({})}>
              Clear filters
            </Button>
          )}
        </section>
      ) : null}

      {state === 'loading' ? (
        <StatePanel tone="loading" title="Loading deals" description="Checking what is on offer…" />
      ) : state === 'offline' ? (
        <StatePanel
          tone="offline"
          title="Deals are not cached"
          description="They change too often to be useful offline."
          action={
            <Button type="button" variant="outline" onClick={() => void dealsQuery.refetch()}>
              Try again
            </Button>
          }
        />
      ) : state === 'error' ? (
        <StatePanel
          tone="error"
          title="Could not load the deals"
          description={queryErrorMessage(dealsQuery.error, 'The feed did not respond.')}
          action={
            <Button type="button" variant="outline" onClick={() => void dealsQuery.refetch()}>
              Try again
            </Button>
          }
        />
      ) : state === 'empty' ? (
        <StatePanel
          tone="empty"
          icon={Tag}
          title={filtered ? 'Nothing matches those filters' : 'No deals recorded yet'}
          description={
            filtered
              ? 'Try widening the discount or clearing a filter.'
              : canEdit
                ? 'The sale pages have not been scraped yet. A live run against real shops is a manual step — start it from Retailers.'
                : 'Craig has not run a deals scrape yet.'
          }
          action={
            filtered ? (
              <Button type="button" variant="outline" onClick={() => setFilters({})}>
                Clear filters
              </Button>
            ) : canEdit ? (
              <Button asChild variant="outline">
                <Link to="/retailers">Go to Retailers</Link>
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {items.length} {items.length === 1 ? 'deal' : 'deals'}
            {filtered ? ' matching your filters' : ''}.
          </p>
          <div className={cn('grid gap-4', 'sm:grid-cols-2 xl:grid-cols-3')}>
            {items.map((deal) => (
              <DealCard key={deal.id} deal={deal} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
