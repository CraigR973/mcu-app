import { Mic, MicOff, Square } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition'
import { cn } from '@/lib/utils'

interface Props {
  /** Called with each finished phrase — this is what lands in the text input. */
  onTranscript: (text: string) => void
  /** Live text while the engine is still revising, for the caller to show. */
  onInterim?: (text: string) => void
  disabled?: boolean
}

/**
 * §9.5's mic button — *"tapping mic, speaking a query, sends correct transcription"*.
 *
 * **It fills the input; it does not send.** The engine mishears, and a button that
 * submitted on the last word would put a wrong question to the assistant with no chance to
 * fix it. The person reads what was heard and presses send — which is also what makes the
 * acceptance criterion checkable, since "correct transcription" is something they can see.
 *
 * Renders nothing at all where there is no engine, rather than a disabled button: a
 * permanently dead control is a worse answer than no control.
 */
export function MicButton({ onTranscript, onInterim, disabled }: Props) {
  const speech = useSpeechRecognition((text) => onTranscript(text))

  if (speech.state === 'unsupported') return null

  const listening = speech.state === 'listening'
  if (listening && onInterim) onInterim(speech.transcript)

  return (
    <div className="flex flex-col items-end">
      <Button
        type="button"
        variant={listening ? 'default' : 'outline'}
        size="icon"
        disabled={disabled || speech.state === 'denied'}
        aria-label={listening ? 'Stop listening' : 'Dictate a question'}
        aria-pressed={listening}
        onClick={() => (listening ? speech.stop() : speech.start())}
        className={cn(listening && 'animate-pulse')}
      >
        {speech.state === 'denied' ? (
          <MicOff className="h-4 w-4" aria-hidden />
        ) : listening ? (
          <Square className="h-4 w-4" aria-hidden />
        ) : (
          <Mic className="h-4 w-4" aria-hidden />
        )}
      </Button>
      {speech.error ? (
        <span className="mt-1 max-w-[14rem] text-right text-xs text-muted-foreground">
          {speech.error}
        </span>
      ) : null}
    </div>
  )
}
