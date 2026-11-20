import { randomUUID } from 'node:crypto'
import { ENTRY_BUDGET } from '../../web/src/lib/entry-budget.ts'
import { expect, test } from '../support/test.ts'

// AG10 (UX54-04, UX54-05, #393). Rows go only into the harness's disposable Postgres and are put
// back afterwards.

/** At least 44 px tall: the box the browser lays out, not a pseudo-element's hit area. */
async function heights(locator: import('@playwright/test').Locator): Promise<number[]> {
  const found: number[] = []
  for (const item of await locator.all()) {
    await item.scrollIntoViewIfNeeded()
    found.push((await item.boundingBox())?.height ?? 0)
  }
  return found
}

const TITANIC = '219a59fc-8a0b-4eeb-ba7c-18b0391eb69f'
const WANTED = '58df19fb-d961-457c-8374-6df550b563cf'
const SHETLAND = 'd90ea74d-8ad3-4864-9070-043c4e358e59'
const ids = `'${TITANIC}','${WANTED}','${SHETLAND}'`

test("AG10 Settings' switches, Needs you's links and its \"Inspect the film and copies\" links are 44 px tall at 375 px", async ({ db, api, signedIn }, testInfo) => {
  const disc = randomUUID(), seriesCopy = randomUUID(), doubt = randomUUID(), want = randomUUID()
  db.sql(`INSERT INTO movies (id,title,year,tmdb_id,media_type) VALUES
    ('${TITANIC}','Titanic',1953,16535,'film'),
    ('${WANTED}','Dead Man''s Shoes',1940,416920,'film'),
    ('${SHETLAND}','Shetland - Series 5',NULL,NULL,'film');
    INSERT INTO collection_items (id,movie_id,formats,condition) VALUES
    ('${disc}','${TITANIC}','["blu_ray"]','good'),('${seriesCopy}','${SHETLAND}','["dvd"]','good');
    INSERT INTO identify_doubts (id,movie_id,collection_item_id,source,status,identified_as,proposed_tmdb_id,note)
    VALUES ('${doubt}','${TITANIC}','${disc}','specs','open',16535,597,'Disc page names 1997');
    INSERT INTO wanted_list (id,movie_id,is_active) VALUES ('${want}','${WANTED}',true)`)
  try {
    const craig = await api('Craig')
    for (const proposal of await craig.get<Record<string, unknown>[]>('/needs-you/reviews/proposals')) {
      await craig.post('/needs-you/reviews', proposal)
    }
    const { page } = await signedIn('Mark')
    await page.setViewportSize({ width: 375, height: 812 })

    await page.goto('/settings/notifications')
    const switches = page.getByRole('switch')
    await expect(switches.first()).toBeVisible()
    const switchHeights = await heights(switches)
    expect(switchHeights.length, 'the notification switches').toBeGreaterThanOrEqual(8)
    for (const height of switchHeights) expect(height).toBeGreaterThanOrEqual(44)
    // The track still draws as a switch, 24 px tall, inside its 44 px button.
    const track = await switches.first().locator('span').first().boundingBox()
    expect(track?.height).toBe(24)
    await page.screenshot({ path: testInfo.outputPath('ag10-settings-375.png') })

    await page.goto('/needs-you')
    const others = page.getByRole('navigation', { name: 'Other Needs you actions' }).getByRole('link')
    await expect(others).toHaveCount(2)
    for (const height of await heights(others)) expect(height).toBeGreaterThanOrEqual(44)
    const inspect = page.getByRole('link', { name: 'Inspect the film and copies' })
    await expect(inspect.first()).toBeVisible()
    const inspectHeights = await heights(inspect)
    expect(inspectHeights.length, 'one link per review whose film exists').toBe(3)
    for (const height of inspectHeights) expect(height).toBeGreaterThanOrEqual(44)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath('ag10-needs-you-375.png'), fullPage: true })
  } finally {
    db.sql(`BEGIN; SET LOCAL app.permanent_delete = 'on';
      DELETE FROM admin_actions WHERE target_table='assigned_reviews' AND target_id IN
      (SELECT id::text FROM assigned_reviews WHERE snapshot->>'movieId' IN (${ids}));
      DELETE FROM assigned_reviews WHERE snapshot->>'movieId' IN (${ids});
      DELETE FROM identify_doubts WHERE movie_id IN (${ids});
      DELETE FROM collection_items WHERE movie_id IN (${ids});
      DELETE FROM wanted_list WHERE movie_id IN (${ids});
      DELETE FROM movies WHERE id IN (${ids}); COMMIT`)
    expect(db.scalar(`SELECT count(*) FROM collection_items WHERE movie_id IN (${ids})`)).toBe('0')
  }
})

