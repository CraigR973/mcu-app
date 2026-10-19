import type { Api } from './api.ts'

interface FilmRow {
  id: string
  title: string
}

/** The id of an owned film, found the way the app lists them. */
export async function filmId(api: Api, title: string): Promise<string> {
  const page = await api.get<{ items: FilmRow[] }>('/movies?perPage=2000')
  const found = page.items.find((film) => film.title === title)
  if (!found) throw new Error(`no owned film called ${title}`)
  return found.id
}
