// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/**
 * `/debug` in a development build — Batch U3, `DECISIONS.md` #221. Tests run as one
 * (`import.meta.env.DEV` is true under vitest). That a production build has neither the
 * route nor the page is `production-build.test.ts`'s to prove.
 */
describe('/debug, in development', () => {
  it('is a page, with its own title', async () => {
    expect(import.meta.env.DEV).toBe(true)
    renderAt('/debug')

    expect(screen.getByRole('button', { name: 'Break the world' })).not.toBeNull()
    await waitFor(() => expect(document.title).toBe('Debug tools · The Real MCU'))
  })

  it('still throws its test error when its button is pressed', () => {
    // An error thrown by a click handler is not React's to catch: it goes to the window as
    // an uncaught error, which is where Sentry's global handler reports it from.
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const thrown: string[] = []
    const onError = (event: ErrorEvent) => {
      thrown.push(event.error instanceof Error ? event.error.message : event.message)
      event.preventDefault()
    }
    window.addEventListener('error', onError)
    renderAt('/debug')

    try {
      fireEvent.click(screen.getByRole('button', { name: 'Break the world' }))
    } catch (error) {
      thrown.push(error instanceof Error ? error.message : String(error))
    } finally {
      window.removeEventListener('error', onError)
    }

    expect(thrown).toContain('This is your first error!')
  })
})

/**
 * The privacy policy — Batch T8b, `DECISIONS.md` #227. eBay links to it from its sign-in
 * page, where the reader is not signed in here, so it is public and has its own title.
 */
describe('/privacy', () => {
  it('opens without signing in, with its own title', async () => {
    renderAt('/privacy')

    expect(await screen.findByRole('heading', { level: 1, name: 'Privacy' })).not.toBeNull()
    await waitFor(() => expect(document.title).toBe('Privacy · The Real MCU'))
  })
})
