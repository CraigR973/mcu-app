import { useQuery } from '@tanstack/react-query'
import type { CountSlice, Stats } from '@mcu/shared'

import { StatePanel } from '@/components/ui/state-panel'
import { fetchStats, poundsFromCents, posterUrl } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-l-2 border-l-accent bg-card px-4 py-4 shadow-soft">
      <dt className="metadata-label">{label}</dt>
      <dd className="mt-1 font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">{value}</dd>
    </div>
  )
}

/**
 * A horizontal bar chart, in CSS.
 *
 * No chart library. Three of §13.1's four populated charts are "a label and a
 * proportion", which a flex row expresses exactly; pulling in a charting dependency for
 * that would add weight to every page load in a PWA whose whole point is working on a
 * phone with the network off.
 */
function BarChart({
  slices,
  countOf,
  max,
}: {
  slices: CountSlice[]
  countOf: (slice: CountSlice) => number
  max?: number
}) {
  const ceiling = max ?? Math.max(1, ...slices.map(countOf))
  return (
    <ul className="space-y-1.5">
      {slices.map((slice) => {
        const count = countOf(slice)
        return (
          <li key={slice.key} className="flex items-center gap-2">
            <span className="w-28 shrink-0 truncate text-xs text-muted-foreground">
              {slice.label}
            </span>
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

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="archive-panel space-y-4 p-5">
      <h3 className="section-heading text-lg">{title}</h3>
      {children}
    </section>
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
            <span className="sr-only">{point.month}: {poundsFromCents(point.cumulativeCents)}</span>
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
 * §13.1's stats, as a section of the merged Home rather than a page of its own — Batch S3.
 *
 * **Two of §13.1's five charts still have no data, and they are now hidden rather than
 * drawn empty.** `watch_log` is empty and no disc carries a `purchase_price`, so "most
 * watched" and "collection value over time" had nothing to show. Batch 14 answered that
 * with an explanatory panel each, on gotcha 19's principle that a page which lies
 * confidently is worse than one that errors. Batch S3 keeps the honesty and drops the
 * frames: the reasons are collected into **one line beneath the charts**, because two
 * empty panels on a page whose whole complaint was emptiness is the complaint (snag 5).
 *
 * The export moved to Admin with this batch — it is a maintenance action, not a reading
 * one, and it sat oddly at the foot of a dashboard.
 */
export function ArchiveStats() {
  const statsQuery = useQuery({ queryKey: ['stats'], queryFn: fetchStats })
  const stats = statsQuery.data
  const state = listState(statsQuery, false)

  if (state === 'offline') {
    return (
      <StatePanel
        compact
        tone="offline"
        title="Stats are not cached here"
        description="Reconnect to load the collection ledger on this device."
      />
    )
  }
  if (state === 'error') {
    return (
      <StatePanel
        compact
        tone="error"
        title="The collection ledger is unavailable"
        description={queryErrorMessage(statsQuery.error, 'Could not load the stats.')}
      />
    )
  }
  if (!stats) return <StatePanel compact tone="loading" title="Counting the archive" />

  // Collected rather than rendered as panels. Each entry says what is missing *and* what
  // would fill it, which is the part a hidden chart would otherwise take with it.
  const notShown: string[] = []
  if (stats.mostWatched.length === 0) {
    notShown.push('Most watched — nothing logged yet; it fills in as watches are recorded')
  }
  if (stats.spendOverTime.length === 0) {
    notShown.push(
      stats.itemsWithPrice === 0
        ? 'Spend over time — no purchase prices recorded, because the imported spreadsheet never carried one'
        : 'Spend over time — prices are recorded, but none carry a purchase date yet',
    )
  }

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Films" value={stats.totalMovies.toLocaleString()} />
        <Tile label="Discs" value={stats.totalItems.toLocaleString()} />
        <Tile label="Identified" value={stats.identifiedMovies.toLocaleString()} />
        <Tile label="You've watched" value={stats.watchedMovies.toLocaleString()} />
      </dl>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="Formats">
          <BarChart slices={stats.formats} countOf={(s) => s.itemCount} />
        </Panel>
        <Panel title="Where they live">
          <BarChart slices={stats.sections} countOf={(s) => s.itemCount} />
        </Panel>
        <Panel title="Genres">
          <BarChart slices={stats.genres.slice(0, 12)} countOf={(s) => s.movieCount} />
        </Panel>
        <Panel title="Decades">
          <BarChart
            slices={stats.decades.map((d) => ({
              key: String(d.decade),
              label: d.label,
              itemCount: d.movieCount,
              movieCount: d.movieCount,
            }))}
            countOf={(s) => s.movieCount}
          />
        </Panel>

        {stats.mostWatched.length > 0 && (
          <Panel title="Most watched">
            <ul className="space-y-1.5">
              {stats.mostWatched.map((film) => (
                <li key={film.movieId} className="flex items-center gap-2">
                  <img
                    src={posterUrl(film.posterPath, 'w92')}
                    alt=""
                    loading="lazy"
                    className="h-10 w-7 shrink-0 rounded object-cover"
                  />
                  <span className="min-w-0 flex-1 truncate text-xs text-foreground">
                    {film.title}
                  </span>
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {film.watchCount}×
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
        )}

        {stats.spendOverTime.length > 0 && (
          <Panel title="Spend over time">
            <SpendChart stats={stats} />
          </Panel>
        )}
      </div>

      {notShown.length > 0 && (
        <p className="text-xs leading-5 text-muted-foreground">
          <span className="font-semibold text-foreground">Not shown yet:</span>{' '}
          {notShown.join('. ')}.
        </p>
      )}
    </div>
  )
}
