import { writeFileSync } from 'node:fs'
import { test } from '../support/test.ts'

const ROUTES = (process.env.EXPLORE ?? '/dashboard').split(',')
const WHO = (process.env.WHO ?? 'Craig') as 'Craig' | 'Mark'

test('explore', async ({ signedIn }) => {
  const { page } = await signedIn(WHO)
  for (const route of ROUTES) {
    await page.goto(route)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(800)
    const snap = await page.locator('main').ariaSnapshot()
    writeFileSync(`/private/tmp/claude-501/-Users-craigrobinson-mcu-app/252d5c3f-afe6-434a-88f7-1e768c127e40/scratchpad/explore${route.replace(/[^a-z0-9]/gi, '_')}.txt`, snap)
  }
})
