import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Gift } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { fetchGiftPage, formatLabel, posterUrl } from '@/lib/api'

/**
 * §12.2's public gift page — *"non-logged-in visitor can browse Dad's wanted list"*.
 *
 * **Outside the auth shell entirely.** No `ProtectedRoute`, no `authFetch`, no session
 * check — a visitor here has never logged in and never will, and any of those would either
 * redirect them to a sign-in page or try to refresh a session that does not exist.
 *
 * The page shows a title, posters, formats, price guidance and links to shops. It shows
 * **nothing** about the collection: not what is owned, not what has been watched, not who
 * the list belongs to. The API enforces that with a response model that is deliberately not
 * a superset of the admin one; this page could not display those fields if it tried.
 *
 * A wrong, expired, revoked or deactivated link all render the same "not available"
 * message, because the API answers all four identically.
 */
export default function GiftPage() {
  const { slug = '' } = useParams<{ slug: string }>()

  const pageQuery = useQuery({
    queryKey: ['gift-page', slug],
    queryFn: () => fetchGiftPage(slug),
    retry: false,
  })

  // A capability URL must not be indexed. The header is set by the API for its own
  // response; this is the page a crawler would actually see.
  useEffect(() => {
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    document.head.appendChild(meta)
    return () => {
      meta.remove()
    }
  }, [])

  const page = pageQuery.data

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-10">
        {pageQuery.isPending ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : pageQuery.isError || !page ? (
          <div className="flex flex-col items-center gap-3 py-24 text-center">
            <Gift className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              This list is not available. The link may have expired or been turned off.
            </p>
          </div>
        ) : (
          <>
            <header className="space-y-1">
              <h1 className="text-3xl font-bold text-foreground">{page.title}</h1>
              <p className="text-sm text-muted-foreground">
                {page.total} film{page.total === 1 ? '' : 's'} still wanted
                {page.filterConfig.maxPrice
                  ? ` · under £${page.filterConfig.maxPrice}`
                  : ''}
                {page.filterConfig.formats.length > 0
                  ? ` · ${page.filterConfig.formats.map((f) => formatLabel(f) ?? f).join(', ')}`
                  : ''}
              </p>
            </header>

            {page.films.length === 0 ? (
              <p className="py-16 text-center text-sm text-muted-foreground">
                Nothing on the list matches these filters right now.
              </p>
            ) : (
              <ul className="grid grid-cols-2 gap-5 sm:grid-cols-3 md:grid-cols-4">
                {page.films.map((film) => (
                  <li key={`${film.title}-${String(film.year)}`} className="space-y-1.5">
                    <img
                      src={posterUrl(film.posterPath, 'w342')}
                      alt=""
                      loading="lazy"
                      className="aspect-[2/3] w-full rounded-md object-cover"
                    />
                    <p className="text-sm font-medium text-foreground">{film.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {[
                        film.year ? String(film.year) : null,
                        formatLabel(film.preferredFormat) ?? null,
                        film.maxPrice ? `around £${film.maxPrice}` : null,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                    {film.retailerLinks.length > 0 ? (
                      <ul className="flex flex-wrap gap-x-2 gap-y-0.5">
                        {film.retailerLinks.map((link) => (
                          <li key={link.name}>
                            <a
                              href={link.url}
                              target="_blank"
                              // `noopener` so the opened page cannot reach back through
                              // `window.opener`; `noreferrer` so a shop is not told which
                              // gift link sent the visitor.
                              rel="noopener noreferrer nofollow"
                              className="inline-flex items-center gap-0.5 text-[11px] text-primary hover:underline"
                            >
                              {link.name}
                              <ExternalLink className="h-2.5 w-2.5" />
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}

            <footer className="border-t border-border pt-4 text-xs text-muted-foreground">
              Prices are a guide only. This page shows a wish list and nothing else about
              the collection.
            </footer>
          </>
        )}
      </div>
    </div>
  )
}
