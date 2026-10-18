import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronRight, LogOut } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { COLLECTION_ICONS } from '@/components/collections/icons'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { useAuth } from '@/context/auth'
import { fetchNavSections, fetchSmartCollections, tellCraig } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import {
  adminNavGroup,
  BOTTOM_BAR_PATHS,
  navGroups,
  visibleGroups,
  type NavGroup,
  type NavItem,
} from '@/lib/nav-items'

const IN_THE_BAR = new Set<string>(BOTTOM_BAR_PATHS)

/** A group without the destinations the bottom bar already carries; `null` when that
 *  leaves it empty, because a heading over nothing is its own kind of dead link. */
function beyondTheBar(group: NavGroup): NavGroup | null {
  const items = group.items.filter((item) => !IN_THE_BAR.has(item.path))
  return items.length > 0 ? { ...group, items } : null
}

function DestinationLink({ item }: { item: NavItem }) {
  const Icon = item.icon
  return (
    <Link
      to={item.path}
      className="flex min-h-12 items-center gap-3 px-4 py-2 text-sm font-semibold text-foreground hover:bg-muted"
    >
      <Icon className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
      <span className="min-w-0 flex-1 truncate">{item.label}</span>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
    </Link>
  )
}

function DestinationGroup({ group }: { group: NavGroup }) {
  return (
    <section aria-labelledby={`you-${group.label}`}>
      <h2 id={`you-${group.label}`} className="px-1 pb-1 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {group.label}
      </h2>
      <div className="archive-panel divide-y divide-border overflow-hidden">
        {group.items.map((item) => <DestinationLink key={item.path} item={item} />)}
      </div>
    </section>
  )
}

/**
 * "Tell Craig" (Batch X12a, UX48-05): a line to Craig that lands in his Home "Needs attention"
 * row, for Mark, who had no way to say "this is wrong" from inside the app.
 */
function TellCraig() {
  const [message, setMessage] = useState('')
  const send = useMutation({
    mutationFn: () => tellCraig(message.trim()),
    onSuccess: () => setMessage(''),
  })
  return (
    <section aria-labelledby="you-tell-craig" className="space-y-2">
      <h2 id="you-tell-craig" className="px-1 pb-1 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        Tell Craig
      </h2>
      <form
        className="archive-panel space-y-2 p-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (message.trim()) send.mutate()
        }}
      >
        <label htmlFor="tell-craig" className="text-sm text-muted-foreground">
          Something wrong, or something you want. It shows on Craig&apos;s Home until he clears it.
        </label>
        <textarea
          id="tell-craig"
          value={message}
          onChange={(event) => {
            setMessage(event.target.value)
            send.reset()
          }}
          maxLength={300}
          rows={3}
          className="block w-full rounded-md border border-input bg-background px-3 py-2 text-base"
        />
        <div className="flex items-center justify-between gap-3">
          <Button type="submit" disabled={send.isPending || message.trim().length === 0}>
            Send
          </Button>
          {send.isSuccess ? <p role="status" className="text-sm text-muted-foreground">Sent to Craig.</p> : null}
          {send.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {queryErrorMessage(send.error, 'That could not be sent.')}
            </p>
          ) : null}
        </div>
      </form>
    </section>
  )
}

/**
 * Everything the bottom bar does not carry, and the account — Batch T3, `DECISIONS.md` #201.
 *
 * Opened from the person's initial in the phone's top bar. It replaces the slide-out
 * menu, so it lists **every** destination except the four in the bar: the same groups the
 * desktop sidebar shows, with the same hide-when-empty rule (#154), and the admin pages
 * for an admin.
 */
export default function YouPage() {
  const { profile, signOut } = useAuth()
  const isAdmin = profile?.role === 'admin'

  const { data: sections } = useQuery({
    queryKey: ['nav-sections'],
    queryFn: fetchNavSections,
    staleTime: 5 * 60 * 1000,
  })
  const { data: collections } = useQuery({
    queryKey: ['smart-collections'],
    queryFn: () => fetchSmartCollections(),
    staleTime: 5 * 60 * 1000,
  })

  const groups = visibleGroups(navGroups, sections)
    .map(beyondTheBar)
    .filter((group): group is NavGroup => group !== null)
  const admin = isAdmin ? beyondTheBar(adminNavGroup) : null
  const saved = collections?.items ?? []

  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader eyebrow="Your account" title="You" />

      <section className="archive-panel flex items-center gap-3 p-4" aria-label="Signed in as">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-secondary font-display text-lg font-semibold text-secondary-foreground">
          {profile?.displayName?.slice(0, 1).toUpperCase() ?? '?'}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold text-foreground">{profile?.displayName ?? 'Not signed in'}</span>
          <span className="block text-xs capitalize text-muted-foreground">{profile?.role ?? ''}</span>
        </span>
        <ThemeToggle />
      </section>

      {groups.map((group) => <DestinationGroup key={group.label} group={group} />)}

      {saved.length > 0 ? (
        <section aria-labelledby="you-saved">
          <h2 id="you-saved" className="px-1 pb-1 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Saved collections
          </h2>
          <div className="archive-panel divide-y divide-border overflow-hidden">
            {saved.map((collection) => (
              <DestinationLink
                key={collection.id}
                item={{ label: collection.name, path: `/collections/${collection.id}`, icon: COLLECTION_ICONS[collection.icon] }}
              />
            ))}
          </div>
        </section>
      ) : null}

      {admin ? <DestinationGroup group={admin} /> : null}

      {profile && !isAdmin ? <TellCraig /> : null}

      <Button type="button" variant="outline" className="w-full justify-center" onClick={() => void signOut()}>
        <LogOut aria-hidden /> Sign out
      </Button>
    </div>
  )
}
