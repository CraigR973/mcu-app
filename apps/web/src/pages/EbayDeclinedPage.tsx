import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'

/**
 * Where eBay sends a person who chose not to agree — Batch T8b, the RuName's "Auth declined
 * URL" (`DECISIONS.md` #227). Nothing reached the app, so there is nothing to undo.
 */
export default function EbayDeclinedPage() {
  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader eyebrow="Settings" title="eBay not connected" />
      <p className="text-sm leading-6 text-muted-foreground">
        You chose not to connect eBay, so the app has stored nothing. You can connect it from
        Settings whenever you like.
      </p>
      <Button asChild size="sm" variant="outline">
        <Link to="/settings?tab=ebay">Back to Settings</Link>
      </Button>
    </div>
  )
}
