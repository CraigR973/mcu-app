import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bookmark, Check, Loader2, Plus, PoundSterling, Search, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { WantedItem } from '@mcu/shared'

/** The body `PUT /wanted/{id}` replaces the row with — every field, always. */
type WantedUpdate = Parameters<typeof updateWanted>[1]

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { Badge } from '@/components/ui/badge'
import { Poster } from '@/components/movies/Poster'
import { FormatBadge } from '@/components/movies/FormatBadge'
import { useAuth } from '@/context/auth'
import {
  addWanted,
  fetchWanted,
  FORMATS,
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
  const [preferredEdition, setPreferredEdition] = useState('')
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
        preferredEdition: preferredEdition.trim() || null,
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
    <section className="archive-panel space-y-4 p-4 sm:p-5" aria-labelledby="add-wanted-heading">
      <div>
        <h2 id="add-wanted-heading" className="section-heading">Add a wanted film</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Search by title, then optionally set the format, edition and maximum price. The
          edition is free text — it picks between listings, it does not narrow the search.
        </p>
      </div>
      <form
        className="flex flex-col gap-2 sm:flex-row"
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
            className="select-control"
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
          value={preferredEdition}
          onChange={(event) => setPreferredEdition(event.target.value)}
          placeholder="Edition, e.g. Steelbook (optional)"
          aria-label="Preferred edition"
          className="max-w-56"
        />
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
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(searchQuery.error, 'Could not reach TMDB.')}
        </p>
      ) : null}
      {submitted.length >= 2 && searchState === 'offline' ? (
        <p className="text-sm text-muted-foreground">Search is waiting for a connection.</p>
      ) : null}
      {submitted.length >= 2 && searchState === 'empty' ? (
        <p className="text-xs text-muted-foreground">No films matched “{submitted}”.</p>
      ) : null}
      {add.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(add.error, 'Could not add that film.')}
        </p>
      ) : null}

      {results.length > 0 ? (
        <ul className="space-y-2">
          {results.map((result) => (
            <li
              key={result.tmdbId}
              className="flex items-center gap-3 border-t border-border py-3 first:border-t-0"
            >
              <Poster path={result.posterPath} title={result.title} size="w92" decorative className="h-14 w-10 shrink-0 rounded-sm" />
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

/**
 * The complete resource, with only what is changing overridden.
 *
 * **`PUT /wanted/{id}` is a full replace, and every field on its request model defaults to
 * `null`.** Sending `{ isActive }` alone therefore did not toggle a flag — it also wiped
 * the format, the edition, the maximum price and the notes, silently, every time somebody
 * pressed "Stop looking". Building the whole item here is what makes a partial-looking
 * call safe. `DECISIONS.md` #123.
 */
function fullUpdate(item: WantedItem, changes: Partial<WantedUpdate>): WantedUpdate {
  return {
    preferredFormat: item.preferredFormat,
    preferredEdition: item.preferredEdition,
    maxPrice: item.maxPrice,
    currency: item.currency,
    isActive: item.isActive,
    notes: item.notes ?? null,
    ...changes,
  }
}

function Card({ item }: { item: WantedItem }) {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const [editingBudget, setEditingBudget] = useState(false)
  const [budget, setBudget] = useState(item.maxPrice ?? '')

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['wanted'] })
    void queryClient.invalidateQueries({ queryKey: ['recommendations'] })
    void queryClient.invalidateQueries({ queryKey: ['new-releases'] })
  }

  const toggle = useMutation({
    mutationFn: () => updateWanted(item.id, fullUpdate(item, { isActive: !item.isActive })),
    onSuccess: refresh,
  })
  const saveBudget = useMutation({
    mutationFn: () =>
      updateWanted(item.id, fullUpdate(item, { maxPrice: budget.trim() || null })),
    onSuccess: () => {
      setEditingBudget(false)
      refresh()
    },
  })
  const remove = useMutation({
    mutationFn: () => removeWanted(item.id),
    onSuccess: refresh,
  })

  return (
    <li
      className={cn(
        'archive-panel flex flex-col gap-3 p-3 sm:flex-row sm:items-center',
        item.isActive ? '' : 'opacity-60',
      )}
    >
      <div className="flex min-w-0 flex-1 gap-3">
      <Poster path={item.posterPath} title={item.movieTitle} size="w92" decorative className="h-20 w-[3.35rem] shrink-0 rounded-sm" />
      <div className="min-w-0 flex-1 py-0.5">
        <Link
          to={`/movies/${item.movieId}`}
          className="font-medium text-foreground hover:underline"
        >
          {item.movieTitle}
        </Link>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {item.year && <span>{item.year}</span>}
          {item.preferredFormat && <FormatBadge format={item.preferredFormat} />}
          {item.preferredEdition && <Badge>{item.preferredEdition}</Badge>}
          {item.maxPrice && <Badge tone="primary">Up to £{item.maxPrice}</Badge>}
          {!item.preferredFormat && !item.preferredEdition && !item.maxPrice && <span>Any format or edition</span>}
        </div>
        {/* Wanting a film you own is not an error — a DVD-to-4K upgrade is exactly that —
            so it is said plainly rather than refused. */}
        {item.ownedAlready ? (
          <p className="mt-1 text-xs font-medium text-warning">
            You already own a copy — an upgrade?
          </p>
        ) : null}
        {!item.isActive ? (
          <p className="mt-1 text-xs text-muted-foreground">No longer looking</p>
        ) : null}
        {saveBudget.isError ? (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {queryErrorMessage(saveBudget.error, 'Could not save that limit.')}
          </p>
        ) : null}
      </div>
      </div>

      {profile?.role === 'admin' && editingBudget ? (
        <form
          className="flex flex-wrap items-center gap-2 border-t border-border pt-3 sm:border-0 sm:pt-0"
          onSubmit={(event) => {
            event.preventDefault()
            saveBudget.mutate()
          }}
        >
          <Input
            autoFocus
            value={budget}
            onChange={(event) => setBudget(event.target.value)}
            inputMode="decimal"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="Max £"
            aria-label={`Maximum price for ${item.movieTitle}`}
            className="w-24"
          />
          <Button
            type="button"
            size="sm"
            disabled={saveBudget.isPending}
            onClick={() => saveBudget.mutate()}
          >
            {saveBudget.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setBudget(item.maxPrice ?? '')
              setEditingBudget(false)
            }}
          >
            Cancel
          </Button>
        </form>
      ) : null}

      {profile?.role === 'admin' && !editingBudget ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3 sm:border-0 sm:pt-0">
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-label={`Set a maximum price for ${item.movieTitle}`}
            onClick={() => setEditingBudget(true)}
          >
            <PoundSterling className="h-4 w-4" />
            {item.maxPrice ? `£${item.maxPrice}` : 'Set a limit'}
          </Button>
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
          {(toggle.isError || remove.isError) && <p role="alert" className="w-full text-xs text-destructive">{queryErrorMessage(toggle.error ?? remove.error, 'That wanted-list change could not be saved.')}</p>}
        </div>
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
  // Keep the established one-step admin workflow: the form begins open, while the
  // header control lets it be folded away during routine list review.
  const [adding, setAdding] = useState(true)
  const { profile } = useAuth()

  const wantedQuery = useQuery({
    queryKey: ['wanted', activeOnly],
    queryFn: () => fetchWanted(activeOnly),
  })
  const items = wantedQuery.data?.items ?? []
  const state = listState(wantedQuery, items.length === 0)

  return (
    <div className="page-shell-narrow space-y-5">
      <PageHeader
        eyebrow="Acquisition list"
        title="Wanted"
        description="Titles and editions worth looking out for, with a clear ceiling before a tempting listing appears."
        meta={wantedQuery.data ? <span>{wantedQuery.data.activeCount} still being sought</span> : undefined}
        actions={profile?.role === 'admin' ? <Button type="button" onClick={() => setAdding((value) => !value)} aria-expanded={adding}><Plus aria-hidden />{adding ? 'Close add form' : 'Add a film'}</Button> : undefined}
      />

      {profile?.role === 'admin' && adding ? <AddWantedPanel /> : null}

      <div className="inline-flex overflow-hidden rounded-md border border-input bg-card" role="group" aria-label="Wanted-list view">
        {[
          { value: false, label: 'All' },
          { value: true, label: 'Still looking' },
        ].map((option) => (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => setActiveOnly(option.value)}
            className={cn(
              'touch-target min-h-11 border-r border-border px-4 text-sm font-semibold transition-colors last:border-r-0',
              activeOnly === option.value
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted',
            )}
            aria-pressed={activeOnly === option.value}
          >
            {option.label}
          </button>
        ))}
      </div>

      {state === 'loading' ? (
        <StatePanel tone="loading" title="Opening the wanted list" />
      ) : state === 'offline' ? (
        <StatePanel tone="offline" title="The wanted list is not cached here" description="Reconnect to load it on this device." />
      ) : state === 'error' ? (
        <StatePanel tone="error" title="The wanted list could not be opened" description={queryErrorMessage(wantedQuery.error, 'The server did not answer.')} />
      ) : state === 'empty' ? (
        <StatePanel tone="empty" icon={Bookmark} title={activeOnly ? 'Nothing is actively being sought' : 'Nothing on the wanted list yet'} description={profile?.role === 'admin' ? <>Add a title here, or add a set’s missing films from <Link to="/insights" className="font-semibold text-primary hover:underline">Insights</Link>.</> : 'Craig has not added any wanted titles yet.'} />
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
