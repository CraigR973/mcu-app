// Runs the suite once per browser, each against a fresh copy of the seeded database, and
// fails if any browser failed. `pnpm --filter @mcu/e2e e2e [chromium firefox webkit] [-- args]`
import { spawnSync } from 'node:child_process'

const known = ['chromium', 'firefox', 'webkit', 'jobs']
const argv = process.argv.slice(2)
const split = argv.indexOf('--')
const named = (split === -1 ? argv : argv.slice(0, split)).filter((a) => known.includes(a))
const extra = split === -1 ? argv.filter((a) => !known.includes(a)) : argv.slice(split + 1)
const browsers = named.length ? named : known

let failed = false
let first = true
for (const browser of browsers) {
  console.log(`\n=== ${browser} ===`)
  const result = spawnSync('pnpm', ['exec', 'playwright', 'test', `--project=${browser}`, `--output=test-results/${browser}`, ...extra], {
    stdio: 'inherit',
    env: {
      ...process.env,
      PLAYWRIGHT_HTML_REPORT: `playwright-report/${browser}`,
      // The bundle is built once, by the first run; the others serve it.
      ...(first ? {} : { E2E_SKIP_BUILD: '1' }),
    },
  })
  first = false
  if (result.status !== 0) failed = true
}
process.exit(failed ? 1 : 0)
