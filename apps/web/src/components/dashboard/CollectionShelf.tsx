import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { formatMonth } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { BarChart3 } from 'lucide-react'
import type { CountSlice, Stats } from '@mcu/shared'

import { ShelfHeading, ShelfLink } from '@/components/dashboard/Shelf'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchCollectionValue, fetchStats, poundsFromCents, type CollectionValue } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

const COUNT = new Intl.NumberFormat('en-GB')

function pounds(total: string, currency: string): string {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency, maximumFractionDigits: 0 }).format(
    Number(total),
  )
}

function copiesDetail(stats: Stats): ReactNode {
  if (stats.physicalCopies === undefined || stats.physicalAndDownloadCopies === undefined) {
    return <>Physical/download split is temporarily unavailable.</>
  }
  return (
    <>
      <span className="block">{COUNT.format(stats.physicalCopies)} physical · {COUNT.format(stats.downloadCopies)} download</span>
      <span className="mt-1 block">{COUNT.format(stats.physicalAndDownloadCopies)} include both</span>
    </>
  )
}

function NumberCard({ label, value, detail, wide = false }: { label: string; value: string; detail?: ReactNode; wide?: boolean }) {
  return (
    <li className={`min-w-0 ${wide ? 'col-span-2' : ''}`}>
      <dl className="h-full border-l-2 border-l-accent bg-card px-4 py-3 shadow-soft">
        <dt className="metadata-label">{label}</dt>
        <dd className="mt-1 break-words font-display text-2xl font-semibold tabular-nums tracking-tight text-foreground">
          {value}
        </dd>
        {detail ? <dd className="mt-0.5 text-xs leading-4 text-muted-foreground">{detail}</dd> : null}
      </dl>
    </li>
  )
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

/**
 * The worth card: the stored used-copy figure, with observed sales counted when present.
 * "Update values" and the bid trial moved to Admin's "Collection value" with W2 (#249).
 * Both people see an explicit no-value state; only an admin sees where to start one.
 */
function WorthCard({ value, isAdmin, pending, error, offline }: { value: CollectionValue | undefined; isAdmin: boolean; pending: boolean; error: boolean; offline: boolean }) {
  if (!value) return <NumberCard wide label="Estimated used value" value={pending && !offline ? '…' : 'Unavailable'} detail={offline ? 'Reconnect to load the stored estimate. Collection counts are still available.' : pending ? 'Loading the stored estimate' : 'The value could not be loaded. Collection counts are still available.'} />
  const running = value.run?.status === 'running'
  if (value.total === null) {
    return (
      <NumberCard
        wide
        label="Estimated used value"
        value="Not valued yet"
        detail={running ? 'Pricing now' : isAdmin ? <ShelfLink to="/valuation">Value it in Admin</ShelfLink> : 'No stored estimate is available yet.'}
      />
    )
  }
  return (
    <NumberCard
      wide
      label="Estimated used value"
      value={`≈ ${pounds(value.total, value.currency)}`}
      detail={
        <>
          <span className="block">{COUNT.format(value.pricedDiscs)} of {COUNT.format(value.discs)} physical copies priced</span>
          <span className="mt-1 block">{COUNT.format(value.salesBackedDiscs)} based on observed sales</span>
          {running ? <span className="mt-1 block" role="status">Pricing now</span> : null}
          {error ? <span className="mt-1 block" role="status">The latest value could not be loaded; showing the stored estimate.</span> : null}
          <details className="mt-2 border-t border-border pt-1">
            <summary className="list-link flex min-h-11 cursor-pointer items-center text-primary">How this estimate works</summary>
            <p className="pb-2 leading-5">
              Each physical copy is valued as used, including postage. Three observed sales use the median
              of their last advertised listing prices; otherwise a current used asking-price stand-in is
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

/**
 * AA3 (#299): five visible metrics, then an in-place breakdown. Craig approved this
 * collection-only exception to W2's sideways shelves and retained both personal/match counts.
 *
 * **Most watched is gone** (snag 4): on 5 Oct 8 of its 10 films were also in Highlights' Most
 * rewatched, which counts the same viewings and says whose. The stats API still returns it,
 * so a web build from before W2 still parses the response.
 *
 * Spend over time keeps S3's rule: shown only with data, and when it has none one line says
 * why, rather than an empty chart.
 */
export function CollectionShelf() {
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const statsQuery = useQuery({ queryKey: ['stats'], queryFn: fetchStats })
  const valueQuery = useQuery({
    queryKey: ['collection-value'],
    queryFn: fetchCollectionValue,
    // Poll while a run is pricing, as the full panel in Admin does.
    refetchInterval: (current) => (current.state.data?.run?.status === 'running' ? 5_000 : false),
  })
  const stats = statsQuery.data
  const value = valueQuery.data
  const state = listState(statsQuery, false)

  let body: ReactNode
  let breakdown: ReactNode = null
  if (state === 'offline') {
    body = (
      <StatePanel
        compact
        tone="offline"
        title="Stats are not cached here"
        description="Reconnect to load the collection ledger on this device."
      />
    )
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
    body = <StatePanel compact tone="loading" title="Counting the archive" />
  } else {
    const spendNote =
      stats.spendOverTime.length > 0
        ? null
        : stats.itemsWithPrice === 0
          ? 'Spend over time appears once purchase prices are recorded; the imported spreadsheet never carried one.'
          : 'Spend over time appears once the recorded prices carry a purchase date.'
    body = (
        <ul aria-label="The collection in numbers" className="grid grid-cols-2 gap-3">
          <NumberCard label="Titles owned" value={COUNT.format(stats.totalMovies)} detail="Films and TV series" />
          <NumberCard
            label="Copies catalogued"
            value={COUNT.format(stats.totalItems)}
            detail={copiesDetail(stats)}
          />
          <WorthCard value={value} isAdmin={isAdmin} pending={valueQuery.isPending} error={valueQuery.isError} offline={listState(valueQuery, false) === 'offline'} />
          <NumberCard label="You've watched" value={COUNT.format(stats.watchedMovies)} detail="Distinct titles in your diary, including titles you don't own" />
          <NumberCard label="Matched on TMDB" value={COUNT.format(stats.identifiedMovies)} detail={<>Of {COUNT.format(stats.totalMovies)} owned titles. A match can still need checking.</>} />
        </ul>
    )
    breakdown = (
        <details className="border-t border-border">
          <summary className="list-link flex min-h-11 cursor-pointer items-center text-sm font-semibold text-primary">Collection breakdown</summary>
          <ul aria-label="The collection's shape" className="grid grid-cols-1 gap-3 pb-3 sm:grid-cols-2">
          <ChartCard title="Formats (copies)">
            <BarChart slices={stats.formats} countOf={(s) => s.itemCount} />
            <p className="text-xs text-muted-foreground">Copies can carry more than one format; these counts overlap.</p>
          </ChartCard>
          <ChartCard title="Where they live (copies)">
            <BarChart slices={stats.sections} countOf={(s) => s.itemCount} />
          </ChartCard>
          <ChartCard title="Genres (titles)">
            <BarChart slices={stats.genres.slice(0, 12)} countOf={(s) => s.movieCount} />
            <p className="text-xs text-muted-foreground">The 12 most common genres. A title can have more than one.</p>
          </ChartCard>
          <ChartCard title="Decades (titles)">
            <BarChart
              slices={stats.decades.map((d) => ({
                key: String(d.decade),
                label: d.label,
                itemCount: d.movieCount,
                movieCount: d.movieCount,
              }))}
              countOf={(s) => s.movieCount}
            />
          </ChartCard>
          {stats.spendOverTime.length > 0 ? (
            <ChartCard title="Recorded spending">
              <SpendChart stats={stats} />
            </ChartCard>
          ) : null}
          </ul>
        {spendNote ? <p className="text-xs leading-5 text-muted-foreground">{spendNote}</p> : null}
        </details>
    )
  }

  return (
    <section aria-labelledby="home-collection" className="space-y-3">
      <ShelfHeading
        id="home-collection"
        title="The collection"
        icon={BarChart3}
      />
      {body}
      <Link to="/movies" className="list-link flex min-h-11 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
        Browse the archive
      </Link>
      {breakdown}
    </section>
  )
}
