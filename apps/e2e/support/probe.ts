import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import type { Page } from '@playwright/test'

/** While writing a case: save what the page's main region says to `$E2E_PROBE_DIR`. A no-op
 * when the variable is not set, so a probe left in a case does nothing in CI. */
export async function probe(page: Page, name: string, selector = 'main'): Promise<void> {
  const dir = process.env.E2E_PROBE_DIR
  if (!dir) return
  mkdirSync(dir, { recursive: true })
  writeFileSync(path.join(dir, `${name}.txt`), await page.locator(selector).first().ariaSnapshot())
}
