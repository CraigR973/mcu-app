export function normaliseProductCode(raw: string): string {
  return raw.replace(/[^0-9]/g, '')
}

export function hasProductCodeLength(value: string): boolean {
  return value.length === 8 || value.length === 12 || value.length === 13
}
