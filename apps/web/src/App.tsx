import { lazy, Suspense, useEffect } from 'react'
import { Link, Navigate, Routes, Route, useLocation } from 'react-router-dom'
import { ThemeProvider } from '@/context/theme'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './components/layouts/AppLayout'
import ErrorBoundary from './components/ErrorBoundary'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { BrandMark } from '@/components/brand/BrandMark'
import { adminNavItems, navItems, titleForPath } from '@/lib/nav-items'

const HomePage = lazy(() => import('./pages/HomePage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const UnauthorizedPage = lazy(() => import('./pages/UnauthorizedPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const MoviesPage = lazy(() => import('./pages/MoviesPage'))
const MovieDetailPage = lazy(() => import('./pages/MovieDetailPage'))
const ExternalFilmPage = lazy(() => import('./pages/ExternalFilmPage'))
const YouPage = lazy(() => import('./pages/YouPage'))
const WatchlistPage = lazy(() => import('./pages/WatchlistPage'))
const AddToCollectionPage = lazy(() => import('./pages/AddToCollectionPage'))
const TrashPage = lazy(() => import('./pages/TrashPage'))
const OfflinePage = lazy(() => import('./pages/OfflinePage'))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'))
const BoxSetsPage = lazy(() => import('./pages/BoxSetsPage'))
const BoxSetDetailPage = lazy(() => import('./pages/BoxSetDetailPage'))
const CollectionsPage = lazy(() => import('./pages/CollectionsPage'))
const CollectionResultsPage = lazy(() => import('./pages/CollectionResultsPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const LoansPage = lazy(() => import('./pages/LoansPage'))
const AuditPage = lazy(() => import('./pages/AuditPage'))
const ReleasesPage = lazy(() => import('./pages/ReleasesPage'))
const WantedPage = lazy(() => import('./pages/WantedPage'))
const DealsPage = lazy(() => import('./pages/DealsPage'))
const RetailersPage = lazy(() => import('./pages/RetailersPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const ExportPage = lazy(() => import('./pages/ExportPage'))
const SpecsPage = lazy(() => import('./pages/SpecsPage'))
const IdentifyFilmsPage = lazy(() => import('./pages/IdentifyFilmsPage'))
const PriceAlertsPage = lazy(() => import('./pages/PriceAlertsPage'))
const AiChatPage = lazy(() => import('./pages/AiChatPage'))
const MovieNightPage = lazy(() => import('./pages/MovieNightPage'))
const MovieNightJoinPage = lazy(() =>
  import('./pages/MovieNightPage').then((module) => ({ default: module.MovieNightJoinPage })),
)
const MovieNightSessionPage = lazy(() => import('./pages/MovieNightSessionPage'))

function AdminPage() {
  return (
    <div className="page-shell">
      <PageHeader eyebrow="Craig’s tools" title="Administration" description="Collection maintenance, audit and private sharing controls in one place." />
      <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 xl:grid-cols-3">
        {adminNavItems.filter((item) => item.path !== '/admin').map(({ label, path, icon: Icon }) => (
          <Link key={path} to={path} className="group flex min-h-32 flex-col justify-between bg-card p-5 transition-colors hover:bg-muted">
            <Icon className="h-5 w-5 text-primary" aria-hidden />
            <span><span className="block font-display text-lg font-semibold text-foreground">{label}</span><span className="mt-1 block text-xs text-muted-foreground">Open {label.toLowerCase()}</span></span>
          </Link>
        ))}
      </div>
    </div>
  )
}

function DebugPage() {
  return (
    <main className="page-shell-narrow space-y-4">
      <PageHeader eyebrow="Diagnostics" title="Debug tools" description="A deliberate error trigger used to verify the application error boundary." />
      <button
        className="min-h-11 rounded-md bg-destructive px-4 py-2 font-semibold text-destructive-foreground hover:opacity-90"
        onClick={() => { throw new Error('This is your first error!') }}
      >
        Break the world
      </button>
    </main>
  )
}

/** The blank moment before a lazy route arrives — the cinematic first impression. */
function PageLoader() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-6 bg-background px-4">
      <BrandMark size={64} label="Mark's Cinematic Universe" />
      <StatePanel tone="loading" title="Opening the archive" className="w-full max-w-md" />
    </div>
  )
}

/** One owner for the tab title. `AppLayout` used to set it too, which meant the
 *  shell and the router could disagree — 'Film archive' against 'Page not found' —
 *  and the archive root rendered its own name twice. */
const APP_NAME = 'The Real MCU'

function RouteTitle() {
  const { pathname } = useLocation()
  useEffect(() => {
    const publicTitles: Record<string, string> = {
      '/': APP_NAME,
      '/login': 'Sign in',
      '/welcome': 'Welcome',
      '/unauthorized': 'Access denied',
      '/offline': 'Offline',
      '/debug': 'Debug tools',
    }
    const item = [...navItems, ...adminNavItems]
      .filter(({ path }) => pathname === path || pathname.startsWith(`${path}/`))
      .sort((a, b) => b.path.length - a.path.length)[0]
    // Batch T2 and T3. Routes with no menu entry of their own — the film card, the "You"
    // page — take the name the phone's top bar gives them.
    const title = publicTitles[pathname] ?? item?.label ?? titleForPath(pathname) ?? 'Page not found'
    document.title = title === APP_NAME ? APP_NAME : `${title} · ${APP_NAME}`
  }, [pathname])
  return null
}

function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
  )
}

/** Batch 7's write surface is admin-only end to end — the API refuses a viewer with a
 *  403, and routing them away is how they find that out without hitting an error page. */
function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="admin">
      <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <RouteTitle />
      <ErrorBoundary>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />
            <Route path="/debug" element={<DebugPage />} />
            {/* Public: it has to render when the API is unreachable, and requiring a
                session check would be the one thing guaranteed to fail offline. */}
            <Route path="/offline" element={<OfflinePage />} />
            {/* Protected routes — all wrapped in AppLayout sidebar */}
            {/* Protected, but outside AppShell: the wizard is the full screen, and it
                must not be gated by the very flag it exists to set. */}
            <Route
              path="/welcome"
              element={<ProtectedRoute><OnboardingPage /></ProtectedRoute>}
            />
            <Route
              path="/movies"
              element={<AppShell><MoviesPage /></AppShell>}
            />
            <Route
              path="/movies/:id"
              element={<AppShell><MovieDetailPage /></AppShell>}
            />
            {/* Batch T3. Everything the phone's five bottom tabs do not carry. */}
            <Route
              path="/you"
              element={<AppShell><YouPage /></AppShell>}
            />
            {/* Batch T8a. Each person's own eBay price alerts. */}
            <Route
              path="/price-alerts"
              element={<AppShell><PriceAlertsPage /></AppShell>}
            />
            {/* Batch T2. A film the collection does not hold, reached from search. */}
            <Route
              path="/films/tmdb/:tmdbId"
              element={<AppShell><ExternalFilmPage /></AppShell>}
            />
            <Route
              path="/watchlist"
              element={<AppShell><WatchlistPage /></AppShell>}
            />
            {/* Batch 12. Box sets are readable by either person and written by an
                admin, so the route is the ordinary shell and the page hides its own
                write controls — matching what the API enforces. Smart collections are
                private to whoever made them, so there is nothing role-shaped here. */}
            <Route
              path="/box-sets"
              element={<AppShell><BoxSetsPage /></AppShell>}
            />
            <Route
              path="/box-sets/:id"
              element={<AppShell><BoxSetDetailPage /></AppShell>}
            />
            <Route
              path="/collections"
              element={<AppShell><CollectionsPage /></AppShell>}
            />
            <Route
              path="/collections/:id"
              element={<AppShell><CollectionResultsPage /></AppShell>}
            />
            <Route
              path="/wanted"
              element={<AppShell><WantedPage /></AppShell>}
            />
            <Route
              path="/deals"
              element={<AppShell><DealsPage /></AppShell>}
            />
            {/* Batch S6, snag 2. Calendar and Coming soon are one screen: both answered
                "what is coming out", from two sources. `/discover` redirects rather than
                404s, for the same reason `/stats` does — it is in history, in the command
                palette's index, and in whatever links exist outside the app. */}
            <Route
              path="/calendar"
              element={<AppShell><ReleasesPage /></AppShell>}
            />
            <Route path="/discover" element={<Navigate to="/calendar" replace />} />
            {/* Batch S3. Home, Stats and Insights are one reading page. The two old
                paths **redirect rather than 404**: both are in browser history, in the
                command palette's index, and in whatever links exist outside the app —
                and a 404 for a page that still exists under another name is the worst
                of the three possible answers. */}
            <Route path="/stats" element={<Navigate to="/dashboard" replace />} />
            <Route path="/insights" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="/dashboard"
              element={<AppShell><DashboardPage /></AppShell>}
            />
            {/* Batch S4 (`DECISIONS.md` #155). **The ordinary shell, not the admin one.**
                `profiles` holds exactly two rows and there is no public sign-up, so "only
                Mark and Craig" already described every page; what Craig wanted was for
                Mark to be able to add a disc. Every endpoint behind this page moved in the
                same commit — a route guard that opens onto an API that still refuses is
                worse than leaving it shut. */}
            <Route
              path="/collection/add"
              element={<AppShell><AddToCollectionPage /></AppShell>}
            />
            {/* Loans are readable by both — knowing where a disc went is not an
                admin question, even though lending one is. §6.5 marks GET /loans "Any". */}
            <Route
              path="/loans"
              element={<AppShell><LoansPage /></AppShell>}
            />
            <Route
              path="/trash"
              element={<AdminShell><TrashPage /></AdminShell>}
            />
            <Route
              path="/audit"
              element={<AdminShell><AuditPage /></AdminShell>}
            />
            <Route
              path="/retailers"
              element={<AdminShell><RetailersPage /></AdminShell>}
            />
            {/* Batch S3. Moved off the foot of Stats — it is a maintenance action, and
                Stats is a section of Home now rather than a page it could sit under. */}
            <Route
              path="/export"
              element={<AdminShell><ExportPage /></AdminShell>}
            />
            {/* Batch T7. Admin-only, like the API behind it. */}
            <Route
              path="/specs"
              element={<AdminShell><SpecsPage /></AdminShell>}
            />
            {/* Batch T9. Admin-only, like the API behind it. */}
            <Route
              path="/identify"
              element={<AdminShell><IdentifyFilmsPage /></AdminShell>}
            />
            {/* Batch S3. Notifications and AI settings are one page with two tabs.
                Both belong to whoever is signed in — each person has their own devices
                and their own spend cap — so this is the ordinary shell, not the admin
                one. The three old paths redirect, each onto its own tab. */}
            <Route
              path="/settings"
              element={<AppShell><SettingsPage /></AppShell>}
            />
            <Route path="/settings/notifications" element={<Navigate to="/settings" replace />} />
            <Route path="/notifications" element={<Navigate to="/settings" replace />} />
            <Route path="/settings/ai" element={<Navigate to="/settings?tab=assistant" replace />} />
            {/* Batch 31. The chat is a real route rather than an overlay, so a
                conversation can be linked to, returned to, and left open. */}
            <Route
              path="/assistant"
              element={<AppShell><AiChatPage /></AppShell>}
            />
            {/* Batch 35. Both people vote, so none of these is admin-gated — a movie
                night where one of them may not swipe is not one. */}
            <Route
              path="/movie-night"
              element={<AppShell><MovieNightPage /></AppShell>}
            />
            <Route
              path="/movie-night/join/:token"
              element={<AppShell><MovieNightJoinPage /></AppShell>}
            />
            <Route
              path="/movie-night/:id"
              element={<AppShell><MovieNightSessionPage /></AppShell>}
            />
            <Route
              path="/admin"
              element={<AdminShell><AdminPage /></AdminShell>}
            />

            {/* 404 */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </ThemeProvider>
  )
}
