import './instrument'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import * as Sentry from '@sentry/react'
import { AuthProvider } from './context/auth'
import App from './App'
import './index.css'
import { createQueryClient } from './lib/query-client'
import { registerServiceWorker } from './lib/register-sw'
import { reloadOnceForNewBuild } from './lib/describe-error'
import { applyAppleStandaloneChrome } from './lib/apple-standalone-chrome'

const queryClient = createQueryClient()

// Batch X8 (UX48-03): a deploy removed a chunk this page still asks for. Vite raises this when
// a dynamic import fails; a reload fetches the new build. Once only (see the helper); after
// that the screen says it needs the newest version.
window.addEventListener('vite:preloadError', (event) => {
  if (reloadOnceForNewBuild()) event.preventDefault()
})

applyAppleStandaloneChrome()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<p className="p-8 text-destructive">Something went wrong.</p>}>
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </QueryClientProvider>
      </BrowserRouter>
    </Sentry.ErrorBoundary>
  </StrictMode>,
)

// After render, so a worker registration can never delay first paint.
registerServiceWorker()
