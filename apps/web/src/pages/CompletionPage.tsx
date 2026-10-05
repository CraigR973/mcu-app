import { CompletionSets } from '@/components/dashboard/CompletionSets'
import { PageHeader } from '@/components/ui/page-header'

/**
 * Every completion set, with its filters — Batch W2 (#249).
 *
 * Home shows a row of the sets closest to complete; this is the whole list behind its "All"
 * link, at `/insights`, the old Insights page's address, which redirected to Home from Batch
 * S3 until W2. Opening a set shows it in place of the list, and Craig's "Refresh from TMDB"
 * lives here, off Home.
 */
export default function CompletionPage() {
  return (
    <div className="page-shell-narrow">
      {/* No spacing utility here: hidden on a phone, the header would still leave a gap. */}
      <PageHeader
        eyebrow="Your archive"
        title="Completion"
        description="How much of each director’s and actor’s work is on the shelf."
      />
      <CompletionSets />
    </div>
  )
}
