// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'
import { describe, expect, it } from 'vitest'
import { renderCardSide, patchRenderContext } from './clientRenderer'
import type { CardRenderTemplate } from '../model/types'

const { JSDOM } = createRequire(import.meta.url)('jsdom') as {
  JSDOM: new (html: string, options: { runScripts: 'dangerously' }) => { window: Window }
}

function render(slug: string, values: Record<string, unknown>) {
  const folder = resolve(process.cwd(), '..', 'note-type-templates', slug)
  const source = readFileSync(resolve(folder, 'back.html'), 'utf8')
  const prototype = JSON.parse(readFileSync(resolve(folder, 'prototype.json'), 'utf8'))
  const scripts = [...source.matchAll(/<script[^>]*>[\s\S]*?<\/script>/g)].map((match) => match[0])
  const template: CardRenderTemplate = {
    renderer_abi: 'flama-client-mustache.v1', version: 'fixture', front_source: '',
    back_source: source.replace(/<script[^>]*>[\s\S]*?<\/script>/g, ''),
    front_inline_scripts: [], back_inline_scripts: scripts,
    shared_css: readFileSync(resolve(folder, 'style.css'), 'utf8'),
    field_defs: prototype.note_type.field_defs.map((field: Record<string, unknown>) => ({ ...field, id: field.name })),
  }
  const result = renderCardSide(template, {
    renderer_abi: template.renderer_abi, field_values: values,
    render_context: patchRenderContext({}, values, template.field_defs), media: [],
  }, 'back')
  return new JSDOM(result.html, { runScripts: 'dangerously' })
}

describe('array-backed template JavaScript through the client renderer', () => {
  it('renders native pairs once and keeps empty positions and literal punctuation', () => {
    const dom = render('advanced-vocabulary-card', {
      Vocabulary: 'native', Meaning: ['one', 'two'],
      Collocation: ['first, literal', 'second; literal', 'third'],
      Coollocation_VI: ['trùng', '', 'trùng'],
    })
    const doc = dom.window.document
    expect(doc.querySelectorAll('#coll-raw')).toHaveLength(1)
    expect(doc.querySelectorAll('#coll-pairs')).toHaveLength(1)
    expect(doc.querySelectorAll('.meaning-vi')).toHaveLength(1)
    expect([...doc.querySelectorAll('#coll-pairs .pair-left')].map(el => el.textContent)).toEqual(['first, literal', 'second; literal', 'third'])
    expect([...doc.querySelectorAll('#coll-pairs .pair-right')].map(el => el.textContent)).toEqual(['trùng', '', 'trùng'])
    dom.window.close()
  })

  it('keeps native Default items and its existing prose formatting without repeated blocks', () => {
    const dom = render('flama-default', { word: '食べる', reading: ['たべる', 'くう'],
      translation_vi: ['ăn; nguyên một mục', 'ăn; nguyên một mục'], meaning_jp: 'one$two' })
    const doc = dom.window.document
    expect(doc.querySelectorAll('[data-array-field="reading"]')).toHaveLength(1)
    expect(doc.querySelectorAll('[data-array-field="translation_vi"]')).toHaveLength(1)
    expect(doc.querySelector('[data-array-field="translation_vi"]')!.textContent).toContain('ăn; nguyên một mụcăn; nguyên một mục')
    expect(doc.querySelector('[auto-split]')!.querySelectorAll('br')).toHaveLength(1)
    expect(doc.querySelectorAll('[data-native-array-guard], [data-native-array-value]')).toHaveLength(0)
    dom.window.close()
  })
  it('keeps six EN/VI rows, duplicates, punctuation and missing translations', () => {
    const dom = render('advanced-vocabulary-card', {
      Vocabulary: 'parallel', Meaning: 'một; còn nguyên\nhai',
      Collocation: 'a\nb\nc; literal\nd\ne\nf', Coollocation_VI: 'trùng\nhai\ntrùng\nbốn\nnăm\nsáu',
      Antonym: 'one\ntwo\nthree', Antonym_VI: 'một\nhai',
    })
    const doc = dom.window.document
    expect([...doc.querySelectorAll('#coll-pairs .pair-left')].map((el) => el.textContent)).toEqual(['a', 'b', 'c; literal', 'd', 'e', 'f'])
    expect([...doc.querySelectorAll('#coll-pairs .pair-right')].map((el) => el.textContent)).toEqual(['trùng', 'hai', 'trùng', 'bốn', 'năm', 'sáu'])
    expect(doc.querySelectorAll('#ant-pairs .pair-left')).toHaveLength(3)
    expect(doc.querySelectorAll('#ant-pairs .pair-right')[2].textContent).toBe('')
    const meaning = doc.querySelector('[data-array-field="Meaning"]')!
    expect(meaning.querySelectorAll('br')).toHaveLength(1)
    expect(meaning.querySelectorAll('p, div')).toHaveLength(0)
    expect(meaning.textContent).toContain('một; còn nguyên')
    dom.window.close()
  })

  it('lets Default arrays break naturally and retains legacy prose formatting', () => {
    const dom = render('flama-default', { word: '食べる', reading: 'たべる\nくう', translation_vi: 'ăn; nguyên một mục\nhai', meaning_jp: 'one$two' })
    const doc = dom.window.document
    for (const name of ['reading', 'translation_vi']) {
      const field = doc.querySelector(`[data-array-field="${name}"]`)!
      expect(field.querySelectorAll('br')).toHaveLength(1)
      expect(field.querySelectorAll('p, div')).toHaveLength(0)
      expect((field as HTMLElement).style.display).toBe('')
    }
    expect(doc.querySelector('[data-array-field="translation_vi"]')!.textContent).toContain('ăn; nguyên một mục')
    expect(doc.querySelector('[auto-split]')!.querySelectorAll('br')).toHaveLength(1)
    dom.window.close()
  })

  it.each(['flama-default', 'advanced-vocabulary-card'])('hides null fields safely: %s', (slug) => {
    const dom = render(slug, {})
    expect(dom.window.document.querySelectorAll('[data-array-field], .pairs-grid')).toHaveLength(0)
    dom.window.close()
  })
})
