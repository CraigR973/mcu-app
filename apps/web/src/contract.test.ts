import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import * as shared from '@mcu/shared'
import { describe, expect, it } from 'vitest'
import { z, type ZodTypeAny } from 'zod'

/**
 * **The API and the web cannot drift apart unseen** — Batch X8 (CR43-04). A guard (CI).
 *
 * Every function in `lib/api.ts` that parses an answer names the endpoint it calls and the
 * zod schema it parses with. This reads both from the source, finds the endpoint in the API's
 * own OpenAPI description (`packages/shared/openapi.json`, held to the app by the API's
 * `test_openapi_snapshot.py`), and walks the schema against the response model:
 *
 * - **enums** — every value the API may send is one the schema accepts (a newer API's value
 *   turned a whole page into raw JSON, UX48-03);
 * - **nullability** — a field the API may send as null, or leave out, is one the schema
 *   accepts as null, or as missing;
 * - **minimums** — a number the schema bounds below is bounded at least as high by the API.
 *
 * Twice before (#205) a client broke on an answer it had always received: a sold film's page
 * and a cached answer missing a new field. Each is one of the three checks above.
 */

type Json = Record<string, unknown>

/** Where the source splices a value into a path. Printable, and never in a real route. */
const SPLICE = '⟨⟩'

const root = (path: string) => fileURLToPath(new URL(path, import.meta.url))
const spec = JSON.parse(readFileSync(root('../../../packages/shared/openapi.json'), 'utf8')) as Json
const source = readFileSync(root('./lib/api.ts'), 'utf8')
const components = ((spec.components as Json).schemas ?? {}) as Record<string, Json>
const paths = spec.paths as Record<string, Record<string, Json>>

// ---------------------------------------------------------------------------
// Reading lib/api.ts: endpoint, method and schema per parsing function
// ---------------------------------------------------------------------------

interface Call {
  fn: string
  method: string
  path: string | null
  schemaExpr: string
}

/** The text from `open` up to its balanced closing bracket. */
function balanced(text: string, start: number): string {
  const pairs: Record<string, string> = { '(': ')', '{': '}', '[': ']' }
  const stack: string[] = []
  let quote: string | null = null
  for (let i = start; i < text.length; i += 1) {
    const ch = text[i]
    if (quote) {
      if (ch === '\\') i += 1
      else if (ch === quote) quote = null
      else if (quote === '`' && ch === '$' && text[i + 1] === '{') {
        // A template expression: skip it as a balanced block.
        const inner = balanced(text, i + 1)
        i += inner.length
      }
      continue
    }
    if (ch === "'" || ch === '"' || ch === '`') quote = ch
    else if (ch in pairs) stack.push(pairs[ch])
    else if (ch === stack[stack.length - 1]) {
      stack.pop()
      if (stack.length === 0) return text.slice(start, i + 1)
    }
  }
  return text.slice(start)
}

/** Split an argument list at its top-level commas. */
function args(list: string): string[] {
  const inner = list.slice(1, -1)
  const out: string[] = []
  let depth = 0
  let quote: string | null = null
  let current = ''
  for (let i = 0; i < inner.length; i += 1) {
    const ch = inner[i]
    if (quote) {
      if (ch === '\\') {
        current += ch + inner[i + 1]
        i += 1
        continue
      }
      if (ch === quote) quote = null
      current += ch
      continue
    }
    if (ch === "'" || ch === '"' || ch === '`') quote = ch
    if ('({['.includes(ch)) depth += 1
    if (')}]'.includes(ch)) depth -= 1
    if (ch === ',' && depth === 0) {
      out.push(current.trim())
      current = ''
    } else current += ch
  }
  if (current.trim()) out.push(current.trim())
  return out
}

