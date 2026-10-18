// @vitest-environment happy-dom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { DataSources } from './DataSources'

afterEach(cleanup)

describe('DataSources — Batch X12c (DS44-06, CT46-06)', () => {
  it("shows TMDB's logo and its 'not endorsed' notice", () => {
    render(<DataSources />)

    const logo = screen.getByAltText('TMDB')
    expect(logo.getAttribute('src')).toBe('/third-party/tmdb.svg')
    expect(
      screen.getByText(/This product uses the TMDB API but is not endorsed or certified by TMDB/),
    ).not.toBeNull()
    expect(screen.getByRole('link', { name: 'themoviedb.org' }).getAttribute('href')).toBe(
      'https://www.themoviedb.org',
    )
  })

  it('credits JustWatch for where-to-watch data', () => {
    render(<DataSources />)

    expect(screen.getByRole('link', { name: 'JustWatch' }).getAttribute('href')).toBe(
      'https://www.justwatch.com',
    )
    expect(screen.getByText(/Where-to-watch data is provided by/)).not.toBeNull()
  })
})
