import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, Copy, Eye, EyeOff, Globe, HelpCircle, MapPin, Search, Tv, WifiOff, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { FormatBadge } from '@/components/movies/FormatBadge'
import { Poster } from '@/components/movies/Poster'
import { fetchSearch, fetchSearchBeyond, type BeyondResult, type MovieListItem } from '@/lib/api'
import { cn, formatShortDate } from '@/lib/utils'

function highlight(text: string, query: string): ReactNode {
  if (!query.trim()) return text
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const matcher = new RegExp(`(${escaped})`, 'gi')
  return text.split(matcher).map((part, index) =>
    index % 2 === 1 ? (
      <mark key={`${part}-${index}`} className="rounded-sm bg-warning/20 text-inherit">
        {part}
      </mark>
    ) : part,
  )
}

/** Batch T2: the person's own last watch, on every result that has one. */
function SeenLine({ lastWatchedAt }: { lastWatchedAt: string | null }) {
  return lastWatchedAt ? (
    <span className="inline-flex items-center gap-1 text-foreground">
      <Eye className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden /> Seen {formatShortDate(lastWatchedAt)}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1">
      <EyeOff className="h-3.5 w-3.5 shrink-0" aria-hidden /> Not seen
    </span>
  )
}

interface OptionProps {
  query: string
  active: boolean
  id: string
  onSelect: () => void
  onActivate: () => void
}

const OPTION_CLS = 'flex min-h-[4.75rem] w-full items-center gap-3 border-b border-border/70 px-3 py-2.5 text-left last:border-0'

function OwnedResult({ item, query, active, id, onSelect, onActivate }: OptionProps & { item: MovieListItem }) {
  const locations = item.locations.map((location) => location.label).join(' · ')

  return (
    <button
      id={id}
      type="button"
      role="option"
      aria-selected={active}
      tabIndex={-1}
      className={cn(OPTION_CLS, active ? 'bg-primary/10' : 'hover:bg-muted')}
      onMouseMove={onActivate}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onSelect}
    >
      <Poster path={item.posterPath} title={item.title} size="w92" decorative className="h-14 w-[2.35rem] shrink-0 rounded-sm" />
      <span className="min-w-0 flex-1">
        <span className="flex min-w-0 items-baseline gap-2">
          <span className="truncate text-sm font-semibold text-foreground">{highlight(item.title, query)}</span>
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{item.year ?? 'Year unknown'}</span>
        </span>
        <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1 font-semibold text-success">
            <Check className="h-3.5 w-3.5" aria-hidden /> Owned
          </span>
          {item.bestFormatOwned && <FormatBadge format={item.bestFormatOwned} />}
          {item.copyCount > 1 && (
            <span className="inline-flex items-center gap-1">
              <Copy className="h-3.5 w-3.5" aria-hidden /> {item.copyCount} copies
            </span>
          )}
        </span>
        <span className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex min-w-0 items-center gap-1 text-foreground">
            <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
            <span className="truncate">{locations || 'Location not recorded'}</span>
          </span>
          <SeenLine lastWatchedAt={item.lastWatchedAt} />
        </span>
      </span>
    </button>
  )
}

/** What a film beyond the shelf says under its title. */
function beyondLine(item: BeyondResult): ReactNode {
  if (item.maybeOwned) {
    return (
      <span className="inline-flex items-center gap-1 font-semibold text-warning">
        <HelpCircle className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="line-clamp-2">Might be your copy of “{item.maybeOwned.title}”</span>
      </span>
    )
  }
  if (!item.streamingChecked) {
    return <span>Tap for where to watch</span>
  }
  if (item.streamingOn.length === 0) {
    return <span>Not on a streaming service you'd subscribe to here</span>
  }
  return (
    <span className="inline-flex min-w-0 items-center gap-1 text-foreground">
      <Tv className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
      <span className="truncate">Streaming on {item.streamingOn.join(', ')}</span>
    </span>
  )
}

function BeyondResultOption({ item, query, active, id, onSelect, onActivate }: OptionProps & { item: BeyondResult }) {
  return (
    <button
      id={id}
      type="button"
      role="option"
      aria-selected={active}
      tabIndex={-1}
      className={cn(OPTION_CLS, active ? 'bg-primary/10' : 'hover:bg-muted')}
      onMouseMove={onActivate}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onSelect}
    >
      <Poster path={item.posterPath} title={item.title} size="w92" decorative className="h-14 w-[2.35rem] shrink-0 rounded-sm opacity-90" />
      <span className="min-w-0 flex-1">
        <span className="flex min-w-0 items-baseline gap-2">
          <span className="truncate text-sm font-semibold text-foreground">{highlight(item.title, query)}</span>
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{item.year ?? 'Year unknown'}</span>
        </span>
        <span className="mt-1.5 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {beyondLine(item)}
          {item.lastWatchedAt ? <SeenLine lastWatchedAt={item.lastWatchedAt} /> : null}
        </span>
      </span>
    </button>
  )
}

