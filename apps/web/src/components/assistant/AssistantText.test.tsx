// @vitest-environment happy-dom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { AssistantText } from './AssistantText'

afterEach(cleanup)
describe('AssistantText', () => {
  it('makes ordinary paragraphs, emphasis, lists and links readable', () => {
    const { container } = render(<AssistantText text={'# Shelf results\n\n**Jaws** is on `B4`.\n\n- First film\n- Second film\n\n[Details](https://example.com/film) and https://example.com/source.'} />)
    expect(screen.getByRole('heading', { name: 'Shelf results' })).not.toBeNull()
    expect(container.querySelector('strong')?.textContent).toBe('Jaws')
    expect(container.querySelector('code')?.textContent).toBe('B4')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByRole('link', { name: 'Details' }).getAttribute('href')).toBe('https://example.com/film')
    expect(screen.getByRole('link', { name: 'https://example.com/source' }).getAttribute('rel')).toBe('noopener noreferrer')
    expect(container.textContent).toContain('https://example.com/source.')
  })
  it('keeps raw HTML and unsafe protocols inert, without loading images', () => {
    const { container } = render(<AssistantText text={'<img src=x onerror=alert(1)> <script>bad()</script>\n\n[Bad](javascript:alert(1)) [Data](data:text/html,bad)\n\nhttps://user:password@example.com/private'} />)
    expect(container.querySelectorAll('img, script, a')).toHaveLength(0)
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(container.textContent).toContain('[Bad](javascript:alert(1))')
  })
  it('keeps streamed partial and unsupported markup as text', () => {
    const { container } = render(<AssistantText text={'**An unfinished heading\n\n1. One\n2. Two\n\n[unfinished\n```\nplain'} />)
    expect(container.textContent).toContain('**An unfinished heading')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(container.querySelectorAll('a')).toHaveLength(0)
  })
})
