import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { assignReview, fetchReviewProposals } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/** AG3 (UX54-03): the control that assigns the three catalogue reviews, moved from Needs you to
 *  the admin's tools, where it is the admin's job and not a card on the page the other person
 *  reads. It still checks first and assigns only on its own click. */
export function AssignReviewsPanel() {
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
