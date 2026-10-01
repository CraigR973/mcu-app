import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Gavel, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/auth'
import {
  fetchBidTrial,
  formatLabel,
  startBidTrial,
  type BidTrial as Trial,
  type BidTrialStart,
  type TrialSummary,
} from '@/lib/api'
import { plural, summaryLines, trialStatus, wholePounds } from '@/lib/bid-trial'
import { queryErrorMessage } from '@/lib/query-state'

/** What pressing the button did, when it did not start anything. */
const NOT_STARTED: Record<Exclude<BidTrialStart['outcome'], 'started'>, string> = {
  running: 'A valuation or a trial is already running.',
  budget_spent: "Today's share of eBay lookups is used. Try again tomorrow.",
  nothing_to_sample: 'No film has a stored price to compare with yet.',
}

function Totals({ summary, currency }: { summary: TrialSummary; currency: string }) {
  const rows = [
    ['Asking, stored', summary.stored.total, plural(summary.stored.discs, 'disc')],
    ['Asking, today', summary.asking.total, plural(summary.asking.discs, 'disc')],
    ['Bids only', summary.bids.total, plural(summary.bids.discs, 'disc')],
    ['Blend', summary.blend.total, `${plural(summary.blend.discs, 'disc')}, ${String(summary.blend.fromBids)} by bids`],
  ] as const
  return (
    <table className="w-full text-left text-sm">
      <caption className="sr-only">What these discs total on each basis</caption>
      <thead>
        <tr className="text-xs text-muted-foreground">
          <th scope="col" className="py-1 pr-2 font-medium">Basis</th>
          <th scope="col" className="py-1 pr-2 text-right font-medium">Total</th>
          <th scope="col" className="py-1 font-medium">Behind it</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([basis, total, discs]) => (
          <tr key={basis} className="border-t border-border">
            <th scope="row" className="py-1.5 pr-2 font-normal text-foreground">{basis}</th>
            <td className="py-1.5 pr-2 text-right font-semibold text-foreground">{wholePounds(total, currency)}</td>
            <td className="py-1.5 text-xs text-muted-foreground">{discs}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Summary({ summary, trial, open }: { summary: TrialSummary; trial: Trial; open?: boolean }) {
  const name = summary.formatCode ? (formatLabel(summary.formatCode) ?? summary.formatCode) : 'All formats'
  return (
    <details className="group rounded-md border border-border p-3" open={open}>
      <summary className="cursor-pointer text-sm font-semibold text-foreground">
        {name} · {plural(summary.films, 'film')}
      </summary>
      {summary.films > 0 ? (
        <div className="mt-3 space-y-3">
          <dl className="space-y-2 text-sm">
            {summaryLines(summary, trial.minSample, trial.endingWindowHours).map((line) => (
              <div key={line.label}>
                <dt className="metadata-label">{line.label}</dt>
                <dd className="leading-6 text-foreground">{line.text}</dd>
              </div>
            ))}
          </dl>
          <Totals summary={summary} currency={trial.currency} />
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">None of these were looked up.</p>
      )}
    </details>
  )
}

function Report({ trial }: { trial: Trial }) {
  const report = trial.report
  if (!report || report.films.length === 0) return null
  const priced = report.films.filter((film) => film.bids?.price)
  return (
    <div className="space-y-3">
      <Summary summary={report.overall} trial={trial} open />
      {report.formats.map((summary) => (
        <Summary key={summary.formatCode} summary={summary} trial={trial} />
      ))}
      {priced.length > 0 ? (
        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-semibold text-foreground">
            Films with a bid price ({String(priced.length)})
          </summary>
          <ul className="mt-2 space-y-1 text-sm">
            {priced.map((film) => (
              <li key={`${film.movieId}-${film.formatCode}`} className="leading-6">
                <span className="text-foreground">{film.title}</span>{' '}
                <span className="text-muted-foreground">
                  · {formatLabel(film.formatCode)} · bids £{film.bids?.price} from {String(film.bids?.counted)}
                  {film.asking?.price ? ` · asking £${film.asking.price}` : ''} · stored £{film.stored.price}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      <p className="text-xs leading-5 text-muted-foreground">
        Asking prices usually run above what discs sell for, and a current bid runs below the final price until an
        auction&rsquo;s last minutes. Nothing here changes the collection&rsquo;s value: which to use, a blend or bids
        only, is your call.
      </p>
    </div>
  )
}

/**
 * Home's "Try bid prices" — Batch V6, snag 2's first step (#228: "trial first"). Admin only.
 *
 * One eBay search each for up to 100 priced films, Buy It Now and auctions together, out of
 * the same day's share as the value's runs. **It saves no prices**: the report says what bids
 * would do to the value, by format, so Craig can pick a blend or bids only (V7).
 */
export function BidTrial() {
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['bid-trial'],
    queryFn: fetchBidTrial,
    enabled: isAdmin,
    // Poll while it runs, so the count moves in front of whoever started it.
    refetchInterval: (current) => (current.state.data?.status === 'running' ? 5_000 : false),
  })
  const start = useMutation({
    mutationFn: startBidTrial,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bid-trial'] })
      // Its lookups come out of the share the value panel reports.
      void queryClient.invalidateQueries({ queryKey: ['collection-value'] })
    },
  })

  if (!isAdmin) return null
  const trial = query.data ?? null
  const running = trial?.status === 'running'
  const notStarted = start.data && start.data.outcome !== 'started' ? NOT_STARTED[start.data.outcome] : null

  return (
    <section className="space-y-4" aria-labelledby="bid-trial-heading">
      <h2 id="bid-trial-heading" className="section-heading flex items-center gap-2">
        <Gavel className="h-5 w-5 text-primary" aria-hidden />
        Bid prices: a trial
      </h2>
      <div className="archive-panel space-y-3 p-4 sm:p-5">
        <p className="text-sm leading-6 text-muted-foreground">
          Searches eBay once for each of up to {String(trial?.sampleSize ?? 100)} priced films, a third each on 4K,
          Blu-ray and DVD, with Buy It Now and auctions together. Each search is one of the day&rsquo;s eBay lookups
          for valuations{trial ? ` (${String(trial.dailyShare)})` : ''}. It saves no prices.
        </p>

        {query.isError ? (
          <p role="alert" className="text-sm text-destructive-text">
            {queryErrorMessage(query.error, 'The last trial could not be read.')}
          </p>
        ) : null}

        {trial ? (
          <p className="flex items-center gap-2 text-sm text-foreground" role="status">
            {running ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            {trialStatus(trial)}
          </p>
        ) : null}
        {trial && trial.failed > 0 && !running ? (
          <p className="text-xs text-muted-foreground">
            eBay did not answer for {plural(trial.failed, 'film')}; they are left out of every figure.
          </p>
        ) : null}

        {trial ? <Report trial={trial} /> : null}

        {!running ? (
          <div className="space-y-2 border-t border-border pt-3">
            <Button type="button" size="sm" variant="secondary" onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Gavel aria-hidden />}
              Try bid prices
            </Button>
            {notStarted ? <p className="text-xs text-muted-foreground">{notStarted}</p> : null}
            {start.isError ? (
              <p role="alert" className="text-sm text-destructive-text">
                {queryErrorMessage(start.error, 'The trial could not be started.')}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  )
}
