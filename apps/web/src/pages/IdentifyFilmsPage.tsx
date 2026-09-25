import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, GitMerge, Search, SkipForward, Tv, Undo2, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  fetchIdentifyOverview,
  fetchIdentifyQueue,
  fetchRecentIdentifications,
  identifyFilm,
  posterUrl,
  searchIdentify,
  setFilmAside,
  skipFilm,
  undoIdentification,
  type IdentifyCandidate,
  type IdentifyOverview,
  type IdentifyQueueItem,
  type RecentIdentification,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

const COUNT = new Intl.NumberFormat('en-GB')

const HOW: Record<string, string> = {
  auto: 'automatically',
  picked: 'by you',
  searched: 'by you, after a search',
  film_page: 'on the film page',
}

function Overview({ overview }: { overview: IdentifyOverview }) {
  const rows: Array<[string, number]> = [
    ['Set aside as TV', overview.setAsideTv],
    ['Not a film', overview.setAsideNotFilm],
    ['Skipped', overview.skipped],
    ['Identified', overview.identified],
  ]
  return (
    <section className="archive-panel space-y-3 p-4 sm:p-5" aria-labelledby="identify-overview-heading">
      <h2 id="identify-overview-heading" className="metadata-label">Where they stand</h2>
      <p className="font-display text-2xl font-semibold text-foreground">
        {COUNT.format(overview.waiting)} of {COUNT.format(overview.unidentified)} unmatched films wait for you
      </p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-right font-semibold tabular-nums text-foreground">{COUNT.format(value)}</dd>
          </div>
        ))}
      </dl>
      {overview.run ? (
        <p className="text-xs text-muted-foreground">
          Last run, {formatShortDate(overview.run.startedAt)}: {overview.run.identified} identified,{' '}
          {overview.run.queued} for you, {overview.run.setAside} set aside
          {overview.run.failed ? `, ${String(overview.run.failed)} failed` : ''}.
        </p>
      ) : null}
    </section>
  )
}

function CandidateRow({
  candidate,
  busy,
  onPick,
}: {
  candidate: IdentifyCandidate
  busy: boolean
  onPick: (candidate: IdentifyCandidate) => void
}) {
  const held = candidate.inCollection
  return (
    <li className="flex gap-3 py-3 first:pt-0 last:pb-0">
      <img
        src={posterUrl(candidate.posterPath, 'w92')}
        alt=""
        className="h-20 w-[3.4rem] shrink-0 rounded bg-muted object-cover"
        loading="lazy"
      />
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="text-sm font-semibold leading-5 text-foreground">
          {candidate.title}
          {candidate.year ? <span className="font-normal text-muted-foreground"> ({candidate.year})</span> : null}
        </p>
        {candidate.notes.length > 0 ? (
          <p className="text-xs leading-5 text-muted-foreground">{candidate.notes.join(' · ')}</p>
        ) : null}
        {held ? (
          <p className="rounded-md border border-warning/40 bg-warning/10 p-2 text-xs leading-5 text-foreground">
            You already have this as{' '}
            <Link to={`/movies/${held.movieId}`} className="font-semibold hover:text-primary">
              {held.title}
              {held.year ? ` (${String(held.year)})` : ''}
            </Link>{' '}
            · {held.discs} {held.discs === 1 ? 'disc' : 'discs'} · {held.watches}{' '}
            {held.watches === 1 ? 'watch' : 'watches'}. Choosing it merges the two.
          </p>
        ) : null}
        <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => onPick(candidate)}>
          {held ? <GitMerge aria-hidden /> : <Check aria-hidden />}
          {held ? 'Merge into this film' : 'This is it'}
        </Button>
      </div>
    </li>
  )
}

