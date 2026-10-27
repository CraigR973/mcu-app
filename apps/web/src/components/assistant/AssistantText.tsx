import { memo, type ReactNode } from 'react'

// A bounded text treatment, not an HTML/Markdown engine. Unsupported syntax remains text.
// In particular, model output never becomes HTML, an image request or an inferred film link.
const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^[\]\n]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s<>]+)/g

function link(label: string, target: string, key: number): ReactNode {
  try {
    const url = new URL(target)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return label
    return <a key={key} href={url.href} target="_blank" rel="noopener noreferrer" className="break-all text-primary underline underline-offset-2">{label}</a>
  } catch {
    return label
  }
}

function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index} className="rounded bg-muted px-1 font-mono">{part.slice(1, -1)}</code>
    const named = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part)
    if (named) return link(named[1], named[2], index)
    if (/^https?:\/\//.test(part)) {
      const target = part.replace(/[.,;!?)]+$/, '')
      return <span key={index}>{link(target, target, index)}{part.slice(target.length)}</span>
    }
    return part
  })
}

export const AssistantText = memo(function AssistantText({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  for (let i = 0; i < lines.length;) {
    const line = lines[i]
    if (!line.trim()) { i += 1; continue }
    const heading = /^#{1,3}\s+(.+)$/.exec(line)
    if (heading) {
      blocks.push(<h3 key={i} className="font-semibold">{inline(heading[1])}</h3>)
      i += 1
      continue
    }
    const item = /^\s*(?:[-*]|\d+\.)\s+(.+)$/.exec(line)
    if (item) {
      const ordered = /^\s*\d+\./.test(line)
      const start = i
      const entries: ReactNode[] = []
      while (i < lines.length) {
        const match = /^\s*(?:[-*]|\d+\.)\s+(.+)$/.exec(lines[i])
        if (!match || /^\s*\d+\./.test(lines[i]) !== ordered) break
        entries.push(<li key={i}>{inline(match[1])}</li>)
        i += 1
      }
      blocks.push(ordered
        ? <ol key={start} className="list-decimal space-y-1 pl-5">{entries}</ol>
        : <ul key={start} className="list-disc space-y-1 pl-5">{entries}</ul>)
      continue
    }
    const start = i
    const paragraph = [line]
    i += 1
    while (i < lines.length && lines[i].trim() && !/^#{1,3}\s|^\s*(?:[-*]|\d+\.)\s/.test(lines[i])) {
      paragraph.push(lines[i]); i += 1
    }
    blocks.push(<p key={start} className="whitespace-pre-wrap">{inline(paragraph.join('\n'))}</p>)
  }
  return <div className="min-w-0 space-y-3 break-words text-sm leading-6 [overflow-wrap:anywhere]">{blocks}</div>
})