type Pick = { kind: 'owned'; item: MovieListItem } | { kind: 'beyond'; item: BeyondResult }

interface SearchBarProps {
  /** An owned film was picked. Defaults to opening its page. */
  onPickOwned?: (item: MovieListItem) => void
  /** A film beyond the shelf was picked. Defaults to its page, or its card if it has none. */
  onPickBeyond?: (item: BeyondResult) => void
  /** The app-wide search answers the "/" shortcut; a search embedded in a page must not. */
  global?: boolean
  label?: string
  placeholder?: string
}

/**
 * The film search — the header's, the phone's search sheet, and movie night's.
 *
 * **Batch T2 made it one search.** Owned films come first, with where they are and when
 * you last watched them; then films that are *not* on the shelf, from TMDB, with where they
 * stream. An owned film never appears in the second group — the API excludes it — and an
 * owned film nothing has identified yet is flagged there rather than shown as a stranger.
 */
export default function SearchBar({
  onPickOwned,
  onPickBeyond,
  global = true,
  label = 'Search films',
  placeholder = 'Search title, format or shelf…',
}: SearchBarProps = {}) {
  const navigate = useNavigate()
  const resultsId = useId()
  const statusId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)

  const searchQuery = useQuery({
    queryKey: ['search', query],
    queryFn: () => fetchSearch(query, 20),
    enabled: query.length >= 2,
    staleTime: 30_000,
  })
  const beyondQuery = useQuery({
    queryKey: ['search-beyond', query],
    queryFn: () => fetchSearchBeyond(query),
    enabled: query.length >= 2,
    staleTime: 5 * 60_000,
    retry: false,
  })
  const results = searchQuery.data?.items ?? []
  const beyond = beyondQuery.data?.items ?? []
  const options: Pick[] = [
    ...results.map((item) => ({ kind: 'owned' as const, item })),
    ...beyond.map((item) => ({ kind: 'beyond' as const, item })),
  ]
  const unavailable = searchQuery.fetchStatus === 'paused' && searchQuery.data === undefined
  const showDropdown = open && query.length >= 2

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }, [])

  useEffect(() => {
    setActiveIndex(options.length > 0 ? 0 : -1)
  }, [query, options.length])

  const handleChange = useCallback((value: string) => {
    setInputValue(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const next = value.trim()
      setQuery(next)
      setOpen(next.length >= 2)
    }, 250)
  }, [])

  const handleClear = useCallback(() => {
    setInputValue('')
    setQuery('')
    setOpen(false)
    setActiveIndex(-1)
    inputRef.current?.focus()
  }, [])

  const handleSelect = useCallback((pick: Pick) => {
    setOpen(false)
    setInputValue('')
    setQuery('')
    if (pick.kind === 'owned') {
      if (onPickOwned) onPickOwned(pick.item)
      else navigate(`/movies/${pick.item.id}`)
      return
    }
    if (onPickBeyond) {
      onPickBeyond(pick.item)
      return
    }
    // A film with a page here — watched, wanted or sold — opens it, history and all.
    if (pick.item.movieId) navigate(`/movies/${pick.item.movieId}`)
    else navigate(`/films/tmdb/${pick.item.tmdbId}`, { state: { maybeOwned: pick.item.maybeOwned } })
  }, [navigate, onPickBeyond, onPickOwned])

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setOpen(false)
      inputRef.current?.blur()
      return
    }
    if (!showDropdown || options.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % options.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => (index <= 0 ? options.length - 1 : index - 1))
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault()
      handleSelect(options[activeIndex])
    }
  }

  useEffect(() => {
    const onFocusSearch = () => {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
    const onEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        if (document.activeElement === inputRef.current) inputRef.current?.blur()
      }
    }
    if (global) window.addEventListener('mcu:focus-search', onFocusSearch)
    document.addEventListener('keydown', onEscape)
    return () => {
      if (global) window.removeEventListener('mcu:focus-search', onFocusSearch)
      document.removeEventListener('keydown', onEscape)
    }
  }, [global])

  let status = ''
  if (searchQuery.isFetching && results.length === 0) status = 'Searching your archive…'
  else if (unavailable) status = 'Search is waiting for a connection. Cached collection pages are still available.'
  else if (searchQuery.isError) status = 'The archive could not be searched. Try again when the connection is stable.'
  else if (results.length === 0) status = `No owned films found for “${query}”.`

  let beyondStatus: ReactNode = null
  if (beyondQuery.fetchStatus === 'paused' && beyondQuery.data === undefined) {
    beyondStatus = <><WifiOff className="h-3.5 w-3.5 shrink-0" aria-hidden /> Films outside the collection need a connection.</>
  } else if (beyondQuery.isFetching && beyond.length === 0) {
    beyondStatus = <><Globe className="h-3.5 w-3.5 shrink-0" aria-hidden /> Looking beyond the shelf…</>
  } else if (beyondQuery.isError || beyondQuery.data?.unavailable) {
    beyondStatus = <><AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden /> TMDB didn't answer, so only your own films are shown.</>
  }

  return (
    <div className="relative w-full">
      <div className="relative flex items-center">
        <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-muted-foreground" aria-hidden />
        <input
          ref={inputRef}
          type="search"
          role="combobox"
          value={inputValue}
          onChange={(event) => handleChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (query.length >= 2) setOpen(true) }}
          onBlur={() => setOpen(false)}
          placeholder={placeholder}
          aria-label={label}
          aria-autocomplete="list"
          aria-expanded={showDropdown}
          aria-controls={showDropdown ? resultsId : undefined}
          aria-activedescendant={activeIndex >= 0 ? `${resultsId}-${activeIndex}` : undefined}
          aria-describedby={showDropdown && status ? statusId : undefined}
          className="h-11 w-full rounded-md border border-input bg-card pl-10 pr-11 text-sm text-foreground shadow-soft placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30"
        />
        {inputValue ? (
          <button
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={handleClear}
            className="touch-target absolute right-0 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        ) : global ? (
          <kbd className="pointer-events-none absolute right-3 hidden rounded-sm border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.625rem] text-muted-foreground sm:block">/</kbd>
        ) : null}
      </div>

      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 max-h-[min(32rem,70dvh)] overflow-y-auto rounded-lg border border-border bg-popover shadow-lift">
          {status && (
            <div id={statusId} role={searchQuery.isError ? 'alert' : 'status'} className="flex min-h-16 items-center justify-center gap-2 px-5 py-3 text-center text-sm text-muted-foreground">
              {unavailable ? <WifiOff className="h-4 w-4 shrink-0" aria-hidden /> : searchQuery.isError ? <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden /> : null}
              <span>{status}</span>
            </div>
          )}
          {options.length > 0 && (
            <div id={resultsId} role="listbox" aria-label="Film search results">
              {results.length > 0 && (
                <div role="group" aria-label="In the archive">
                  {results.map((item, index) => (
                    <OwnedResult
                      key={item.id}
                      id={`${resultsId}-${index}`}
                      item={item}
                      query={query}
                      active={index === activeIndex}
                      onActivate={() => setActiveIndex(index)}
                      onSelect={() => handleSelect({ kind: 'owned', item })}
                    />
                  ))}
                </div>
              )}
              {beyond.length > 0 && (
                <div role="group" aria-labelledby={`${resultsId}-beyond`}>
                  <p id={`${resultsId}-beyond`} className="border-y border-border bg-surface-sunken/60 px-3 py-1.5 text-[0.6875rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    Not in the collection
                  </p>
                  {beyond.map((item, offset) => {
                    const index = results.length + offset
                    return (
                      <BeyondResultOption
                        key={item.tmdbId}
                        id={`${resultsId}-${index}`}
                        item={item}
                        query={query}
                        active={index === activeIndex}
                        onActivate={() => setActiveIndex(index)}
                        onSelect={() => handleSelect({ kind: 'beyond', item })}
                      />
                    )
                  })}
                </div>
              )}
            </div>
          )}
          {beyondStatus && (
            <p role="status" className="flex items-center justify-center gap-2 border-t border-border px-3 py-2 text-center text-xs text-muted-foreground">
              {beyondStatus}
            </p>
          )}
          {results.length > 0 && (
            <p className="border-t border-border bg-surface-sunken/50 px-3 py-2 text-center text-xs text-muted-foreground">
              {searchQuery.data?.total.toLocaleString()} owned {searchQuery.data?.total === 1 ? 'film' : 'films'} found
              {beyond.length > 0 ? ` · ${String(beyond.length)} more not in the collection` : ''} · Use ↑ and ↓ to move
            </p>
          )}
        </div>
      )}
    </div>
  )
}
