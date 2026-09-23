import { useMemo, useState, type ReactNode } from 'react'

import { PageChromeContext } from './page-chrome'

/** Holds the title the current page announced — see `page-chrome.ts`. */
export function PageChromeProvider({ children }: { children: ReactNode }) {
  const [title, setTitle] = useState<string | null>(null)
  const value = useMemo(() => ({ title, setTitle }), [title])
  return <PageChromeContext.Provider value={value}>{children}</PageChromeContext.Provider>
}
