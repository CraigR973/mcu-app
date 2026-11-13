import { dayAndDate, shortDay } from '@/lib/cinemas'
import { cn } from '@/lib/utils'

import { CHIP, CHIP_OFF, CHIP_ON } from './chip-styles'

/**
 * The day strip — AE5 (#355, point 4), shared since AF3 (#372) by At the cinema and each film's
 * page: All days first, then a chip per day, scrolling sideways and pinned while the times scroll
 * under it. A day with nothing under the current choice is greyed, not hidden.
 */
export function DayStrip({ days, selected, today, showing, onPick }: {
  days: string[]
  /** The day picked; null for All days. */
  selected: string | null
  today: string
  /** The days with something to show; any other is greyed. Omitted when every day has. */
  showing?: Set<string>
  onPick: (day: string | null) => void
}) {
  return (
    <div className="sticky top-0 z-10 -mx-4 border-b border-border bg-background/95 px-4 py-2 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <div role="group" aria-label="Day" className="flex gap-2 overflow-x-auto pb-1">
        {/* AF3: All days leads, so the default choice is in sight rather than at the far end. */}
        <button type="button" aria-pressed={selected === null} onClick={() => onPick(null)} className={cn(CHIP, selected === null ? CHIP_ON : CHIP_OFF)}>All days</button>
        {days.map((day) => {
          const empty = showing !== undefined && !showing.has(day)
          return (
            <button
              key={day}
              type="button"
              aria-pressed={selected === day}
              aria-label={dayAndDate(day)}
              title={empty ? 'Nothing showing' : undefined}
              onClick={() => onPick(day)}
              className={cn(CHIP, selected === day ? CHIP_ON : CHIP_OFF, empty && selected !== day && 'border-dashed text-muted-foreground opacity-60')}
            >
              {shortDay(day, today)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
