import { useState } from 'react'
import type { SmartCollection, SmartCollectionIcon } from '@mcu/shared'

import { FilterBar } from '@/components/movies/FilterBar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  describeFilters,
  filtersToMovieFilters,
  type MovieFilters,
  type SmartCollectionInput,
} from '@/lib/api'
import { cn } from '@/lib/utils'

import { COLLECTION_ICONS, COLLECTION_ICON_NAMES } from './icons'

interface Props {
  existing?: SmartCollection
  pending: boolean
  error?: string | null
  onSave: (input: SmartCollectionInput) => void
  onCancel: () => void
}

const SELECT_CLS = 'select-control w-auto text-sm'

/**
 * Editing a smart collection *is* using the filter bar.
 *
 * §6.31 describes these as saved filter sets, so the editor reuses `FilterBar` rather
 * than growing its own controls. Two benefits, one of which is the point of the feature:
 * the person picks filters with the control they already know, and there is no second
 * place for the vocabulary to drift — a filter the collection view cannot express is one
 * this form cannot offer.
 */
export function SmartCollectionEditor({ existing, pending, error, onSave, onCancel }: Props) {
  const [name, setName] = useState(existing?.name ?? '')
  const [icon, setIcon] = useState<SmartCollectionIcon>(existing?.icon ?? 'sparkles')
  const [filters, setFilters] = useState<MovieFilters>(
    existing ? filtersToMovieFilters(existing.filters) : {},
  )
  const [sortBy, setSortBy] = useState<SmartCollection['sortBy']>(existing?.sortBy ?? 'title')
  const [sortOrder, setSortOrder] = useState<SmartCollection['sortOrder']>(
    existing?.sortOrder ?? 'asc',
  )
  const [isPinned, setIsPinned] = useState(existing?.isPinned ?? false)

  const trimmed = name.trim()

  function save() {
    onSave({
      name: trimmed,
      icon,
      // Spelled out rather than spread. `MovieFilters` also carries `sort` and
      // `order`, which the API's filter model rejects outright (`extra="forbid"`), and
      // relying on `JSON.stringify` to drop two `undefined`s would make a 422 the only
      // warning that the two shapes had diverged.
      filters: toNullable(filters),
      sortBy,
      sortOrder,
      isPinned,
      displayOrder: existing?.displayOrder ?? 0,
    })
  }

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Unwatched 4Ks from the 2010s"
          className="max-w-xs"
          aria-label="Collection name"
        />
        <div className="flex items-center gap-1" role="group" aria-label="Icon">
          {COLLECTION_ICON_NAMES.map((candidate) => {
            const Icon = COLLECTION_ICONS[candidate]
            return (
              <button
                key={candidate}
                type="button"
                aria-label={candidate}
                aria-pressed={icon === candidate}
                onClick={() => setIcon(candidate)}
                className={cn(
                  'touch-target flex items-center justify-center rounded-md border p-2 transition-colors',
                  icon === candidate
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-transparent text-muted-foreground hover:bg-muted',
                )}
              >
                <Icon size={16} />
              </button>
            )
          })}
        </div>
      </div>

      <div className="-mx-4 border-y border-border">
        {/* Saved collections persist the shared filter schema only. Live-only AV
            specification toggles and collection sort are deliberately omitted here so
            the editor never presents a choice it cannot save. */}
        <FilterBar filters={filters} onChange={setFilters} context="saved" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted-foreground" htmlFor="sc-sort">
          Sort by
        </label>
        <select
          id="sc-sort"
          className={SELECT_CLS}
          value={sortBy}
          onChange={(event) => setSortBy(event.target.value as SmartCollection['sortBy'])}
        >
          <option value="title">Title</option>
          <option value="year">Year</option>
          <option value="rating">Rating</option>
        </select>
        <select
          className={SELECT_CLS}
          aria-label="Sort direction"
          value={sortOrder}
          onChange={(event) =>
            setSortOrder(event.target.value as SmartCollection['sortOrder'])
          }
        >
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </select>

        <label className="ml-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={isPinned}
            onChange={(event) => setIsPinned(event.target.checked)}
          />
          Pin to dashboard
        </label>
      </div>

      <p className="text-xs text-muted-foreground">
        Selects: {describeFilters(toNullable(filters))}
      </p>

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}

      <div className="flex gap-2">
        <Button type="button" size="sm" disabled={pending || trimmed.length === 0} onClick={save}>
          {existing ? 'Save changes' : 'Create collection'}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

/** `MovieFilters` leaves an unset filter absent; the saved shape states it as `null`. */
function toNullable(filters: MovieFilters) {
  return {
    genreId: filters.genreId ?? null,
    year: filters.year ?? null,
    format: filters.format ?? null,
    section: filters.section ?? null,
    shelf: filters.shelf ?? null,
    decadeFrom: filters.decadeFrom ?? null,
    decadeTo: filters.decadeTo ?? null,
    minRating: filters.minRating ?? null,
    watched: filters.watched ?? null,
  }
}
