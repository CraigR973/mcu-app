/**
 * Web Speech API declarations — Batch 32, §9.5.
 *
 * **TypeScript's `lib.dom.d.ts` does not declare any of this.** The API has been in Chrome
 * since 2013 and is still not in the standard DOM library, so the alternative to writing it
 * out is casting `window` to `any` at every call site — which would silently accept a
 * misspelled event name and produce a mic button that listens and never reports anything.
 *
 * Only the surface `useSpeechRecognition` actually uses is declared. A larger, half-right
 * copy of the whole spec would be worse than a small exact one.
 */

interface SpeechRecognitionAlternative {
  readonly transcript: string
  readonly confidence: number
}

interface SpeechRecognitionResult {
  readonly length: number
  /** True once the engine has stopped revising this phrase. */
  readonly isFinal: boolean
  item(index: number): SpeechRecognitionAlternative
  [index: number]: SpeechRecognitionAlternative
}

interface SpeechRecognitionResultList {
  readonly length: number
  item(index: number): SpeechRecognitionResult
  [index: number]: SpeechRecognitionResult
}

interface SpeechRecognitionEvent extends Event {
  /** Where in `results` this event's new content starts — **not** always 0. */
  readonly resultIndex: number
  readonly results: SpeechRecognitionResultList
}

/** `not-allowed` and `service-not-allowed` are permission; `no-speech` is a non-event. */
type SpeechRecognitionErrorCode =
  | 'aborted'
  | 'audio-capture'
  | 'bad-grammar'
  | 'language-not-supported'
  | 'network'
  | 'no-speech'
  | 'not-allowed'
  | 'service-not-allowed'

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: SpeechRecognitionErrorCode
  readonly message: string
}

interface SpeechRecognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
}

declare const SpeechRecognition: { new (): SpeechRecognition }

interface Window {
  SpeechRecognition?: { new (): SpeechRecognition }
  /** Chrome and Safari still only expose the prefixed constructor. */
  webkitSpeechRecognition?: { new (): SpeechRecognition }
}
