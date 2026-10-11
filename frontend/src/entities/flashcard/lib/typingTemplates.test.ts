// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'
import { describe, expect, it, vi } from 'vitest'
import { renderCardSide, patchRenderContext } from './clientRenderer'
import type { CardRenderTemplate } from '../model/types'

type TestWindow = Window & { HTMLMediaElement: typeof HTMLMediaElement; Event: typeof Event; KeyboardEvent: typeof KeyboardEvent; eval: (source: string) => void }
const { JSDOM } = createRequire(import.meta.url)('jsdom') as {
  JSDOM: new (html: string, options: { runScripts: 'dangerously'; pretendToBeVisual: boolean; beforeParse: (window: TestWindow) => void }) => { window: TestWindow }
}
const slugs = ['typing-reading', 'typing-meaning', 'typing-image', 'typing-dictation']

function render(slug: string, values: Record<string, unknown>, side: 'front' | 'back' = 'back', blocked = false) {
  const folder = resolve(process.cwd(), '..', 'note-type-templates', slug)
  const source = readFileSync(resolve(folder, `${side}.html`), 'utf8')
  const prototype = JSON.parse(readFileSync(resolve(folder, 'prototype.json'), 'utf8'))
  const scripts = [...source.matchAll(/<script[^>]*>[\s\S]*?<\/script>/g)].map(match => match[0])
  const template: CardRenderTemplate = {
    renderer_abi: 'flama-client-mustache.v1', version: 'fixture', front_source: '', back_source: '',
    front_inline_scripts: [], back_inline_scripts: [], shared_css: readFileSync(resolve(folder, 'style.css'), 'utf8'),
    field_defs: prototype.note_type.field_defs.map((field: Record<string, unknown>) => ({ ...field, id: field.name })),
  }
  template[`${side}_source`] = source.replace(/<script[^>]*>[\s\S]*?<\/script>/g, '')
  template[`${side}_inline_scripts`] = scripts
  const result = renderCardSide(template, {
    renderer_abi: template.renderer_abi, field_values: values,
    render_context: patchRenderContext({}, values, template.field_defs), media: [],
  }, side)
  const played: string[] = []
  const timers: Array<() => void> = []
  const dom = new JSDOM(result.html, { runScripts: 'dangerously', pretendToBeVisual: true,
    beforeParse(window) {
      window.HTMLMediaElement.prototype.play = vi.fn(function (this: HTMLMediaElement) {
        played.push(this.getAttribute('src') || '')
        return blocked ? Promise.reject(new Error('Autoplay blocked')) : Promise.resolve()
      })
      window.HTMLMediaElement.prototype.pause = vi.fn()
      window.setTimeout = ((callback: () => void) => { timers.push(callback); return timers.length }) as typeof window.setTimeout
      window.clearTimeout = ((id: number) => { timers[id - 1] = () => undefined }) as typeof window.clearTimeout
    },
  })
  return { window: dom.window, played, scripts, advance: () => { const pending = timers.splice(0); pending.forEach(callback => callback()) } }
}

const audio = '<audio src="/media/proxy/word"></audio>'
const exampleAudio = '<audio src="/media/proxy/example"></audio>'
const values = { PromptText: 'apple', PromptImage: '<img src="/media/proxy/image">', Answer: 'apple', Audio: audio,
  Example: '<p>This is an apple.</p>', ExampleTranslation: '<p>Đây là một quả táo.</p>', ExampleAudio: exampleAudio,
  Usage: '<p>Dùng khi gọi tên loại quả.</p>', UsageTranslation: '<p>A common noun.</p>', Notes: '<p>Ghi chú riêng.</p>' }

describe.each(['typing-reading', 'typing-meaning', 'typing-image', 'typing-answer', 'typing-dictation'])('native answer alternatives: %s', slug => {
  it('accepts each item independently, with punctuation kept inside its answer', () => {
    const dom = render(slug, { Prompt: 'Question', PromptText: 'Question', Answer: ['first, literal', 'second; literal'] }, 'front')
    const doc = dom.window.document
    const input = doc.querySelector<HTMLInputElement>('.ft-input, #cz-input')!
    const button = doc.querySelector<HTMLElement>('.ft-check, #cz-check')
    const status = doc.querySelector<HTMLElement>('.ft-status, #cz-result')!
    for (const answer of ['first, literal', 'second; literal']) {
      if (slug === 'typing-dictation') doc.querySelector<HTMLElement>('.ft-dict-reset')!.click()
      input.value = answer
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
      if (button) button.click()
      else input.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
      expect(status.className).toMatch(/is-correct|cz-ok/)
    }
    if (slug === 'typing-dictation') doc.querySelector<HTMLElement>('.ft-dict-reset')!.click()
    input.value = 'first, literal,second; literal'
    input.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
    if (button) button.click()
    else input.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    expect(status.className).toMatch(/is-incorrect|cz-bad/)
    dom.window.close()
  })
})

