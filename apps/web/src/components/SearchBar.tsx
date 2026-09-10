import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, Copy, MapPin, Search, WifiOff, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { FormatBadge } from '@/components/movies/FormatBadge'
import { Poster } from '@/components/movies/Poster'
import { fetchSearch, type MovieListItem } from '@/lib/api'
import { cn } from '@/lib/utils'

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

interface MovieResultProps {
  item: MovieListItem
  query: string
  active: boolean
  id: string
  onSelect: (id: string) => void
  onActivate: () => void
}

function MovieResult({ item, query, active, id, onSelect, onActivate }: MovieResultProps) {
  const locations = item.locations.map((location) => location.label).join(' · ')

  return (
    <button
      id={id}
      type="button"
      role="option"
      aria-selected={active}
      tabIndex={-1}
      className={cn(
        'flex min-h-[4.75rem] w-full items-center gap-3 border-b border-border/70 px-3 py-2.5 text-left last:border-0',
        active ? 'bg-primary/10' : 'hover:bg-muted',
      )}
      onMouseMove={onActivate}
      onMouseDown={(event) => event.preventDefault()}
      onClick={() => onSelect(item.id)}
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
        <span className="mt-1 flex min-w-0 items-center gap-1 text-xs text-foreground">
          <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
          <span className="truncate">{locations || 'Location not recorded'}</span>
        </span>
      </span>
    </button>
  )
}

export default function SearchBar() {
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
  const results = searchQuery.data?.items ?? []
  const unavailable = searchQuery.fetchStatus === 'paused' && searchQuery.data === undefined
  const showDropdown = open && query.length >= 2

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }, [])

  useEffect(() => {
    setActiveIndex(results.length > 0 ? 0 : -1)
  }, [query, results.length])

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

  const handleSelect = useCallback((id: string) => {
    setOpen(false)
    setInputValue('')
    setQuery('')
    navigate(`/movies/${id}`)
  }, [navigate])

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setOpen(false)
      inputRef.current?.blur()
      return
    }
    if (!showDropdown || results.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => (index <= 0 ? results.length - 1 : index - 1))
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault()
      handleSelect(results[activeIndex].id)
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
    window.addEventListener('mcu:focus-search', onFocusSearch)
    document.addEventListener('keydown', onEscape)
    return () => {
      window.removeEventListener('mcu:focus-search', onFocusSearch)
      document.removeEventListener('keydown', onEscape)
    }
  }, [])

  let status = ''
  if (searchQuery.isFetching && results.length === 0) status = 'Searching your archive…'
  else if (unavailable) status = 'Search is waiting for a connection. Cached collection pages are still available.'
  else if (searchQuery.isError) status = 'The archive could not be searched. Try again when the connection is stable.'
  else if (results.length === 0) status = `No owned films found for “${query}”.`

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
          placeholder="Search title, format or shelf…"
          aria-label="Search films"
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
        ) : (
          <kbd className="pointer-events-none absolute right-3 hidden rounded-sm border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.625rem] text-muted-foreground sm:block">/</kbd>
        )}
      </div>

      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 max-h-[min(28rem,65dvh)] overflow-y-auto rounded-lg border border-border bg-popover shadow-lift">
          {status && (
            <div id={statusId} role={searchQuery.isError ? 'alert' : 'status'} className="flex min-h-20 items-center justify-center gap-2 px-5 py-4 text-center text-sm text-muted-foreground">
              {unavailable ? <WifiOff className="h-4 w-4 shrink-0" aria-hidden /> : searchQuery.isError ? <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" aria-hidden /> : null}
              <span>{status}</span>
            </div>
          )}
          {results.length > 0 && (
            <div id={resultsId} role="listbox" aria-label="Owned film search results">
              {results.map((item, index) => (
                <MovieResult
                  key={item.id}
                  id={`${resultsId}-${index}`}
                  item={item}
                  query={query}
                  active={index === activeIndex}
                  onActivate={() => setActiveIndex(index)}
                  onSelect={handleSelect}
                />
              ))}
            </div>
          )}
          {results.length > 0 && (
            <p className="border-t border-border bg-surface-sunken/50 px-3 py-2 text-center text-xs text-muted-foreground">
              {searchQuery.data?.total.toLocaleString()} owned {searchQuery.data?.total === 1 ? 'film' : 'films'} found · Use ↑ and ↓ to move
            </p>
          )}
        </div>
      )}
    </div>
  )
}
