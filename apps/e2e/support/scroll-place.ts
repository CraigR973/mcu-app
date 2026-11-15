import type { Locator } from '@playwright/test'

type Tapping = Window & { placeAtTap?: number }

/**
 * Taps `target` and returns where `box` was scrolled at the tap itself: the place Back has to
 * come back to (AF4, #372).
 *
 * Read at the tap, not before it (#379). Playwright's click waits for its target to stop moving,
 * then scrolls it into view again before tapping, so a place read before the click can be one the
 * page has already left. On main's run of 14 Nov, in WebKit, the case read 857, the click moved
 * the film's link to 693 and tapped it there, and Back rightly came back to 693.
 */
export async function tapKeepingPlace(box: Locator, target: Locator): Promise<number> {
  await box.evaluate((element) => {
    window.addEventListener('click', () => { (window as Tapping).placeAtTap = element.scrollTop }, { capture: true, once: true })
  })
  await target.click()
  const place = await box.page().evaluate(() => (window as Tapping).placeAtTap)
  if (place === undefined) throw new Error('The tap never reached the page')
  return place
}
