import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const sourceRoot = fileURLToPath(new URL('./', import.meta.url))

function tsxSources(directory: string): { path: string; source: string }[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = `${directory}/${entry.name}`
    if (entry.isDirectory()) return tsxSources(path)
    if (!entry.name.endsWith('.tsx')) return []
    return [{ path: path.slice(sourceRoot.length).replace(/^\/+/, ''), source: readFileSync(path, 'utf8') }]
  })
}

describe('brand integration hierarchy', () => {
  const sources = tsxSources(sourceRoot)

  it('reserves the personalised photographic edition for the onboarding reveal', () => {
    const uses = sources
      .filter(({ source }) => source.includes('/brand/personalised-poster-'))
      .map(({ path }) => path)

    expect(uses).toEqual(['pages/OnboardingPage.tsx'])
  })

  it('does not use photographic hero artwork as interface chrome', () => {
    const uses = sources
      .filter(({ source }) => source.includes('/brand/hero-photo'))
      .map(({ path }) => path)

    expect(uses).toEqual([])
  })

  it('uses the rights-independent social card at its native dimensions', () => {
    const html = readFileSync(fileURLToPath(new URL('../index.html', import.meta.url)), 'utf8')

    expect(html).toContain('<meta property="og:image" content="/brand/social-card-1200x630.png" />')
    expect(html).toContain('<meta property="og:image:width" content="1200" />')
    expect(html).toContain('<meta property="og:image:height" content="630" />')
    expect(html).toContain('<meta name="twitter:image" content="/brand/social-card-1200x630.png" />')
  })
})
