import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import postcss from 'postcss'
import tailwindcss from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import { describe, expect, it } from 'vitest'

import tailwindConfig from '../../tailwind.config'

/**
 * Every colour class names an opacity step the theme has — Batch V1, `DECISIONS.md` #228.
 *
 * Tailwind 3 builds `bg-background/94` only when 94 is a key of `theme.opacity`, and drops
 * the class without a warning when it is not. That is how the top bar lost its background on
 * 10 Sep (`9afc173`) with every check green: the build, the types, the tests and the lint
 * all passed while twenty classes in ten files were never generated. This file reads the
 * source the way Tailwind does and fails on a step the scale lacks, naming the file and line.
 */

const srcRoot = fileURLToPath(new URL('..', import.meta.url))
const theme = resolveConfig(tailwindConfig).theme

/** Utilities whose `/N` suffix is an opacity step. `text-sm/6` is a line height, which is
 *  why a class counts only when what follows the utility is one of the theme's colours. */
const COLOUR_UTILITIES = [
  'bg', 'text', 'border', 'border-x', 'border-y', 'border-t', 'border-r', 'border-b', 'border-l',
  'ring', 'ring-offset', 'from', 'via', 'to', 'fill', 'stroke', 'divide', 'outline', 'shadow',
  'decoration', 'accent', 'caret', 'placeholder',
]

/** `{ primary: { DEFAULT, foreground } }` → `primary`, `primary-foreground`. */
function colourNames(scale: object, prefix = ''): string[] {
  return Object.entries(scale).flatMap(([key, value]: [string, unknown]) => {
    const name = key === 'DEFAULT' ? prefix.replace(/-$/, '') : `${prefix}${key}`
    return value !== null && typeof value === 'object' ? colourNames(value, `${name}-`) : [name]
  })
}

const COLOURS = new Set([
  ...colourNames(theme.colors),
  ...colourNames(theme.textColor),
  ...colourNames(theme.fill),
])
const STEPS = new Set(Object.keys(theme.opacity))

interface ColourClass {
  className: string
  step: string
  line: number
}

/** The colour classes in one file's text, each with its opacity step. */
export function colourClasses(text: string): ColourClass[] {
  const found: ColourClass[] = []
  text.split('\n').forEach((content, index) => {
    for (const match of content.matchAll(/(?<![\w-])([a-z][a-z0-9-]*)\/(\d+)(?![\w./])/g)) {
      const [, stem, step] = match
      const isColour = COLOUR_UTILITIES.some(
        (utility) => stem.startsWith(`${utility}-`) && COLOURS.has(stem.slice(utility.length + 1)),
      )
      if (isColour) found.push({ className: `${stem}/${step}`, step, line: index + 1 })
    }
  })
  return found
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.tsx?$/.test(entry.name) ? [path] : []
  })
}

// Every file but this one, whose examples below name a missing step on purpose.
const thisFile = fileURLToPath(import.meta.url)
const inSource = sourceFiles(srcRoot)
  .filter((path) => path !== thisFile)
  .flatMap((path) =>
    colourClasses(readFileSync(path, 'utf8')).map((found) => ({ ...found, file: relative(srcRoot, path) })),
  )

/** What Tailwind generates from these class names, with the app's own config. */
async function build(classNames: string[]): Promise<string> {
  const result = await postcss([
    tailwindcss({ ...tailwindConfig, content: [{ raw: classNames.join(' '), extension: 'html' }] }),
  ]).process('@tailwind utilities;', { from: undefined })
  return result.css
}

/** How a class name appears as a selector in the built stylesheet. */
const selector = (className: string) => `.${className.replace('/', '\\/')}`

describe('opacity steps', () => {
  it('reads the classes V1 found dropped, so a pass below means something', () => {
    // Representative retained classes from 30 Sep's reconciliation, one class from each kind.
    const names = new Set(inSource.map(({ className }) => className))
    for (const className of [
      'bg-popover/96',
      'bg-warning/12',
      'bg-quality-4k/14',
      'bg-primary/88',
      'bg-destructive/88',
    ]) {
      expect(names.has(className), className).toBe(true)
    }
  })

  it('catches a step the scale lacks, and only a colour class', () => {
    const found = colourClasses('bg-primary/93 text-sm/6 w-1/2 -translate-y-1/2 top-1/2 hover:bg-primary/10')
    expect(found.map(({ className }) => className)).toEqual(['bg-primary/93', 'bg-primary/10'])
    expect(found.filter(({ step }) => !STEPS.has(step)).map(({ className }) => className)).toEqual(['bg-primary/93'])
  })

  it('names no step the theme lacks, anywhere in apps/web/src', () => {
    const missing = inSource
      .filter(({ step }) => !STEPS.has(step))
      .map(({ file, line, className }) => `${file}:${line} ${className}`)
    expect(missing).toEqual([])
  })

  it('is what Tailwind builds: every colour class in the source is in the stylesheet', async () => {
    const names = [...new Set(inSource.map(({ className }) => className))]
    const css = await build(names)
    expect(names.filter((name) => !css.includes(selector(name)))).toEqual([])
  })

  it('is the fault it guards against: an unknown step is dropped without a word', async () => {
    const css = await build(['bg-primary/93', 'bg-primary/95'])
    expect(css).toContain(selector('bg-primary/95'))
    expect(css).not.toContain(selector('bg-primary/93'))
  })
})
