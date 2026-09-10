import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Dictating a question instead of typing it — §9.5.
 *
 * **This is on-device speech recognition, not a transcription service.** Nothing is
 * uploaded by this app: the browser's own engine listens and hands back text. `microphone`
 * is already allowed for this origin by `vercel.json`'s Permissions-Policy (since Batch 2),
 * so no hosting change was needed.
 *
 * **The state is a union rather than a boolean for the same reason `usePushSubscription`'s
 * is.** "Not listening" covers at least four different situations — the browser has no
 * engine, the person refused the microphone, the microphone heard nothing, the network
 * dropped — and a button that renders them identically leaves somebody tapping it again.
 */
export type SpeechState =
  /** No engine. Firefox, and any browser without the prefixed constructor. */
  | 'unsupported'
  | 'idle'
  | 'listening'
  /** Refused at the browser or OS level. Only the person can undo it. */
  | 'denied'
  | 'error'

export interface UseSpeechRecognition {
  state: SpeechState
  /** What has been heard so far, including the words still being revised. */
  transcript: string
  error: string | null
  start: () => void
  stop: () => void
}

function constructorFor(): { new (): SpeechRecognition } | null {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

/** What each error code means to a person, rather than to a spec. */
function describe(code: SpeechRecognitionErrorCode): string {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'The microphone is blocked for this site. That has to be changed in browser settings.'
    case 'no-speech':
      return 'Nothing was heard. Try again a little closer to the microphone.'
    case 'audio-capture':
      return 'No microphone was found.'
    case 'network':
      return 'Speech recognition needs a connection and could not reach it.'
    case 'aborted':
      return ''
    default:
      return 'Speech recognition stopped unexpectedly.'
  }
}

export function useSpeechRecognition(
  onFinalTranscript?: (text: string) => void,
): UseSpeechRecognition {
  const [state, setState] = useState<SpeechState>('idle')
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  // Held in a ref so the recognition object's handlers never close over a stale callback —
  // they are assigned once and outlive several renders.
  const callbackRef = useRef(onFinalTranscript)
  callbackRef.current = onFinalTranscript

  useEffect(() => {
    if (!constructorFor()) setState('unsupported')
  }, [])

  // Abort on unmount, or the engine keeps the microphone open after the page has gone.
  useEffect(
    () => () => {
      recognitionRef.current?.abort()
      recognitionRef.current = null
    },
    [],
  )

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  const start = useCallback(() => {
    const Recognition = constructorFor()
    if (!Recognition) {
      setState('unsupported')
      return
    }
    // Starting an already-running recognition throws `InvalidStateError`, which is what a
    // double tap produces.
    recognitionRef.current?.abort()

    const recognition = new Recognition()
    recognitionRef.current = recognition
    recognition.lang = 'en-GB'
    // One phrase, then stop. A question to an assistant is a sentence, and `continuous`
    // leaves the microphone open until something explicitly closes it.
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    setTranscript('')
    setError(null)
    setState('listening')

    recognition.onresult = (event) => {
      let interim = ''
      let final = ''
      // From 0, not from `resultIndex`: with `interimResults` on, earlier entries are
      // revised in place, so rebuilding the whole string is what keeps it correct.
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index]
        const text = result[0].transcript
        if (result.isFinal) final += text
        else interim += text
      }
      setTranscript((final + interim).trim())
      if (final.trim()) callbackRef.current?.(final.trim())
    }

    recognition.onerror = (event) => {
      const message = describe(event.error)
      // `aborted` is what `stop()` and a re-tap produce. It is not a failure and must not
      // paint the button red.
      if (event.error === 'aborted') return
      setError(message || null)
      setState(
        event.error === 'not-allowed' || event.error === 'service-not-allowed'
          ? 'denied'
          : 'error',
      )
    }

    recognition.onend = () => {
      // Only back to idle if nothing already moved us to a terminal state.
      setState((current) => (current === 'listening' ? 'idle' : current))
    }

    try {
      recognition.start()
    } catch {
      setState('error')
      setError('Speech recognition would not start.')
    }
  }, [])

  return { state, transcript, error, start, stop }
}