/** Lighthouse's mobile profile: 150 ms round trip, 1.6 Mbit/s down, 750 kbit/s up, a CPU four
 *  times slower. Chromium alone can be throttled from here, so the time is held there. */
const PHONE = { latency: 150, downloadThroughput: 1_638_400 / 8, uploadThroughput: 750_000 / 8, cpuSlowdown: 4 }
/** Home drawn at a first open on that profile: 4.9–6.4 s on 20 Nov (the owner's Mac, Chromium). The
 *  harness serves the bundle uncompressed, so this is slower than production, where the entry
 *  script travels gzipped at under a third of its size. The ceiling is for a gross regression (a
 *  waterfall of chunks, a blocking request); the entry chunk's own growth is the budget's. */
const FIRST_OPEN_CEILING_MS = 15_000
/** No script but the entry is this large at a first open: the scanner's decoder (416 kB), the
 *  assistant and the charts load with the screens that use them. */
const LARGEST_OTHER_SCRIPT = 100_000

test('AG10 first open of Home on a throttled phone: the entry script inside its budget, nothing large besides, timed in Chromium', async ({ signedIn, browserName }, testInfo) => {
  for (const person of ['Craig', 'Mark'] as const) {
    // A new context: nothing cached and no service worker, as a first open after a deploy.
    const { context, page } = await signedIn(person)
    await page.setViewportSize({ width: 375, height: 812 })
    if (browserName === 'chromium') {
      const cdp = await context.newCDPSession(page)
      await cdp.send('Network.enable')
      await cdp.send('Network.emulateNetworkConditions', {
        offline: false,
        latency: PHONE.latency,
        downloadThroughput: PHONE.downloadThroughput,
        uploadThroughput: PHONE.uploadThroughput,
      })
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: PHONE.cpuSlowdown })
    }
    const scripts: Promise<[string, number]>[] = []
    page.on('response', (response) => {
      if (response.request().resourceType() !== 'script') return
      const name = new URL(response.url()).pathname
      scripts.push(response.body().then(body => [name, body.length] as [string, number], () => [name, Number(response.headers()['content-length'] ?? 0)] as [string, number]))
    })
    const started = Date.now()
    await page.goto('/dashboard')
    await expect(page.getByRole('list', { name: 'The collection in numbers' })).toBeVisible({ timeout: 45_000 })
    const firstOpenMs = Date.now() - started
    const fetched = await Promise.all(scripts)
    const entry = await page.locator('script[type="module"][src]').first().getAttribute('src')
    const entryBytes = fetched.find(([name]) => name === entry)?.[1] ?? 0
    const others = fetched.filter(([name]) => name !== entry)
    const total = fetched.reduce((sum, [, bytes]) => sum + bytes, 0)
    const note = `${person} ${browserName}: entry ${String(entryBytes)} B, ${String(others.length)} other scripts, ${String(total)} B in all` +
      (browserName === 'chromium' ? `, Home drawn in ${String(firstOpenMs)} ms on the phone profile` : '')
    testInfo.annotations.push({ type: 'AG10 first open', description: note })
    console.log(`AG10-MEASURE ${note}`)

    expect(entryBytes, 'the entry script was fetched and read').toBeGreaterThan(0)
    expect(entryBytes, 'the entry script inside its budget').toBeLessThanOrEqual(ENTRY_BUDGET.raw)
    for (const [name, bytes] of others) expect(bytes, `${name} at a first open`).toBeLessThanOrEqual(LARGEST_OTHER_SCRIPT)
    if (browserName === 'chromium') expect(firstOpenMs, 'Home drawn on the phone profile').toBeLessThanOrEqual(FIRST_OPEN_CEILING_MS)
    await context.close()
  }
})
