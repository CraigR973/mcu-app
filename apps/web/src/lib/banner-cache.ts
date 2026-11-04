import { authFetch } from './auth-tokens'

/**
 * AC2: the Home banner, kept on the device after its first load so Home never shows a grey
 * box again — the private artwork is still fetched only with the person's token (AA8).
 *
 * A data URL in localStorage, because it is read synchronously on the first render; a
 * Cache Storage read is a promise, and a promise is a frame of placeholder. The key names
 * the artwork's version and size, so a new banner is a new key and the old one is dropped.
 */
const PREFIX = 'mcu.banner.'

/**
 * Which size this device needs: a phone's 3x width, or a desktop's 2x (`routers/brand.py`).
 * Decided once per mount, so a rotation does not fetch the other.
 */
export function bannerName(): string {
  const needed = typeof window === 'undefined' ? 0 : window.innerWidth * (window.devicePixelRatio || 1)
  return needed > 1125 ? 'letters-v1-1800' : 'letters-v1-1125'
}

/** In memory too, so a return to Home in the same visit does not touch storage at all. */
const memory = new Map<string, string>()

export function cachedBanner(name: string): string | null {
  const known = memory.get(name)
  if (known) return known
  try {
    const stored = localStorage.getItem(PREFIX + name)
    if (stored?.startsWith('data:image/')) {
      memory.set(name, stored)
      return stored
    }
  } catch {
    /* storage off (a private window): fetch each visit */
  }
  return null
}

function asDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error ?? new Error('Could not read the banner'))
    reader.readAsDataURL(blob)
  })
}

export async function loadBanner(name: string): Promise<string> {
  const response = await authFetch(`/brand/heroes/${name}`)
  if (!response.ok) throw new Error('Brand artwork could not be loaded.')
  const url = await asDataUrl(await response.blob())
  memory.set(name, url)
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(PREFIX) && key !== PREFIX + name) localStorage.removeItem(key)
    }
    localStorage.setItem(PREFIX + name, url)
  } catch {
    /* full or off: the in-memory copy still serves this visit */
  }
  return url
}

/** At sign-out, with the rest of what the device kept for the person. */
export function forgetBanners(): void {
  memory.clear()
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(PREFIX)) localStorage.removeItem(key)
    }
  } catch {
    /* nothing was kept */
  }
}
