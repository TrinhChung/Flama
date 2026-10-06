// @vitest-environment jsdom

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { TemplateDiffView, type TemplateSources } from './TemplateDiffView'

describe('TemplateDiffView', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  const identicalSources: TemplateSources = {
    front_html: '<div>{{Word}}</div>',
    back_html: '<div>{{Word}}<hr>{{Meaning}}</div>',
    shared_css: '.card { font-size: 20px; }',
  }

  it('hiển thị nhãn so sánh chính xác', async () => {
    await act(async () => {
      root.render(
        <TemplateDiffView
          before={identicalSources}
          after={identicalSources}
          beforeLabel="Phiên bản 1"
          afterLabel="Hiện tại"
        />,
      )
    })

    const labelPara = container.querySelector('p')
    expect(labelPara?.textContent).toBe('So sánh Phiên bản 1 → Hiện tại')
  })

  it('hiển thị 3 lần "Không có thay đổi" và không có thẻ pre khi before bằng after', async () => {
    await act(async () => {
      root.render(
        <TemplateDiffView
          before={identicalSources}
          after={identicalSources}
          beforeLabel="Phiên bản 1"
          afterLabel="Hiện tại"
        />,
      )
    })

    const noChanges = Array.from(container.querySelectorAll('p')).filter(
      (p) => p.textContent === 'Không có thay đổi',
    )
    expect(noChanges).toHaveLength(3)

    const preElements = container.querySelectorAll('pre')
    expect(preElements).toHaveLength(0)
  })

  it('hiển thị đúng diff khi front thay đổi', async () => {
    const before: TemplateSources = {
      front_html: '{{Word}}',
      back_html: identicalSources.back_html,
      shared_css: identicalSources.shared_css,
    }
    const after: TemplateSources = {
      front_html: '{{Kanji}}',
      back_html: identicalSources.back_html,
      shared_css: identicalSources.shared_css,
    }

    await act(async () => {
      root.render(
        <TemplateDiffView
          before={before}
          after={after}
          beforeLabel="Phiên bản 1"
          afterLabel="Hiện tại"
        />,
      )
    })

    const sections = container.querySelectorAll('section')
    expect(sections).toHaveLength(3)

    const frontSection = sections[0]
    expect(frontSection.querySelector('header')?.textContent).toContain('+1 −1')

    const removedEl = frontSection.querySelector('[data-kind="removed"]')
    expect(removedEl).not.toBeNull()
    expect(removedEl?.textContent).toContain('{{Word}}')

    const addedEl = frontSection.querySelector('[data-kind="added"]')
    expect(addedEl).not.toBeNull()
    expect(addedEl?.textContent).toContain('{{Kanji}}')

    // back and css sections have no changes
    const backSection = sections[1]
    const cssSection = sections[2]
    expect(backSection.querySelector('p')?.textContent).toBe('Không có thay đổi')
    expect(cssSection.querySelector('p')?.textContent).toBe('Không có thay đổi')
  })

  it('không chèn mã HTML vào DOM khi render (an toàn XSS, hiển thị thô)', async () => {
    const before: TemplateSources = {
      front_html: '',
      back_html: '',
      shared_css: '',
    }
    const after: TemplateSources = {
      front_html: '<b>x</b>',
      back_html: '<img src="x" onerror="alert(1)" />',
      shared_css: '<style>body { color: red; }</style>',
    }

    await act(async () => {
      root.render(
        <TemplateDiffView
          before={before}
          after={after}
          beforeLabel="Trước"
          afterLabel="Sau"
        />,
      )
    })

    // DOM must not have rendered <b>, <img>, or <style> tags from the template content
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('style')).toBeNull()

    const frontSection = container.querySelectorAll('section')[0]
    const addedFront = frontSection.querySelector('[data-kind="added"]')
    expect(addedFront?.textContent).toContain('<b>x</b>')
  })

  it('hiển thị đúng diff cho cả Back HTML và Shared CSS cùng các ký hiệu dòng', async () => {
    const before: TemplateSources = {
      front_html: 'same line',
      back_html: 'line 1\nline 2',
      shared_css: '.old { color: red; }',
    }
    const after: TemplateSources = {
      front_html: 'same line',
      back_html: 'line 1\nline 2 modified',
      shared_css: '.new { color: blue; }',
    }

    await act(async () => {
      root.render(
        <TemplateDiffView
          before={before}
          after={after}
          beforeLabel="V1"
          afterLabel="V2"
        />,
      )
    })

    const sections = container.querySelectorAll('section')
    // Front has no changes
    expect(sections[0].querySelector('p')?.textContent).toBe('Không có thay đổi')

    // Back has changes (+1 -1)
    const backSection = sections[1]
    expect(backSection.querySelector('header')?.textContent).toContain('+1 −1')
    const backLines = backSection.querySelectorAll('[data-kind]')
    expect(backLines).toHaveLength(3) // 1 same, 1 removed, 1 added
    expect(backLines[0].getAttribute('data-kind')).toBe('same')
    expect(backLines[0].querySelector('span')?.textContent).toBe(' ')
    expect(backLines[1].getAttribute('data-kind')).toBe('removed')
    expect(backLines[1].querySelector('span')?.textContent).toBe('-')
    expect(backLines[2].getAttribute('data-kind')).toBe('added')
    expect(backLines[2].querySelector('span')?.textContent).toBe('+')

    // CSS has changes (+1 -1)
    const cssSection = sections[2]
    expect(cssSection.querySelector('header')?.textContent).toContain('+1 −1')
  })

  it('an toàn khi before hoặc after là nullish hoặc thiếu thuộc tính', async () => {
    await act(async () => {
      root.render(
        <TemplateDiffView
          before={null as unknown as TemplateSources}
          after={undefined as unknown as TemplateSources}
          beforeLabel="Rỗng"
          afterLabel="Rỗng"
        />,
      )
    })

    const noChanges = Array.from(container.querySelectorAll('p')).filter(
      (p) => p.textContent === 'Không có thay đổi',
    )
    expect(noChanges).toHaveLength(3)
  })
})

