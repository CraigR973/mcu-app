import { useQuery } from '@tanstack/react-query'

import { Input } from '@/components/ui/input'
import {
  CONDITIONS,
  fetchFacets,
  FORMATS,
  shelfLabel,
  type CollectionItemFields,
  type Condition,
} from '@/lib/api'

interface Props {
  value: CollectionItemFields
  onChange: (value: CollectionItemFields) => void
  disabled?: boolean
}

/** The section value meaning "somewhere the vocabulary does not cover". */
const FREE_TEXT = ''

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  )
}

const selectClass =
  'flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50'

/**
 * The editable fields of one disc — §3.2's "location, format, notes, condition, price"
 * plus §3.11's playback issues.
 *
 * The section and shelf pickers are built from `GET /collection/facets`, the same
 * source Batch 6's filter bar uses, so the form cannot offer a shelf that does not
 * exist or miss one a new disc has just created. Choosing "Somewhere else" hands over
 * to the free-text box, which the API parses with the importer's own `parse_location`.
 *
 * **The Section picker offers every section, including one with no disc yet** — Batch V4.
 * Craig's house held nothing when it was added, and a picker built from the places that
 * hold a disc could never offer it. `allSections` is the whole vocabulary; an older cached
 * response without it falls back to the populated ones, as the form did before.
 */
