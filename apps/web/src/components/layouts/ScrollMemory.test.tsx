// @vitest-environment happy-dom
import { act, cleanup, render } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { ScrollMemory } from './ScrollMemory'

let go: ReturnType<typeof useNavigate>
function Steer() {
  go = useNavigate()
  return null
}

/** The app's panel, its heights given, since happy-dom lays nothing out. */
function Panel() {
  return (
    <main
      data-scroll-memory="main"
      ref={(element) => {
        if (!element || 'laidOut' in element.dataset) return
        element.dataset.laidOut = ''
        Object.defineProperty(element, 'scrollHeight', { configurable: true, get: () => 6000 })
        Object.defineProperty(element, 'clientHeight', { configurable: true, get: () => 800 })
        let top = 0
        Object.defineProperty(element, 'scrollTop', { configurable: true, get: () => top, set: (value: number) => { top = Math.max(0, Math.min(value, 5200)) } })
      }}
    />
  )
}

function panel(): HTMLElement {
  return document.querySelector<HTMLElement>('[data-scroll-memory="main"]') as HTMLElement
}

/** The reader scrolls: the place, and the event the memory listens for. */
function scrollTo(top: number) {
  panel().scrollTop = top
  panel().dispatchEvent(new Event('scroll'))
}

afterEach(() => {
  cleanup()
  sessionStorage.clear()
})

describe('ScrollMemory — AF4 (#372): Back keeps your place', () => {
  it('opens a new page at the top and puts the last one back on Back', () => {
    render(<MemoryRouter initialEntries={['/movies']}><ScrollMemory /><Steer /><Panel /></MemoryRouter>)
    scrollTo(1800)
    act(() => go('/movies/heat'))
    expect(panel().scrollTop).toBe(0)
    scrollTo(300)
    act(() => go(-1))
    expect(panel().scrollTop).toBe(1800)
    // And Forward puts the film's place back too.
    act(() => go(1))
    expect(panel().scrollTop).toBe(300)
  })

  it('leaves the place alone when a filter replaces the address', () => {
    render(<MemoryRouter initialEntries={['/movie-night/cinema']}><ScrollMemory /><Steer /><Panel /></MemoryRouter>)
    scrollTo(900)
    act(() => go('/movie-night/cinema?run=olderFilm', { replace: true }))
    expect(panel().scrollTop).toBe(900)
  })

  it('opens a link to a heading at the heading', () => {
    let reached = ''
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <ScrollMemory />
        <Steer />
        <Panel />
        <h2 id="identify-doubts-heading" ref={(element) => { if (element) element.scrollIntoView = () => { reached = element.id } }}>Films in doubt</h2>
      </MemoryRouter>,
    )
    act(() => go('/identify#identify-doubts-heading'))
    expect(reached).toBe('identify-doubts-heading')
  })
})

describe('ScrollMemory — a page opened afresh', () => {
  it('does not take the places another page left under history’s first step', () => {
    sessionStorage.setItem('mcu-scroll-memory', JSON.stringify([['default', { main: 1373 }]]))
    render(<MemoryRouter initialEntries={['/dashboard']}><ScrollMemory /><Steer /><Panel /></MemoryRouter>)
    expect(panel().scrollTop).toBe(0)
  })
})
