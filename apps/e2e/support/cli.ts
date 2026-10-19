import { writeFileSync } from 'node:fs'
import path from 'node:path'
import { E2E_DIR, RUN_DB, RUN_DIR } from '../harness/env.ts'
import { runPython } from '../harness/stack.ts'

/** Run one of the app's command-line jobs against this run's database, with the fake world. */
export function runJob(module: string, args: string[] = []): { status: number; output: string } {
  return runPython(['-m', module, ...args], RUN_DB, {}, module)
}

/** Build a sheet in the catalogue's column layout and import it with the real import CLI. */
export function importSheet(
  name: string,
  rows: [string, string, string][],
  firstRow = 200,
): { status: number; output: string } {
  const rowsFile = path.join(RUN_DIR, `${name}.json`)
  const sheet = path.join(RUN_DIR, `${name}.xlsx`)
  writeFileSync(rowsFile, JSON.stringify(rows))
  const made = runPython([path.join(E2E_DIR, 'seed', 'make_sheet.py'), sheet, rowsFile, String(firstRow)], RUN_DB)
  if (made.status !== 0) throw new Error(`could not make the sheet:\n${made.output}`)
  return runJob('src.scripts.import_collection', ['--xlsx', sheet, '--review-out', path.join(RUN_DIR, `${name}-review.csv`)])
}
