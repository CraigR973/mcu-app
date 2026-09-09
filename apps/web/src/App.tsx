import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/context/theme'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './components/layouts/AppLayout'
import ErrorBoundary from './components/ErrorBoundary'

const HomePage = lazy(() => import('./pages/HomePage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const UnauthorizedPage = lazy(() => import('./pages/UnauthorizedPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const MoviesPage = lazy(() => import('./pages/MoviesPage'))
const MovieDetailPage = lazy(() => import('./pages/MovieDetailPage'))
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
const InsightsPage = lazy(() => import('./pages/InsightsPage'))
const StatsPage = lazy(() => import('./pages/StatsPage'))
const LoansPage = lazy(() => import('./pages/LoansPage'))
const AuditPage = lazy(() => import('./pages/AuditPage'))
const DiscoverPage = lazy(() => import('./pages/DiscoverPage'))
const CalendarPage = lazy(() => import('./pages/CalendarPage'))

function AdminPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-foreground">Admin</h1>
      <p className="text-muted-foreground mt-1">Admin dashboard — coming soon.</p>
    </div>
  )
}

function DebugPage() {
  return (
    <div className="p-8 space-y-4">
      <h1 className="text-xl font-bold">Debug Tools</h1>
      <button
        className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        onClick={() => { throw new Error('This is your first error!') }}
      >
        Break the world
      </button>
    </div>
  )
}

function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  )
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
              path="/insights"
              element={<AppShell><InsightsPage /></AppShell>}
            />
            <Route
              path="/calendar"
              element={<AppShell><CalendarPage /></AppShell>}
            />
            <Route
              path="/discover"
              element={<AppShell><DiscoverPage /></AppShell>}
            />
            <Route
              path="/stats"
              element={<AppShell><StatsPage /></AppShell>}
            />
            <Route
              path="/dashboard"
              element={<AppShell><DashboardPage /></AppShell>}
            />
            <Route
              path="/collection/add"
              element={<AdminShell><AddToCollectionPage /></AdminShell>}
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
