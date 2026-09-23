/**
 * Hand a link to the phone's share sheet, or copy it where there is none — Batch T4.
 *
 * The movie-night invite used to be copy-only, so sharing it meant copy, switch apps,
 * paste. The share sheet goes straight to WhatsApp or Messages. A desktop browser without
 * one still gets the copy.
 *
 * `cancelled` is its own outcome: somebody closing the share sheet has not failed at
 * anything, and saying "couldn't share" would be wrong.
 */
export type ShareOutcome = 'shared' | 'copied' | 'cancelled'

export async function shareLink(link: { title: string; text?: string; url: string }): Promise<ShareOutcome> {
  if (typeof navigator.share === 'function') {
    try {
      await navigator.share(link)
      return 'shared'
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled'
      // Anything else — a browser that has the function but refuses this call — falls
      // through to copying, which still gets the link to the person.
    }
  }
  if (!navigator.clipboard) throw new Error('This browser can neither share nor copy the link.')
  await navigator.clipboard.writeText(link.url)
  return 'copied'
}
