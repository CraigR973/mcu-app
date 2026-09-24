import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, ExternalLink, Loader2, Play, SkipForward } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  acceptSpecPage,
  fetchSpecBackfill,
  fetchSpecQueue,
  skipSpecDisc,
  startSpecBatch,
  type SpecBackfill,
  type SpecBatchStart,
  type SpecQueueItem,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

const COUNT = new Intl.NumberFormat('en-GB')
const FORMAT_NAMES: Record<string, string> = { '4k_uhd': '4K', blu_ray: 'Blu-ray' }

const NOT_STARTED: Record<Exclude<SpecBatchStart['outcome'], 'started'>, string> = {
  running: 'A batch is already running.',
  halted: 'The Blu-ray.com integration is halted, so nothing was started.',
  nothing_due: 'Nothing to search for or fetch right now.',
}

const RUN_STATES: Record<string, string> = {
  running: 'Running',
  finished: 'Finished',
  budget_spent: 'Stopped at its budget',
  stopped: 'Stopped early',
  halted: 'Halted',
  abandoned: 'Stopped without finishing',
}

function Coverage({ backfill }: { backfill: SpecBackfill }) {
  const { coverage, run } = backfill
  const rows: Array<[string, number]> = [
    ['Waiting to be fetched', coverage.accepted],
    ['Need you', coverage.needsYou + coverage.noMatch],
    ['Skipped', coverage.skipped],
    ['Not searched yet', coverage.notSearched],
  ]
  return (
    <section className="archive-panel space-y-3 p-4 sm:p-5" aria-labelledby="specs-coverage-heading">
      <h2 id="specs-coverage-heading" className="metadata-label">Coverage</h2>
      <p className="font-display text-2xl font-semibold text-foreground">
        {COUNT.format(coverage.withSpecs)} of {COUNT.format(coverage.discs)} discs have specs
      </p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-right font-semibold tabular-nums text-foreground">{COUNT.format(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-muted-foreground">
        Brave searches this month: {COUNT.format(backfill.searchesThisMonth)} of {COUNT.format(backfill.monthlyCeiling)}.
        Each batch searches up to {backfill.searchesPerRun} discs and fetches up to {backfill.fetchesPerRun} pages.
      </p>
      {run ? (
        <p className="text-xs text-muted-foreground">
          Last batch, {formatShortDate(run.startedAt)}: {RUN_STATES[run.status] ?? run.status}.{' '}
          {run.searched} searched, {run.accepted} accepted, {run.queued + run.noMatch} for you, {run.applied} specs saved
          {run.restored ? `, ${String(run.restored)} restored from 10 Sep` : ''}.
          {run.lastError ? ` ${run.lastError}` : ''}
        </p>
      ) : null}
    </section>
  )
}

