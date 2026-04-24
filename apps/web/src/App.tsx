import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/context/theme'
import ProtectedRoute from './components/ProtectedRoute'

const HomePage = lazy(() => import('./pages/HomePage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const SignupPage = lazy(() => import('./pages/SignupPage'))
const UnauthorizedPage = lazy(() => import('./pages/UnauthorizedPage'))

function AdminPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <p className="text-foreground text-xl font-semibold">Admin dashboard (coming soon)</p>
    </div>
  )
}

function ErrorButton() {
  return (
    <button
      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
      onClick={() => {
        throw new Error('This is your first error!')
      }}
    >
      Break the world
    </button>
  )
}

function DebugPage() {
  return (
    <div className="p-8 space-y-4">
      <h1 className="text-xl font-bold">Debug Tools</h1>
      <ErrorButton />
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

export default function App() {
  return (
    <ThemeProvider>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />
          <Route path="/debug" element={<DebugPage />} />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div className="min-h-screen flex items-center justify-center bg-background">
                  <p className="text-foreground text-xl font-semibold">Dashboard (coming soon)</p>
                </div>
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin"
            element={
              <ProtectedRoute role="admin">
                <AdminPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </Suspense>
    </ThemeProvider>
  )
}
