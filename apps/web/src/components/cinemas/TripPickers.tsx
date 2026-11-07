import type { TripPerson } from '@mcu/shared'

import { dayHeading } from '@/lib/cinemas'
import { tripClock, type TripDay } from '@/lib/cinema-trips'
import { cn } from '@/lib/utils'

/** Pick one time. Each is a toggle named for screen readers by its time, cinema and day. */
export function TripTimes({ days, today, selected, onSelect, disabled }: {
  days: TripDay[]; today: string; selected: string | null; onSelect: (id: string) => void; disabled?: boolean
}) {
  if (days.length === 0) {
    return <p className="text-sm text-muted-foreground">No other confirmed times are listed for this film now.</p>
  }
  return (
    <div className="space-y-4">
      {days.map(({ day, cinemas }) => (
        <section key={day} aria-label={dayHeading(day, today)} className="space-y-2">
          <h4 className="text-sm font-semibold">{dayHeading(day, today)}</h4>
          {cinemas.map(({ venue, showings }) => (
            <div key={venue.id} className="space-y-1.5">
              <p className="text-xs text-muted-foreground">{venue.name}</p>
              <ul className="flex flex-wrap gap-2">
                {showings.map((showing) => {
                  const on = selected === showing.id
                  return (
                    <li key={showing.id}>
                      <button
                        type="button"
                        aria-pressed={on}
                        disabled={disabled}
                        aria-label={`${tripClock(showing.startsAtUtc, showing.formats)} at ${venue.name}, ${dayHeading(day, today)}`}
                        onClick={() => onSelect(showing.id)}
                        className={cn(
                          'touch-target min-h-11 min-w-[4.5rem] rounded-md border px-3 py-1.5 text-sm font-semibold tabular-nums transition-colors disabled:opacity-50',
                          on ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-background hover:border-primary/45 hover:bg-primary/5',
                        )}
                      >
                        {tripClock(showing.startsAtUtc, showing.formats)}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}

/** Pick people: everyone who can be invited, none ticked (#345 §6). Nothing assumes two. */
export function PeoplePicker({ people, chosen, onChange, disabled }: {
  people: TripPerson[]; chosen: ReadonlySet<string>; onChange: (next: Set<string>) => void; disabled?: boolean
}) {
  if (people.length === 0) return <p className="text-sm text-muted-foreground">There is nobody else to invite.</p>
  return (
    <ul className="divide-y divide-border rounded-md border border-border">
      {people.map((person) => (
        <li key={person.profileId}>
          <label className="flex min-h-12 cursor-pointer items-center gap-3 px-3 text-sm">
            <input
              type="checkbox"
              className="size-5 accent-primary"
              checked={chosen.has(person.profileId)}
              disabled={disabled}
              onChange={(event) => {
                const next = new Set(chosen)
                if (event.target.checked) next.add(person.profileId)
                else next.delete(person.profileId)
                onChange(next)
              }}
            />
            <span className="font-medium">{person.displayName}</span>
          </label>
        </li>
      ))}
    </ul>
  )
}
