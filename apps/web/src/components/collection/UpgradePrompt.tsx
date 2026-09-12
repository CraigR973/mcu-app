import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpCircle, Loader2, Tag, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { FormatBadge } from '@/components/movies/FormatBadge'
import {
  bestFormat,
  fetchEbayPriceEstimate,
  formatLabel,
  updateListingStatus,
  type CollectionCopy,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/**
 * The tail of §4.2's upgrade path: *"flag old format as superseded · show suggested sell
 * price from 4.1 · admin adjusts or accepts"*.
 *
 * **The criterion is "completes in ≤ 3 taps", and this is what makes that true.** Without
 * it the upgrade ends at "disc saved" and the old Blu-ray is left on the shelf for
 * somebody to remember about — which is not a flow with a tap count, it is a flow with a
 * chance of being forgotten. So the film's own page opens with the superseded discs named
 * and a one-tap action against each:
 *
 * 1. **"This is an upgrade"** on the duplicate prompt — which is also the save.
 * 2. **"List for sale"** here.
 *
 * Two, with the price already in the box.
 *
 * **The price arrives pre-filled, not pre-committed.** §4.1's median is fetched once for
 * the whole prompt and offered as the default; the disc is listed at whatever is showing,
 * and the number can be edited afterwards on the disc itself. That is "admin adjusts or
 * accepts" — the alternative, making them type a price before anything can happen, is the
 * tap this exists to remove.
 */
export function UpgradePrompt({
  movieId,
  filmTitle,
  copies,
  onDismiss,
}: {
  movieId: string
  filmTitle: string
  /** Every owned copy of this film. The superseded ones are worked out here so the
   *  caller does not have to duplicate the format ranking. */
  copies: CollectionCopy[]
  onDismiss: () => void
}) {
  const queryClient = useQueryClient()

  const inCollection = copies.filter((copy) => copy.listingStatus === 'in_collection')
  const best = bestFormat(inCollection.flatMap((copy) => copy.formats))
  // Superseded: owned, not already listed, and not the best format in the house.
  const superseded = inCollection.filter((copy) => bestFormat(copy.formats) !== best)

  const estimate = useQuery({
    queryKey: ['ebay-estimate', filmTitle, superseded[0]?.id],
    queryFn: () =>
      fetchEbayPriceEstimate({
        filmTitle,
        formatCode: bestFormat(superseded[0]?.formats ?? []),
      }),
    enabled: superseded.length > 0,
    // One estimate per prompt. Each call spends a unit of a 5,000-a-day quota, and the
    // superseded discs of one film are the same product.
    staleTime: 10 * 60 * 1000,
    retry: false,
  })

  const list = useMutation({
    mutationFn: ({ id, price }: { id: string; price: string | null }) =>
      updateListingStatus(id, { status: 'listed_for_sale', listingPrice: price }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['movie-copies', movieId] })
      void queryClient.invalidateQueries({ queryKey: ['movie', movieId] })
    },
  })

  if (superseded.length === 0) return null

  const suggested = estimate.data?.headline?.median ?? null

  return (
    <section
      className="rounded-xl border border-accent/40 bg-accent/10 p-4"
      aria-labelledby="upgrade-prompt-heading"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <ArrowUpCircle className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden />
          <div>
            <h2 id="upgrade-prompt-heading" className="text-sm font-semibold text-foreground">
              You&apos;ve upgraded to {formatLabel(best)}
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {superseded.length === 1
                ? 'The older disc is still on the shelf.'
                : `${superseded.length} older discs are still on the shelf.`}{' '}
              {suggested
                ? `Current asking prices on eBay UK put it around £${suggested}.`
                : estimate.isPending
                  ? 'Checking what it is worth…'
                  : 'No price estimate — list it and set the price yourself.'}
            </p>
          </div>
        </div>
        <Button type="button" size="icon" variant="ghost" onClick={onDismiss} aria-label="Dismiss">
          <X aria-hidden />
        </Button>
      </div>

      <ul className="mt-3 space-y-2">
        {superseded.map((copy) => (
          <li
            key={copy.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-background/60 px-3 py-2"
          >
            <span className="flex flex-wrap items-center gap-2">
              {copy.formats.map((format) => (
                <FormatBadge key={format} format={format} />
              ))}
              {copy.location && (
                <span className="text-xs text-muted-foreground">{copy.location}</span>
              )}
            </span>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => list.mutate({ id: copy.id, price: suggested })}
              disabled={list.isPending}
            >
              {list.isPending ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : (
                <Tag aria-hidden />
              )}
              List for sale{suggested ? ` at £${suggested}` : ''}
            </Button>
          </li>
        ))}
      </ul>

      {list.isError && (
        <p role="alert" className="mt-2 text-sm text-destructive-text">
          {queryErrorMessage(list.error, 'The disc could not be listed.')}
        </p>
      )}
    </section>
  )
}
