import {
  Bookmark,
  Clapperboard,
  Disc,
  Eye,
  Flame,
  Heart,
  Layers,
  Sparkles,
  Star,
  type LucideIcon,
} from 'lucide-react'
import type { SmartCollectionIcon } from '@mcu/shared'

/**
 * The nine icons a smart collection may carry — §6.31's "custom icons".
 *
 * **A static record, not a dynamic lookup.** The value comes out of a JSONB-adjacent
 * column that a person types into, and rendering it by looking a name up in lucide's
 * whole export surface would mean either importing the entire icon set into the bundle
 * or resolving an arbitrary server-supplied string to a component. The API refuses
 * anything outside this list and a CHECK constraint refuses it again; this is the third
 * place the same nine names are stated, and the one the bundler can tree-shake.
 */
export const COLLECTION_ICONS: Record<SmartCollectionIcon, LucideIcon> = {
  sparkles: Sparkles,
  star: Star,
  heart: Heart,
  clapperboard: Clapperboard,
  disc: Disc,
  eye: Eye,
  flame: Flame,
  bookmark: Bookmark,
  layers: Layers,
}

export const COLLECTION_ICON_NAMES = Object.keys(COLLECTION_ICONS) as SmartCollectionIcon[]