function Candidate({
  item,
  url,
  title,
  country,
  edition,
  matches,
  origin,
  busy,
  onUse,
}: SpecQueueItem['candidates'][number] & { item: SpecQueueItem; busy: boolean; onUse: (url: string) => void }) {
  return (
    <li className="space-y-2 py-2.5 first:pt-0 last:pb-0">
      <p className="text-sm leading-5 text-foreground">{title}</p>
      <div className="flex flex-wrap items-center gap-1.5">
        {country ? (
          <Badge tone={country === 'United Kingdom' ? 'success' : 'neutral'}>
            {country === 'United Kingdom' ? 'UK' : country}
          </Badge>
        ) : null}
        {edition ? <Badge tone="neutral">{edition}</Badge> : null}
        {matches ? <Badge tone="neutral">Right film and format</Badge> : null}
        {origin === 'restored' ? <Badge tone="warning">Used on 10 Sep</Badge> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => onUse(url)}>
          <Check aria-hidden /> Use this page
        </Button>
        <Button asChild size="sm" variant="ghost">
          <a href={url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${title} on Blu-ray.com for ${item.filmTitle}`}>
            <ExternalLink aria-hidden /> Open
          </a>
        </Button>
      </div>
    </li>
  )
}

function QueueCard({ item }: { item: SpecQueueItem }) {
  const queryClient = useQueryClient()
  const [pasted, setPasted] = useState('')
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['spec-queue'] })
    void queryClient.invalidateQueries({ queryKey: ['spec-backfill'] })
  }
  const accept = useMutation({ mutationFn: (url: string) => acceptSpecPage(item.lookupId, url), onSuccess: refresh })
  const skip = useMutation({ mutationFn: () => skipSpecDisc(item.lookupId), onSuccess: refresh })
  const busy = accept.isPending || skip.isPending
  const failure = accept.error ?? skip.error

  return (
    <article className="archive-panel space-y-3 p-4" aria-labelledby={`spec-${item.lookupId}`}>
      <div>
        <h3 id={`spec-${item.lookupId}`} className="font-display text-lg font-semibold text-foreground">
          <Link to={`/movies/${item.movieId}`} className="hover:text-primary">{item.filmTitle}</Link>
        </h3>
        <p className="text-xs text-muted-foreground">
          {[item.year ? String(item.year) : 'No year', FORMAT_NAMES[item.formatCode] ?? item.formatCode, item.location]
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>
      {item.note ? <p className="text-sm leading-6 text-muted-foreground">{item.note}</p> : null}

      {item.candidates.length > 0 ? (
        <ul className="divide-y divide-border">
          {item.candidates.map((candidate) => (
            <Candidate key={candidate.url} {...candidate} item={item} busy={busy} onUse={(url) => accept.mutate(url)} />
          ))}
        </ul>
      ) : null}

      <form
        className="space-y-2 border-t border-border pt-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (pasted.trim()) accept.mutate(pasted.trim())
        }}
      >
        <input
          type="url"
          inputMode="url"
          className="form-control w-full"
          placeholder="Paste a Blu-ray.com link"
          aria-label={`Blu-ray.com link for ${item.filmTitle}`}
          value={pasted}
          onChange={(event) => setPasted(event.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" size="sm" variant="secondary" disabled={busy || !pasted.trim()}>
            Use link
          </Button>
          <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => skip.mutate()}>
            <SkipForward aria-hidden /> Skip this disc
          </Button>
        </div>
      </form>

      {failure ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(failure, 'That choice could not be saved.')}
        </p>
      ) : null}
    </article>
  )
}

/**
 * Disc specs — Batch T7, `DECISIONS.md` #202 within #110.
 *
 * **Where Craig settles the discs the matcher would not.** A search proposes Blu-ray.com
 * pages; one clear UK match is accepted on its own, and every other disc lands here with its
 * candidates and the reason. Choosing a page fetches nothing: the next batch does, at the
 * pace #110 sets, and a 403 or 429 from the site halts everything.
 */
export default function SpecsPage() {
  const queryClient = useQueryClient()
  const backfillQuery = useQuery({
    queryKey: ['spec-backfill'],
    queryFn: fetchSpecBackfill,
    refetchInterval: (current) => (current.state.data?.run?.status === 'running' ? 10_000 : false),
  })
  const queueQuery = useQuery({ queryKey: ['spec-queue'], queryFn: () => fetchSpecQueue(20) })
  const batch = useMutation({
    mutationFn: startSpecBatch,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['spec-backfill'] }),
  })

  const backfill = backfillQuery.data
  const running = backfill?.run?.status === 'running'
  const items = queueQuery.data?.items ?? []
  const queueState = listState(queueQuery, items.length === 0)
  const notStarted = batch.data && batch.data.outcome !== 'started' ? NOT_STARTED[batch.data.outcome] : null

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="Craig’s tools"
        title="Disc specs"
        description="Finding each Blu-ray and 4K disc's Blu-ray.com page, then reading its video, audio and region."
      />

      {backfill?.halted ? (
        <div role="alert" className="flex gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive-text">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p>
            The Blu-ray.com integration is halted{backfill.haltedReason ? `: ${backfill.haltedReason}` : ''}. Nothing is fetched
            until you decide to resume it (DECISIONS.md #110).
          </p>
        </div>
      ) : null}
      {backfill && !backfill.searchConfigured ? (
        <p className="rounded-md border border-border bg-muted/40 p-3 text-sm leading-6 text-muted-foreground">
          Searching isn&rsquo;t set up yet: the Brave key is missing. Until it&rsquo;s added, only pages you choose
          are fetched.
        </p>
      ) : null}

      {backfillQuery.isError ? (
        <StatePanel compact tone="error" title="Coverage is unavailable" description={queryErrorMessage(backfillQuery.error, 'Could not load the backfill.')} />
      ) : null}
      {backfill ? <Coverage backfill={backfill} /> : null}

      {backfill && !backfill.halted ? (
        <div className="space-y-2">
          <Button type="button" variant="secondary" disabled={batch.isPending || running} onClick={() => batch.mutate()}>
            {batch.isPending || running ? <Loader2 className="animate-spin" aria-hidden /> : <Play aria-hidden />}
            {running ? 'A batch is running' : 'Run a batch now'}
          </Button>
          {notStarted ? <p className="text-xs text-muted-foreground">{notStarted}</p> : null}
          {batch.isError ? (
            <p role="alert" className="text-sm text-destructive-text">
              {queryErrorMessage(batch.error, 'The batch could not be started.')}
            </p>
          ) : null}
        </div>
      ) : null}

      <section className="space-y-3" aria-labelledby="specs-queue-heading">
        <h2 id="specs-queue-heading" className="section-heading">
          Need you{queueQuery.data ? ` (${COUNT.format(queueQuery.data.total)})` : ''}
        </h2>
        {queueState === 'loading' ? <StatePanel compact tone="loading" title="Loading the discs waiting for you" /> : null}
        {queueState === 'error' ? (
          <StatePanel compact tone="error" title="The queue is unavailable" description={queryErrorMessage(queueQuery.error, 'Could not load the queue.')} />
        ) : null}
        {queueState === 'empty' ? <p className="text-sm text-muted-foreground">Nothing is waiting for you.</p> : null}
        {items.map((item) => <QueueCard key={item.lookupId} item={item} />)}
        {queueQuery.data && queueQuery.data.total > items.length ? (
          <p className="text-xs text-muted-foreground">
            Showing {items.length} of {COUNT.format(queueQuery.data.total)}. More appear as you settle these.
          </p>
        ) : null}
      </section>
    </div>
  )
}
