import { useState } from 'react'
import { Bell, Bot, Clapperboard } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { WatchHistoryPanel } from '@/components/settings/WatchHistoryPanel'
import { PageHeader } from '@/components/ui/page-header'
import { cn } from '@/lib/utils'
import { AiSettings } from './AiSettingsPage'
import { NotificationSettings } from './NotificationSettingsPage'

type Tab = 'notifications' | 'assistant' | 'history'

const TABS: { key: Tab; label: string; icon: typeof Bell }[] = [
  { key: 'notifications', label: 'Notifications', icon: Bell },
  // Batch S5. A third tab rather than a fourth sidebar destination: it is a setting about
  // your own account, which is what this page is for.
  { key: 'history', label: 'Watch history', icon: Clapperboard },
  { key: 'assistant', label: 'Assistant', icon: Bot },
]

/**
 * One Settings page — Batch S3, snag 5 (`DECISIONS.md` #154).
 *
 * Notifications and AI settings were two sidebar destinations for one job. Merging them
 * removes an item, and it **puts AI settings back in the menu at all**: it was defined as
 * a destination before this batch but sat in no group, reachable only from a header button,
 * which is how a page becomes a thing you have to already know about.
 *
 * **Tabs rather than a stack.** The two have nothing to do with each other — one is about
 * which alerts reach which device, the other about a spend cap — and stacking a 514-line
 * page above a 260-line one would make the second effectively unreachable on a phone. The
 * choice is in the query string so a tab can be linked to, and so the redirects from the
 * two old paths land on the right half.
 */
export default function SettingsPage() {
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const [fallback, setFallback] = useState<Tab>('notifications')
  const active: Tab =
    requested === 'assistant' || requested === 'notifications' || requested === 'history'
      ? requested
      : fallback

  function select(tab: Tab) {
    setFallback(tab)
    setParams(tab === 'notifications' ? {} : { tab }, { replace: true })
  }

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="Your account"
        title="Settings"
        description="Which alerts reach you and on which devices, how your watch history stays current, and what the assistant is allowed to spend."
      />

      <div role="tablist" aria-label="Settings sections" className="flex gap-1 border-b border-border">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`settings-tab-${key}`}
            aria-selected={active === key}
            aria-controls={`settings-panel-${key}`}
            onClick={() => select(key)}
            className={cn(
              'touch-target -mb-px flex min-h-11 items-center gap-2 border-b-2 px-4 text-sm font-semibold transition-colors',
              active === key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            {label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`settings-panel-${active}`}
        aria-labelledby={`settings-tab-${active}`}
        tabIndex={0}
      >
        {active === 'notifications' ? <NotificationSettings /> : null}
        {active === 'history' ? <WatchHistoryPanel /> : null}
        {active === 'assistant' ? <AiSettings /> : null}
      </div>
    </div>
  )
}
