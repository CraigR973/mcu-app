import { randomUUID } from 'node:crypto'
import { expect, test } from '../support/test.ts'

test('AB1 reconciles historical warnings and clears a real doubt when it is kept', async ({ signedIn, api, db }, testInfo) => {
  const film = randomUUID()
  const historical = randomUUID()
  const copy = randomUUID()
  const doubt = randomUUID()
  // No public API creates historical provider evidence or daily health snapshots.
  db.sql(`INSERT INTO movies (id, title, original_title, year, media_type, tmdb_id) VALUES
    ('${film}', 'AB1 actionable film', 'AB1 actionable film', 2000, 'film', 1999001),
    ('${historical}', 'AB1 resolved film', 'AB1 resolved film', 2001, 'film', 1999002);
    INSERT INTO collection_items (id, movie_id, formats) VALUES ('${copy}', '${film}', '["blu_ray"]');
    INSERT INTO identify_lookups (id, movie_id, status, created_utc) VALUES
      ('${randomUUID()}', '${historical}', 'needs_you', timezone('utc', now()) - interval '20 days');
    INSERT INTO identify_doubts (id, movie_id, collection_item_id, source, status, note, created_utc)
      VALUES ('${doubt}', '${film}', '${copy}', 'specs', 'open', 'AB1 another year', timezone('utc', now()) - interval '20 days');
    INSERT INTO health_checks (check_key, ok, message, checked_utc, failing_since_utc) VALUES
      ('identify:waiting', false, '1 historical proposal', timezone('utc', now()), timezone('utc', now())),
      ('identify:year-doubt', false, '48 historical disagreements', timezone('utc', now()), timezone('utc', now()))
      ON CONFLICT (check_key) DO UPDATE SET ok = false, message = excluded.message, checked_utc = excluded.checked_utc;
  `)
  try {
    const { page, context } = await signedIn('Craig')
    await page.setViewportSize({ width: 375, height: 844 })
    for (const theme of ['dark', 'light']) {
      await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
      await page.goto('/dashboard')
      const attention = page.getByRole('region', { name: 'Needs attention' })
      await expect(attention.getByText('1 Identify proposal has waited more than a fortnight.', { exact: false })).toBeVisible()
      await expect(attention.getByText(/1 identified film has a disc page/)).toBeVisible()
      await expect(attention.getByText(/48 historical/)).toHaveCount(0)
      await page.screenshot({ path: testInfo.outputPath(`ab1-attention-${theme}-375.png`) })
    }
    await page.getByRole('link', { name: 'Open films in doubt', exact: true }).click()
    const card = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'AB1 actionable film (2000)', exact: true }) })
    await expect(card).toBeVisible()
    await card.getByRole('button', { name: "It’s right", exact: true }).click()
    await expect(card).toHaveCount(0)
    // Client navigation preserves the previously cached Home query: invalidation must work.
    await page.getByRole('navigation', { name: 'Primary mobile navigation' }).getByRole('link', { name: 'Home', exact: true }).click()
    await expect(page.getByText(/1 Identify proposal has waited/)).toHaveCount(0)
    await expect(page.getByText(/1 identified film has a disc page/)).toHaveCount(0)
    const client = await api('Craig')
    const current = await client.get<{ items: { key: string }[] }>('/attention')
    expect(current.items.filter(item => item.key.startsWith('identify:'))).toEqual([])
    expect(db.scalar(`SELECT message FROM health_checks WHERE check_key = 'identify:year-doubt'`)).toBe('48 historical disagreements')
    expect(db.scalar(`SELECT count(*) FROM identify_lookups WHERE movie_id = '${historical}'`)).toBe('1')
  } finally {
    db.sql(`UPDATE collection_items SET deleted_at = timezone('utc', now()) WHERE id = '${copy}';
      UPDATE movies SET deleted_at = timezone('utc', now()) WHERE id IN ('${film}', '${historical}');
      DELETE FROM health_checks WHERE check_key IN ('identify:waiting', 'identify:year-doubt');`)
  }
})

test('AB1 actions open the real settings panels and job controls, with honest device guidance', async ({ signedIn, db }, testInfo) => {
  const craig = db.scalar("SELECT id FROM profiles WHERE display_name = 'Craig'")
  const mark = db.scalar("SELECT id FROM profiles WHERE display_name = 'Mark'")
  const checks = ['ebay:listings', 'assistant:failures', 'job:cron-specs', 'job:cron-values', 'job:cron-reminders', `person:${craig}:notifications`, `person:${mark}:notifications`]
  db.sql(`INSERT INTO health_checks (check_key, ok, message, checked_utc, failing_since_utc) VALUES ${checks.map(key => `('${key}', false, 'AB1 ${key}', timezone('utc', now()), timezone('utc', now()))`).join(',')}
    ON CONFLICT (check_key) DO UPDATE SET ok = false, message = excluded.message, checked_utc = excluded.checked_utc;`)
  try {
    const { page } = await signedIn('Craig')
    await page.setViewportSize({ width: 375, height: 844 })
    const destinations = [
      ['Open eBay settings', 'tab', 'eBay', 'Connect your own eBay'],
      ['Open Assistant settings', 'tab', 'Assistant', 'Your limits'],
      ['Open your device settings', 'tab', 'Notifications', 'Each browser you turn notifications on in gets its own entry.'],
      ['Open Disc specs', 'heading', 'Disc specs', 'Coverage'],
      ['Open Collection value', 'heading', 'Collection value', 'Used-sale tracking'],
    ] as const
    for (const [link, role, name, content] of destinations) {
      await page.goto('/dashboard')
      const attention = page.getByRole('region', { name: 'Needs attention' })
      await attention.getByRole('link', { name: link, exact: true }).click()
      const destination = page.getByRole(role, { name, exact: true })
      await expect(destination).toBeVisible()
      if (role === 'tab') await expect(destination).toHaveAttribute('aria-selected', 'true')
      await expect(page.getByRole('main').getByText(content, { exact: false }).first()).toBeVisible()
    }
    await page.goto('/dashboard')
    const attention = page.getByRole('region', { name: 'Needs attention' })
    const otherPhone = attention.getByRole('listitem').filter({ hasText: `person:${mark}:notifications` })
    await expect(otherPhone.getByRole('link')).toHaveCount(0)
    await expect(otherPhone).toContainText('on their own phone')
    const job = attention.getByRole('listitem').filter({ hasText: 'job:cron-reminders' })
    await expect(job.getByRole('link')).toHaveCount(0)
    await expect(job).toContainText('Railway')
    await page.screenshot({ path: testInfo.outputPath('ab1-destinations-375.png') })
  } finally {
    db.sql(`DELETE FROM health_checks WHERE check_key IN (${checks.map(key => `'${key}'`).join(',')});`)
  }
})
