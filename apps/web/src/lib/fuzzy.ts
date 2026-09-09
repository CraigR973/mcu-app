/**
 * Subsequence fuzzy match: every character of `query` must appear in `target`, in
 * order, but not necessarily contiguously. Returns `null` when it doesn't match, or a
 * score (higher is better) otherwise — consecutive-run and match-from-start bonuses so
 * "mov" ranks "Movies" above a page that merely contains the letters scattered.
 *
 * Only used to rank the small, local pages/actions list — film matches come from the
 * server's tsvector search (Batch 5), which this does not touch.
 */
export function fuzzyScore(query: string, target: string): number | null {
  const q = query.trim().toLowerCase()
  if (!q) return 0
  const t = target.toLowerCase()

  let qi = 0
  let score = 0
  let consecutive = 0
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      consecutive += 1
      score += consecutive
      qi += 1
    } else {
      consecutive = 0
    }
  }

  if (qi < q.length) return null
  if (t.startsWith(q)) score += 10
  return score
}
