import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { COLLECTION_ICONS } from '@/components/collections/icons'
import { fetchSmartCollections } from '@/lib/api'
import { useAuth } from '@/context/auth'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { navItems, adminNavItems } from '@/lib/nav-items'
import { cn } from '@/lib/utils'

interface Props {
  open: boolean
  onClose: () => void
}

const LINK_CLS =
  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors'

export default function Sidebar({ open, onClose }: Props) {
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

  return (
    <>
      {/* Backdrop (mobile) */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-card border-r border-border transition-transform duration-200',
          'lg:relative lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-border">
          <span className="font-bold text-foreground tracking-tight">The Real MCU</span>
          <button className="lg:hidden text-muted-foreground hover:text-foreground" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2">
          {navItems.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}

          {profile?.role === 'admin' &&
            adminNavItems.map(({ label, path, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}

          {saved.length > 0 && (
            <>
              <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Collections
              </p>
              {saved.map((collection) => {
                const Icon = COLLECTION_ICONS[collection.icon]
                return (
                  <NavLink
                    key={collection.id}
                    to={`/collections/${collection.id}`}
                    onClick={onClose}
                    className={({ isActive }) =>
                      cn(
                        LINK_CLS,
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )
                    }
                  >
                    <Icon size={16} />
                    <span className="truncate">{collection.name}</span>
                  </NavLink>
                )
              })}
            </>
          )}
        </nav>

        {/* Footer */}
        <div className="border-t border-border px-4 py-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground truncate max-w-[140px]">{profile?.displayName}</span>
            <ThemeToggle />
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </aside>
    </>
  )
}