/** A path literal as the API would route it: `${…}` segments become parameters. */
function literalPath(expr: string, body: string): string | null {
  let text = expr.trim()
  if (/^\w+$/.test(text)) {
    const assigned = new RegExp(`(?:const|let)\\s+${text}\\s*=\\s*`).exec(body)
    if (!assigned) return null
    const start = assigned.index + assigned[0].length
    text = body[start] === '`' || body[start] === "'" ? body.slice(start, start + balancedString(body, start)) : ''
    if (!text) return null
  }
  const quote = text[0]
  if (quote !== '`' && quote !== "'") return null
  let raw = text.slice(1, text.lastIndexOf(quote))
  // Replace each `${…}` with SPLICE, balanced, so a nested template counts as one.
  let out = ''
  for (let i = 0; i < raw.length; i += 1) {
    if (raw[i] === '$' && raw[i + 1] === '{') {
      const block = balanced(raw, i + 1)
      out += SPLICE
      i += block.length
    } else out += raw[i]
  }
  raw = out.split('?')[0]
  // A query string spliced in whole (`/deals${query}`) ends a segment with a marker.
  return raw.replace(new RegExp(`([^/])(?:${SPLICE})+$`), '$1')
}

function balancedString(text: string, start: number): number {
  const quote = text[start]
  for (let i = start + 1; i < text.length; i += 1) {
    if (text[i] === '\\') i += 1
    else if (quote === '`' && text[i] === '$' && text[i + 1] === '{') i += balanced(text, i + 1).length
    else if (text[i] === quote) return i - start + 1
  }
  return text.length - start
}