it('renders one answer panel and one Meaning section with native lists', () => {
  const dom = render('typing-reading', { PromptText: '你好', Answer: ['nǐ hǎo', 'ni hao'], Meaning: ['xin chào', 'xin chào'] })
  const doc = dom.window.document
  expect(doc.querySelectorAll('.ft-answer-panel')).toHaveLength(1)
  expect(doc.querySelectorAll('[data-info="Meaning"]')).toHaveLength(1)
  expect([...doc.querySelectorAll('.ft-info-list li')].map(el => el.textContent)).toEqual(['xin chào', 'xin chào'])
  expect(doc.querySelector('.ft-answer-primary')!.textContent).toBe('nǐ hǎo')
  expect(doc.querySelector('.ft-answer-variants')!.textContent).toBe('ni hao')
  dom.window.close()
})

describe.each(slugs)('typing back audio: %s', slug => {
  it('plays primary then example once, and a manual replay does not chain', () => {
    const dom = render(slug, values), doc = dom.window.document
    expect(dom.played).toEqual(['/media/proxy/word'])
    doc.querySelector('.ft-primary-audio audio')!.dispatchEvent(new dom.window.Event('ended'))
    expect(dom.played).toHaveLength(1)
    dom.advance()
    expect(dom.played).toEqual(['/media/proxy/word', '/media/proxy/example'])
    doc.querySelector('.ft-primary-audio button')!.dispatchEvent(new dom.window.Event('click'))
    doc.querySelector('.ft-primary-audio audio')!.dispatchEvent(new dom.window.Event('ended'))
    dom.advance()
    expect(dom.played).toEqual(['/media/proxy/word', '/media/proxy/example', '/media/proxy/word'])
    dom.window.close()
  })
  it('plays example alone and keeps optional usage/notes independently visible', () => {
    const dom = render(slug, { Answer: 'apple', ExampleAudio: exampleAudio, UsageTranslation: 'Only a translated note', Notes: 'Notes' })
    expect(dom.played).toEqual(['/media/proxy/example'])
    expect(dom.window.document.querySelector('[data-info="UsageTranslation"]')?.textContent).toContain('Only a translated note')
    expect(dom.window.document.querySelector('[data-info="Notes"]')?.textContent).toContain('Notes')
    dom.window.close()
  })
  it('hides empty media and optional wrappers without hiding the prompt', () => {
    const dom = render(slug, { PromptText: 'apple', Answer: 'apple', ExampleAudio: '<audio></audio>' }), doc = dom.window.document
    expect(dom.played).toEqual([])
    expect(doc.querySelector('.ft-example-group')?.hasAttribute('hidden')).toBe(true)
    expect(doc.querySelector('.ft-back-content')?.hasAttribute('hidden')).toBe(true)
    if (slug === 'typing-reading' || slug === 'typing-meaning') expect(doc.querySelector('.ft-prompt-line')?.hasAttribute('hidden')).toBe(false)
    dom.window.close()
  })
  it('plays multiple primary clips before the example and cancels pending play on page exit', () => {
    const dom = render(slug, { ...values, Audio: audio + '<audio src="/media/proxy/word2"></audio>' }), doc = dom.window.document
    doc.querySelectorAll('.ft-primary-audio audio')[0].dispatchEvent(new dom.window.Event('ended'))
    expect(dom.played).toEqual(['/media/proxy/word', '/media/proxy/word2'])
    doc.querySelectorAll('.ft-primary-audio audio')[1].dispatchEvent(new dom.window.Event('ended'))
    dom.window.dispatchEvent(new dom.window.Event('pagehide'))
    dom.advance()
    expect(dom.played).toHaveLength(2)
    expect(doc.querySelectorAll('[aria-pressed="true"]')).toHaveLength(0)
    dom.window.close()
  })
  it('shows a replay fallback when autoplay is blocked', async () => {
    const dom = render(slug, values, 'back', true)
    await expect.poll(() => dom.window.document.querySelector('.ft-primary-audio [role="status"]')?.textContent).toContain('Nhấn nút nghe')
    expect(dom.window.document.querySelector('.ft-primary-audio button')?.getAttribute('aria-pressed')).toBe('false')
    dom.window.close()
  })
  it('keeps the front silent and ignores duplicate script execution on the same back', () => {
    const front = render(slug, values, 'front')
    expect(front.played).toEqual([])
    front.window.close()
    const back = render(slug, values)
    back.window.eval(back.scripts[0].replace(/^<script[^>]*>|<\/script>$/g, ''))
    expect(back.played).toHaveLength(1)
    back.window.close()
  })
})
