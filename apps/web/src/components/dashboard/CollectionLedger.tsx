import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { CountSlice, Stats } from '@mcu/shared'

import { ShelfLink } from '@/components/dashboard/Shelf'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchCollectionValue, fetchStats, poundsFromCents, type CollectionValue } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn, formatMonth } from '@/lib/utils'

const COUNT = new Intl.NumberFormat('en-GB')

function pounds(total: string, currency: string): string {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency, maximumFractionDigits: 0 }).format(
    Number(total),
  )
}

/** Each format in its own quality colour, as on the format badges (`--quality-*`). */
const FORMAT_TONE: Record<string, string> = {
  '4k_uhd': 'bg-[hsl(var(--quality-4k))]',
  blu_ray: 'bg-[hsl(var(--quality-bluray))]',
  dvd: 'bg-[hsl(var(--quality-dvd))]',
  download: 'bg-[hsl(var(--quality-digital))]',
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <li className="min-w-0 self-start">
      <section className="archive-panel h-full space-y-3 p-4">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {children}
      </section>
    </li>
  )
}

/**
 * A horizontal bar chart, in CSS.
 *
 * No chart library. Each of these is "a label and a proportion", which a flex row expresses
 * exactly; a charting dependency would add weight to every page load in a PWA whose whole
 * point is working on a phone with the network off. Moved here from `ArchiveStats` (W2).
 */
