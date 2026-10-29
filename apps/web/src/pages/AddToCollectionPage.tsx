import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Check, Loader2, Plus, Search, Type } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import BarcodeLookupPanel from '@/components/collection/BarcodeLookupPanel'
import CopyForm, { EMPTY_COPY } from '@/components/collection/CopyForm'
import DuplicatePrompt from '@/components/collection/DuplicatePrompt'
import MaybeOwnedNotice from '@/components/collection/MaybeOwnedNotice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { Poster } from '@/components/movies/Poster'
import {
  checkDuplicate,
  confirmBarcode,
  DuplicateItemError,
  searchTmdb,
  type FilmReference,
  type BarcodeCandidate,
  type CollectionItemFields,
  type DuplicateCheck,
  type DuplicateReason,
  type TmdbSearchResult,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { addOrQueue } from '@/lib/sync'

/** The film this disc is a copy of, however it was found. */
interface ChosenFilm {
  title: string
  year: number | null
  posterPath: string | null
  /** Set when the catalogue already has the film; otherwise the TMDB id creates it. */
  movieId: string | null
  tmdbId: number | null
  /** Batch Y5: a TMDB series the catalogue does not have yet, by its own id. */
  tmdbTvId: number | null
  /** Batch Y5: a disc TMDB does not have, added by its title and filed as not a film. */
  byTitle: boolean
  /** Which result was picked, to mark it: a film's and a series' ids can be the same number. */
  pick: string
}

function resultKey(result: TmdbSearchResult): string {
  return `${result.mediaType ?? 'film'}-${String(result.tmdbId)}`
}

function chosenFrom(result: TmdbSearchResult): ChosenFilm {
  const series = result.mediaType === 'tv'
  return {
    title: result.title,
    year: result.year,
    posterPath: result.posterPath,
    // Attaching to the existing row rather than the TMDB id when we already have the
    // film: `movies.tmdb_id` is unique, and two rows would split one film's discs.
    movieId: result.movieId,
    tmdbId: result.movieId || series ? null : result.tmdbId,
    tmdbTvId: result.movieId || !series ? null : result.tmdbId,
    byTitle: false,
    pick: resultKey(result),
  }
}

function chosenFromBarcode(candidate: BarcodeCandidate): ChosenFilm {
  return {
    title: candidate.title,
    year: candidate.year,
    posterPath: candidate.posterPath,
    movieId: candidate.movieId,
    tmdbId: candidate.movieId ? null : candidate.tmdbId,
    tmdbTvId: null,
    byTitle: false,
    pick: `barcode-${candidate.movieId ?? String(candidate.tmdbId)}`,
  }
}

function chosenByTitle(title: string): ChosenFilm {
  return { title, year: null, posterPath: null, movieId: null, tmdbId: null, tmdbTvId: null, byTitle: true, pick: 'title' }
}

export default function AddToCollectionPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [method, setMethod] = useState<'barcode' | 'title'>('barcode')
  const [scannedBarcode, setScannedBarcode] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [film, setFilm] = useState<ChosenFilm | null>(null)
  const [fields, setFields] = useState<CollectionItemFields>(EMPTY_COPY)
  const [duplicate, setDuplicate] = useState<DuplicateCheck | null>(null)
  // Batch X10: an unidentified owned film this may be. A warning, never a reason to refuse.
  const [maybeOwned, setMaybeOwned] = useState<DuplicateCheck['maybeOwned']>(null)

  const searchQuery = useQuery({
    queryKey: ['tmdb-search', submitted],
    queryFn: () => searchTmdb(submitted),
    enabled: submitted.length >= 2,
  })

  function filmRef(chosen: ChosenFilm): FilmReference {
    if (chosen.movieId) return { movieId: chosen.movieId }
    if (chosen.tmdbTvId !== null) return { tmdbTvId: chosen.tmdbTvId }
    if (chosen.byTitle) return { title: chosen.title }
    return { tmdbId: chosen.tmdbId ?? 0 }
  }

  async function chooseFilm(chosen: ChosenFilm, barcode: string | null = scannedBarcode) {
    setFilm(chosen)
    setDuplicate(null)
    setMaybeOwned(null)
    // §3.1 wants the warning *before* saving, so ask as soon as the film is known
    // rather than letting the save be rejected. The POST enforces it independently.
    // Batch X10 (#280): the barcode and the title go too, so a box already on a shelf and an
    // unidentified twin are named, neither of which the film's id can see.
    try {
      const check = await checkDuplicate(filmRef(chosen), fields.formats, {
        barcode,
        title: chosen.title,
        year: chosen.year,
      })
      if (check.isDuplicate) setDuplicate(check)
      setMaybeOwned(check.maybeOwned)
    } catch {
      // A failed preflight must not block the add — the server-side 409 still holds.
    }
  }

  async function chooseBarcode(candidate: BarcodeCandidate, barcode: string) {
    setScannedBarcode(barcode)
    // The state above is not read until the next render, so the barcode is passed.
    await chooseFilm(chosenFromBarcode(candidate), barcode)
  }

  const manualChoice = useMutation({
    mutationFn: async ({ result, barcode }: { result: TmdbSearchResult; barcode: string }) => {
      const chosen = chosenFrom(result)
      await confirmBarcode({
        barcode,
        title: chosen.title,
        source: 'manual',
        movieId: chosen.movieId,
        tmdbId: chosen.tmdbId,
      })
      return chosen
    },
    onSuccess: (chosen, { barcode }) => void chooseFilm(chosen, barcode),
  })

  function chooseTitle(result: TmdbSearchResult) {
    // Batch Y5: the barcode cache knows films only, so a series skips the confirmation; the
    // barcode still goes on the copy, where the next scan finds it as an owned disc.
    if (scannedBarcode && result.mediaType !== 'tv') {
      manualChoice.mutate({ result, barcode: scannedBarcode })
      return
    }
    void chooseFilm(chosenFrom(result))
  }

  // The film's local id at the moment the mutation is defined, so `onSuccess` does not
  // have to narrow a nullable piece of state it cannot prove is still set.
  const chosenMovieId = film?.movieId ?? null

  // Which reason the save was confirmed with, read in `onSuccess`. §4.2's upgrade path
  // does not end at "disc saved" — the old disc still has to be listed — so the film's
  // page needs to know it was arrived at by upgrading.
  const [confirmedAs, setConfirmedAs] = useState<DuplicateReason | null>(null)

  const addAttempt = useRef<{ body: string; id: string } | null>(null)

  const add = useMutation({
    mutationFn: (confirmDuplicate?: DuplicateReason) => {
      if (!film) throw new Error('Choose a film first')
      const input = {
        ...fields,
        ...filmRef(film),
        ...(scannedBarcode ? { barcode: scannedBarcode } : {}),
        confirmDuplicate,
      }
      const body = JSON.stringify(input)
      if (addAttempt.current?.body !== body) addAttempt.current = { body, id: crypto.randomUUID() }
      return addOrQueue({ ...input, clientRequestId: addAttempt.current.id })
    },
    onSuccess: ({ item, queued }) => {
      void queryClient.invalidateQueries({ queryKey: ['movies'] })
      void queryClient.invalidateQueries({ queryKey: ['search'] })
      void queryClient.invalidateQueries({ queryKey: ['facets'] })
      if (item !== null) {
        void queryClient.invalidateQueries({ queryKey: ['movie-copies', item.movieId] })
        navigate(`/movies/${item.movieId}${confirmedAs === 'upgrade' ? '?upgraded=1' : ''}`)
        return
      }
      // Queued. A film added by TMDB id has no local row yet, so there is nothing to
      // navigate to — the banner is where this disc lives until it syncs. `film` is
      // captured here rather than read from state, which the mutation may outlive.
      const known = chosenMovieId
      if (queued && known !== null) {
        void queryClient.invalidateQueries({ queryKey: ['movie-copies', known] })
        navigate(`/movies/${known}`)
        return
      }
      navigate('/movies')
    },
    onError: (error) => {
      // The 409 is not a failure to report — it is §3.5's prompt arriving the other way
      // round, for a save that skipped or outran the preflight check.
      if (error instanceof DuplicateItemError) {
        addAttempt.current = null
        setDuplicate(error.duplicate)
      }
    },
  })

  const results = searchQuery.data?.results ?? []
  const series = searchQuery.data?.series ?? []
  const searchState = listState(searchQuery, results.length === 0 && series.length === 0)
  const searchedFor = searchQuery.data?.query ?? submitted
  const seriesHeading = useRef<HTMLParagraphElement>(null)
  const canSave = film !== null && fields.formats.length > 0

  return (
    <div className="page-shell-narrow space-y-7">
      <PageHeader backTo="/movies" backLabel="Back to the archive" eyebrow="Catalogue entry" title="Add a disc" description="Find the film first, then record the exact edition, format and shelf location." />

      <section className="archive-panel space-y-4 p-4 sm:p-6" aria-labelledby="choose-film-heading">
        <div><p className="page-kicker">Step 1</p><h2 id="choose-film-heading" className="section-heading">Which film?</h2></div>
        <div className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1" role="tablist" aria-label="How to find the film">
          <button
            type="button"
            role="tab"
            id="barcode-tab"
            aria-controls="barcode-panel"
            aria-selected={method === 'barcode'}
            onClick={() => {
              setMethod('barcode')
              setScannedBarcode(null)
              setFilm(null)
              setDuplicate(null)
              manualChoice.reset()
            }}
            className={`touch-target inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium transition-colors ${
              method === 'barcode' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'
            }`}
          >
            <Camera className="h-4 w-4" />
            Scan barcode
          </button>
          <button
            type="button"
            role="tab"
            id="title-tab"
            aria-controls="title-panel"
            aria-selected={method === 'title'}
            onClick={() => {
              // An explicit tab switch is a fresh title-only add. The scanner's
              // "search by title" callback below is the one path that deliberately
              // retains a code for manual resolution.
              setMethod('title')
              setScannedBarcode(null)
              setFilm(null)
              setDuplicate(null)
              manualChoice.reset()
            }}
            className={`touch-target inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium transition-colors ${
              method === 'title' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'
            }`}
          >
            <Search className="h-4 w-4" />
            Search title
          </button>
        </div>

        {method === 'barcode' ? (
          <div id="barcode-panel" role="tabpanel" aria-labelledby="barcode-tab">
            <BarcodeLookupPanel
              onBarcodeChange={(barcode) => {
                // A newly read physical product invalidates any earlier candidate.
                // Keeping the old film selected here would let its save button attach
                // the new barcode to the wrong movie while lookup was still pending.
                setScannedBarcode(barcode)
                setFilm(null)
                setDuplicate(null)
              }}
              onConfirmed={chooseBarcode}
              onManualSearch={(barcode) => {
                setScannedBarcode(barcode)
                setFilm(null)
                setDuplicate(null)
                setMethod('title')
              }}
            />
          </div>
        ) : (
          <div id="title-panel" role="tabpanel" aria-labelledby="title-tab" className="space-y-4">
            {scannedBarcode && (
              <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                <p className="font-medium text-foreground">Finding barcode {scannedBarcode} manually</p>
                <p className="mt-1 text-muted-foreground">
                  Choose the correct film below. It will still be confirmed against this barcode before the disc is added.
                </p>
              </div>
            )}
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
                placeholder="Title, and its year if you know it"
                aria-label="Search for a film"
              />
              <Button type="submit" disabled={query.trim().length < 2}>
                {searchQuery.isFetching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                Search
              </Button>
            </form>

            {submitted.length >= 2 && searchState === 'error' && (
              <p role="alert" className="text-sm text-destructive">
                {queryErrorMessage(searchQuery.error, 'Could not reach TMDB.')}
              </p>
            )}

            {submitted.length >= 2 && searchState === 'offline' && (
              <p className="text-sm text-muted-foreground">
                Waiting for the network — TMDB has not answered yet.
              </p>
            )}

            {/* Only once results genuinely arrived: a paused query has no results either,
                and "no films matched" would be a confident lie about a search that never ran. */}
            {submitted.length >= 2 && searchState === 'empty' && (
              <p className="text-sm text-muted-foreground">No films or series matched “{submitted}”.</p>
            )}

            {results.length > 0 && series.length > 0 && (
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="page-kicker">Films</p>
                {/* The series follow up to twenty films; on a phone that is a long way down. */}
                <button
                  type="button"
                  className="text-xs font-semibold text-primary underline-offset-2 hover:underline"
                  onClick={() => seriesHeading.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                >
                  {series.length === 1 ? '1 TV series' : `${String(series.length)} TV series`}, below ↓
                </button>
              </div>
            )}
            <ul className="space-y-2" aria-label="Films found">
              {results.map((result) => (
                <li key={resultKey(result)}>
                  <ResultButton
                    result={result}
                    active={film?.pick === resultKey(result)}
                    disabled={manualChoice.isPending}
                    pending={manualChoice.isPending && manualChoice.variables?.result === result}
                    onChoose={() => chooseTitle(result)}
                  />
                </li>
              ))}
            </ul>

            {/* Batch Y5 (#277): TMDB's series for the same words, apart from the films. */}
            {series.length > 0 && (
              <>
                <p ref={seriesHeading} className="page-kicker scroll-mt-20">TV series</p>
                <ul className="space-y-2" aria-label="TV series found">
                  {series.map((result) => (
                    <li key={resultKey(result)}>
                      <ResultButton
                        result={result}
                        active={film?.pick === resultKey(result)}
                        disabled={manualChoice.isPending}
                        pending={false}
                        onChoose={() => chooseTitle(result)}
                      />
                    </li>
                  ))}
                </ul>
              </>
            )}

            {/* Batch Y5: a disc TMDB does not have (John Krish's "A Day in the Life", 16 Oct). */}
            {submitted.length >= 2 && (searchState === 'ready' || searchState === 'empty') && (
              <div className="rounded-lg border border-dashed border-border p-3 text-sm">
                <p className="text-muted-foreground">
                  Not on TMDB? Add it by its title. It is filed as not a film, so it stays off “Still to identify”.
                </p>
                <Button
                  type="button"
                  variant={film?.pick === 'title' ? 'default' : 'secondary'}
                  size="sm"
                  className="mt-2 max-w-full"
                  aria-pressed={film?.pick === 'title'}
                  onClick={() => void chooseFilm(chosenByTitle(searchedFor))}
                >
                  <Type className="h-4 w-4" />
                  <span className="truncate">Add “{searchedFor}” by its title</span>
                </Button>
              </div>
            )}

            {manualChoice.isError && (
              <p role="alert" className="text-sm text-destructive">
                {queryErrorMessage(manualChoice.error, 'That barcode match could not be confirmed.')}
              </p>
            )}
          </div>
        )}
      </section>

      {film && (
        <>
          {maybeOwned && <MaybeOwnedNotice film={maybeOwned} />}

          {duplicate && (
            <DuplicatePrompt
              duplicate={duplicate}
              pending={add.isPending}
              onConfirm={(reason) => {
                setConfirmedAs(reason)
                add.mutate(reason)
              }}
              onCancel={() => {
                setDuplicate(null)
                setFilm(null)
              }}
            />
          )}

          <section className="archive-panel space-y-4 p-4 sm:p-6" aria-labelledby="describe-disc-heading">
            <div><p className="page-kicker">Step 2</p><h2 id="describe-disc-heading" className="section-heading">Which edition, and where does it live?</h2></div>
            <CopyForm value={fields} onChange={setFields} disabled={add.isPending} />
          </section>

          {add.isError && !(add.error instanceof DuplicateItemError) && (
            <p role="alert" className="text-sm text-destructive">
              {queryErrorMessage(add.error, 'Could not save that disc.')}
            </p>
          )}

          <div className="sticky bottom-0 -mx-4 flex flex-col gap-2 border-t border-border bg-background/95 px-4 py-4 backdrop-blur sm:static sm:mx-0 sm:flex-row sm:items-center sm:border-0 sm:bg-transparent sm:p-0">
            <Button
              type="button"
              className="w-full min-w-0 sm:w-auto"
              disabled={!canSave || add.isPending}
              onClick={() => add.mutate(duplicate ? 'another_copy' : undefined)}
            >
              {add.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              <span className="truncate">Add “{film.title}”</span>
            </Button>
            <Button type="button" className="w-full sm:w-auto" variant="ghost" onClick={() => setFilm(null)}>
              Choose a different film
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function ResultButton({
  result,
  active,
  disabled,
  pending,
  onChoose,
}: {
  result: TmdbSearchResult
  active: boolean
  disabled: boolean
  pending: boolean
  onChoose: () => void
}) {
  return (
    <button
      type="button"
      onClick={onChoose}
      aria-pressed={active}
      disabled={disabled}
      className={`flex min-h-20 w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors disabled:opacity-50 ${
        active ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/50'
      }`}
    >
      <Poster path={result.posterPath} title={result.title} size="w92" decorative className="h-16 w-11 shrink-0 rounded-sm" />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-foreground">{result.title}</span>
          {result.year && <span className="text-xs text-muted-foreground">{result.year}</span>}
          {result.mediaType === 'tv' && <Badge>TV series</Badge>}
          {result.inCollection && <Badge tone="success">Already catalogued</Badge>}
        </span>
        {/* Batch Y5: no `block` here, which overrode the clamp and printed a whole overview. */}
        <span className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{result.overview}</span>
      </span>
      {pending ? (
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
      ) : active ? (
        <Check className="h-4 w-4 shrink-0 text-primary" />
      ) : null}
    </button>
  )
}
