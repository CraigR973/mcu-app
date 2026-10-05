import { BidTrial } from '@/components/dashboard/BidTrial'
import { CollectionValue } from '@/components/dashboard/CollectionValue'
import { PageHeader } from '@/components/ui/page-header'

/**
 * Admin's "Collection value" — Batch W2, snag 7 (`DECISIONS.md` #249: "Move to Admin").
 *
 * The valuation's run button and the bid trial, off Home so Home only reads. Both are
 * unchanged: the panel that starts and follows a valuation run (Batch T6) and V6's "Try bid
 * prices", which saves no prices and can be run again if bids ever thicken (#237). Home keeps
 * the total, as the collection row's "Worth" card. Admin-only, as the route and the API are.
 */
export default function ValuationPage() {
  return (
    <div className="page-shell-narrow">
      {/* Outside the sections' spacing: hidden on a phone, it would still leave a gap. */}
      <PageHeader
        eyebrow="Craig’s tools"
        title="Collection value"
        description="What the collection is worth at eBay asking prices, the run that keeps it current, and the bid-price trial."
      />
      <div className="space-y-10">
        <CollectionValue />
        <BidTrial />
      </div>
    </div>
  )
}