function BarChart({
  slices,
  countOf,
}: {
  slices: CountSlice[]
  countOf: (slice: CountSlice) => number
}) {
  const ceiling = Math.max(1, ...slices.map(countOf))
  return (
    <ul className="space-y-1.5">
      {slices.map((slice) => {
        const count = countOf(slice)
        return (
          <li key={slice.key} className="grid grid-cols-[minmax(0,1fr)_minmax(2rem,1fr)_3rem] items-center gap-2">
            <span className="break-words text-xs text-muted-foreground">{slice.label}</span>
            <span className="h-2.5 flex-1 overflow-hidden rounded-sm bg-muted" aria-hidden>
              <span
                className="block h-full rounded-sm bg-primary/70"
                style={{ width: `${String(Math.round((count / ceiling) * 100))}%` }}
              />
            </span>
            <span className="w-12 shrink-0 text-right text-xs tabular-nums text-foreground">
              {count.toLocaleString()}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function SpendChart({ stats }: { stats: Stats }) {
  const points = stats.spendOverTime
  const peak = Math.max(1, ...points.map((p) => p.cumulativeCents))
  const datedCopies = points.reduce((sum, point) => sum + point.itemCount, 0)
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {poundsFromCents(points[points.length - 1]?.cumulativeCents ?? 0)} across{' '}
        {datedCopies.toLocaleString()} copies with a purchase date and price.
        {' '}{stats.itemsWithPrice.toLocaleString()} copies have a recorded purchase price.
        {' '}This is recorded spending, not the collection&apos;s lifetime cost or estimated used value.
      </p>
      <ul className="flex h-24 items-end gap-1">
        {points.map((point) => (
          <li
            key={point.month}
            className="relative flex-1 rounded-t-sm bg-primary/60"
            style={{ height: `${String(Math.max(4, (point.cumulativeCents / peak) * 100))}%` }}
            title={`${formatMonth(point.month)} · ${poundsFromCents(point.cumulativeCents)}`}
          >
            <span className="sr-only">
              {formatMonth(point.month)}: {poundsFromCents(point.cumulativeCents)}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        {formatMonth(points[0]?.month ?? '')} – {formatMonth(points[points.length - 1]?.month ?? '')}
      </p>
      <details className="text-xs">
        <summary className="list-link flex min-h-11 cursor-pointer items-center text-primary">Monthly spending figures</summary>
        <ul className="space-y-2">
          {points.map((point) => (
            <li key={point.month} className="flex flex-wrap justify-between gap-x-3 gap-y-1">
              <span>{formatMonth(point.month)}</span>
              <span>{poundsFromCents(point.spentCents)} · {poundsFromCents(point.cumulativeCents)} total</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}

/** One figure of the ledger: a label, the figure, and one short line about it. */
function Figure({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="metadata-label">{label}</p>
      <p className="mt-1 break-words font-display text-2xl font-semibold tabular-nums tracking-tight text-foreground">{value}</p>
      {detail ? <div className="mt-0.5 text-xs leading-4 text-muted-foreground">{detail}</div> : null}
    </div>
  )
}

/**
 * The estimated value, the ledger's second figure, with its method behind a tap (AC2).
 * "Update values" and the bid trial stay in Admin's Collection value (W2, #249). Both people
 * see an explicit no-value state; only an admin sees where to start one.
 */
function Worth({ value, isAdmin, pending, error, offline }: { value: CollectionValue | undefined; isAdmin: boolean; pending: boolean; error: boolean; offline: boolean }) {
  if (!value) {
    return (
      <Figure
        label="Estimated used value"
        value={pending && !offline ? '…' : 'Unavailable'}
        detail={offline ? 'Reconnect to load the stored estimate. Collection counts are still available.' : pending ? 'Loading the stored estimate' : 'The value could not be loaded. Collection counts are still available.'}
      />
    )
  }
  const running = value.run?.status === 'running'
  if (value.total === null) {
    return (
      <Figure
        label="Estimated used value"
        value="Not valued yet"
        detail={running ? 'Pricing now' : isAdmin ? <ShelfLink to="/valuation">Value it in Admin</ShelfLink> : 'No stored estimate is available yet.'}
      />
    )
  }
  return (
    <Figure
      label="Estimated used value"
      value={`≈ ${pounds(value.total, value.currency)}`}
      detail={
        <>
          <span className="block">{COUNT.format(value.pricedDiscs)} of {COUNT.format(value.discs)} physical copies priced</span>
          {value.salesBackedDiscs > 0 ? <span className="mt-0.5 block">{COUNT.format(value.salesBackedDiscs)} based on observed sales</span> : null}
          {running ? <span className="mt-0.5 block" role="status">Pricing now</span> : null}
          {error ? <span className="mt-0.5 block" role="status">The latest value could not be loaded; showing the stored estimate.</span> : null}
          <details className="mt-1">
            <summary className="list-link flex min-h-11 cursor-pointer items-center text-primary">How this estimate works</summary>
            <p className="pb-2 leading-5">
              Each physical copy is valued as used, including postage. At least three observed sales
              in 90 days use the median of their last advertised listing prices; otherwise a current used asking-price stand-in is
              used, with a scaled New-price fallback when used listings are scarce. A listing that disappears
              is only an inferred sale; a Best Offer may have closed below its advertised price.
              Downloads have no value here.
            </p>
          </details>
        </>
      }
    />
  )
}

/** "You've watched", as a share of the titles owned, never inferred when the API omits it. */
function Watched({ stats }: { stats: Stats }) {
  if (stats.ownedWatchedMovies === undefined) {
    return <Figure label="You've watched" value="Unavailable" detail="Watched coverage is unavailable in this saved response." />
  }
  const share = stats.totalMovies > 0 ? Math.round((stats.ownedWatchedMovies / stats.totalMovies) * 100) : null
  return (
    <Figure
      label="You've watched"
      value={share === null ? '—' : `${String(share)}%`}
      detail={`${COUNT.format(stats.ownedWatchedMovies)} of ${COUNT.format(stats.totalMovies)} titles you own`}
    />
  )
}

/** The formats as one stacked bar and a legend. A copy on two formats counts in both. */
function FormatsBar({ slices }: { slices: CountSlice[] }) {
  const total = slices.reduce((sum, slice) => sum + slice.itemCount, 0)
  return (
    <section aria-labelledby="collection-format-preview" className="space-y-2">
      <h3 id="collection-format-preview" className="metadata-label">Formats at a glance</h3>
      {total > 0 ? (
        <div className="flex h-2.5 gap-px overflow-hidden rounded-full bg-muted" aria-hidden>
          {slices.map((slice) => (
            <span
              key={slice.key}
              className={cn('h-full', FORMAT_TONE[slice.key] ?? 'bg-primary/70')}
              style={{ width: `${String((slice.itemCount / total) * 100)}%` }}
            />
          ))}
        </div>
      ) : null}
      <ul aria-label="Copies by format" className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {slices.map((slice) => (
          <li key={slice.key} className="flex items-center gap-1.5">
            <span aria-hidden className={cn('size-2 rounded-full', FORMAT_TONE[slice.key] ?? 'bg-primary/70')} />
            {slice.label === 'Downloads' ? 'Digital' : slice.label}
            <span className="tabular-nums text-foreground">{COUNT.format(slice.itemCount)}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">Copies can carry more than one format; these counts overlap.</p>
    </section>
  )
}

function copiesLine(stats: Stats): ReactNode {
  if (stats.physicalCopies === undefined || stats.physicalAndDownloadCopies === undefined) {
    return (
      <>
        <span className="tabular-nums text-foreground">{COUNT.format(stats.totalItems)}</span> copies owned ·{' '}
        Physical/download split is temporarily unavailable.
      </>
    )
  }
  return (
    <>
      <span className="tabular-nums text-foreground">{COUNT.format(stats.totalItems)}</span> copies ·{' '}
      {COUNT.format(stats.physicalCopies)} on disc · {COUNT.format(stats.downloadCopies)} digital ·{' '}
      {COUNT.format(stats.physicalAndDownloadCopies)} both
    </>
  )
}

/**
 * The collection as one ledger — AC2, Craig's pick A (#337).
 *
 * Each fact once: titles as the headline figure; copies with on disc and digital in one line;
 * the estimated value second, its method behind a tap; watched as a share of the titles owned
 * with a bar; the formats as one stacked bar, the full breakdown one tap away. "Matched on
 * TMDB" left Home with AC2: it stays in Identify films and its attention checks.
 *
 * Before AC2 these were five number cards, a formats chart, a button and a breakdown that drew
 * the formats a second time (the 4 Nov review's repetition). The states stay as AB2 and X8
 * made them: offline, failed, an older API without the split or the watched count, and an
 * empty collection, each said plainly rather than guessed.
 */
export function CollectionLedger() {
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const statsQuery = useQuery({ queryKey: ['stats', profile?.id], queryFn: fetchStats })
  const valueQuery = useQuery({
    queryKey: ['collection-value'],
    queryFn: fetchCollectionValue,
    // Poll while a run is pricing, as the full panel in Admin does.
    refetchInterval: (current) => (current.state.data?.run?.status === 'running' ? 5_000 : false),
  })
  const stats = statsQuery.data
  const state = listState(statsQuery, false)

  let body: ReactNode
  if (state === 'offline') {
    body = <StatePanel compact tone="offline" title="Stats are not cached here" description="Reconnect to load the collection ledger on this device." />
  } else if (state === 'error') {
    body = (
      <StatePanel
        compact
        tone="error"
        title="The collection ledger is unavailable"
        description={queryErrorMessage(statsQuery.error, 'Could not load the stats.')}
      />
    )
  } else if (!stats) {
    // The ledger's own height while it counts, so nothing below it moves when it arrives.
    body = <div aria-hidden className="mt-3 h-[21rem] animate-pulse rounded-lg bg-muted/50" />
  } else {
    const share = stats.ownedWatchedMovies !== undefined && stats.totalMovies > 0
      ? Math.round((stats.ownedWatchedMovies / stats.totalMovies) * 100)
      : null
    const spendNote =
      stats.spendOverTime.length > 0
        ? null
        : stats.itemsWithPrice === 0
          ? 'Spend over time appears once purchase prices are recorded; the imported spreadsheet never carried one.'
          : 'Spend over time appears once the recorded prices carry a purchase date.'
    body = (
      <>
        <ul aria-label="The collection in numbers" className="mt-3 space-y-4">
          <li>
            <p className="flex items-end gap-2">
              <span className="font-display text-[2.75rem] font-semibold leading-none tracking-tight tabular-nums text-foreground">
                {COUNT.format(stats.totalMovies)}
              </span>
              <span className="pb-1 text-sm text-muted-foreground">titles</span>
            </p>
            <p className="mt-1.5 text-sm text-muted-foreground">{copiesLine(stats)}</p>
          </li>
          <li className="border-t border-border pt-4">
            <div className="grid grid-cols-2 gap-3">
              <Worth value={valueQuery.data} isAdmin={isAdmin} pending={valueQuery.isPending} error={valueQuery.isError} offline={listState(valueQuery, false) === 'offline'} />
              <Watched stats={stats} />
            </div>
            {share !== null ? (
              <span
                role="progressbar"
                aria-label="Share of the collection you have watched"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={share}
                className="mt-2 block h-1.5 overflow-hidden rounded-full bg-muted"
              >
                <span className="block h-full rounded-full bg-[hsl(var(--accent))]" style={{ width: `${String(share)}%` }} />
              </span>
            ) : null}
          </li>
          <li className="border-t border-border pt-4">
            <FormatsBar slices={stats.formats} />
          </li>
        </ul>
        <details className="mt-3 border-t border-border">
          <summary className="list-link flex min-h-11 cursor-pointer items-center text-sm font-semibold text-primary">Collection breakdown</summary>
          <ul aria-label="The collection's shape" className="grid grid-cols-1 gap-3 pb-3 sm:grid-cols-2">
            <ChartCard title="Where they live (copies)">
              <BarChart slices={stats.sections} countOf={(s) => s.itemCount} />
            </ChartCard>
            <ChartCard title="Genres (titles)">
              <BarChart slices={stats.genres.slice(0, 12)} countOf={(s) => s.movieCount} />
              <p className="text-xs text-muted-foreground">The 12 most common genres. A title can have more than one.</p>
            </ChartCard>
            <ChartCard title="Decades (titles)">
              <BarChart
                slices={stats.decades.map((d) => ({ key: String(d.decade), label: d.label, itemCount: d.movieCount, movieCount: d.movieCount }))}
                countOf={(s) => s.movieCount}
              />
            </ChartCard>
            {stats.spendOverTime.length > 0 ? (
              <ChartCard title="Recorded spending">
                <SpendChart stats={stats} />
              </ChartCard>
            ) : null}
          </ul>
          {spendNote ? <p className="pb-3 text-xs leading-5 text-muted-foreground">{spendNote}</p> : null}
        </details>
      </>
    )
  }

  return (
    <section aria-labelledby="home-collection" className="archive-panel p-4 sm:p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="home-collection" className="section-heading text-lg">The collection</h2>
        {/* AA1: the collection opens the Archive. Always there, loading or failed. */}
        <Link to="/movies" aria-label="Browse the archive" className="list-link shrink-0 text-sm font-semibold text-primary hover:underline">
          Browse ›
        </Link>
      </div>
      {body}
    </section>
  )
}
