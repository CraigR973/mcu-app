import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { WORLD_DIR } from '../harness/env.ts'

export interface Call {
  kind: 'call' | 'unfaked' | 'unknown' | string
  host: string
  path: string
  query?: string
  method?: string
  body?: string
  t: number
  [key: string]: unknown
}

/** The fake outside world, seen from a case: what the app asked it, and what it should say. */
export const world = {
  log(): Call[] {
    const file = path.join(WORLD_DIR, 'log.jsonl')
    if (!existsSync(file)) return []
    return readFileSync(file, 'utf8')
      .split('\n')
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Call)
  },
  /** Calls to one host (and, optionally, a path fragment) since `since`. */
  calls(host: string, since = 0, pathPart = ''): Call[] {
    return world.log().filter((c) => c.kind === 'call' && c.host === host && c.t >= since && c.path.includes(pathPart))
  },
  /** Anything that tried to leave: an unfaked host, or a path on a faked host nobody wrote. */
  leaks(since = 0): Call[] {
    return world.log().filter((c) => (c.kind === 'unfaked' || c.kind === 'unknown') && c.t >= since)
  },
  scenario(): Record<string, unknown> {
    const file = path.join(WORLD_DIR, 'scenario.json')
    return existsSync(file) ? (JSON.parse(readFileSync(file, 'utf8')) as Record<string, unknown>) : {}
  },
  setScenario(values: Record<string, unknown>): void {
    writeFileSync(path.join(WORLD_DIR, 'scenario.json'), JSON.stringify({ ...world.scenario(), ...values }))
  },
  clearScenario(): void {
    writeFileSync(path.join(WORLD_DIR, 'scenario.json'), '{}')
  },
}
