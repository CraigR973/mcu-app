import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { Dialog } from '@/components/ui/dialog'
import { fetchSearch, posterUrl } from '@/lib/api'
import { fuzzyScore } from '@/lib/fuzzy'
import { HOME_ITEM, navItems, adminNavItems, type NavItem } from '@/lib/nav-items'
import { useRecentItems, type RecentItem } from '@/hooks/useRecentItems'
import { cn } from '@/lib/utils'

interface MovieResult {
  type: 'movie'
  key: string
  id: string
  title: string
  year: number | null
  posterPath: string | null
}

interface PageResult {
  type: 'page'
  key: string
  label: string
  path: string
  icon: NavItem['icon']
}

type Result = MovieResult | PageResult

function toMovieResult(item: RecentItem): MovieResult {
  return { type: 'movie', key: `movie-${item.id}`, id: item.id, title: item.title, year: item.year, posterPath: item.posterPath }
}

function toPageResult(item: NavItem): PageResult {
  return { type: 'page', key: `page-${item.path}`, label: item.label, path: item.path, icon: item.icon }
}

interface Props {
  open: boolean
  onClose: () => void
  isAdmin: boolean
}

/** Phase 6.3. Indexes films (via Batch 5's search endpoint), every page, the write
 *  action a viewer can't reach, and recently-viewed films — dropped: "recent
 *  conversations with the AI assistant" (§7.5), because Batch 31 hasn't built the
 *  assistant yet. Unmounts on close (`Dialog` returns null), so every reopen starts
 *  from a fresh query and a fresh read of recent items. */
export default function CommandPalette({ open, onClose, isAdmin }: Props) {
  const navigate = useNavigate()
  const { recentItems } = useRecentItems()
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const trimmed = query.trim()

  const { data: searchData, isFetching } = useQuery({
    queryKey: ['command-palette-search', trimmed],
    queryFn: () => fetchSearch(trimmed, 8),
    enabled: open && trimmed.length >= 2,
    staleTime: 30_000,
  })

  const pages = useMemo<NavItem[]>(
    () => [HOME_ITEM, ...navItems, ...(isAdmin ? adminNavItems : [])],
    [isAdmin],
  )

  const recentResults: Result[] = trimmed.length === 0 ? recentItems.map(toMovieResult) : []
  const movieResults: Result[] = trimmed.length >= 2 ? (searchData?.items ?? []).map(toMovieResult) : []
  const pageResults: Result[] =
    trimmed.length === 0
      ? pages.map(toPageResult)
      : pages
          .map((page) => ({ page, score: fuzzyScore(trimmed, page.label) }))
          .filter((entry): entry is { page: NavItem; score: number } => entry.score !== null)
          .sort((a, b) => b.score - a.score)
          .map((entry) => toPageResult(entry.page))

  const results: Result[] = [...recentResults, ...movieResults, ...pageResults]

  useEffect(() => {
    setActiveIndex(0)
  }, [trimmed, recentResults.length, movieResults.length, pageResults.length])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setActiveIndex(0)
    // The input isn't mounted yet on the render that flips `open` to true.
    const id = requestAnimationFrame(() => inputRef.current?.focus())
    return () => cancelAnimationFrame(id)
  }, [open])

  function select(result: Result) {
    onClose()
    navigate(result.type === 'movie' ? `/movies/${result.id}` : result.path)
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const active = results[activeIndex]
      if (active) select(active)
    }
  }

  const showEmpty = trimmed.length > 0 && !isFetching && results.length === 0
  let rowIndex = -1

  function row(result: Result) {
    rowIndex += 1
    const index = rowIndex
    return (
      <li key={result.key}>
        <button
          type="button"
          role="option"
          aria-selected={index === activeIndex}
          onMouseEnter={() => setActiveIndex(index)}
          onClick={() => select(result)}
          className={cn(
            'flex w-full items-center gap-3 px-3 py-2 text-left text-sm',
            index === activeIndex ? 'bg-accent text-accent-foreground' : 'text-foreground',
          )}
        >
          {result.type === 'movie' ? (
            <>
              <img
                src={posterUrl(result.posterPath, 'w92')}
                alt=""
                className="h-8 w-6 shrink-0 rounded object-cover"
                loading="lazy"
              />
              <span className="truncate">
                {result.title}
                {result.year ? ` (${result.year})` : ''}
              </span>
            </>
          ) : (
            <>
              <result.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate">{result.label}</span>
            </>
          )}
        </button>
      </li>
    )
  }

  return (
    <Dialog open={open} onClose={onClose} label="Command palette" className="max-w-xl">
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Search films, pages, actions…"
          aria-label="Command palette"
          className="h-12 w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
        />
      </div>
      <ul role="listbox" aria-label="Results" className="max-h-96 overflow-y-auto py-1">
        {recentResults.length > 0 && (
          <li className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Recent
          </li>
        )}
        {recentResults.map(row)}
        {movieResults.length > 0 && (
          <li className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Films
          </li>
        )}
        {movieResults.map(row)}
        {pageResults.length > 0 && (
          <li className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Pages
          </li>
        )}
        {pageResults.map(row)}
        {showEmpty && (
          <li className="px-3 py-4 text-center text-sm text-muted-foreground">
            No results for &quot;{trimmed}&quot;
          </li>
        )}
      </ul>
    </Dialog>
  )
}
