import { useQuery } from '@tanstack/react-query'
import type { PersonPage as Person } from '@mcu/shared'
import { Link, Navigate, useParams } from 'react-router-dom'

import { ProfileAvatar } from '@/components/ProfileAvatar'
import { Poster } from '@/components/movies/Poster'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { ApiError, fetchPerson, formatLabel } from '@/lib/api'
import { inFormOrder } from '@/lib/copy-formats'
import { queryErrorMessage } from '@/lib/query-state'
import { formatDate } from '@/lib/utils'

function films(count: number): string {
  return `${count.toLocaleString('en-GB')} film${count === 1 ? '' : 's'}`
}

function Section({ title, empty, children, count }: { title: string; empty: string; children: React.ReactNode[]; count?: number }) {
  return (
    <section aria-label={title} className="archive-panel space-y-2 p-4">
      <h2 className="font-display text-lg font-semibold">{title}{count !== undefined ? ` · ${count.toLocaleString('en-GB')}` : ''}</h2>
      {children.length ? <ul className="divide-y divide-border">{children}</ul> : <p className="text-sm text-muted-foreground">{empty}</p>}
    </section>
  )
}

function Row({ to, poster, title, detail }: { to: string; poster: string | null; title: string; detail: string }) {
  return (
    <li>
      <Link to={to} className="touch-target flex min-h-14 items-center gap-3 py-2 text-foreground hover:text-primary">
        <Poster path={poster} title={title} size="w92" decorative className="h-12 w-8 shrink-0 rounded-sm border border-border" />
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 text-sm font-semibold">{title}</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">{detail}</span>
        </span>
      </Link>
    </li>
  )
}

function Page({ person }: { person: Person }) {
  const name = person.displayName
  return (
    <div className="space-y-5">
      <header className="flex items-center gap-4">
        <ProfileAvatar profileId={person.profileId} name={name} className="h-16 w-16 text-2xl" />
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold leading-tight">{name}</h1>
          <p className="text-sm text-muted-foreground">{films(person.watchedThisYear)} watched this year · {films(person.watchedTotal)} in all</p>
        </div>
      </header>
      <Section title="Lately in the diary" empty={`Nothing in ${name}’s diary yet.`}>
        {person.diary.map((entry, index) => (
          <Row key={`${entry.movieId}:${entry.watchedOn}:${String(index)}`} to={`/movies/${entry.movieId}`} poster={entry.posterPath} title={entry.year ? `${entry.title} (${String(entry.year)})` : entry.title}
            detail={[formatDate(entry.watchedOn), entry.rating !== null ? `rated ${String(entry.rating)}` : null, entry.rewatch ? 'rewatch' : null].filter(Boolean).join(' · ')} />
        ))}
      </Section>
      <Section title="Added lately" empty={`${name} has added no copies in the app yet.`}>
        {person.recentlyAdded.map((copy) => (
          <Row key={copy.copyId} to={`/movies/${copy.movieId}`} poster={copy.posterPath} title={copy.title}
            detail={[formatDate(copy.addedOn), inFormOrder(copy.formats).map((code) => formatLabel(code) ?? code).join(' + ')].filter(Boolean).join(' · ')} />
        ))}
      </Section>
      <Section title="Wants" count={person.wantsTotal} empty={`${name} wants nothing yet.`}>
        {person.wants.map((film) => (
          <Row key={film.movieId} to={`/movies/${film.movieId}`} poster={film.posterPath} title={film.year ? `${film.title} (${String(film.year)})` : film.title} detail="Wanted" />
        ))}
      </Section>
      {person.wantsTotal > person.wants.length ? <p className="-mt-3 text-sm text-muted-foreground">And {(person.wantsTotal - person.wants.length).toLocaleString('en-GB')} more on Wanted.</p> : null}
      <Section title="Has now" empty={`${name} has no discs out.`}>
        {person.loans.map((loan) => (
          <Row key={loan.loanId} to={`/loans?loan=${loan.loanId}`} poster={loan.posterPath} title={loan.title}
            detail={loan.state === 'asked_for'
              ? `Asked for${loan.neededBy ? ` · needed by ${formatDate(loan.neededBy)}` : ''}`
              : [loan.lentDate ? `Since ${formatDate(loan.lentDate)}` : 'Out', loan.dueDate ? `due ${formatDate(loan.dueDate)}` : null].filter(Boolean).join(' · ')} />
        ))}
      </Section>
    </div>
  )
}

/**
 * A page for each person — AE9 (#355). Read-only: their diary, the copies they added, their wants
 * and the discs they have now, and nothing from Settings. The reader's own name opens You.
 */
export default function PersonPage() {
  const { profileId = '' } = useParams()
  const { profile } = useAuth()
  const own = Boolean(profile) && profileId === profile?.id
  const query = useQuery({
    queryKey: ['person', profileId],
    queryFn: () => fetchPerson(profileId),
    enabled: Boolean(profile) && Boolean(profileId) && !own,
    retry: false,
  })
  if (own) return <Navigate to="/you" replace />
  const missing = query.error instanceof ApiError && (query.error.status === 404 || query.error.status === 422)
  return (
    <div className="page-shell-narrow space-y-5">
      {query.data ? <Page person={query.data} /> : null}
      {query.isPending && query.fetchStatus !== 'idle' ? <StatePanel tone="loading" title="Loading their page" /> : null}
      {query.isPending && query.fetchStatus === 'idle' && profile ? <StatePanel tone="offline" title="Not kept offline" description="Reconnect to see this page." /> : null}
      {missing ? <StatePanel tone="empty" title="No such person" description="They may no longer use the app." /> : null}
      {query.isError && !missing ? <StatePanel tone="error" title="Could not load this page" description={queryErrorMessage(query.error, 'Please try again.')} /> : null}
    </div>
  )
}
