import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AssignedReview, ReviewAnswer } from '@mcu/shared'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { NeedsYouList } from '@/components/dashboard/NeedsYouList'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { answerReview, assignReview, fetchAssignedReviews, fetchNeedsYou, fetchReviewProposals } from '@/lib/api'
import { needsYouRows } from '@/lib/needs-you'
import { listState, queryErrorMessage } from '@/lib/query-state'

const STATUS = {
  open: 'Needs your observation',
  answered: 'Answered — awaiting correction',
  changed: 'The record changed — needs another look',
  resolved: 'Resolved through the catalogue',
}

function ReviewCard({ review, selected }: { review: AssignedReview; selected: boolean }) {
  const client = useQueryClient()
  const section = useRef<HTMLElement>(null)
  const [choice, setChoice] = useState<ReviewAnswer | ''>(review.answer ?? '')
  useEffect(() => {
    if (selected) section.current?.scrollIntoView({ block: 'start' })
  }, [selected])
  const save = useMutation({
    mutationFn: () => {
      if (!choice) throw new Error('Choose an answer first.')
      return answerReview(review.id, review.revision, choice)
    },
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['assigned-reviews'] }) },
  })
  return (
    <section ref={section} id={`review-${review.id}`} aria-labelledby={`title-${review.id}`}
      className={`archive-panel scroll-mt-24 space-y-3 p-4 ${selected ? 'ring-2 ring-primary' : ''}`}>
      <h2 id={`title-${review.id}`} className="font-display text-lg font-semibold">{review.title}</h2>
      <p className="text-xs text-muted-foreground">For {review.assigneeName} · {STATUS[review.status]}</p>
      <p>{review.question}</p>
      <p className="text-sm text-muted-foreground">{review.evidence}</p>
      {review.movieId ? <Link to={`/movies/${review.movieId}`} className="inline-block text-sm text-primary hover:underline">Inspect the film and copies</Link> : <p className="text-sm">The film is no longer available. Craig needs to check this review.</p>}
      {review.answer ? <p role="status" className="text-sm">Recorded answer: {review.choices.find(option => option.value === review.answer)?.label}</p> : null}
      {review.canAnswer ? (
        <form onSubmit={(event) => { event.preventDefault(); save.mutate() }} className="space-y-3">
          <fieldset disabled={save.isPending} className="space-y-1">
            <legend className="text-sm font-semibold">Your observation</legend>
            {review.choices.map(option => (
              <label key={option.value} className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
                <input type="radio" name={`choice-${review.id}`} value={option.value} checked={choice === option.value}
                  onChange={() => setChoice(option.value)} />
                {option.label}
              </label>
            ))}
          </fieldset>
          <p className="text-xs text-muted-foreground">Saving records your answer. It does not change the film, move copies or rewrite prices.</p>
          <Button type="submit" disabled={!choice || save.isPending}>{save.isPending ? 'Saving…' : 'Save observation'}</Button>
          {save.isSuccess ? <p role="status" className="text-sm">Observation saved. The review stays visible until the catalogue work is resolved.</p> : null}
          {save.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(save.error, 'Could not save your observation.')} Re-open the page if the review changed.</p> : null}
        </form>
      ) : null}
      {review.status === 'changed' ? <p className="text-sm">The current record differs from this question. Craig needs to review it before another answer.</p> : null}
    </section>
  )
}

