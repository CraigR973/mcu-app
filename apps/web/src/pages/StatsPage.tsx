import { useQuery } from '@tanstack/react-query'
import { Download, FileJson, FileSpreadsheet, Loader2, Printer } from 'lucide-react'
import { useState } from 'react'
import type { CountSlice, Stats } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import {
  downloadExport,
  fetchStats,
  openPrintableCollection,
  poundsFromCents,
  posterUrl,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold text-foreground">{value}</p>
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
            <span className="h-3 flex-1 overflow-hidden rounded-sm bg-muted">
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

function Section({
  title,
  children,
  empty,
}: {
  title: string
  children: React.ReactNode
  empty?: string
}) {
  return (
    <section className="space-y-2 rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      {empty ? <p className="text-xs text-muted-foreground">{empty}</p> : children}
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
            className="flex-1 rounded-t-sm bg-primary/60"
            style={{ height: `${String(Math.max(4, (point.cumulativeCents / peak) * 100))}%` }}
            title={`${point.month} · ${poundsFromCents(point.cumulativeCents)}`}
          />
        ))}
      </ul>
      <p className="text-[11px] text-muted-foreground">
        {points[0]?.month} – {points[points.length - 1]?.month}
      </p>
    </div>
  )
}

/**
 * §13.1's stats dashboard and §13.3/§13.4's export links.
 *
 * **Two charts have no data in this collection yet, and they say so.** `watch_log` is
 * empty and no disc carries a `purchase_price` — the spreadsheet never had one — so
 * "most watched" and "collection value over time" would otherwise render as an empty
 * frame, which reads as a broken chart rather than as an honest absence. Each says what
 * it is waiting for. This is `STATUS.md` gotcha 19's lesson (a page that lies confidently
 * is worse than one that errors) applied to a dashboard instead of a list.
 */
export default function StatsPage() {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const statsQuery = useQuery({ queryKey: ['stats'], queryFn: fetchStats })
  const stats = statsQuery.data
  const state = listState(statsQuery, false)

  async function run(name: string, action: () => Promise<void>) {
    setBusy(name)
    setError(null)
    try {
      await action()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The export failed.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Stats</h1>
        <p className="text-sm text-muted-foreground">
          What the collection is made of, and how to take a copy of it with you.
        </p>
      </div>

      {state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the stats could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(statsQuery.error, 'Could not load the stats.')}
        </p>
      ) : !stats ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile label="Films" value={stats.totalMovies.toLocaleString()} />
            <Tile label="Discs" value={stats.totalItems.toLocaleString()} />
            <Tile label="Identified" value={stats.identifiedMovies.toLocaleString()} />
            <Tile label="You've watched" value={stats.watchedMovies.toLocaleString()} />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Section title="Formats">
              <BarChart slices={stats.formats} countOf={(s) => s.itemCount} />
            </Section>
            <Section title="Where they live">
              <BarChart slices={stats.sections} countOf={(s) => s.itemCount} />
            </Section>
            <Section title="Genres">
              <BarChart slices={stats.genres.slice(0, 12)} countOf={(s) => s.movieCount} />
            </Section>
            <Section title="Decades">
              <BarChart
                slices={stats.decades.map((d) => ({
                  key: String(d.decade),
                  label: d.label,
                  itemCount: d.movieCount,
                  movieCount: d.movieCount,
                }))}
                countOf={(s) => s.movieCount}
              />
            </Section>

            <Section
              title="Most watched"
              empty={
                stats.mostWatched.length === 0
                  ? 'Nothing logged yet — this fills in as you record watches.'
                  : undefined
              }
            >
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
            </Section>

            <Section
              title="Spend over time"
              empty={
                stats.spendOverTime.length === 0
                  ? stats.itemsWithPrice === 0
                    ? 'No purchase prices recorded — the imported spreadsheet never carried one. Add a price to a disc and this fills in.'
                    : 'Prices are recorded, but none carry a purchase date yet.'
                  : undefined
              }
            >
              <SpendChart stats={stats} />
            </Section>
          </div>

          <section className="space-y-3 rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground">Export</h2>
            <p className="text-xs text-muted-foreground">
              One row per disc. The printable view opens in a new tab — use your
              browser&rsquo;s Print dialog and &ldquo;Save as PDF&rdquo;.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy !== null}
                onClick={() => void run('csv', () => downloadExport('csv'))}
              >
                {busy === 'csv' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileSpreadsheet className="h-4 w-4" />
                )}
                CSV
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy !== null}
                onClick={() => void run('json', () => downloadExport('json'))}
              >
                {busy === 'json' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileJson className="h-4 w-4" />
                )}
                JSON
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy !== null}
                onClick={() => void run('html', () => downloadExport('html'))}
              >
                <Download className="h-4 w-4" />
                HTML
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={busy !== null}
                onClick={() => void run('print', openPrintableCollection)}
              >
                {busy === 'print' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Printer className="h-4 w-4" />
                )}
                Printable view
              </Button>
            </div>
            {error ? <p className={cn('text-sm text-destructive')}>{error}</p> : null}
          </section>
        </>
      )}
    </div>
  )
}
