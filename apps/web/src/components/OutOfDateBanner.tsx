import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { OUT_OF_DATE, OUT_OF_DATE_EVENT } from '@/lib/describe-error'

/**
 * "This screen needs the newest version", with Reload — Batch X8 (UX48-03, CR43-04).
 *
 * Shown when a screen met an answer this build cannot read: the API gained a value after
 * this phone loaded the app, or a deploy removed a chunk the page still asks for. The
 * query or mutation cache raises the event (`query-client.ts`); a reload fetches the build
 * that matches the API.
 */
export default function OutOfDateBanner() {
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const show = () => setShown(true)
    window.addEventListener(OUT_OF_DATE_EVENT, show)
    return () => window.removeEventListener(OUT_OF_DATE_EVENT, show)
  }, [])

  if (!shown) return null
  return (
    <div role="alert" className="border-b border-primary/30 bg-primary/10">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-2 text-sm">
        <span className="flex-1">{OUT_OF_DATE}</span>
        <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
          <RefreshCw className="mr-1 h-3 w-3" aria-hidden />
          Reload
        </Button>
      </div>
    </div>
  )
}
