import { expect, test } from '../support/test.ts'
import { world } from '../support/world.ts'

test('Admin shows the owner-started used-sale pass without searching eBay on read', async ({ signedIn }) => {
  const since = Date.now() / 1000
  const { page } = await signedIn('Craig')
  await page.goto('/valuation')
  await expect(page.getByRole('heading', { name: "What it’s worth" })).toBeVisible()
  await expect(page.getByText('Used-sale tracking', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start used-sale tracking' })).toBeVisible()
  expect(world.calls('api.ebay.com', since)).toEqual([])
})
