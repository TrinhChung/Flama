// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { copiedImageLink } from './copiedImageLink'

function clipboard(formats: Record<string, string>) {
  return { getData: (format: string) => formats[format] || '' }
}

describe('copiedImageLink', () => {
  it("reads the image address from Chrome's HTML snippet", () => {
    expect(copiedImageLink(clipboard({
      'text/html': '<!--StartFragment--><img src="https://cdn.example.com/a/dog.webp?w=600"><!--EndFragment-->',
    }))).toBe('https://cdn.example.com/a/dog.webp?w=600')
  })

  it('keeps an image copied from Flama as its managed media path', () => {
    expect(copiedImageLink(clipboard({
      'text/html': `<img src="${window.location.origin}/media/proxy/0f9e8d7c-1234">`,
    }))).toBe('/media/proxy/0f9e8d7c-1234')
  })

  it('falls back to the URI list and skips addresses that cannot be stored', () => {
    expect(copiedImageLink(clipboard({
      'text/html': '<img src="http://plain-http.example.com/a.png">',
      'text/uri-list': '# comment\r\nhttps://example.com/b.png',
    }))).toBe('https://example.com/b.png')
    expect(copiedImageLink(clipboard({ 'text/html': '<img src="data:image/png;base64,AAAA">' }))).toBeNull()
    expect(copiedImageLink(clipboard({}))).toBeNull()
    expect(copiedImageLink(null)).toBeNull()
  })
})
