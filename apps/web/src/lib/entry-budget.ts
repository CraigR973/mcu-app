/**
 * The entry chunk's budget — AG10 (UX54-05, #393).
 *
 * The first open downloads one script before Home can draw: the entry chunk (React, the router,
 * zod, Sentry and the app shell; every page, the assistant, the charts and the scanner are their
 * own chunks, loaded when first used). The owner chose to cap it at about its size on 20 Nov
 * ("Just cap it") rather than move anything out of it, so the build fails if it grows past this
 * budget instead of growing unnoticed. Raising the budget is a decision, not a fix.
 *
 * Measured 20 Nov at `32cc3ce`: 756,905 bytes, 230,768 gzipped. The budget leaves 3–4%.
 */
export const ENTRY_BUDGET = {
  /** Bytes of minified script. */
  raw: 780_000,
  /** Bytes after gzip at level 9, the size a phone fetches (near enough: Vercel may send brotli). */
  gzip: 240_000,
} as const

export interface BuiltChunk {
  fileName: string
  isEntry: boolean
  raw: number
  gzip: number
}

/** Why the build must fail, or `null` when every entry chunk is inside the budget. */
export function entryBudgetBreach(
  chunks: readonly BuiltChunk[],
  budget: { raw: number; gzip: number } = ENTRY_BUDGET,
): string | null {
  const entries = chunks.filter((chunk) => chunk.isEntry)
  if (entries.length === 0) return 'The build has no entry chunk to hold to its budget.'
  const over = entries.filter((chunk) => chunk.raw > budget.raw || chunk.gzip > budget.gzip)
  if (over.length === 0) return null
  return over
    .map(
      (chunk) =>
        `The entry chunk ${chunk.fileName} is ${chunk.raw.toLocaleString('en-GB')} bytes ` +
        `(${chunk.gzip.toLocaleString('en-GB')} gzipped); its budget is ` +
        `${budget.raw.toLocaleString('en-GB')} (${budget.gzip.toLocaleString('en-GB')} gzipped). ` +
        'Load the new code with the page that needs it, or raise the budget as a decision.',
    )
    .join('\n')
}
