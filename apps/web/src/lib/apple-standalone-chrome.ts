/**
 * AB4, #308: the affected iPhone measured 32px below its native top-edge blur.
 * Apple's signal excludes Safari tabs and Android's standalone installations.
 * CSS limits the shared clearance to phone layout with a positive top safe area.
 * Run before React mounts, so header and Search start with the same geometry.
 */
export function applyAppleStandaloneChrome(): void {
  const appleNavigator = window.navigator as Navigator & { standalone?: boolean }
  document.documentElement.toggleAttribute('data-apple-standalone', appleNavigator.standalone === true)
}
