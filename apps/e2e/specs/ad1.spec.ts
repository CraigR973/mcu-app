import { randomUUID } from 'node:crypto'
import { expect, test } from '../support/test.ts'

interface Review { id: string; kind: string }

const TITANIC = '219a59fc-8a0b-4eeb-ba7c-18b0391eb69f'
const WANTED = '58df19fb-d961-457c-8374-6df550b563cf'
const SHETLAND = 'd90ea74d-8ad3-4864-9070-043c4e358e59'
const ids = `'${TITANIC}','${WANTED}','${SHETLAND}'`

// These fixture facts reproduce the three approved targets in disposable Postgres only.
// The assignment, observations and every read then use the app's real API and UI.
test('Mark answers his three private reviews; Craig inspects; changed and resolved targets stay honest', async ({ db, api, signedIn, page: anonymous }, info) => {
  await anonymous.goto('/needs-you')
  await expect(anonymous).toHaveURL(/\/login(?:\?|$)/)
  await expect(anonymous.getByRole('region', { name: "Check Titanic's Blu-ray" })).toHaveCount(0)
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
    const craig = await api('Craig'), mark = await api('Mark')
    const proposals = await craig.get<Record<string, unknown>[]>('/needs-you/reviews/proposals')
    expect(proposals).toHaveLength(3)
    const { page: adminPage } = await signedIn('Craig')
    await adminPage.setViewportSize({ width: 375, height: 812 })
    await adminPage.goto('/needs-you')
    await expect(adminPage.getByRole('banner', { name: 'Top bar' })).toContainText('Needs you')
    await adminPage.getByRole('button', { name: 'Check current targets' }).click()
    await adminPage.getByRole('button', { name: 'Assign these three reviews to Mark' }).click()
    await expect(adminPage.getByRole('region', { name: "Check Titanic's Blu-ray" })).toBeVisible()
    for (const proposal of proposals) await craig.post('/needs-you/reviews', proposal)
    const reviews = await mark.get<Review[]>('/needs-you/reviews')
    expect(reviews).toHaveLength(3)
    expect((await mark.get<{ reviews: Review[] }>('/needs-you')).reviews).toHaveLength(3)
    expect((await craig.get<{ reviews: Review[] }>('/needs-you')).reviews).toHaveLength(0)
    await mark.call('GET', '/needs-you/reviews?allAssignees=true', undefined, [403])

    const { page } = await signedIn('Mark')
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/you')
    await page.getByRole('link', { name: 'Needs you — assigned reviews' }).click()
    await expect(page.getByRole('banner', { name: 'Top bar' })).toContainText('Needs you')
    const titanic = page.getByRole('region', { name: "Check Titanic's Blu-ray" })
    await expect(titanic).toBeVisible()
    await expect(page.getByRole('region', { name: 'Check Shetland Series 5' })).toBeVisible()
    await titanic.getByRole('radio', { name: 'Not sure yet' }).check()
    await titanic.getByRole('button', { name: 'Save observation' }).click()
    await expect(titanic.getByText('Recorded answer: Not sure yet')).toBeVisible()
    await expect(titanic.getByText('Needs your observation', { exact: false })).toBeVisible()
    expect(db.scalar(`SELECT year FROM movies WHERE id='${TITANIC}'`)).toBe('1953')
    expect(db.scalar(`SELECT movie_id FROM collection_items WHERE id='${disc}'`)).toBe(TITANIC)
    await page.screenshot({ path: info.outputPath('ad1-mark-reviews-375.png'), fullPage: true })

    await adminPage.reload()
    const inspected = adminPage.getByRole('region', { name: "Check Titanic's Blu-ray" })
    await expect(inspected.getByText('Recorded answer: Not sure yet')).toBeVisible()
    await expect(inspected.getByRole('radio')).toHaveCount(0)
    await expect(adminPage.getByRole('button', { name: 'Check current targets' })).toBeVisible()

    db.sql(`UPDATE movies SET title='A changed wanted identity' WHERE id='${WANTED}';
      UPDATE movies SET tmdb_tv_id=46923,media_type='tv' WHERE id='${SHETLAND}'`)
    await page.reload()
    const wanted = page.getByRole('region', { name: "Check Dead Man's Shoes on Wanted" })
    await expect(wanted.getByText('The record changed — needs another look', { exact: false })).toBeVisible()
    await expect(wanted.getByRole('radio')).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Check Shetland Series 5' }).getByText('Resolved through the catalogue', { exact: false })).toBeVisible()
    const wantedReview = reviews.find(row => row.kind === 'wanted_identity')!
    await mark.post(`/needs-you/reviews/${wantedReview.id}/answer`, { revision: 1, answer: '2004' }, [409])
    expect((await mark.get<{ reviews: Review[] }>('/needs-you')).reviews).toHaveLength(2)
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
