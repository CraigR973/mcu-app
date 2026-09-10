import { cn } from '@/lib/utils'

/**
 * §3.8 — *"a 4K disc with Dolby Vision + Atmos shows three distinct coloured badges"*.
 *
 * **Three colours, and they are not decoration.** Resolution, HDR and audio are three
 * different claims about a disc, and a row of identically-styled pills makes them one
 * blur — the criterion says *distinct* for a reason. Amber for resolution, violet for HDR,
 * teal for audio, and each carries a `title` so the abbreviations are readable to somebody
 * who does not already know them.
 *
 * **Nothing is inferred.** A disc with no `videoSpecs` renders no badges rather than a grey
 * "unknown" — until Blu-ray.com has been asked, the app genuinely does not know, and a
 * placeholder that looks like data is how a catalogue starts lying.
 */

interface Props {
  videoSpecs: Record<string, unknown> | null
  audioSpecs: Array<Record<string, unknown>> | null
  regionCode?: string | null
  className?: string
}

const RESOLUTION_LABEL: Record<string, string> = {
  '2160p': '4K',
  '1080p': 'HD',
  '1080i': 'HD',
  '720p': 'HD',
  '480p': 'SD',
}

/** Highest-value audio format on the disc — the one worth a badge. */
const AUDIO_RANK = [
  'Dolby Atmos',
  'DTS:X',
  'Dolby TrueHD',
  'DTS-HD MA',
  'Dolby Digital Plus',
  'DTS',
  'Dolby Digital',
  'LPCM',
]

function Badge({
  children,
  tone,
  title,
}: {
  children: React.ReactNode
  tone: 'resolution' | 'hdr' | 'audio' | 'region'
  title?: string
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
        tone === 'resolution' && 'bg-quality-4k/15 text-quality-4k',
        tone === 'hdr' && 'bg-quality-hdr/15 text-quality-hdr',
        tone === 'audio' && 'bg-quality-audio/15 text-quality-audio',
        tone === 'region' && 'bg-muted text-muted-foreground',
      )}
    >
      {children}
    </span>
  )
}

export function SpecBadges({ videoSpecs, audioSpecs, regionCode, className }: Props) {
  const resolution =
    typeof videoSpecs?.resolution === 'string' ? (videoSpecs.resolution as string) : null
  const hdr = Array.isArray(videoSpecs?.hdr) ? (videoSpecs.hdr as string[]) : []

  const formats = (audioSpecs ?? [])
    .map((track) => (typeof track.format === 'string' ? track.format : null))
    .filter((value): value is string => Boolean(value))
  const bestAudio = AUDIO_RANK.find((candidate) => formats.includes(candidate)) ?? null

  if (!resolution && hdr.length === 0 && !bestAudio && !regionCode) return null

  return (
    <div className={cn('flex flex-wrap items-center gap-1', className)}>
      {resolution ? (
        <Badge tone="resolution" title={`Resolution: ${resolution}`}>
          {RESOLUTION_LABEL[resolution] ?? resolution}
        </Badge>
      ) : null}
      {hdr.map((format) => (
        <Badge key={format} tone="hdr" title={`High dynamic range: ${format}`}>
          {format === 'Dolby Vision' ? 'DV' : format}
        </Badge>
      ))}
      {bestAudio ? (
        <Badge tone="audio" title={`Best audio track: ${bestAudio}`}>
          {bestAudio === 'Dolby Atmos' ? 'Atmos' : bestAudio}
        </Badge>
      ) : null}
      {regionCode ? (
        <Badge tone="region" title={`Blu-ray region: ${regionCode}`}>
          {regionCode === 'Free' ? 'Region free' : `Region ${regionCode}`}
        </Badge>
      ) : null}
    </div>
  )
}
