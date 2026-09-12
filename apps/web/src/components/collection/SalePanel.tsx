import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, PackageCheck, Tag, Undo2 } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  LISTING_STATUS_LABELS,
  updateListingStatus,
  type CollectionCopy,
  type ListingStatus,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/**
 * Selling a disc — §4.2's upgrade tail and §4.4's listing states.
 *
 * **Marking sold is not deleting.** The disc leaves the collection views and keeps its
 * row, its price and its audit trail; the server explains why in
 * `collection.update_listing_status`, and the short version is that soft-deleting it
 * would hand it to the 90-day trash purge and destroy the record of what it fetched.
 *
 * **A listed disc is still shown.** It is still in the house until somebody buys it, so
 * it keeps its place on the film's page with a badge, and the only new control is
 * "Mark as sold".
 */
export function SalePanel({
  copy,
  movieId,
  suggestedPrice,
}: {
  copy: CollectionCopy
  movieId: string
  /** The median of current asking prices, when §4.1 has been asked. Pre-fills the box —
   *  §4.2's "admin adjusts or accepts" means the number arrives already filled in. */
  suggestedPrice?: string | null
}) {
  const queryClient = useQueryClient()
  const [price, setPrice] = useState(copy.listingPrice ?? suggestedPrice ?? '')

  const move = useMutation({
    mutationFn: (status: ListingStatus) =>
      updateListingStatus(copy.id, {
        status,
        listingPrice: status === 'in_collection' ? null : price || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['movie-copies', movieId] })
      void queryClient.invalidateQueries({ queryKey: ['movie', movieId] })
      void queryClient.invalidateQueries({ queryKey: ['item-history', movieId] })
    },
  })

  const status = copy.listingStatus as ListingStatus
  const busy = move.isPending

  return (
    <div className="space-y-3">
      {status !== 'in_collection' && (
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={status === 'listed_for_sale' ? 'warning' : 'neutral'}>
            {LISTING_STATUS_LABELS[status] ?? status}
          </Badge>
          {copy.listingPrice && (
            <span className="text-sm text-muted-foreground">
              {status === 'sold' ? 'for' : 'at'} £{copy.listingPrice}
            </span>
          )}
        </div>
      )}

      {status === 'in_collection' && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex-1 min-w-[8rem]">
            <span className="metadata-label">Asking price</span>
            <Input
              type="text"
              inputMode="decimal"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              placeholder={suggestedPrice ? `£${suggestedPrice} suggested` : 'e.g. 9.99'}
              className="mt-1"
            />
          </label>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => move.mutate('listed_for_sale')}
            disabled={busy}
          >
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Tag aria-hidden />}
            List for sale
          </Button>
        </div>
      )}

      {status === 'listed_for_sale' && (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => move.mutate('sold')}
            disabled={busy}
          >
            {busy ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <PackageCheck aria-hidden />
            )}
            Mark as sold
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => move.mutate('in_collection')}
            disabled={busy}
          >
            <Undo2 aria-hidden />
            Keep it after all
          </Button>
        </div>
      )}

      {(status === 'sold' || status === 'donated') && (
        <p className="text-xs text-muted-foreground">
          Out of the collection, and still in the audit log. Nothing was deleted.
        </p>
      )}

      {move.isError && (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(move.error, 'The listing could not be updated.')}
        </p>
      )}
    </div>
  )
}
