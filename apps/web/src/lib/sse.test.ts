import { describe, expect, it } from 'vitest'

import { describeToolCall, readSse, type ChatStreamEvent } from './api'

/**
 * The chat stream parser.
 *
 * **Its failure mode is silent and partial.** A chunk boundary falls wherever the network
 * puts it, so a frame routinely arrives split across two reads; a parser that assumes one
 * chunk is one event drops text at random and the answer merely reads oddly. There is no
 * error anywhere, which is why this has its own tests.
 */
function responseOf(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(stream, { status: 200 })
}

async function collect(response: Response): Promise<ChatStreamEvent[]> {
  const events: ChatStreamEvent[] = []
  for await (const event of readSse(response)) events.push(event)
  return events
}

describe('readSse', () => {
  it('reads one frame per event', async () => {
    const events = await collect(
      responseOf([
        'data: {"kind":"text","text":"Hello "}\n\n',
        'data: {"kind":"text","text":"world"}\n\n',
        'data: {"kind":"done","text":""}\n\n',
      ]),
    )

    expect(events.map((event) => event.kind)).toEqual(['text', 'text', 'done'])
    expect(events[0].text + events[1].text).toBe('Hello world')
  })

  it('reassembles a frame split across two reads', async () => {
    // The case that loses text without erroring.
    const events = await collect(
      responseOf(['data: {"kind":"text","te', 'xt":"split"}\n\n']),
    )

    expect(events).toHaveLength(1)
    expect(events[0].text).toBe('split')
  })

  it('reads several frames arriving in one chunk', async () => {
    const events = await collect(
      responseOf(['data: {"kind":"text","text":"a"}\n\ndata: {"kind":"text","text":"b"}\n\n']),
    )

    expect(events.map((event) => event.text)).toEqual(['a', 'b'])
  })

  it('survives a malformed frame rather than dropping the rest of the answer', async () => {
    const events = await collect(
      responseOf(['data: not json\n\n', 'data: {"kind":"text","text":"still here"}\n\n']),
    )

    expect(events).toHaveLength(1)
    expect(events[0].text).toBe('still here')
  })

  it('carries the pending tool calls on a confirm event', async () => {
    const frame = JSON.stringify({
      kind: 'confirm',
      text: '',
      toolCalls: [{ id: 'abc', toolName: 'add_to_wanted', input: { title: 'Nosferatu' } }],
    })

    const events = await collect(responseOf([`data: ${frame}\n\n`]))

    expect(events[0].kind).toBe('confirm')
    expect(events[0].toolCalls?.[0].toolName).toBe('add_to_wanted')
  })

  it('reports a failed request as an error event rather than throwing', async () => {
    // The chat has to render something; an exception mid-stream leaves a blank bubble.
    const events = await collect(new Response('nope', { status: 500 }))

    expect(events[0].kind).toBe('error')
  })
})

describe('describeToolCall', () => {
  it('says what will actually happen, not which tool will run', () => {
    // §9.4's prompt has to be a decision somebody can make. "Claude wants to use a tool"
    // is not one.
    const sentence = describeToolCall({
      toolName: 'add_to_wanted',
      input: { title: 'Nosferatu', preferredFormat: '4k_uhd', maxPrice: '19.99' },
    })

    expect(sentence).toContain('Nosferatu')
    expect(sentence).toContain('wanted list')
    expect(sentence).toContain('19.99')
  })

  it('describes a watch log in the first person', () => {
    const sentence = describeToolCall({
      toolName: 'log_watch',
      input: { title: 'Heat', rating: 4.5 },
    })

    expect(sentence).toContain('you watched Heat')
    expect(sentence).toContain('4.5')
  })

  it('names the exact film the server settled, with its year and the date', () => {
    // Batch X7: "Halloween" is two films; the card says which one will be written.
    const sentence = describeToolCall({
      toolName: 'log_watch',
      input: {
        title: 'Halloween',
        watchedAt: '2026-10-12',
        resolved: { movieId: 'x', tmdbId: null, label: 'Halloween (2018)' },
      },
    })

    expect(sentence).toBe('Record that you watched Halloween (2018) on 12 Oct 2026.')
  })

  it('falls back to naming the tool for one it does not know', () => {
    expect(describeToolCall({ toolName: 'future_tool', input: { a: 1 } })).toContain(
      'future_tool',
    )
  })
})
