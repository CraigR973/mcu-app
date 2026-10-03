import type { FilmReview } from '@mcu/shared'

import { formatLabel } from '@/lib/api'

function scoreText(score: number): string {
  return score.toFixed(1)
}

function siteLabel(review: FilmReview): string {
  return review.formatCode ? `${review.siteName} (${formatLabel(review.formatCode)})` : review.siteName
}

/**
 * A film's reviews — Batch V9, snag 8 (`DECISIONS.md` #228, #241).
 *
 * "Reviews: Blu-ray.com · AVForums" as links, then each review's line: Blu-ray.com's scores
 * under its own headings once read, Brave's one-line description, and why there are none
 * when there are none. AVForums never has scores: it forbids apps reading its pages. Shown
 * on Wanted items and on the film page; nothing renders when no review was found.
 */
export function ReviewLinks({ reviews, className }: { reviews: FilmReview[]; className?: string }) {
  if (reviews.length === 0) return null
  return (
    <div className={className}>
      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Reviews:</span>{' '}
        {reviews.map((review, index) => (
          <span key={review.url}>
            {index > 0 ? ' · ' : null}
            <a
              href={review.url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-primary underline-offset-2 hover:underline"
            >
              {siteLabel(review)}
            </a>
          </span>
        ))}
      </p>
      <ul className="mt-1 space-y-1.5">
        {reviews.map((review) => {
          const others = review.scores.filter((score) => score.heading.toLowerCase() !== 'overall')
          return (
            <li key={review.url} className="text-xs leading-5 text-muted-foreground">
              <span className="font-medium text-foreground">{review.siteName}</span>
              {review.overall !== null && review.outOf !== null ? (
                <>
                  {' · '}
                  <span className="font-semibold text-foreground">
                    {scoreText(review.overall)}/{review.outOf}
                  </span>{' '}
                  overall
                  {others.length > 0 ? (
                    <span className="block">
                      {others.map((score) => `${score.heading} ${scoreText(score.score)}`).join(' · ')}
                    </span>
                  ) : null}
                </>
              ) : null}
              {review.description ? (
                <span className="line-clamp-2">{review.description}</span>
              ) : null}
              {review.note ? <span className="block italic">{review.note}</span> : null}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
