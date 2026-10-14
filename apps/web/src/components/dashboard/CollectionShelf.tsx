import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3 } from 'lucide-react'
import type { CountSlice, Stats } from '@mcu/shared'

import { ShelfHeading, ShelfLink, ShelfRow } from '@/components/dashboard/Shelf'
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

function NumberCard({ label, value, detail }: { label: string; value: string; detail?: ReactNode }) {
  return (
    <li className="w-40 shrink-0 snap-start">
      <dl className="h-full border-l-2 border-l-accent bg-card px-4 py-3 shadow-soft">
        <dt className="metadata-label">{label}</dt>
        <dd className="mt-1 whitespace-nowrap font-display text-2xl font-semibold tabular-nums tracking-tight text-foreground">
          {value}
        </dd>
        {detail ? <dd className="mt-0.5 text-xs leading-4 text-muted-foreground">{detail}</dd> : null}
      </dl>
    </li>
  )
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <li className="w-72 shrink-0 snap-start self-start sm:w-80">
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
          <li key={slice.key} className="flex items-center gap-2">
            <span className="w-24 shrink-0 truncate text-xs text-muted-foreground">{slice.label}</span>
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
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {poundsFromCents(points[points.length - 1]?.cumulativeCents ?? 0)} across{' '}
        {stats.itemsWithPrice.toLocaleString()} priced discs
      </p>
      <ul className="flex h-24 items-end gap-1">
        {points.map((point) => (
          <li
            key={point.month}
            className="relative flex-1 rounded-t-sm bg-primary/60"
            style={{ height: `${String(Math.max(4, (point.cumulativeCents / peak) * 100))}%` }}
            title={`${point.month} · ${poundsFromCents(point.cumulativeCents)}`}
          >
            <span className="sr-only">
              {point.month}: {poundsFromCents(point.cumulativeCents)}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-muted-foreground">
        {points[0]?.month} – {points[points.length - 1]?.month}
      </p>
    </div>
  )
}

/**
 * The worth card: what the collection is worth at eBay asking prices (Batch T6), read only.
 * "Update values" and the bid trial moved to Admin's "Collection value" with W2 (#249).
 * Hidden from a viewer until there is a total, as before; an admin sees where to start one.
 */
function WorthCard({ value, isAdmin }: { value: CollectionValue | undefined; isAdmin: boolean }) {
  if (!value) return null
  const running = value.run?.status === 'running'
  if (value.total === null) {
    if (!isAdmin && !running) return null
    return (
      <NumberCard
        label="Worth"
        value="—"
        detail={running ? 'Pricing now' : <ShelfLink to="/valuation">Value it in Admin</ShelfLink>}
      />
    )
  }
  return (
    <NumberCard
      label="Worth"
      value={`≈ ${pounds(value.total, value.currency)}`}
      detail={running ? 'Pricing now' : `${COUNT.format(value.pricedDiscs)} of ${COUNT.format(value.discs)} discs priced`}
    />
  )
}

/**
 * The collection, first on Home — Batch W2 (#249: "maybe also have the collection section
 * at the top"). Two sideways rows under one heading: the numbers, then the charts.
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
      <>
        <ShelfRow label="The collection in numbers">
          <NumberCard label="Films" value={COUNT.format(stats.totalMovies)} />
          <NumberCard label="Discs" value={COUNT.format(stats.totalItems)} />
          <WorthCard value={value} isAdmin={isAdmin} />
          <NumberCard label="You've watched" value={COUNT.format(stats.watchedMovies)} />
          <NumberCard label="Identified" value={COUNT.format(stats.identifiedMovies)} />
        </ShelfRow>
        <ShelfRow label="The collection's shape">
          <ChartCard title="Formats">
            <BarChart slices={stats.formats} countOf={(s) => s.itemCount} />
          </ChartCard>
          <ChartCard title="Where they live">
            <BarChart slices={stats.sections} countOf={(s) => s.itemCount} />
          </ChartCard>
          <ChartCard title="Genres">
            <BarChart slices={stats.genres.slice(0, 12)} countOf={(s) => s.movieCount} />
          </ChartCard>
          <ChartCard title="Decades">
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
            <ChartCard title="Spend over time">
              <SpendChart stats={stats} />
            </ChartCard>
          ) : null}
        </ShelfRow>
        {spendNote ? <p className="text-xs leading-5 text-muted-foreground">{spendNote}</p> : null}
      </>
    )
  }

  return (
    <section aria-labelledby="home-collection" className="space-y-3">
      <ShelfHeading
        id="home-collection"
        title="The collection"
        icon={BarChart3}
        caption={
          value?.total
            ? `Worth is ${value.valuedAs ? `${value.valuedAs}, ` : ''}at eBay asking prices, which usually run above what discs sell for.`
            : undefined
        }
      />
      {body}
    </section>
  )
}
