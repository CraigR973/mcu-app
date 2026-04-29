import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { fetchSearch, posterUrl, formatLabel, FORMAT_COLORS, type SearchResultItem } from '@/lib/api'

function highlight(text: string, query: string): string {
  if (!query.trim()) return text
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="bg-yellow-400/30 text-inherit rounded-sm">$1</mark>')
}

function MovieResult({ item, query, onSelect }: { item: SearchResultItem; query: string; onSelect: (id: number) => void }) {
  const year = item.release_date ? new Date(item.release_date).getFullYear() : null
  const fmtColor = item.best_format_owned ? FORMAT_COLORS[item.best_format_owned] ?? '' : ''
  const fmtLabel = formatLabel(item.best_format_owned)
  const titleHtml = highlight(item.title, query)

  return (
    <button
      className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-accent focus:bg-accent focus:outline-none"
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => onSelect(item.id)}
    >
      <img
        src={posterUrl(item.poster_path, 'w92')}
        alt=""
        className="h-10 w-7 shrink-0 rounded object-cover"
        loading="lazy"
      />
      <div className="min-w-0 flex-1">
        <p
          className="truncate text-sm font-medium text-foreground"
          dangerouslySetInnerHTML={{ __html: titleHtml }}
        />
        <p className="text-xs text-muted-foreground">
          {year}
          {fmtLabel && (
            <span className={`ml-2 rounded px-1 py-0.5 text-[10px] font-medium ${fmtColor}`}>
              {fmtLabel}
            </span>
          )}
        </p>
      </div>
    </button>
  )
}

export default function SearchBar() {
  const navigate = useNavigate()
  const [inputValue, setInputValue] = useState('')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data, isFetching } = useQuery({
    queryKey: ['search', query],
    queryFn: () => fetchSearch(query, 20),
    enabled: query.length >= 2,
    staleTime: 30_000,
  })

  const handleChange = useCallback((value: string) => {
    setInputValue(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setQuery(value.trim())
      if (value.trim().length >= 2) setOpen(true)
      else setOpen(false)
    }, 300)
  }, [])

  const handleClear = useCallback(() => {
    setInputValue('')
    setQuery('')
    setOpen(false)
    inputRef.current?.focus()
  }, [])

  const handleSelect = useCallback((id: number) => {
    setOpen(false)
    setInputValue('')
    setQuery('')
    inputRef.current?.blur()
    navigate(`/movies/${id}`)
  }, [navigate])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      }
      if (e.key === 'Escape') {
        setOpen(false)
        inputRef.current?.blur()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  const results = data?.data ?? []
  const showDropdown = open && query.length >= 2

  return (
    <div className="relative w-full">
      <div className="relative flex items-center">
        <Search className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground" />
        <input
          ref={inputRef}
          type="search"
          value={inputValue}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => { if (query.length >= 2) setOpen(true) }}
          onBlur={() => setOpen(false)}
          placeholder="Search films…"
          aria-label="Search films"
          className="h-8 w-full rounded-md border border-border bg-background pl-9 pr-8 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
        {inputValue ? (
          <button
            tabIndex={-1}
            onClick={handleClear}
            className="absolute right-2 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : (
          <kbd className="pointer-events-none absolute right-2 hidden rounded border border-border bg-muted px-1 text-[10px] text-muted-foreground sm:block">
            /
          </kbd>
        )}
      </div>

      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-y-auto rounded-md border border-border bg-popover shadow-md">
          {isFetching && results.length === 0 && (
            <p className="px-3 py-4 text-center text-sm text-muted-foreground">Searching…</p>
          )}
          {!isFetching && results.length === 0 && (
            <p className="px-3 py-4 text-center text-sm text-muted-foreground">
              No results for <strong>"{query}"</strong>
            </p>
          )}
          {results.map((item) => (
            <MovieResult key={item.id} item={item} query={query} onSelect={handleSelect} />
          ))}
          {results.length > 0 && (
            <p className="border-t border-border px-3 py-2 text-center text-xs text-muted-foreground">
              {data?.total} result{data?.total !== 1 ? 's' : ''}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