function QueueCard({ item }: { item: IdentifyQueueItem }) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState(item.title)
  const [searched, setSearched] = useState<string | null>(null)
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['identify-queue'] })
    void queryClient.invalidateQueries({ queryKey: ['identify-overview'] })
    void queryClient.invalidateQueries({ queryKey: ['identify-recent'] })
  }
  const search = useQuery({
    queryKey: ['identify-search', item.movieId, searched],
    queryFn: () => searchIdentify(item.movieId, searched ?? ''),
    enabled: searched !== null,
  })
  const pick = useMutation({
    mutationFn: ({ candidate, fromSearch }: { candidate: IdentifyCandidate; fromSearch: boolean }) =>
      identifyFilm(item.movieId, candidate.tmdbId, { merge: candidate.inCollection !== null, searched: fromSearch }),
    onSuccess: refresh,
  })
  const aside = useMutation({ mutationFn: (kind: 'tv' | 'not_film') => setFilmAside(item.movieId, kind), onSuccess: refresh })
  const skip = useMutation({ mutationFn: () => skipFilm(item.movieId), onSuccess: refresh })
  const busy = pick.isPending || aside.isPending || skip.isPending
  const failure = pick.error ?? aside.error ?? skip.error

  return (
    <article className="archive-panel space-y-3 p-4" aria-labelledby={`identify-${item.movieId}`}>
      <div>
        <h3 id={`identify-${item.movieId}`} className="font-display text-lg font-semibold text-foreground">
          <Link to={`/movies/${item.movieId}`} className="hover:text-primary">{item.title}</Link>
        </h3>
        <p className="text-xs text-muted-foreground">
          {[...item.discs.map((disc) => disc.label), item.watches ? `watched ${String(item.watches)}×` : '']
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>
      {item.note ? <p className="text-sm leading-6 text-muted-foreground">{item.note}</p> : null}

      {item.candidates.length > 0 ? (
        <ul className="divide-y divide-border" aria-label={`Films offered for ${item.title}`}>
          {item.candidates.map((candidate) => (
            <CandidateRow
              key={candidate.tmdbId}
              candidate={candidate}
              busy={busy}
              onPick={(chosen) => pick.mutate({ candidate: chosen, fromSearch: false })}
            />
          ))}
        </ul>
      ) : null}

      <form
        className="space-y-2 border-t border-border pt-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim()) setSearched(query.trim())
        }}
      >
        <div className="flex gap-2">
          <input
            className="form-control min-w-0 flex-1"
            aria-label={`Search TMDB again for ${item.title}`}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Button type="submit" size="sm" variant="secondary" disabled={busy || !query.trim()}>
            <Search aria-hidden /> Search
          </Button>
        </div>
        {search.isLoading ? <p className="text-xs text-muted-foreground">Searching TMDB…</p> : null}
        {search.isError ? (
          <p role="alert" className="text-sm text-destructive-text">
            {queryErrorMessage(search.error, 'TMDB search is unavailable.')}
          </p>
        ) : null}
        {search.data && search.data.candidates.length === 0 ? (
          <p className="text-xs text-muted-foreground">No films found for “{search.data.query}”.</p>
        ) : null}
        {search.data && search.data.candidates.length > 0 ? (
          <ul className="divide-y divide-border" aria-label={`Search results for ${item.title}`}>
            {search.data.candidates.map((candidate) => (
              <CandidateRow
                key={candidate.tmdbId}
                candidate={candidate}
                busy={busy}
                onPick={(chosen) => pick.mutate({ candidate: chosen, fromSearch: true })}
              />
            ))}
          </ul>
        ) : null}
      </form>

      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => aside.mutate('tv')}>
          <Tv aria-hidden /> TV series
        </Button>
        <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => aside.mutate('not_film')}>
          <X aria-hidden /> Not a film
        </Button>
        <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => skip.mutate()}>
          <SkipForward aria-hidden /> Skip
        </Button>
      </div>

      {failure ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(failure, 'That choice could not be saved.')}
        </p>
      ) : null}
    </article>
  )
}

