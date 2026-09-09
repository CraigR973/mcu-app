import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bookmark, Check, Loader2, Plus, Search, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { WantedItem } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/auth'
import {
  addWanted,
  fetchWanted,
  FORMATS,
  formatLabel,
  posterUrl,
  removeWanted,
  searchTmdb,
  updateWanted,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

function AddWantedPanel() {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [preferredFormat, setPreferredFormat] = useState('')
  const [maxPrice, setMaxPrice] = useState('')

  const searchQuery = useQuery({
    queryKey: ['tmdb-search', submitted],
    queryFn: () => searchTmdb(submitted),
    enabled: submitted.length >= 2,
  })
  const add = useMutation({
    mutationFn: (result: NonNullable<typeof searchQuery.data>['results'][number]) =>
      addWanted({
        ...(result.movieId ? { movieId: result.movieId } : { tmdbId: result.tmdbId }),
        preferredFormat: preferredFormat || null,
        maxPrice: maxPrice || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['wanted'] })
      void queryClient.invalidateQueries({ queryKey: ['recommendations'] })
      void queryClient.invalidateQueries({ queryKey: ['new-releases'] })
    },
  })

  const results = searchQuery.data?.results ?? []
  const searchState = listState(searchQuery, results.length === 0)

  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Add a film</h2>
        <p className="text-xs text-muted-foreground">
          Search by title, then optionally set the format and maximum price you want.
        </p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          setSubmitted(query.trim())
        }}
      >
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search TMDB by title…"
          aria-label="Search for a wanted film"
        />
        <Button type="submit" size="sm" disabled={query.trim().length < 2}>
          {searchQuery.isFetching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          Search
        </Button>
      </form>
      <div className="flex flex-wrap gap-2">
        <label className="text-xs text-muted-foreground">
          <span className="sr-only">Preferred format</span>
          <select
            value={preferredFormat}
            onChange={(event) => setPreferredFormat(event.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground"
            aria-label="Preferred format"
          >
            <option value="">Any format</option>
            {FORMATS.map((format) => (
              <option key={format.value} value={format.value}>
                {format.label}
              </option>
            ))}
          </select>
        </label>
        <Input
          value={maxPrice}
          onChange={(event) => setMaxPrice(event.target.value)}
          inputMode="decimal"
          type="number"
          min="0.01"
          step="0.01"
          placeholder="Max £ (optional)"
          aria-label="Maximum price in pounds"
          className="max-w-40"
        />
      </div>

      {submitted.length >= 2 && searchState === 'error' ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(searchQuery.error, 'Could not reach TMDB.')}
        </p>
      ) : null}
      {submitted.length >= 2 && searchState === 'empty' ? (
        <p className="text-xs text-muted-foreground">No films matched “{submitted}”.</p>
      ) : null}
      {add.isError ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(add.error, 'Could not add that film.')}
        </p>
      ) : null}

      {results.length > 0 ? (
        <ul className="space-y-2">
          {results.map((result) => (
            <li
              key={result.tmdbId}
              className="flex items-center gap-3 rounded-md border border-border p-2"
            >
              <img
                src={posterUrl(result.posterPath, 'w92')}
                alt=""
                loading="lazy"
                className="h-14 w-10 shrink-0 rounded object-cover"
              />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground">{result.title}</p>
                <p className="text-xs text-muted-foreground">
                  {result.year ?? 'Year unknown'}
                  {result.inCollection ? ' · already catalogued' : ''}
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                disabled={add.isPending}
                onClick={() => add.mutate(result)}
              >
                {add.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Add
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function Card({ item }: { item: WantedItem }) {
  const { profile } = useAuth()
  const queryClient = useQueryClient()

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['wanted'] })
    void queryClient.invalidateQueries({ queryKey: ['recommendations'] })
    void queryClient.invalidateQueries({ queryKey: ['new-releases'] })
  }

  const toggle = useMutation({
    mutationFn: () => updateWanted(item.id, { isActive: !item.isActive }),
    onSuccess: refresh,
  })
  const remove = useMutation({
    mutationFn: () => removeWanted(item.id),
    onSuccess: refresh,
  })

  return (
    <li
      className={cn(
        'flex items-center gap-3 rounded-lg border border-border bg-card p-3',
        item.isActive ? '' : 'opacity-60',
      )}
    >
      <img
        src={posterUrl(item.posterPath, 'w92')}
        alt=""
        loading="lazy"
        className="h-16 w-11 shrink-0 rounded object-cover"
      />
      <div className="min-w-0 flex-1">
        <Link
          to={`/movies/${item.movieId}`}
          className="font-medium text-foreground hover:underline"
        >
          {item.movieTitle}
        </Link>
        <p className="text-xs text-muted-foreground">
          {[
            item.year ? String(item.year) : null,
            formatLabel(item.preferredFormat) ?? null,
            item.maxPrice ? `under £${item.maxPrice}` : null,
          ]
            .filter(Boolean)
            .join(' · ') || 'any format, any price'}
        </p>
        {/* Wanting a film you own is not an error — a DVD-to-4K upgrade is exactly that —
            so it is said plainly rather than refused. */}
        {item.ownedAlready ? (
          <p className="text-[11px] text-amber-500">
            You already own a copy — an upgrade?
          </p>
        ) : null}
        {!item.isActive ? (
          <p className="text-[11px] text-muted-foreground">No longer looking</p>
        ) : null}
      </div>

      {profile?.role === 'admin' ? (
        <>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={toggle.isPending}
            onClick={() => toggle.mutate()}
          >
            {toggle.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            {item.isActive ? 'Stop looking' : 'Look again'}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-label={`Remove ${item.movieTitle}`}
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </>
      ) : null}
    </li>
  )
}

/**
 * §5.1's wanted list — the table four earlier batches were waiting on.
 *
 * **"Stop looking" and "remove" are different buttons on purpose.** `is_active` is a
 * decision worth keeping ("I bought it elsewhere", "I went off it"); `deleted_at` is an
 * accident worth undoing, and only the second goes to the Trash. Collapsing them would
 * lose the distinction the schema is built around.
 */
export default function WantedPage() {
  const [activeOnly, setActiveOnly] = useState(false)
  const { profile } = useAuth()

  const wantedQuery = useQuery({
    queryKey: ['wanted', activeOnly],
    queryFn: () => fetchWanted(activeOnly),
  })
  const items = wantedQuery.data?.items ?? []
  const state = listState(wantedQuery, items.length === 0)

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Wanted</h1>
        <p className="text-sm text-muted-foreground">
          Films to look out for.{' '}
          {wantedQuery.data ? `${wantedQuery.data.activeCount} still looking.` : ''}
        </p>
      </div>

      {profile?.role === 'admin' ? <AddWantedPanel /> : null}

      <div className="flex gap-1">
        {[
          { value: false, label: 'All' },
          { value: true, label: 'Still looking' },
        ].map((option) => (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => setActiveOnly(option.value)}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              activeOnly === option.value
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the wanted list could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(wantedQuery.error, 'Could not load the wanted list.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Bookmark className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Nothing on the wanted list yet.</p>
          <p className="max-w-sm text-xs text-muted-foreground">
            Use “Add a film” above, or add a whole set&rsquo;s missing films from{' '}
            <Link to="/insights" className="text-primary hover:underline">Insights</Link>.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <Card key={item.id} item={item} />
          ))}
        </ul>
      )}
    </div>
  )
}
