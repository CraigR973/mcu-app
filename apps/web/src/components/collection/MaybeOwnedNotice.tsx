import { HelpCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

interface Props {
  film: { movieId: string; title: string }
}

/**
 * "You may already own this" — Batch X10 (CT46-04, #280).
 *
 * An owned film nothing has identified yet whose title reads as the one being added, found by
 * Search's own lookalike check. A warning, not a refusal: the person decides whether the disc
 * in hand is that one. Worded as Search's film card words it.
 */
export default function MaybeOwnedNotice({ film }: Props) {
  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/45 bg-warning/10 p-3 text-sm"
      role="status"
    >
      <HelpCircle className="h-4 w-4 shrink-0 text-warning" aria-hidden />
      <span className="min-w-0 flex-1">
        You may already own this: “{film.title}” is on a shelf and hasn't been identified yet.
      </span>
      <Button asChild size="sm" variant="outline">
        <Link to={`/movies/${film.movieId}`}>Open it</Link>
      </Button>
    </div>
  )
}
