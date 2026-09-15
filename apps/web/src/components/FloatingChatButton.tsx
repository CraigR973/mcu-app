import { Bot } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'

/**
 * §9.3's "floating chat button on every page".
 *
 * A link rather than a modal: the chat is a real route with its own conversations, and a
 * button that opened an overlay would make "send me that answer" and "come back to it
 * later" both impossible. Hidden on the chat itself, where it would cover the input, and
 * on the pages that have no shell — a floating action button on the login screen is just
 * a thing to mis-tap.
 */
export function FloatingChatButton() {
  const { pathname } = useLocation()
  const hidden =
    pathname.startsWith('/assistant') ||
    pathname.startsWith('/settings/ai') ||
    pathname.startsWith('/login') ||
    pathname.startsWith('/welcome')

  if (hidden) return null

  return (
    <Link
      to="/assistant"
      aria-label="Ask the assistant"
      className={cn(
        'fixed bottom-[5.5rem] right-4 z-20 flex h-12 w-12 items-center justify-center rounded-full lg:bottom-5 lg:right-5',
        'bg-primary text-primary-foreground shadow-soft transition-transform hover:-translate-y-0.5',
        // Clear of the iOS home indicator, which otherwise swallows the tap.
        'mb-[env(safe-area-inset-bottom)]',
      )}
    >
      <Bot className="h-5 w-5" aria-hidden />
    </Link>
  )
}
