import { useState } from 'react'

export type ViewMode = 'grid' | 'list' | 'compact'

export const ALL_COLUMNS = [
  { key: 'year',       label: 'Year' },
  { key: 'format',     label: 'Format' },
  { key: 'hdr',        label: 'HDR' },
  { key: 'audio',      label: 'Audio' },
  { key: 'runtime',    label: 'Runtime' },
  { key: 'rating',     label: 'Rating' },
] as const

export type ColumnKey = typeof ALL_COLUMNS[number]['key']

const DEFAULT_COLUMNS: ColumnKey[] = ['year', 'format', 'hdr', 'runtime', 'rating']

const STORAGE_KEYS = {
  viewMode: 'mcu:view-mode',
  columns:  'mcu:list-columns',
} as const

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
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
    localStorage.setItem(STORAGE_KEYS.viewMode, JSON.stringify(mode))
  }

  const setEnabledColumns = (cols: ColumnKey[]) => {
    setEnabledColumnsState(cols)
    localStorage.setItem(STORAGE_KEYS.columns, JSON.stringify(cols))
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
