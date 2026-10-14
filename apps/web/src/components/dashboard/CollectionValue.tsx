import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, PoundSterling, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/auth'
import { fetchCollectionValue, startValuationRun, type CollectionValue as Value, type ValuationStart } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

const COUNT = new Intl.NumberFormat('en-GB')

function pounds(total: string, currency: string): string {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency, maximumFractionDigits: 0 }).format(
    Number(total),
  )
}

/** "checked 24 Sep 2026", "checked 23–24 Sep 2026" or "checked 30 Sep – 2 Oct 2026". */
function checked(value: Value): string | null {
  if (!value.checkedFrom || !value.checkedTo) return null
  const to = formatShortDate(value.checkedTo)
  const [fromDay, fromMonth, fromYear] = formatShortDate(value.checkedFrom).split(' ')
  const [toDay, toMonth, toYear] = to.split(' ')
  if (fromYear !== toYear) return `checked ${formatShortDate(value.checkedFrom)} – ${to}`
  if (fromMonth !== toMonth) return `checked ${fromDay} ${fromMonth} – ${to}`
  return fromDay === toDay ? `checked ${to}` : `checked ${fromDay}–${toDay} ${toMonth} ${toYear}`
}

/** What pressing the button did, when it did not start anything. */
const NOT_STARTED: Record<Exclude<ValuationStart['outcome'], 'started'>, string> = {
  running: 'A valuation is already running.',
  budget_spent: "Today's share of eBay lookups is used. It carries on tomorrow.",
  nothing_due: 'Every price is less than 30 days old, so there is nothing to update.',
}

/**
 * What the collection is worth at current eBay asking prices — Batch T6, snag 7. Each disc
 * as a used copy since Batch X6 (`DECISIONS.md` #256): `valuedAs` carries the words.
 *
 * **It says "asking prices" every time, and that they run high.** eBay's sold prices are
 * closed to apps (`DECISIONS.md` #16, #126), so this is what sellers are asking, which is
 * usually more than discs sell for. It also says how many discs are behind the total:
 * a disc with fewer than three matching listings is not priced rather than guessed.
 *
 * Hidden from Mark until there is a total, as Home hides every empty section. Craig sees it
 * before the first run, because the button that starts one lives here. **On Admin's
 * "Collection value" since W2** (#249), so Home only reads: Home's collection row shows the
 * total as its "Worth" card.
 */
export function CollectionValue() {
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['collection-value'],
    queryFn: fetchCollectionValue,
    // Poll while a run is pricing, so the total grows in front of whoever is watching.
    refetchInterval: (current) => (current.state.data?.run?.status === 'running' ? 5_000 : false),
  })
  const start = useMutation({
    mutationFn: startValuationRun,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['collection-value'] }),
  })

  const value = query.data
  if (!value) return null
  const running = value.run?.status === 'running'
  if (value.total === null && !running && !isAdmin) return null

  const notStarted = start.data && start.data.outcome !== 'started' ? NOT_STARTED[start.data.outcome] : null
  const canStart = isAdmin && !running && value.due > 0 && value.budgetLeft > 0
  const when = checked(value)

  return (
    <section className="space-y-4" aria-labelledby="collection-value-heading">
      <h2 id="collection-value-heading" className="section-heading flex items-center gap-2">
        <PoundSterling className="h-5 w-5 text-primary" aria-hidden />
        What it&rsquo;s worth
      </h2>
      <div className="archive-panel space-y-3 p-4 sm:p-5">
        {value.total !== null ? (
          <div>
            <p className="metadata-label">
              {value.valuedAs ? `${value.valuedAs}, at ${value.basis} on eBay` : `At ${value.basis} on eBay`}
            </p>
            <p className="mt-1 font-display text-3xl font-semibold text-foreground">
              &asymp; {pounds(value.total, value.currency)}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {COUNT.format(value.pricedDiscs)} of {COUNT.format(value.discs)} discs priced
              {when ? ` · ${when}` : ''}
            </p>
          </div>
        ) : (
          <p className="text-sm leading-6 text-muted-foreground">
            Not valued yet. A valuation looks up each film on eBay at current asking prices, about{' '}
            {COUNT.format(value.dailyShare)} lookups a day, so all {COUNT.format(value.discs)} discs take a couple of
            days.
          </p>
        )}

        {running && value.run ? (
          <p className="flex items-center gap-2 text-sm text-foreground" role="status">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Pricing now: {COUNT.format(value.run.priced + value.run.notPriced + value.run.failed)} checked,{' '}
            {COUNT.format(value.due)} to go.
          </p>
        ) : null}

        {value.total !== null && (value.notPricedDiscs > 0 || value.uncheckedDiscs > 0) ? (
          <p className="text-xs leading-5 text-muted-foreground">
            {value.notPricedDiscs > 0
              ? `${COUNT.format(value.notPricedDiscs)} had fewer than ${String(value.minSample)} used and ${String(value.minSample)} new matching eBay listings, so they are not priced rather than guessed. `
              : ''}
            {value.uncheckedDiscs > 0
              ? `${COUNT.format(value.uncheckedDiscs)} not valued as used copies yet; the next run does them first.`
              : ''}
          </p>
        ) : null}

        {value.total !== null ? (
          <p className="text-xs leading-5 text-muted-foreground">
            Each disc is valued as a used copy: the median of its used listings, or New&rsquo;s median at the
            used-to-New rate measured across the collection when used listings are too few. Asking prices
            usually run above what discs actually sell for. eBay does not let apps see sold prices.
          </p>
        ) : null}

        {isAdmin && !running ? (
          <div className="space-y-2 border-t border-border pt-3">
            {canStart ? (
              <Button type="button" size="sm" variant="secondary" onClick={() => start.mutate()} disabled={start.isPending}>
                {start.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <RefreshCw aria-hidden />}
                {value.total === null ? 'Value the collection' : 'Update values'}
              </Button>
            ) : (
              <p className="text-xs text-muted-foreground">
                {value.due === 0
                  ? 'Every price is less than 30 days old.'
                  : "Today's share of eBay lookups is used. More tomorrow."}
              </p>
            )}
            {notStarted ? <p className="text-xs text-muted-foreground">{notStarted}</p> : null}
            {start.isError ? (
              <p role="alert" className="text-sm text-destructive-text">
                {queryErrorMessage(start.error, 'The valuation could not be started.')}
              </p>
            ) : null}
          </div>
        ) : null}

        {value.run && (value.run.status === 'stopped' || value.run.status === 'abandoned') && isAdmin ? (
          <p className="text-xs text-muted-foreground">
            The last run stopped early{value.run.lastError ? `: ${value.run.lastError}` : ''}. The next one carries on.
          </p>
        ) : null}
      </div>
    </section>
  )
}
