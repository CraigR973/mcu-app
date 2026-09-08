import { useState } from 'react'

export type ViewMode = 'grid' | 'list' | 'compact'

export const ALL_COLUMNS = [
  { key: 'year',       label: 'Year' },
  { key: 'format',     label: 'Format' },
  { key: 'location',   label: 'Location' },
  { key: 'hdr',        label: 'HDR' },
  { key: 'audio',      label: 'Audio' },
  { key: 'runtime',    label: 'Runtime' },
  { key: 'rating',     label: 'Rating' },
  { key: 'watched',    label: 'Watched' },
] as const

export type ColumnKey = typeof ALL_COLUMNS[number]['key']

// Location is on by default. "Where is this disc?" is the question the collection
// exists to answer, and it was unanswerable in the app until Batch 6.
const DEFAULT_COLUMNS: ColumnKey[] = ['year', 'format', 'location', 'rating']

const STORAGE_KEYS = {
  viewMode: 'mcu:view-mode:v1',
  columns:  'mcu:list-columns:v2',
} as const

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Preferences are optional; private browsing can refuse local storage.
  }
}

export function useViewPreference() {
  const [viewMode, setViewModeState] = useState<ViewMode>(
    () => read<ViewMode>(STORAGE_KEYS.viewMode, 'grid')
  )
  const [enabledColumns, setEnabledColumnsState] = useState<ColumnKey[]>(
    () => read<ColumnKey[]>(STORAGE_KEYS.columns, DEFAULT_COLUMNS)
  )

  const setViewMode = (mode: ViewMode) => {
    setViewModeState(mode)
    write(STORAGE_KEYS.viewMode, mode)
  }

  const setEnabledColumns = (cols: ColumnKey[]) => {
    setEnabledColumnsState(cols)
    write(STORAGE_KEYS.columns, cols)
  }

  const toggleColumn = (key: ColumnKey) => {
    setEnabledColumns(
      enabledColumns.includes(key)
        ? enabledColumns.filter(c => c !== key)
        : [...enabledColumns, key]
    )
  }

  return { viewMode, setViewMode, enabledColumns, setEnabledColumns, toggleColumn }
}
