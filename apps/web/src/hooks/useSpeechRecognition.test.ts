// @vitest-environment happy-dom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useSpeechRecognition } from './useSpeechRecognition'

/**
 * §9.5's engine handling.
 *
 * **The acceptance criterion needs a person speaking and is deferred to the owner.** What
 * *is* testable here is everything around the microphone: that a browser without an engine
 * says so rather than offering a dead button, that a refusal is distinguishable from
 * silence, and that interim results are assembled rather than concatenated — the last one
 * being the bug that produces "where where is where is Heat".
 */

class FakeRecognition {
  lang = ''
  continuous = false
  interimResults = false
  maxAlternatives = 1
  onresult: ((event: SpeechRecognitionEvent) => void) | null = null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null = null
  onend: (() => void) | null = null
  onstart: (() => void) | null = null
  started = 0
  aborted = 0
  stopped = 0

  start() {
    this.started += 1
  }
  stop() {
    this.stopped += 1
  }
  abort() {
    this.aborted += 1
  }
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {
    return true
  }

  /** Deliver a results event shaped the way the browser shapes one. */
  emit(phrases: Array<{ text: string; final: boolean }>) {
    const results = phrases.map((phrase) => {
      const result = [{ transcript: phrase.text, confidence: 0.9 }] as unknown as
        SpeechRecognitionResult
      Object.defineProperty(result, 'isFinal', { value: phrase.final })
      return result
    }) as unknown as SpeechRecognitionResultList
    Object.defineProperty(results, 'length', { value: phrases.length })
    this.onresult?.({ resultIndex: 0, results } as SpeechRecognitionEvent)
  }
}

let latest: FakeRecognition | null = null

function install() {
  latest = null
  ;(window as Window).webkitSpeechRecognition = function () {
    latest = new FakeRecognition()
    return latest
  } as unknown as { new (): SpeechRecognition }
}

afterEach(() => {
  cleanup()
  delete (window as Window).SpeechRecognition
  delete (window as Window).webkitSpeechRecognition
  vi.restoreAllMocks()
})

describe('useSpeechRecognition', () => {
  it('reports unsupported where the browser has no engine', () => {
    // Firefox, today. The button renders nothing rather than a permanently dead control.
    const { result } = renderHook(() => useSpeechRecognition())

    expect(result.current.state).toBe('unsupported')
  })

  it('starts listening when asked', () => {
    install()
    const { result } = renderHook(() => useSpeechRecognition())

    act(() => result.current.start())

    expect(result.current.state).toBe('listening')
    expect(latest?.started).toBe(1)
    expect(latest?.continuous).toBe(false)
    expect(latest?.lang).toBe('en-GB')
  })

  it('rebuilds the whole phrase rather than appending each revision', () => {
    // **The bug this guards.** With `interimResults` on, earlier entries are revised in
    // place; appending every event produces "where where is where is Heat".
    install()
    const { result } = renderHook(() => useSpeechRecognition())
    act(() => result.current.start())

    act(() => latest?.emit([{ text: 'where', final: false }]))
    act(() => latest?.emit([{ text: 'where is Heat', final: false }]))

    expect(result.current.transcript).toBe('where is Heat')
  })

  it('hands a finished phrase to the caller', () => {
    install()
    const heard = vi.fn()
    const { result } = renderHook(() => useSpeechRecognition(heard))
    act(() => result.current.start())

    act(() => latest?.emit([{ text: 'Where is Heat shelved', final: true }]))

    expect(heard).toHaveBeenCalledWith('Where is Heat shelved')
  })

  it('separates a refused microphone from a quiet one', () => {
    // Different problems, different answers: one is a browser setting, the other is
    // "say it again". A single "not listening" state would show the same thing for both.
    install()
    const { result } = renderHook(() => useSpeechRecognition())
    act(() => result.current.start())

    act(() =>
      latest?.onerror?.({ error: 'not-allowed', message: '' } as SpeechRecognitionErrorEvent),
    )

    expect(result.current.state).toBe('denied')
    expect(result.current.error).toContain('blocked')
  })

  it('treats no-speech as an ordinary outcome, not a failure state', () => {
    install()
    const { result } = renderHook(() => useSpeechRecognition())
    act(() => result.current.start())

    act(() =>
      latest?.onerror?.({ error: 'no-speech', message: '' } as SpeechRecognitionErrorEvent),
    )

    expect(result.current.state).toBe('error')
    expect(result.current.error).toContain('Nothing was heard')
  })

  it('does not paint an abort as an error', () => {
    // `stop()` and a re-tap both produce `aborted`. Neither is a failure.
    install()
    const { result } = renderHook(() => useSpeechRecognition())
    act(() => result.current.start())

    act(() => latest?.onerror?.({ error: 'aborted', message: '' } as SpeechRecognitionErrorEvent))

    expect(result.current.error).toBeNull()
  })

  it('aborts a running recognition before starting another', () => {
    // Starting one that is already running throws `InvalidStateError` — what a double tap
    // produces.
    install()
    const { result } = renderHook(() => useSpeechRecognition())
    act(() => result.current.start())
    const first = latest

    act(() => result.current.start())

    expect(first?.aborted).toBe(1)
  })

  it('releases the microphone when the component goes away', () => {
    install()
    const { result, unmount } = renderHook(() => useSpeechRecognition())
    act(() => result.current.start())
    const recognition = latest

    unmount()

    expect(recognition?.aborted).toBe(1)
  })

  it('returns to idle when the engine ends on its own', () => {
    install()
    const { result } = renderHook(() => useSpeechRecognition())
    act(() => result.current.start())

    act(() => latest?.onend?.())

    expect(result.current.state).toBe('idle')
  })
})
