import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X, Search, AlertTriangle, ChevronLeft, Plus } from 'lucide-react'
import {
  tmdbSearch,
  addToCollection,
  fetchCopies,
  posterUrl,
  ALL_FORMATS,
  CONDITIONS,
  type TMDBSearchResult,
} from '@/lib/api'

interface Props {
  open: boolean
  onClose: () => void
}

type Step = 'search' | 'details'

const EMPTY_FORM = {
  format: '4k_bluray',
  condition: 'very_good',
  edition: '',
  purchase_price: '',
  purchase_date: '',
  purchase_source: '',
  notes: '',
}

export default function AddToCollectionDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient()

  const [step, setStep] = useState<Step>('search')
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [selected, setSelected] = useState<TMDBSearchResult | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const searchInputRef = useRef<HTMLInputElement>(null)

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 350)
    return () => clearTimeout(t)
  }, [query])

  // Focus search input when dialog opens
  useEffect(() => {
    if (open) {
      setTimeout(() => searchInputRef.current?.focus(), 50)
    } else {
      // Reset on close
      setStep('search')
      setQuery('')
      setDebouncedQuery('')
      setSelected(null)
      setForm({ ...EMPTY_FORM })
      setSuccessMsg(null)
    }
  }, [open])

  // TMDB search results
  const { data: searchData, isFetching: searchLoading } = useQuery({
    queryKey: ['tmdb-search', debouncedQuery],
    queryFn: () => tmdbSearch(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60_000,
  })

  // Check if selected movie is already in collection
  const { data: existingCopies } = useQuery({
    queryKey: ['copies', selected?.id],
    queryFn: () => fetchCopies(selected!.id),
    enabled: selected !== null,
    retry: false,
  })

  const duplicateWarning =
    selected !== null && existingCopies !== undefined && existingCopies.length > 0
  const existingFormats = duplicateWarning
    ? [...new Set(existingCopies.map((c) => c.format))]
    : []

  const mutation = useMutation({
    mutationFn: addToCollection,
    onSuccess: (resp) => {
      // Refresh movies list so the new movie appears immediately
      void queryClient.invalidateQueries({ queryKey: ['movies'] })
      void queryClient.invalidateQueries({ queryKey: ['copies', resp.movie_id] })
      setSuccessMsg(
        resp.duplicate_warning
          ? `Added! (${selected?.title} now has ${resp.existing_formats.length + 1} copies)`
          : `${selected?.title} added to your collection.`,
      )
    },
  })

  function handleSelectMovie(movie: TMDBSearchResult) {
    setSelected(movie)
    setStep('details')
  }

  function handleBack() {
    setStep('search')
    setSelected(null)
    mutation.reset()
    setSuccessMsg(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selected) return
    mutation.mutate({
      tmdb_id: selected.id,
      format: form.format,
      condition: form.condition,
      edition: form.edition || undefined,
      purchase_price: form.purchase_price || undefined,
      purchase_date: form.purchase_date || undefined,
      purchase_source: form.purchase_source || undefined,
      notes: form.notes || undefined,
    })
  }

  function handleClose() {
    onClose()
  }

  if (!open) return null

  const releaseYear = (d: string | null) => (d ? d.slice(0, 4) : null)

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Add movie to collection"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="relative w-full max-w-lg bg-background border border-border rounded-xl shadow-2xl flex flex-col max-h-[90vh]">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
            <div className="flex items-center gap-2">
              {step === 'details' && !successMsg && (
                <button
                  type="button"
                  onClick={handleBack}
                  className="text-muted-foreground hover:text-foreground transition-colors mr-1"
                  aria-label="Back to search"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
              )}
              <h2 className="text-base font-semibold text-foreground">
                {step === 'search' ? 'Add Movie to Collection' : 'Add to Collection'}
              </h2>
            </div>
            <button
              type="button"
              onClick={handleClose}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Body */}
          <div className="overflow-y-auto flex-1 px-5 py-4">
            {/* ── Step 1: Search ── */}
            {step === 'search' && (
              <div className="space-y-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search TMDB…"
                    className="w-full pl-9 pr-4 py-2 bg-muted border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  {searchLoading && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  )}
                </div>

                {/* Results */}
                {searchData && searchData.results.length > 0 && (
                  <ul className="space-y-1">
                    {searchData.results.slice(0, 10).map((movie) => (
                      <li key={movie.id}>
                        <button
                          type="button"
                          onClick={() => handleSelectMovie(movie)}
                          className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-muted transition-colors text-left"
                        >
                          <img
                            src={posterUrl(movie.poster_path, 'w92')}
                            alt=""
                            className="h-14 w-10 object-cover rounded shrink-0 bg-muted"
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-foreground truncate">
                              {movie.title}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {releaseYear(movie.release_date) ?? '—'}
                              {movie.vote_average
                                ? ` · ★ ${movie.vote_average.toFixed(1)}`
                                : ''}
                            </p>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {searchData && searchData.results.length === 0 && debouncedQuery.length >= 2 && (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    No results for &ldquo;{debouncedQuery}&rdquo;
                  </p>
                )}

                {debouncedQuery.length < 2 && (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    Type at least 2 characters to search
                  </p>
                )}
              </div>
            )}

            {/* ── Step 2: Details ── */}
            {step === 'details' && selected && (
              <div className="space-y-4">
                {/* Selected movie header */}
                <div className="flex items-center gap-3">
                  <img
                    src={posterUrl(selected.poster_path, 'w92')}
                    alt=""
                    className="h-16 w-11 object-cover rounded shrink-0 bg-muted"
                  />
                  <div>
                    <p className="font-medium text-foreground">{selected.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {releaseYear(selected.release_date) ?? '—'}
                    </p>
                  </div>
                </div>

                {/* Duplicate warning */}
                {duplicateWarning && (
                  <div className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-2">
                    <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                    <div className="text-sm text-amber-600 dark:text-amber-400">
                      <span className="font-medium">Already in your collection</span>
                      {existingFormats.length > 0 && (
                        <span className="text-muted-foreground">
                          {' '}as {existingFormats.join(', ')}
                        </span>
                      )}
                      . You can still add another copy.
                    </div>
                  </div>
                )}

                {/* Success message */}
                {successMsg && (
                  <div className="rounded-lg bg-green-500/10 border border-green-500/30 px-3 py-2 text-sm text-green-600 dark:text-green-400">
                    {successMsg}
                  </div>
                )}

                {/* Form */}
                {!successMsg && (
                  <form onSubmit={handleSubmit} className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <label className="space-y-1">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Format *
                        </span>
                        <select
                          value={form.format}
                          onChange={(e) => setForm((f) => ({ ...f, format: e.target.value }))}
                          className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                          required
                        >
                          {ALL_FORMATS.map((f) => (
                            <option key={f.value} value={f.value}>
                              {f.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="space-y-1">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Condition *
                        </span>
                        <select
                          value={form.condition}
                          onChange={(e) => setForm((f) => ({ ...f, condition: e.target.value }))}
                          className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                          required
                        >
                          {CONDITIONS.map((c) => (
                            <option key={c.value} value={c.value}>
                              {c.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <label className="block space-y-1">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Edition
                      </span>
                      <input
                        type="text"
                        value={form.edition}
                        onChange={(e) => setForm((f) => ({ ...f, edition: e.target.value }))}
                        placeholder="e.g. Collector's Edition, Criterion"
                        className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </label>

                    <div className="grid grid-cols-2 gap-3">
                      <label className="space-y-1">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Purchase Price
                        </span>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          value={form.purchase_price}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, purchase_price: e.target.value }))
                          }
                          placeholder="0.00"
                          className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                      </label>

                      <label className="space-y-1">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          Purchase Date
                        </span>
                        <input
                          type="date"
                          value={form.purchase_date}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, purchase_date: e.target.value }))
                          }
                          className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                      </label>
                    </div>

                    <label className="block space-y-1">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Purchase Source
                      </span>
                      <input
                        type="text"
                        value={form.purchase_source}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, purchase_source: e.target.value }))
                        }
                        placeholder="e.g. Amazon, eBay, in-store"
                        className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Notes
                      </span>
                      <textarea
                        value={form.notes}
                        onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                        placeholder="Any extra notes…"
                        rows={2}
                        className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                      />
                    </label>

                    {mutation.isError && (
                      <p className="text-sm text-destructive">
                        {mutation.error instanceof Error
                          ? mutation.error.message
                          : 'Something went wrong'}
                      </p>
                    )}

                    <button
                      type="submit"
                      disabled={mutation.isPending}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {mutation.isPending ? (
                        <>
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                          Adding…
                        </>
                      ) : (
                        <>
                          <Plus className="h-4 w-4" />
                          Add to Collection
                        </>
                      )}
                    </button>
                  </form>
                )}

                {successMsg && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleBack}
                      className="flex-1 px-4 py-2 border border-border rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
                    >
                      Add Another
                    </button>
                    <button
                      type="button"
                      onClick={handleClose}
                      className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
                    >
                      Done
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