function RecentRow({ entry }: { entry: RecentIdentification }) {
  const queryClient = useQueryClient()
  const undo = useMutation({
    mutationFn: () => undoIdentification(entry.actionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['identify-recent'] })
      void queryClient.invalidateQueries({ queryKey: ['identify-queue'] })
      void queryClient.invalidateQueries({ queryKey: ['identify-overview'] })
    },
  })
  return (
    <li className="space-y-1.5 py-3 first:pt-0 last:pb-0">
      <p className="text-sm leading-5 text-foreground">
        <span className="text-muted-foreground">{entry.replaced}</span> →{' '}
        <Link to={`/movies/${entry.movieId}`} className="font-semibold hover:text-primary">
          {entry.title}
          {entry.year ? ` (${String(entry.year)})` : ''}
        </Link>
      </p>
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
        <span>
          {formatShortDate(entry.at)}, {HOW[entry.how] ?? entry.how}
        </span>
        {entry.merged ? <Badge tone="warning">Merged</Badge> : null}
        {entry.undone ? <Badge tone="neutral">Undone</Badge> : null}
      </div>
      {!entry.undone ? (
        <Button type="button" size="sm" variant="ghost" disabled={undo.isPending} onClick={() => undo.mutate()}>
          <Undo2 aria-hidden /> Undo
        </Button>
      ) : null}
      {undo.isError ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(undo.error, 'That could not be undone.')}
        </p>
      ) : null}
    </li>
  )
}

/**
 * Identify films — Batch T9.
 *
 * **Where Craig settles the films identification would not.** A dry run proposed an outcome
 * for every film TMDB never matched; the ones it could not decide wait here with the films
 * it found and why. Each choice is one tap, a choice that would join two films shows both
 * first, and every identification can be undone from the list below.
 */
export default function IdentifyFilmsPage() {
  const overviewQuery = useQuery({ queryKey: ['identify-overview'], queryFn: fetchIdentifyOverview })
  const queueQuery = useQuery({ queryKey: ['identify-queue'], queryFn: () => fetchIdentifyQueue(20) })
  const recentQuery = useQuery({ queryKey: ['identify-recent'], queryFn: () => fetchRecentIdentifications(20) })

  const items = queueQuery.data?.items ?? []
  const queueState = listState(queueQuery, items.length === 0)
  const recent = recentQuery.data?.items ?? []

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="Craig’s tools"
        title="Identify films"
        description="Films on the shelf that TMDB never matched. Pick the right film, search again, or set it aside."
      />

      {overviewQuery.isError ? (
        <StatePanel
          compact
          tone="error"
          title="The overview is unavailable"
          description={queryErrorMessage(overviewQuery.error, 'Could not load the overview.')}
        />
      ) : null}
      {overviewQuery.data ? <Overview overview={overviewQuery.data} /> : null}

      <section className="space-y-3" aria-labelledby="identify-queue-heading">
        <h2 id="identify-queue-heading" className="section-heading">
          Need you{queueQuery.data ? ` (${COUNT.format(queueQuery.data.total)})` : ''}
        </h2>
        {queueState === 'loading' ? <StatePanel compact tone="loading" title="Loading the films waiting for you" /> : null}
        {queueState === 'error' ? (
          <StatePanel
            compact
            tone="error"
            title="The queue is unavailable"
            description={queryErrorMessage(queueQuery.error, 'Could not load the queue.')}
          />
        ) : null}
        {queueState === 'empty' ? <p className="text-sm text-muted-foreground">Nothing is waiting for you.</p> : null}
        {items.map((item) => <QueueCard key={item.movieId} item={item} />)}
        {queueQuery.data && queueQuery.data.total > items.length ? (
          <p className="text-xs text-muted-foreground">
            Showing {items.length} of {COUNT.format(queueQuery.data.total)}. More appear as you settle these.
          </p>
        ) : null}
      </section>

      <section className="space-y-3" aria-labelledby="identify-recent-heading">
        <h2 id="identify-recent-heading" className="section-heading">Recently identified</h2>
        {recent.length === 0 ? <p className="text-sm text-muted-foreground">Nothing yet.</p> : null}
        {recent.length > 0 ? (
          <ul className="archive-panel divide-y divide-border p-4">
            {recent.map((entry) => <RecentRow key={entry.actionId} entry={entry} />)}
          </ul>
        ) : null}
      </section>
    </div>
  )
}
