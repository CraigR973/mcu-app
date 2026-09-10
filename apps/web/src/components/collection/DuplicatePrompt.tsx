import { AlertTriangle, ArrowUpCircle } from 'lucide-react'

import { formatLabel, type DuplicateCheck, type DuplicateReason } from '@/lib/api'

interface Props {
  duplicate: DuplicateCheck
  onConfirm: (reason: DuplicateReason) => void
  onCancel: () => void
  pending?: boolean
}

/**
 * §3.5's confirmation: "add another copy" or "this is an upgrade".
 *
 * `isUpgrade` is decided by the API against the same format ranking the
 * `best_format_owned` trigger enforces, so the wording here cannot disagree with what
 * the film's card will say once the disc is saved.
 */
export default function DuplicatePrompt({ duplicate, onConfirm, onCancel, pending }: Props) {
  const owned = formatLabel(duplicate.bestFormatOwned)

  return (
    <section
      className="space-y-3 rounded-xl border border-warning/40 bg-warning/10 p-4"
      role="alert"
    >
      <div className="flex items-start gap-2">
        {duplicate.isUpgrade ? (
          <ArrowUpCircle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
        ) : (
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
        )}
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            {duplicate.isUpgrade
              ? `You already own this on ${owned}`
              : 'This film is already in the collection'}
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {duplicate.existingCopies.length === 1
              ? 'One copy is already on a shelf.'
              : `${duplicate.existingCopies.length} copies are already on a shelf.`}
          </p>
        </div>
      </div>

      <ul className="space-y-1.5">
        {duplicate.existingCopies.map((copy) => (
          <li
            key={copy.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-background/70 px-3 py-2 text-xs"
          >
            <span className="font-medium text-foreground">
              {copy.formats.map((format) => formatLabel(format)).join(' + ')}
            </span>
            <span className="text-muted-foreground">{copy.locationLabel}</span>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-2 pt-1">
        {duplicate.isUpgrade && (
          <button
            type="button"
            disabled={pending}
            onClick={() => onConfirm('upgrade')}
            className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground disabled:opacity-60"
          >
            This is an upgrade
          </button>
        )}
        <button
          type="button"
          disabled={pending}
          onClick={() => onConfirm('another_copy')}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold disabled:opacity-60 ${
            duplicate.isUpgrade
              ? 'bg-secondary text-secondary-foreground'
              : 'bg-primary text-primary-foreground'
          }`}
        >
          Add another copy
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={onCancel}
          className="rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </section>
  )
}