export default function CopyForm({ value, onChange, disabled }: Props) {
  const facetsQuery = useQuery({ queryKey: ['facets'], queryFn: fetchFacets })
  const populated = facetsQuery.data?.sections ?? []
  const allSections = facetsQuery.data?.allSections ?? []
  const sectionNames = allSections.length > 0 ? allSections : populated.map((entry) => entry.section)
  const chosen = populated.find((entry) => entry.section === value.section)
  const shelves = chosen?.shelves ?? []
  // Front and Back have shelves; the Lounge has a left and a right side (Mark, 14 Oct).
  const noun = chosen?.shelfNoun ?? 'shelf'

  function set<K extends keyof CollectionItemFields>(key: K, next: CollectionItemFields[K]) {
    onChange({ ...value, [key]: next })
  }

  function toggleFormat(code: string) {
    const next = value.formats.includes(code)
      ? value.formats.filter((entry) => entry !== code)
      : [...value.formats, code]
    set('formats', next)
  }

  function chooseSection(next: string) {
    if (next === FREE_TEXT) {
      // Hand back to free text: clear both normalised columns so the API parses the
      // typed string rather than an explicit picker value silently winning over it.
      onChange({ ...value, section: null, shelf: null })
      return
    }
    onChange({ ...value, section: next, shelf: null, location: null })
  }

  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="text-xs font-medium text-muted-foreground">Formats</legend>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {FORMATS.map((format) => {
            const active = value.formats.includes(format.value)
            return (
              <button
                key={format.value}
                type="button"
                disabled={disabled}
                onClick={() => toggleFormat(format.value)}
                aria-pressed={active}
                className={`touch-target min-h-11 rounded-md border px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
                  active
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-input bg-background text-muted-foreground hover:text-foreground'
                }`}
              >
                {format.label}
              </button>
            )
          })}
        </div>
        {/* One box can hold several discs, which is why `formats` is an array. */}
        <p className="mt-1.5 text-xs text-muted-foreground">
          Pick more than one for a combo pack.
        </p>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Section">
          <select
            className={selectClass}
            disabled={disabled}
            value={value.section ?? FREE_TEXT}
            onChange={(event) => chooseSection(event.target.value)}
          >
            <option value={FREE_TEXT}>Somewhere else…</option>
            {sectionNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </Field>

        {shelves.length > 0 ? (
          <Field label={noun === 'side' ? 'Side' : 'Shelf'}>
            <select
              className={selectClass}
              disabled={disabled}
              value={value.shelf ?? ''}
              // A new shelf drops the old text, as a new section does: the API composes it
              // again from the pickers (Mark's 12 Angry Men, 13 Oct).
              onChange={(event) => onChange({ ...value, shelf: event.target.value || null, location: null })}
            >
              <option value="">No particular {noun}</option>
              {shelves.map((shelf) => (
                <option key={shelf.shelf} value={shelf.shelf}>
                  {shelfLabel(shelf)}
                </option>
              ))}
            </select>
          </Field>
        ) : (
          <Field label="Location">
            <Input
              disabled={disabled}
              value={value.location ?? ''}
              // With a section chosen, the box is for detail within it: the API keeps it
              // after the section, "Garage - top row" (14 Oct).
              placeholder={value.section ? 'Anything more, e.g. top row' : 'Front 2nd shelf'}
              onChange={(event) => set('location', event.target.value || null)}
            />
          </Field>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Condition">
          <select
            className={selectClass}
            disabled={disabled}
            value={value.condition ?? ''}
            onChange={(event) =>
              set('condition', (event.target.value || null) as Condition | null)
            }
          >
            <option value="">Not recorded</option>
            {CONDITIONS.map((condition) => (
              <option key={condition.value} value={condition.value}>
                {condition.label}
              </option>
            ))}
          </select>
        </Field>
        {/* Batch U2: which edition the disc is. The spec batch fills it only where the
            disc's Blu-ray.com page is certainly this copy; anything else is typed here. */}
        <Field label="Edition">
          <Input
            disabled={disabled}
            maxLength={100}
            value={value.edition ?? ''}
            placeholder="SteelBook, Masters of Cinema…"
            onChange={(event) => set('edition', event.target.value || null)}
          />
        </Field>
      </div>

      {/* The spreadsheet's "Sub Category": a grouping such as "Hitchcock" or a box set.
          It was labelled "Collector edition" until editions existed (Batch U2). */}
      <Field label="Sub-category">
        <Input
          disabled={disabled}
          value={value.subCategory ?? ''}
          placeholder="Hitchcock, Bond box set…"
          onChange={(event) => set('subCategory', event.target.value || null)}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Price paid (£)">
          <Input
            disabled={disabled}
            type="number"
            min="0"
            step="0.01"
            value={value.purchasePrice ?? ''}
            onChange={(event) => set('purchasePrice', event.target.value || null)}
          />
        </Field>
        <Field label="Bought from">
          <Input
            disabled={disabled}
            value={value.purchaseSource ?? ''}
            placeholder="Fopp, eBay…"
            onChange={(event) => set('purchaseSource', event.target.value || null)}
          />
        </Field>
        <Field label="Bought on">
          <Input
            disabled={disabled}
            type="date"
            // A purchase cannot be in the future; the API refuses one, and saying so
            // here means the form does not have to be rejected to find that out.
            max={new Date().toISOString().slice(0, 10)}
            value={value.purchaseDate ?? ''}
            onChange={(event) => set('purchaseDate', event.target.value || null)}
          />
        </Field>
      </div>

      <Field label="Notes">
        <textarea
          disabled={disabled}
          rows={2}
          className={`${selectClass} h-auto`}
          value={value.notes ?? ''}
          onChange={(event) => set('notes', event.target.value || null)}
        />
      </Field>

      <div className="space-y-2 rounded-lg border border-border p-3">
        <label className="flex min-h-11 items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            disabled={disabled}
            checked={value.hasPlaybackIssues}
            onChange={(event) => set('hasPlaybackIssues', event.target.checked)}
            className="h-4 w-4 rounded border-input"
          />
          This disc has playback issues
        </label>
        {value.hasPlaybackIssues && (
          <Input
            disabled={disabled}
            value={value.playbackNotes ?? ''}
            placeholder="Freezes about an hour in"
            onChange={(event) => set('playbackNotes', event.target.value || null)}
          />
        )}
      </div>
    </div>
  )
}

/** A blank disc, for the add form and for resetting the edit form. */
export const EMPTY_COPY: CollectionItemFields = {
  formats: ['blu_ray'],
  location: null,
  section: null,
  shelf: null,
  subCategory: null,
  edition: null,
  notes: null,
  condition: null,
  hasPlaybackIssues: false,
  playbackNotes: null,
  purchasePrice: null,
  purchaseSource: null,
  purchaseDate: null,
}
