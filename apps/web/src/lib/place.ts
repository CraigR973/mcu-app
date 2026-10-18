/** Where a copy is kept, said once (Batch X12a, UX48-05). Before it the film page printed a
 *  copy's shelf twice ("Front 4th Shelf", then "Front · 4th shelf"), and two other screens
 *  each had their own copy of the rule. */
export interface Place {
  location: string | null
  section: string | null
  shelf: string | null
}

/** The recorded place when there is one, else the section and shelf it is filed under. */
export function placeLabel(place: Place): string {
  if (place.location) return place.location
  if (place.section) return `${place.section}${place.shelf ? ` · ${place.shelf} shelf` : ''}`
  return 'No place recorded'
}
