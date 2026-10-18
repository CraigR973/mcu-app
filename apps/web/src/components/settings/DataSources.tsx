/**
 * Where the film data comes from — Batch X12c (DS44-06, CT46-06).
 *
 * TMDB's terms require its logo and a notice that the product is not endorsed or certified by
 * it, and neither was anywhere in the app. The logo is TMDB's own file (`public/third-party/tmdb.svg`,
 * from themoviedb.org/about/logos-attribution), unaltered. Where to watch comes from TMDB's
 * endpoint, whose terms require the data to be credited to JustWatch.
 */
export function DataSources() {
  return (
    <section aria-labelledby="data-sources" className="archive-panel flex items-start gap-4 p-4">
      <img src="/third-party/tmdb.svg" alt="TMDB" width="64" height="46" className="mt-1 h-auto w-16 shrink-0" />
      <div className="space-y-1.5">
        <h2 id="data-sources" className="text-sm font-semibold text-foreground">
          Film data
        </h2>
        <p className="text-xs leading-5 text-muted-foreground">
          This product uses the TMDB API but is not endorsed or certified by TMDB. Film details,
          posters and credits come from{' '}
          <a
            href="https://www.themoviedb.org"
            target="_blank"
            rel="noreferrer noopener"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            themoviedb.org
          </a>
          .
        </p>
        <p className="text-xs leading-5 text-muted-foreground">
          Where-to-watch data is provided by{' '}
          <a
            href="https://www.justwatch.com"
            target="_blank"
            rel="noreferrer noopener"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            JustWatch
          </a>
          .
        </p>
      </div>
    </section>
  )
}