function calls(): Call[] {
  const found: Call[] = []
  const fnPattern = /(?:export\s+)?async\s+function\s+(\w+)\s*(?:<[^>]*>)?\s*\(/g
  for (let match = fnPattern.exec(source); match; match = fnPattern.exec(source)) {
    const name = match[1]
    if (name === 'parseResponse' || name === 'parseOrThrowApiError') continue
    const bodyStart = source.indexOf('{', fnPattern.lastIndex + balanced(source, fnPattern.lastIndex - 1).length - 1)
    const body = balanced(source, bodyStart)
    const parse = /\b(parseResponse|parseOrThrowApiError)\s*\(/.exec(body)
    if (!parse) continue
    const parsed = args(balanced(body, parse.index + parse[0].length - 1))
    const fetchCall = /\b(authFetch|send)\s*\(/.exec(body)
    let path: string | null = null
    let method = 'GET'
    if (fetchCall) {
      const fetchArgs = args(balanced(body, fetchCall.index + fetchCall[0].length - 1))
      path = literalPath(fetchArgs[0] ?? '', body)
      const declared = /method:\s*'(\w+)'/.exec(fetchArgs.slice(1).join(','))
      if (declared) method = declared[1]
    }
    found.push({ fn: name, method, path, schemaExpr: parsed[1] ?? '' })
  }
  return found
}

function schemaFor(expr: string): ZodTypeAny {
  const names = Object.keys(shared).filter((key) => /^\w+$/.test(key))
  const values = names.map((key) => (shared as Record<string, unknown>)[key])
  // The expression is the source's own (`fooSchema`, `z.array(fooSchema)`,
  // `fooSchema.nullable()`), evaluated against the real schemas.
  return new Function('z', ...names, `return (${expr})`)(z, ...values) as ZodTypeAny
}

// ---------------------------------------------------------------------------
// Finding the endpoint and its response model
// ---------------------------------------------------------------------------

function operationFor(method: string, webPath: string): Json | null {
  const wanted = `/api/v1${webPath}`.replace(/\/$/, '').split('/')
  // Two passes: a parameter matches a spliced value first, then any literal the web fixes
  // (`/trash/collection_items/…` is `/trash/{table}/…` with the table chosen).
  for (const loose of [false, true]) {
    for (const [apiPath, operations] of Object.entries(paths)) {
      const segments = apiPath.replace(/\/$/, '').split('/')
      if (segments.length !== wanted.length) continue
      const same = segments.every(
        (segment, i) =>
          segment === wanted[i] ||
          (/^\{.+\}$/.test(segment) && (loose || wanted[i].includes(SPLICE))),
      )
      if (same && operations[method.toLowerCase()]) return operations[method.toLowerCase()]
    }
  }
  return null
}

function responseSchema(operation: Json): Json | null {
  const responses = (operation.responses ?? {}) as Record<string, Json>
  const code = Object.keys(responses).find((status) => status.startsWith('2'))
  const content = code ? ((responses[code].content ?? {}) as Record<string, Json>) : {}
  return (content['application/json']?.schema as Json | undefined) ?? null
}

// ---------------------------------------------------------------------------
// Walking a zod schema against an OpenAPI schema
// ---------------------------------------------------------------------------

interface ZodShape {
  inner: ZodTypeAny
  acceptsNull: boolean
  acceptsMissing: boolean
}

function unwrapZod(schema: ZodTypeAny): ZodShape {
  let current: ZodTypeAny = schema
  let acceptsNull = false
  let acceptsMissing = false
  for (;;) {
    const def = current._def as { typeName: string; innerType?: ZodTypeAny; schema?: ZodTypeAny; getter?: () => ZodTypeAny; in?: ZodTypeAny }
    if (def.typeName === 'ZodOptional') acceptsMissing = true
    else if (def.typeName === 'ZodNullable') acceptsNull = true
    else if (def.typeName === 'ZodDefault' || def.typeName === 'ZodCatch') acceptsMissing = true
    else if (def.typeName === 'ZodEffects') {
      current = def.schema as ZodTypeAny
      continue
    } else if (def.typeName === 'ZodLazy') {
      current = (def.getter as () => ZodTypeAny)()
      continue
    } else if (def.typeName === 'ZodPipeline') {
      current = def.in as ZodTypeAny
      continue
    } else if (def.typeName === 'ZodBranded') {
      current = (def as unknown as { type: ZodTypeAny }).type
      continue
    } else break
    current = def.innerType as ZodTypeAny
  }
  if ((current._def as { typeName: string }).typeName === 'ZodCatch') acceptsNull = true
  return { inner: current, acceptsNull, acceptsMissing }
}

interface ApiShape {
  node: Json
  nullable: boolean
}

function resolve(node: Json): Json {
  let current = node
  while (typeof current.$ref === 'string') {
    current = components[(current.$ref as string).split('/').pop() as string]
  }
  return current
}

function unwrapApi(node: Json): ApiShape {
  let current = resolve(node)
  let nullable = false
  const options = (current.anyOf ?? current.oneOf) as Json[] | undefined
  if (options) {
    const rest = options.filter((option) => resolve(option).type !== 'null')
    nullable = rest.length < options.length
    if (rest.length === 1) current = resolve(rest[0])
    else current = { anyOf: rest }
  }
  if (Array.isArray(current.allOf) && current.allOf.length === 1) current = resolve(current.allOf[0] as Json)
  return { node: current, nullable }
}

function apiEnum(node: Json): unknown[] | null {
  if (Array.isArray(node.enum)) return node.enum as unknown[]
  if ('const' in node) return [node.const]
  if (Array.isArray(node.anyOf)) {
    const values = (node.anyOf as Json[]).map((option) => apiEnum(resolve(option)))
    if (values.every((value) => value !== null)) return values.flat() as unknown[]
  }
  return null
}

function zodValues(schema: ZodTypeAny): unknown[] | null {
  const def = schema._def as { typeName: string; values?: unknown; value?: unknown; options?: ZodTypeAny[] }
  if (def.typeName === 'ZodEnum') return def.values as unknown[]
  if (def.typeName === 'ZodNativeEnum') return Object.values(def.values as object)
  if (def.typeName === 'ZodLiteral') return [def.value]
  if (def.typeName === 'ZodUnion') {
    const parts = (def.options ?? []).map((option) => zodValues(unwrapZod(option).inner))
    if (parts.every((part) => part !== null)) return parts.flat() as unknown[]
  }
  return null
}

function zodMinimum(schema: ZodTypeAny): number | null {
  const def = schema._def as { typeName: string; checks?: { kind: string; value?: number; inclusive?: boolean }[] }
  if (def.typeName !== 'ZodNumber') return null
  const mins = (def.checks ?? []).filter((check) => check.kind === 'min')
  if (mins.length === 0) return null
  return Math.max(...mins.map((check) => (check.inclusive === false ? (check.value as number) + Number.EPSILON : (check.value as number))))
}

function apiMinimum(node: Json): number | null {
  if (typeof node.minimum === 'number') return node.minimum
  if (typeof node.exclusiveMinimum === 'number') return node.exclusiveMinimum + Number.EPSILON
  return null
}

function walk(
  zodSchema: ZodTypeAny,
  apiNode: Json,
  at: string,
  problems: string[],
  seen = new Set<string>(),
  owner = '',
): void {
  const zod = unwrapZod(zodSchema)
  const api = unwrapApi(apiNode)
  const key = `${at}|${JSON.stringify(api.node).slice(0, 200)}`
  if (seen.has(key)) return
  seen.add(key)

  if (api.nullable && !zod.acceptsNull) problems.push(`${at}: the API may send null; the schema refuses it`)

  const type = (zod.inner._def as { typeName: string }).typeName
  if (type === 'ZodUnknown' || type === 'ZodAny') return

  const values = zodValues(zod.inner)
  if (values) {
    const sent = apiEnum(api.node)
    if (sent === null) {
      if (api.node.type === 'string') {
        problems.push(`${at}${owner}: the API sends any string; the schema accepts only ${values.join(', ')}`)
      }
    } else {
      const unknown = sent.filter((value) => !values.includes(value))
      if (unknown.length) problems.push(`${at}: the API may send ${unknown.join(', ')}, which the schema refuses`)
    }
    return
  }

  if (type === 'ZodNumber') {
    const floor = zodMinimum(zod.inner)
    if (floor !== null) {
      const apiFloor = apiMinimum(api.node)
      if (apiFloor === null || apiFloor < floor) {
        problems.push(
          `${at}${owner}: the schema refuses values under ${floor}; the API bounds it at ${apiFloor ?? 'nothing'}`,
        )
      }
    }
    return
  }

  if (type === 'ZodArray') {
    const items = (api.node.items ?? {}) as Json
    walk((zod.inner._def as { type: ZodTypeAny }).type, items, `${at}[]`, problems, seen)
    return
  }

  if (type === 'ZodRecord') {
    const values = api.node.additionalProperties
    if (values && typeof values === 'object') walk((zod.inner._def as { valueType: ZodTypeAny }).valueType, values as Json, `${at}{}`, problems, seen)
    return
  }

  if (type === 'ZodObject') {
    const shape = (zod.inner as z.AnyZodObject).shape as Record<string, ZodTypeAny>
    // Every property a response model declares is sent: FastAPI serialises the whole model
    // (no route drops unset or null fields), so "may the API leave it out?" is "does it
    // declare it?". `required` in the description reflects defaults, not the wire.
    const properties = (api.node.properties ?? {}) as Record<string, Json>
    if (!api.node.properties) return // not an object the API describes field by field
    for (const [field, fieldSchema] of Object.entries(shape)) {
      const fieldShape = unwrapZod(fieldSchema)
      if (!(field in properties)) {
        if (!fieldShape.acceptsMissing) problems.push(`${at}.${field}: the schema requires it; the API never sends it`)
        continue
      }
      walk(fieldSchema, properties[field], `${at}.${field}`, problems, seen, ` (${String(api.node.title)}.${field})`)
    }
  }
}

// ---------------------------------------------------------------------------
// The checks
// ---------------------------------------------------------------------------

const all = calls()
const matched = all
  .filter((call) => call.path !== null)
  .map((call) => ({ call, operation: operationFor(call.method, call.path as string) }))

/**
 * Functions whose endpoint this reader cannot settle from the source: the path is built
 * from pieces. Each is named, so a new one fails until it is looked at.
 */
const UNREAD: string[] = []

describe('the web reads what the API sends', () => {
  it('finds the endpoint of every function that parses an answer', () => {
    const lost = [
      ...all.filter((call) => call.path === null).map((call) => call.fn),
      ...matched.filter((entry) => entry.operation === null).map((entry) => `${entry.call.fn} (${entry.call.method} ${entry.call.path?.replaceAll(SPLICE, '{}')})`),
    ]
    expect(lost.filter((name) => !UNREAD.some((known) => name.startsWith(known)))).toEqual([])
    expect(matched.length).toBeGreaterThan(100)
  })

  it('accepts every enum value, null and missing field, and number the API may send', () => {
    const problems: string[] = []
    for (const { call, operation } of matched) {
      if (!operation) continue
      const response = responseSchema(operation)
      if (!response) continue
      walk(schemaFor(call.schemaExpr), response, `${call.fn}`, problems)
    }
    expect(problems).toEqual([])
  })
})