function MarkAssignmentPanel() {
  const client = useQueryClient()
  // Explicit preflight only, not a request on every Home/page read.
  const proposals = useQuery({ queryKey: ['review-proposals'], queryFn: fetchReviewProposals, enabled: false, retry: false })
  const assignment = useMutation({
    mutationFn: async () => {
      if (!proposals.data || proposals.data.length !== 3) throw new Error('Check the three current targets first.')
      // Independent assignments are deliberately sequential: report partial failure; retries
      // re-use assignments already made rather than replacing someone's answer.
      for (const proposal of proposals.data) await assignReview(proposal)
    },
    onSettled: async () => { await client.invalidateQueries({ queryKey: ['assigned-reviews'] }) },
  })
  return (
    <section className="archive-panel space-y-3 p-4" aria-label="Assign Mark's reviews">
      <h2 className="font-display text-lg font-semibold">Mark’s three catalogue reviews</h2>
      <p className="text-sm text-muted-foreground">Check the current Titanic, Dead Man’s Shoes and Shetland records, then assign the questions to Mark. This sends no notification and makes no catalogue corrections.</p>
      <Button variant="outline" disabled={proposals.isFetching || assignment.isPending} onClick={() => { void proposals.refetch() }}>Check current targets</Button>
      {proposals.data && !proposals.isError ? <>
        <ul className="list-inside list-disc text-sm">{proposals.data.map(proposal => <li key={proposal.kind}>{proposal.title}</li>)}</ul>
        <Button disabled={assignment.isPending || proposals.isFetching} onClick={() => assignment.mutate()}>{assignment.isPending ? 'Assigning…' : 'Assign these three reviews to Mark'}</Button>
      </> : null}
      {proposals.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(proposals.error, 'Could not check the current records.')}</p> : null}
      {assignment.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(assignment.error, 'Assignment stopped.')} Some reviews may already be assigned; the list below shows what exists. Recheck the targets before continuing.</p> : null}
      {assignment.isSuccess ? <p role="status" className="text-sm">All three reviews are assigned. Existing answers were preserved.</p> : null}
    </section>
  )
}

/** AE8 (#355): every item on Needs you, Home's five and the rest, each saying whose it is, the
 *  reader's own first. One read, shared with Home's row. */
function EverythingWaiting() {
  const { profile } = useAuth()
  const query = useQuery({ queryKey: ['needs-you', profile?.id], queryFn: fetchNeedsYou, enabled: Boolean(profile) })
  const rows = query.data ? needsYouRows(query.data, profile) : []
  const state = listState(query, rows.length === 0)
  return (
    <section aria-labelledby="needs-you-everything" className="archive-panel p-4">
      <h2 id="needs-you-everything" className="font-display text-lg font-semibold">Everything waiting</h2>
      {state === 'ready' ? <NeedsYouList rows={rows} className="mt-2" /> : null}
      {state === 'loading' ? <p className="mt-1 text-sm text-muted-foreground">Loading what is waiting…</p> : null}
      {state === 'empty' ? <p className="mt-1 text-sm text-muted-foreground">Nothing is waiting on you.</p> : null}
      {state === 'offline' ? <p role="status" className="mt-1 text-sm">Not kept offline. Reconnect to see what is waiting.</p> : null}
      {state === 'error' ? <p role="alert" className="mt-1 text-sm text-destructive">{queryErrorMessage(query.error, 'Could not load what is waiting.')}</p> : null}
    </section>
  )
}

export default function AssignedReviewsPage() {
  const { profile } = useAuth()
  const [params] = useSearchParams()
  const admin = profile?.role === 'admin'
  const query = useQuery({
    queryKey: ['assigned-reviews', profile?.id, admin],
    queryFn: () => fetchAssignedReviews(admin),
    enabled: Boolean(profile),
  })
  const state = listState(query, (query.data?.length ?? 0) === 0)
  return (
    <div className="page-shell-narrow space-y-5">
      <PageHeader eyebrow={admin ? 'Catalogue review' : 'Your account'} title="Needs you"
        description="Loans, cinema trips and reviews waiting, yours first. Only the person an item is for can act on it, except loans, which either of you can." />
      <nav aria-label="Other Needs you actions" className="flex gap-4 text-sm text-primary">
        <Link to="/loans">Loans</Link><Link to="/movie-night">Cinema trips</Link>
      </nav>
      <EverythingWaiting />
      {admin ? <MarkAssignmentPanel /> : null}
      {state === 'loading' ? <StatePanel tone="loading" title="Loading your reviews" /> : null}
      {state === 'offline' ? <StatePanel tone="offline" title="Reviews are unavailable offline" description="Reconnect to see the current records and save an observation." /> : null}
      {state === 'error' ? <StatePanel tone="error" title="Could not load reviews" description={queryErrorMessage(query.error, 'Please try again.')} /> : null}
      {state === 'empty' ? <StatePanel tone="empty" title="No assigned reviews" description="Your loans and cinema trips remain on Home and their own pages." /> : null}
      {state === 'ready' ? query.data?.map(review => <ReviewCard key={`${review.id}:${review.revision}`} review={review} selected={params.get('review') === review.id} />) : null}
    </div>
  )
}
