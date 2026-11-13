/**
 * Back keeps your place — AF4 (#372, snag 4).
 *
 * The app scrolls inside its own panel (`#main-content`), not the browser window, so the browser's
 * own restore never applies, and the panel is reused from page to page. This remembers where each
 * scroll region was for each step in history and puts it back on Back and Forward.
 *
 * A region is any element marked `data-scroll-memory="<name>"`: the app's panel, and the Archive's
 * grid and list, which scroll in a box of their own. Positions are written as the reader scrolls,
 * so the last one is never lost to a page that has already been replaced, and they last for the
 * browser session.
 */

const STORE = 'mcu-scroll-memory'
/** How long a restore waits for the page to be tall enough: data from the cache is drawn at
 *  once, a lazy page or a slow read later. */
export const RESTORE_FOR_MS = 2500
/** How long a place, once reached, is held: a component that sets its own scroll as it mounts
 *  (the Archive's virtual grid starts at the top) is put right on the next frame. */
const HOLD_FOR_MS = 400
/** Steps kept: enough for any real walk back, small enough for the session store. */
const KEPT = 60

type Positions = Record<string, number>
const memory = new Map<string, Positions>()

function load(): void {
  try {
    const saved = sessionStorage.getItem(STORE)
    if (!saved) return
    for (const [key, positions] of JSON.parse(saved) as [string, Positions][]) memory.set(key, positions)
  } catch {
    // A private window or blocked storage: memory alone still covers this visit.
  }
}

let loaded = false
let persistTimer: number | undefined

function persist(): void {
  if (persistTimer !== undefined) return
  persistTimer = window.setTimeout(() => {
    persistTimer = undefined
    try {
      sessionStorage.setItem(STORE, JSON.stringify([...memory].slice(-KEPT)))
    } catch {
      // Not kept past a reload; still kept for this visit.
    }
  }, 250)
}

export function remembered(key: string): Positions | undefined {
  if (!loaded) {
    loaded = true
    load()
  }
  return memory.get(key)
}

/**
 * While a panel stands in for its page (a completion set opened on Home or on the list of sets),
 * the page's own place is what history keeps for it, not the panel's: Back to it later finds the
 * page where the reader left it.
 */
let held: number | null = null
export function holdPlace(top: number | null): void {
  held = top
}

export function remember(key: string, region: string, top: number): void {
  if (!loaded) {
    loaded = true
    load()
  }
  const positions = memory.get(key) ?? {}
  positions[region] = region === 'main' && held !== null ? held : top
  // Most recent last, so the oldest steps are the ones let go.
  memory.delete(key)
  memory.set(key, positions)
  while (memory.size > KEPT) memory.delete(memory.keys().next().value as string)
  persist()
}

/** A step whose places no longer apply. */
export function forget(key: string): void {
  if (!loaded) {
    loaded = true
    load()
  }
  memory.delete(key)
  persist()
}

export function regions(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>('[data-scroll-memory]')]
}

/**
 * Put each remembered region back, frame by frame until its page is tall enough or the time is
 * up, then hold it there briefly, and never against the reader: any wheel, touch or key stops it.
 * A region that cannot reach its old place lands as far down as it can.
 */
export function restore(positions: Positions): () => void {
  const started = performance.now()
  let frame = 0
  let stopped = false
  const stop = () => {
    stopped = true
    cancelAnimationFrame(frame)
    for (const type of ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const) window.removeEventListener(type, stop, true)
  }
  for (const type of ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const) window.addEventListener(type, stop, { capture: true, passive: true })
  const pending = new Map(Object.entries(positions))
  const reached = new Map<string, number>()
  const step = () => {
    if (stopped) return
    const now = performance.now()
    for (const [region, top] of pending) {
      const element = document.querySelector<HTMLElement>(`[data-scroll-memory="${region}"]`)
      if (!element) continue
      const reach = element.scrollHeight - element.clientHeight
      if (Math.abs(element.scrollTop - Math.min(top, reach)) > 1) element.scrollTop = Math.min(top, reach)
      if (reach < top - 1) continue
      const at = reached.get(region) ?? now
      reached.set(region, at)
      if (now - at >= HOLD_FOR_MS) pending.delete(region)
    }
    if (pending.size === 0 || now - started > RESTORE_FOR_MS) {
      stop()
      return
    }
    frame = requestAnimationFrame(step)
  }
  step()
  return stop
}

/** A link to a heading (`/identify#identify-doubts-heading`) opens at it once it is drawn. */
export function scrollToHeading(id: string): () => void {
  const started = performance.now()
  let frame = 0
  const step = () => {
    const target = document.getElementById(decodeURIComponent(id))
    if (target) {
      target.scrollIntoView({ block: 'start' })
      return
    }
    if (performance.now() - started > RESTORE_FOR_MS) return
    frame = requestAnimationFrame(step)
  }
  step()
  return () => cancelAnimationFrame(frame)
}

/** The app's own scrolling panel, where every page but the Archive's views scrolls. */
export function mainPanel(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-scroll-memory="main"]')
}
