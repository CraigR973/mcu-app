// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// A fresh module for each case: the memory is the module's own, as it is the page's.
let remember: typeof import('./scroll-memory').remember
let remembered: typeof import('./scroll-memory').remembered
let restore: typeof import('./scroll-memory').restore

/** happy-dom lays nothing out, so a region's heights are given. */
function region(name: string, scrollHeight: number, clientHeight = 800): HTMLElement {
  const element = document.createElement('div')
  element.dataset.scrollMemory = name
  Object.defineProperty(element, 'scrollHeight', { configurable: true, get: () => scrollHeight })
  Object.defineProperty(element, 'clientHeight', { configurable: true, get: () => clientHeight })
  let top = 0
  // Clamped as a browser clamps it, to however tall the region is now.
  Object.defineProperty(element, 'scrollTop', { configurable: true, get: () => top, set: (value: number) => { top = Math.max(0, Math.min(value, element.scrollHeight - element.clientHeight)) } })
  document.body.append(element)
  return element
}

beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance', 'setTimeout', 'clearTimeout'] })
  vi.resetModules()
  ;({ remember, remembered, restore } = await import('./scroll-memory'))
})
afterEach(() => {
  vi.useRealTimers()
  document.body.innerHTML = ''
  sessionStorage.clear()
})

describe('scroll memory — AF4 (#372)', () => {
  it('remembers each region’s place per step in history', () => {
    remember('step-1', 'main', 1200)
    remember('step-1', 'archive-grid', 3400)
    remember('step-2', 'main', 0)
    expect(remembered('step-1')).toEqual({ main: 1200, 'archive-grid': 3400 })
    expect(remembered('step-2')).toEqual({ main: 0 })
    expect(remembered('step-3')).toBeUndefined()
  })

  it('keeps the places past a reload, in the session', () => {
    remember('step-9', 'main', 640)
    vi.advanceTimersByTime(300)
    expect(sessionStorage.getItem('mcu-scroll-memory')).toContain('step-9')
  })

  it('puts a region back at once when its page is already tall enough', () => {
    const main = region('main', 5000)
    restore({ main: 1200 })
    expect(main.scrollTop).toBe(1200)
  })

  it('waits for a page still arriving, frame by frame, then lands on the place', () => {
    let height = 900
    const main = region('main', 0)
    Object.defineProperty(main, 'scrollHeight', { configurable: true, get: () => height })
    restore({ main: 2000 })
    expect(main.scrollTop).toBe(100)
    height = 4000
    vi.advanceTimersToNextFrame()
    expect(main.scrollTop).toBe(2000)
  })

  it('puts a place back that the region’s own component moved as it mounted, as the Archive’s grid does', () => {
    const grid = region('archive-grid', 6000)
    restore({ 'archive-grid': 1500 })
    expect(grid.scrollTop).toBe(1500)
    // The virtual grid starts itself at the top, right after.
    grid.scrollTop = 0
    vi.advanceTimersToNextFrame()
    expect(grid.scrollTop).toBe(1500)
  })

  it('leaves alone the small moves the grid makes to keep the same films in view', () => {
    const grid = region('archive-grid', 6000)
    restore({ 'archive-grid': 1400 })
    // The grid measures the rows above and moves 45 px to keep the same films where they were.
    grid.scrollTop = 1445
    vi.advanceTimersToNextFrame()
    expect(grid.scrollTop).toBe(1445)
  })

  it('waits for a region not drawn yet, such as the Archive’s grid behind its first read', () => {
    restore({ 'archive-grid': 1500 })
    const grid = region('archive-grid', 6000)
    vi.advanceTimersToNextFrame()
    expect(grid.scrollTop).toBe(1500)
  })

  it('lands as far down as it can on a page that has grown shorter, then stops trying', () => {
    const main = region('main', 1500)
    restore({ main: 4000 })
    expect(main.scrollTop).toBe(700)
    vi.advanceTimersByTime(3000)
    vi.advanceTimersToNextFrame()
    expect(main.scrollTop).toBe(700)
  })

  it('never fights the reader: a touch stops it', () => {
    let height = 900
    const main = region('main', 0)
    Object.defineProperty(main, 'scrollHeight', { configurable: true, get: () => height })
    restore({ main: 2000 })
    window.dispatchEvent(new Event('touchstart'))
    height = 4000
    vi.advanceTimersToNextFrame()
    expect(main.scrollTop).toBe(100)
  })
})
