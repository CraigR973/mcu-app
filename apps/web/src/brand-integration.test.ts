import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const sourceRoot = fileURLToPath(new URL('./', import.meta.url))
const repoRoot = fileURLToPath(new URL('../../../', import.meta.url))

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

  it('keeps photographic heroes out of Vercel public assets and puts the banner only on Home', () => {
    expect(existsSync(join(repoRoot, 'apps/web/public/brand/hero-photo-five-v3.png'))).toBe(false)
    expect(existsSync(join(repoRoot, 'apps/web/public/brand/hero-photo-v3.png'))).toBe(false)
    expect(sources.filter(({ source }) => source.includes('<PrivateHero')).map(({ path }) => path)).toEqual([
      'pages/DashboardPage.tsx',
    ])
  })

  it('uses the rights-independent social card at its native dimensions', () => {
    const html = readFileSync(fileURLToPath(new URL('../index.html', import.meta.url)), 'utf8')

    expect(html).toContain('<meta property="og:image" content="/brand/social-card-1200x630.png" />')
    expect(html).toContain('<meta property="og:image:width" content="1200" />')
    expect(html).toContain('<meta property="og:image:height" content="630" />')
    expect(html).toContain('<meta name="twitter:image" content="/brand/social-card-1200x630.png" />')
  })
})

/**
 * The brand files in git — Batch U3, `DECISIONS.md` #221, Craig's pick B on
 * `OWNER-ACTIONS.md` 15. `docs/brand/` has been in git since 10 Sep, third-party stills,
 * posters and photographs included. From U3 those are untracked and ignored, and stay on
 * disk; history before U3 still holds them. These tests read the repository itself, so a
 * still forced in past `.gitignore` fails the gate rather than reaching the next commit.
 */
describe('brand files in git', () => {
  const tracked = execFileSync('git', ['-C', repoRoot, 'ls-files', '-z', '--', 'docs/brand'], { encoding: 'utf8' })
    .split('\0')
    .filter(Boolean)

  const isIgnored = (path: string) =>
    spawnSync('git', ['-C', repoRoot, 'check-ignore', '-q', '--no-index', path]).status === 0

  it('tracks none of the third-party images', () => {
    expect(tracked.length).toBeGreaterThan(100)
    const thirdParty = tracked.filter(
      (path) =>
        path.startsWith('docs/brand/source-images/') ||
        /^docs\/brand\/logo-system\/concepts\/[^/]+\/sources\//.test(path) ||
        path.endsWith('/poster-source-grid.png') ||
        /\.jpe?g$/i.test(path),
    )
    expect(thirdParty).toEqual([])
  })

  it('ignores their folders, so a new still cannot be added by accident', () => {
    for (const path of [
      'docs/brand/source-images/photo-logo-v3/a-new-still.jpg',
      'docs/brand/logo-system/concepts/catalogue-frame-v2/sources/a-new-poster.png',
      'docs/brand/logo-system/concepts/a-new-concept/sources/a-new-poster.png',
      'docs/brand/logo-system/concepts/catalogue-frame-v2/poster-source-grid.png',
      'docs/brand/logo-system/stack-family/a-photograph.jpeg',
    ]) {
      expect(isIgnored(path), path).toBe(true)
    }
    expect(isIgnored('docs/brand/logo-system/stack-family/stack-mark.svg')).toBe(false)
  })

  it('still tracks the generator and every master it reads', () => {
    for (const path of [
      'docs/brand/logo-system/build_stack_identity.cjs',
      'docs/brand/logo-system/wordmark-dark.svg',
      'docs/brand/logo-system/concepts/poster-stack-v2/poster-stack-concept-art-v1.png',
      'docs/brand/logo-system/concepts/poster-stack-v2/poster-stack-actual-posters-v1.png',
      'docs/brand/logo-system/stack-family/README.md',
    ]) {
      expect(tracked, path).toContain(path)
    }
  })

  // `scripts/brand-sync.mjs --check`, as a gate: CI's clone has had the design system since
  // 10 Sep. It covers the four photographic files 9167430 shipped outside the script's list.
  it('ships only files that are, byte for byte, their tracked design-system source', () => {
    const shipped = join(repoRoot, 'apps/web/public/brand')
    const names = readdirSync(shipped).filter((name) => !name.startsWith('.'))
    expect(names.length).toBeGreaterThan(0)
    for (const name of names) {
      const origin = [`docs/brand/logo-system/stack-family/${name}`, `docs/brand/logo-system/${name}`].find((path) =>
        tracked.includes(path),
      )
      expect(origin, name).toBeDefined()
      expect(readFileSync(join(shipped, name)).equals(readFileSync(join(repoRoot, origin as string))), name).toBe(true)
    }
  })
})
