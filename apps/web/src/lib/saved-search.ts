/**
 * Reading an eBay saved search for the film it is about — Batch T8b (`DECISIONS.md` #245).
 *
 * A saved search is free text ("dog soldiers 4k"); T8a's alert is a film and a format. So the
 * words that name a format choose the format and leave the words that find the film. They
 * have to leave: the catalogue search matches every word it is given, and no film's record
 * contains "4k".
 *
 * **Only format words are taken out.** Edition words ("steelbook", "limited") are left for
 * the person to delete if they get in the way, because some are also title words ("The
 * Collector"), and a title must never lose a word to a guess.
 */

export type AlertFormat = '4k_uhd' | 'blu_ray' | 'dvd'

/** Checked in this order, so "4k blu ray", which is how 4K discs are sold, reads as 4K. */
const FORMAT_WORDS: Array<[pattern: string, format: AlertFormat]> = [
  ['\\b(?:4k|uhd|ultra hd)\\b', '4k_uhd'],
  ['\\b(?:blu ray|bluray)\\b', 'blu_ray'],
  ['\\bdvd\\b', 'dvd'],
]

/** Lower case, apostrophes dropped, anything else that is not a letter or a digit a space. */
export function normaliseWords(text: string): string {
  return text
    .toLowerCase()
    .replace(/['’]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

/** The words that find the film, and the format the search names, if it names one. */
export function readSavedSearch(text: string): { words: string; format: AlertFormat | null } {
  let words = normaliseWords(text)
  let format: AlertFormat | null = null
  for (const [pattern, code] of FORMAT_WORDS) {
    if (format === null && new RegExp(pattern).test(words)) format = code
    words = words.replace(new RegExp(pattern, 'g'), ' ')
  }
  return { words: words.replace(/\s+/g, ' ').trim(), format }
}

const LEADING_ARTICLE = /^(?:the|a|an) /

/**
 * Whether search words name this film: every word of its title is among them, a leading
 * "The" or "A" aside, since a search for "thing 4k" means The Thing. It offers a film to
 * pick, never picks one, so a short title matching more than it should costs a line.
 */
export function wordsNameFilm(words: string, title: string): boolean {
  const searched = new Set(normaliseWords(words).split(' '))
  const full = normaliseWords(title)
  const titleWords = (full.replace(LEADING_ARTICLE, '') || full).split(' ').filter(Boolean)
  return titleWords.length > 0 && titleWords.every((word) => searched.has(word))
}
