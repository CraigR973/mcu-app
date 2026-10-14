import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, MoveRight, Plus, Undo2, X } from 'lucide-react'

import { FilmFinder, type FoundFilm } from '@/components/collection/FilmFinder'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { trayDiscFrom, useMoveTray, type TrayDisc } from '@/hooks/useMoveTray'
import {
  fetchCopies,
  fetchFacets,
  formatLabel,
  moveCollectionItems,
  shelfLabel,
  type CollectionCopy,
  type CollectionMoveEntry,
  type CollectionMoveResponse,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

interface Place {
  location: string | null
  section: string | null
  shelf: string | null
}

/** Where a disc is, as the film page's copy card says it. */
function placeLabel(place: Place): string {
  if (place.location) return place.location
  if (place.section) return `${place.section}${place.shelf ? ` · ${place.shelf} shelf` : ''}`
  return 'No place recorded'
}

function discLabel(disc: { formats: string[]; edition: string | null }): string {
  const formats = disc.formats.map((format) => formatLabel(format) ?? format).join(' + ') || 'Format not recorded'
  return disc.edition ? `${formats} · ${disc.edition}` : formats
}

/** The last move, kept so it can be reported and put back. */
interface LastMove {
  destination: string
  undo: boolean
  response: CollectionMoveResponse
  /** Each moved disc's place before the move, by id: what "Move them back" restores. */
  before: Record<string, Place>
  titles: Record<string, string>
}

/** A film with more than one disc on the shelf: the person says which are moving. */
function ChooseDiscs({
  film,
  copies,
  onDone,
}: {
  film: FoundFilm
  copies: CollectionCopy[]
  onDone: () => void
}) {
  const tray = useMoveTray()
  return (
    <div className="space-y-3">
      <h3 className="font-display text-lg font-semibold text-foreground">Which discs of {film.title}?</h3>
      <ul className="space-y-2">
        {copies.map((copy) => {
          const held = tray.has(copy.id)
          return (
            <li key={copy.id}>
              <button
                type="button"
                aria-pressed={held}
                onClick={() => (held ? tray.remove(copy.id) : tray.add(trayDiscFrom(copy, film.movieId, film.title)))}
                className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2 text-left"
              >
                <span>
                  <span className="block font-semibold text-foreground">{discLabel(copy)}</span>
                  <span className="block text-xs text-muted-foreground">{placeLabel(copy)}</span>
                </span>
                {held ? (
                  <span className="inline-flex items-center gap-1 text-sm font-semibold text-primary">
                    <Check className="h-4 w-4" aria-hidden /> In the tray
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                    <Plus className="h-4 w-4" aria-hidden /> Add
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
      <Button type="button" variant="outline" onClick={onDone}>
        Find another disc
      </Button>
    </div>
  )
}

/**
 * Move discs — Batch Y2 (`DECISIONS.md` #265).
 *
 * Find each disc by search or scan, wherever it lives; it goes into a tray kept on this
 * phone, which survives searching again and leaving the page. Then one place for all of
 * them, one request, and a report: what moved, what was already there, what changed on the
 * other phone meanwhile (left alone, and kept in the tray at its new version), and what is
 * no longer in the collection. "Move them back" sends each disc's own previous place
 * through the same endpoint.
 *
 * **Online only.** A move queued offline would need #42's stale check across a queue of
 * many rows; the button says why it is off instead.
 */
export default function MoveDiscsPage() {
  const queryClient = useQueryClient()
  const online = useOnlineStatus()
  const tray = useMoveTray()
  const [choosing, setChoosing] = useState<{ film: FoundFilm; copies: CollectionCopy[] } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [section, setSection] = useState('')
  const [shelf, setShelf] = useState('')
  const [lastMove, setLastMove] = useState<LastMove | null>(null)

  const facetsQuery = useQuery({ queryKey: ['facets'], queryFn: fetchFacets })
  const populated = facetsQuery.data?.sections ?? []
  const allSections = facetsQuery.data?.allSections ?? []
  const sectionNames = allSections.length > 0 ? allSections : populated.map((entry) => entry.section)
  const chosen = populated.find((entry) => entry.section === section)
  const shelves = chosen?.shelves ?? []
  const noun = chosen?.shelfNoun ?? 'shelf'

  const find = useMutation({
    mutationFn: (film: FoundFilm) => fetchCopies(film.movieId),
    onSuccess: (copies, film) => {
      if (copies.length === 0) {
        setNotice(`No disc of ${film.title} is on the shelf.`)
      } else if (copies.length === 1) {
        // One disc: nothing to choose, so it goes straight in and the finder is ready for
        // the next one in the pile.
        tray.add(trayDiscFrom(copies[0]!, film.movieId, film.title))
        setNotice(`Added ${film.title} (${discLabel(copies[0]!)}) to the tray.`)
      } else {
        setChoosing({ film, copies })
      }
    },
  })

  function refresh() {
    for (const key of ['movies', 'search', 'facets', 'movie-copies', 'movie', 'item-history']) {
      void queryClient.invalidateQueries({ queryKey: [key] })
    }
  }

  const move = useMutation({
    mutationFn: async ({ entries }: { entries: CollectionMoveEntry[]; last: Omit<LastMove, 'response'> }) =>
      moveCollectionItems(entries),
    onSuccess: (response, { last }) => {
      refresh()
      setLastMove({ ...last, response })
      if (last.undo) return
      // Moved, already there, or gone: done with. Changed elsewhere: kept, at the version
      // the server just reported, so moving it again is a deliberate second act.
      const stale = new Map(
        response.results
          .filter((result) => result.status === 'stale' && result.item)
          .map((result) => [result.itemId, result.item!]),
      )
      tray.replace(
        tray.discs
          .filter((disc) => stale.has(disc.itemId))
          .map((disc) => {
            const now = stale.get(disc.itemId)!
            return { ...disc, location: now.location, section: now.section, shelf: now.shelf, updatedAt: now.updatedAt }
          }),
      )
    },
  })

  /** "Lounge · Left hand side", named as the picker named it. */
  function destinationLabel(): string {
    const picked = shelves.find((entry) => entry.shelf === shelf)
    return picked ? `${section} · ${shelfLabel(picked)}` : section
  }

  function moveTray() {
    const target = { section, shelf: shelf || null }
    const before: Record<string, Place> = {}
    const titles: Record<string, string> = {}
    for (const disc of tray.discs) {
      before[disc.itemId] = { location: disc.location, section: disc.section, shelf: disc.shelf }
      // Named with the disc, so a film with two discs says which one: "Alien (DVD)".
      titles[disc.itemId] = `${disc.title} (${discLabel(disc)})`
    }
    setNotice(null)
    move.mutate({
      entries: tray.discs.map((disc) => ({ itemId: disc.itemId, baseUpdatedAt: disc.updatedAt, ...target })),
      last: { destination: destinationLabel(), undo: false, before, titles },
    })
  }

  function moveBack(last: LastMove) {
    const entries = last.response.results
      .filter((result) => result.status === 'moved' && result.item)
      .map((result) => ({
        itemId: result.itemId,
        baseUpdatedAt: result.item!.updatedAt,
        ...last.before[result.itemId]!,
      }))
    move.mutate({ entries, last: { ...last, destination: 'where they were', undo: true } })
  }

  const count = tray.discs.length
  const canMove = online && count > 0 && section !== '' && !move.isPending

  return (
    <div className="page-shell-narrow space-y-7">
      <PageHeader
        eyebrow="The archive"
        title="Move discs"
        description="Pick discs from anywhere, by search or by scanning, then move them all to one place."
      />

      <section aria-labelledby="find-heading" className="archive-panel space-y-4 p-4 sm:p-5">
        <h2 id="find-heading" className="section-heading text-lg">Find a disc</h2>
        {choosing ? (
          <ChooseDiscs film={choosing.film} copies={choosing.copies} onDone={() => setChoosing(null)} />
        ) : (
          <FilmFinder onFound={(film) => { setNotice(null); find.mutate(film) }} />
        )}
        {find.isPending ? (
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Finding its discs…
          </p>
        ) : null}
        {find.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {queryErrorMessage(find.error, 'Its discs could not be read.')}
          </p>
        ) : null}
        {notice ? <p role="status" className="text-sm text-foreground">{notice}</p> : null}
      </section>

      <section aria-labelledby="tray-heading" className="archive-panel space-y-4 p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 id="tray-heading" className="section-heading text-lg">
            In the tray{count > 0 ? ` (${String(count)})` : ''}
          </h2>
          {count > 0 ? (
            <Button type="button" size="sm" variant="ghost" onClick={tray.clear}>Clear</Button>
          ) : null}
        </div>

        {count === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing yet. Find a disc above to add it.</p>
        ) : (
          <ul className="space-y-2">
            {tray.discs.map((disc: TrayDisc) => (
              <li key={disc.itemId} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2">
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-foreground">{disc.title}</span>
                  <span className="block text-xs text-muted-foreground">
                    {discLabel(disc)} · now {placeLabel(disc)}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => tray.remove(disc.itemId)}
                  aria-label={`Take ${disc.title} out of the tray`}
                  className="touch-target -mr-2 flex shrink-0 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="grid gap-3 border-t border-border pt-4 sm:grid-cols-2">
          <label className="space-y-1.5 text-sm">
            <span className="metadata-label">Move to section</span>
            <select
              className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={section}
              onChange={(event) => { setSection(event.target.value); setShelf('') }}
            >
              <option value="">Choose a section</option>
              {sectionNames.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
          {shelves.length > 0 ? (
            <label className="space-y-1.5 text-sm">
              <span className="metadata-label">{noun === 'side' ? 'Side' : 'Shelf'}</span>
              <select
                className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={shelf}
                onChange={(event) => setShelf(event.target.value)}
              >
                <option value="">No particular {noun}</option>
                {shelves.map((entry) => <option key={entry.shelf} value={entry.shelf}>{shelfLabel(entry)}</option>)}
              </select>
            </label>
          ) : null}
        </div>

        <Button type="button" className="w-full" disabled={!canMove} onClick={moveTray}>
          {move.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <MoveRight className="h-4 w-4" aria-hidden />}
          {count === 0 ? 'Move discs' : count === 1 ? 'Move 1 disc' : `Move ${String(count)} discs`}
        </Button>
        {!online ? (
          <p role="status" className="text-sm text-muted-foreground">
            Moving needs a connection. The tray stays on this phone until you are back online.
          </p>
        ) : null}
        {move.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {queryErrorMessage(move.error, 'Those discs could not be moved.')}
          </p>
        ) : null}
      </section>

      {lastMove ? <MoveReport last={lastMove} pending={move.isPending} online={online} onUndo={moveBack} /> : null}
    </div>
  )
}

function MoveReport({
  last,
  pending,
  online,
  onUndo,
}: {
  last: LastMove
  pending: boolean
  online: boolean
  onUndo: (last: LastMove) => void
}) {
  const { results, moved } = last.response
  const named = (status: string) => results.filter((result) => result.status === status)
  const unchanged = named('unchanged')
  const stale = named('stale')
  const missing = named('not_found')
  const verb = last.undo ? 'put back' : 'moved'

  return (
    <section aria-labelledby="report-heading" role="status" className="archive-panel space-y-3 p-4 sm:p-5">
      <h2 id="report-heading" className="section-heading text-lg">
        {moved === 1 ? '1 disc' : `${String(moved)} discs`} {verb}
        {last.undo ? '' : ` to ${last.destination}`}
      </h2>
      {unchanged.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          Already there: {unchanged.map((result) => last.titles[result.itemId]).join(', ')}.
        </p>
      ) : null}
      {stale.length > 0 ? (
        <ul className="space-y-1 text-sm text-foreground">
          {stale.map((result) => (
            <li key={result.itemId}>
              {last.titles[result.itemId]} changed on the other phone and was left where it is
              {result.item ? `, ${placeLabel(result.item)}` : ''}.{last.undo ? '' : ' It is still in the tray.'}
            </li>
          ))}
        </ul>
      ) : null}
      {missing.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          No longer in the collection: {missing.map((result) => last.titles[result.itemId]).join(', ')}.
        </p>
      ) : null}
      {!last.undo && moved > 0 ? (
        <Button type="button" variant="outline" disabled={pending || !online} onClick={() => onUndo(last)}>
          <Undo2 className="h-4 w-4" aria-hidden /> Move them back
        </Button>
      ) : null}
    </section>
  )
}
