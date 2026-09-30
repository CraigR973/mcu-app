import { Link, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { COLLECTION_ICONS } from '@/components/collections/icons'
import { fetchNavSections, fetchSmartCollections } from '@/lib/api'
import { useAuth } from '@/context/auth'
import { ThemeToggle } from '@/components/ThemeToggle'
import { BrandMark } from '@/components/brand/BrandMark'
import { Button } from '@/components/ui/button'
import { adminNavGroup, navGroups, visibleGroups } from '@/lib/nav-items'
import { cn } from '@/lib/utils'

const LINK_CLS =
  'group flex min-h-10 items-center gap-3 rounded-md border border-transparent px-3 py-2 text-sm font-semibold transition-colors'

/**
 * The desktop sidebar — every destination, the account, and sign-out.
 *
 * **Desktop only since Batch T3** (`DECISIONS.md` #201). Below 1024px it used to slide
 * out from a menu button and from the bottom bar's "More"; both are gone, and the "You"
 * page carries everything the five bottom tabs do not.
 */
export default function Sidebar() {
  const { profile, signOut } = useAuth()

  // §6.31: "Smart collections appear in the sidebar with custom icons." Failing quietly
  // is right here — the sidebar is navigation, and a network problem should not cost
  // the person the links that do work.
  const { data: collections } = useQuery({
    queryKey: ['smart-collections'],
    queryFn: () => fetchSmartCollections(),
    staleTime: 5 * 60 * 1000,
  })
  const saved = collections?.items ?? []

  // Batch S3, snag 5. Box sets, Collections and Deals hide while their table is empty
  // (`DECISIONS.md` #154); Loans did too until Batch V1, and is always listed now (#228).
  // Four `COUNT(*)`s in one round trip, cached for five minutes —
  // the menu is drawn on every page, and a count that is one navigation stale costs
  // nothing, while a request per page would cost something on a phone.
  //
  // **Failing quietly shows the items rather than hiding them.** `isVisible` treats an
  // unknown count as "show", so a failed or still-loading request leaves the menu as it
  // was rather than removing four links — hiding them because the network was slow would
  // be a worse bug than the emptiness this is fixing.
  const { data: sections } = useQuery({
    queryKey: ['nav-sections'],
    queryFn: fetchNavSections,
    staleTime: 5 * 60 * 1000,
  })
  const groups = visibleGroups(navGroups, sections)

  return (
    <>
      <aside className="relative hidden w-[17rem] shrink-0 flex-col border-r border-border bg-card lg:flex">
        {/* Header */}
        <div className="flex min-h-[4.75rem] items-center justify-between border-b border-border px-4 py-3">
          <Link to="/movies" className="flex min-w-0 items-center gap-3 rounded-md">
            <BrandMark size={40} />
            <span className="min-w-0">
              <span className="block truncate font-display text-base font-semibold leading-none text-foreground">
                The Real MCU
              </span>
              <span className="mt-1 block truncate text-[0.5625rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Private film archive
              </span>
            </span>
          </Link>
        </div>

        {/* Nav */}
        <nav aria-label="Application destinations" className="flex-1 overflow-y-auto px-3 py-4">
          {groups.map((group) => (
            <div key={group.label} className="mb-5 last:mb-0">
              <p className="mb-1 px-3 text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map(({ label, path, icon: Icon }) => (
                  <NavLink
                    key={path}
                    to={path}
                    className={({ isActive }) =>
                      cn(
                        LINK_CLS,
                        isActive
                          ? 'border-primary/15 bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )
                    }
                  >
                    <Icon className="h-[1.125rem] w-[1.125rem] shrink-0 opacity-80 group-hover:opacity-100" aria-hidden />
                    <span className="truncate">{label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}

          {profile?.role === 'admin' && (
            <div className="mb-5 border-t border-border pt-4">
              <p className="mb-1 px-3 text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {adminNavGroup.label}
              </p>
              <div className="space-y-0.5">
                {adminNavGroup.items.map(({ label, path, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) =>
                  cn(
                    LINK_CLS,
                    isActive
                      ? 'border-primary/15 bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )
                }
              >
                <Icon className="h-[1.125rem] w-[1.125rem] shrink-0 opacity-80" aria-hidden />
                <span className="truncate">{label}</span>
              </NavLink>
                ))}
              </div>
            </div>
          )}

          {saved.length > 0 && (
            <>
              <p className="mb-1 border-t border-border px-3 pb-1 pt-4 text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Saved collections
              </p>
              {saved.map((collection) => {
                const Icon = COLLECTION_ICONS[collection.icon]
                return (
                  <NavLink
                    key={collection.id}
                    to={`/collections/${collection.id}`}
                    className={({ isActive }) =>
                      cn(
                        LINK_CLS,
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )
                    }
                  >
                    <Icon className="h-[1.125rem] w-[1.125rem]" aria-hidden />
                    <span className="truncate">{collection.name}</span>
                  </NavLink>
                )
              })}
            </>
          )}
        </nav>

        {/* Footer */}
        <div className="safe-bottom space-y-2 border-t border-border bg-surface-sunken/45 px-3 py-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-1">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary font-display font-semibold text-secondary-foreground">
              {profile?.displayName?.slice(0, 1).toUpperCase() ?? '—'}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-foreground">{profile?.displayName ?? 'Local preview'}</span>
              <span className="block text-[0.6875rem] capitalize text-muted-foreground">{profile?.role ?? 'Loading profile'}</span>
            </span>
            <ThemeToggle />
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={signOut}>
            <LogOut aria-hidden />
            Sign out
          </Button>
        </div>
      </aside>
    </>
  )
}
