import { createContext, useContext, useEffect } from 'react'

/**
 * What the current page tells the shell about itself — Batch T3, `DECISIONS.md` #201.
 *
 * On a phone the page's title lives in the top bar, not in a block above the content, so
 * the page has to tell the shell what it is called. `PageHeader` does it for every page
 * that has one; a page without one falls back to its route's name (`titleForPath`). The
 * provider is `PageChromeProvider`.
 */
export interface PageChrome {
  title: string | null
  setTitle: (title: string | null) => void
}

export const PageChromeContext = createContext<PageChrome | null>(null)

/** The title the current page has announced, if it has. */
export function usePageChromeTitle(): string | null {
  return useContext(PageChromeContext)?.title ?? null
}

/** Announce this page's title to the shell for as long as the page is mounted. Outside a
 *  shell — a test, a public page — it does nothing. */
export function usePageTitle(title: string | null): void {
  const setTitle = useContext(PageChromeContext)?.setTitle
  useEffect(() => {
    if (!setTitle) return
    setTitle(title)
    return () => setTitle(null)
  }, [setTitle, title])
}
