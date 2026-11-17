import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { WantProposal } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { assignReview, fetchReviewProposals, fetchWantProposals } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/** AG3 (UX54-03): the control that assigns the three catalogue reviews, moved from Needs you to
 *  the admin's tools, where it is the admin's job and not a card on the page the other person
 *  reads. It still checks first and assigns only on its own click. */
function CatalogueReviews() {
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

/** AG5 (MK53-03): any want can ask "which film?". The shop check keeps a listing of another
 *  film of a want's title apart from its prices; this lists those wants, each with the question
 *  it would ask, and assigns one only on its own click. */
function WantQuestions() {
  const client = useQueryClient()
  const proposals = useQuery({ queryKey: ['want-proposals'], queryFn: fetchWantProposals, enabled: false, retry: false })
  const assignment = useMutation({
    mutationFn: (proposal: WantProposal) => assignReview(proposal),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: ['assigned-reviews'] })
      await proposals.refetch()
    },
  })
  return (
    <section className="archive-panel space-y-3 p-4" aria-label="Which film each want is">
      <h2 className="font-display text-lg font-semibold">Which film each want is</h2>
      <p className="text-sm text-muted-foreground">When a shop lists another film under a want’s title, its listing is kept apart from the want’s prices. Check which wants that is, then ask which film each one is. Asking sends no notification and changes no want.</p>
      <Button variant="outline" disabled={proposals.isFetching || assignment.isPending} onClick={() => { void proposals.refetch() }}>Check wants</Button>
      {proposals.data && !proposals.isError && proposals.data.length === 0 ? <p role="status" className="text-sm">No want’s shops list another film.</p> : null}
      {proposals.data && !proposals.isError && proposals.data.length > 0 ? (
        <ul className="space-y-3">
          {proposals.data.map(proposal => (
            <li key={proposal.targetId} className="space-y-1 text-sm">
              <p className="font-semibold">{proposal.title}</p>
              <p>{proposal.question}</p>
              <Button size="sm" disabled={assignment.isPending || proposals.isFetching} onClick={() => assignment.mutate(proposal)}>Ask {proposal.assigneeName}</Button>
            </li>
          ))}
        </ul>
      ) : null}
      {proposals.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(proposals.error, 'Could not check the wants.')}</p> : null}
      {assignment.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(assignment.error, 'The question was not asked.')} Check the wants again before retrying.</p> : null}
      {assignment.isSuccess ? <p role="status" className="text-sm">Asked. It is on their Needs you.</p> : null}
    </section>
  )
}

export function AssignReviewsPanel() {
  return (
    <div className="space-y-6">
      <CatalogueReviews />
      <WantQuestions />
    </div>
  )
}
