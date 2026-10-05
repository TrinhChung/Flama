// @vitest-environment jsdom

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TemplateCodeEditor, type TemplateEditorTab } from './TemplateCodeEditor'

describe('TemplateCodeEditor', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  const baseProps = {
    fields: [
      { id: 'f1', name: 'Kanji' },
      { id: 'f2', name: 'Meaning' },
    ],
    activeTab: 'front' as TemplateEditorTab,
    onActiveTabChange: vi.fn(),
    frontHtml: '{{Kanji}}',
    backHtml: '{{Meaning}}',
    sharedCss: '.card {}',
    onFrontHtmlChange: vi.fn(),
    onBackHtmlChange: vi.fn(),
    onSharedCssChange: vi.fn(),
  }

  it('render tiêu đề mặc định và tiêu đề tùy chỉnh', async () => {
    await act(async () => {
      root.render(<TemplateCodeEditor {...baseProps} />)
    })
    const heading = container.querySelector('h3')
    expect(heading?.textContent).toBe('Trình Soạn Thảo Template')

    await act(async () => {
      root.render(<TemplateCodeEditor {...baseProps} title="Tiêu Đề Tùy Chỉnh" />)
    })
    expect(container.querySelector('h3')?.textContent).toBe('Tiêu Đề Tùy Chỉnh')
  })

  it('render slots headerActions và footer đúng vị trí class', async () => {
    await act(async () => {
      root.render(
        <TemplateCodeEditor
          {...baseProps}
          headerActions={<span data-testid="custom-action">Nút hành động</span>}
          footer={<span data-testid="custom-footer">Chân trang</span>}
        />,
      )
    })
    const actionEl = container.querySelector('[data-testid="custom-action"]')
    expect(actionEl).not.toBeNull()
    expect(actionEl?.closest('.overflow-x-auto')).not.toBeNull()

    const footerEl = container.querySelector('[data-testid="custom-footer"]')
    expect(footerEl).not.toBeNull()
    expect(footerEl?.closest('.border-t')).not.toBeNull()
  })

function setNativeTextareaValue(element: HTMLTextAreaElement, value: string) {
  const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set
  const prototype = Object.getPrototypeOf(element)
  const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set

  if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
    prototypeValueSetter.call(element, value)
  } else if (valueSetter) {
    valueSetter.call(element, value)
  } else {
    element.value = value
  }
  element.dispatchEvent(new Event('input', { bubbles: true }))
  element.dispatchEvent(new Event('change', { bubbles: true }))
}

  it('gõ textarea front gọi onFrontHtmlChange với giá trị mới', async () => {
    const onFrontChange = vi.fn()
    await act(async () => {
      root.render(<TemplateCodeEditor {...baseProps} onFrontHtmlChange={onFrontChange} />)
    })
    const textarea = container.querySelector('textarea')
    expect(textarea).not.toBeNull()

    await act(async () => {
      if (textarea) {
        setNativeTextareaValue(textarea, '<h2>{{Kanji}}</h2>')
      }
    })
    expect(onFrontChange).toHaveBeenCalledWith('<h2>{{Kanji}}</h2>')
  })

  it('chèn placeholder tại con trỏ trong frontHtml', async () => {
    const onFrontChange = vi.fn()
    await act(async () => {
      root.render(
        <TemplateCodeEditor
          {...baseProps}
          frontHtml="ab"
          onFrontHtmlChange={onFrontChange}
        />,
      )
    })
    const textarea = container.querySelector('textarea')!
    textarea.selectionStart = 1
    textarea.selectionEnd = 1

    const kanjiBtn = Array.from(container.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('{{Kanji}}'),
    )
    expect(kanjiBtn).toBeDefined()

    await act(async () => {
      kanjiBtn?.click()
    })
    expect(onFrontChange).toHaveBeenCalledWith('a{{Kanji}}b')
  })

  it('chèn placeholder tại con trỏ trong backHtml', async () => {
    const onBackChange = vi.fn()
    await act(async () => {
      root.render(
        <TemplateCodeEditor
          {...baseProps}
          activeTab="back"
          backHtml="xyz"
          onBackHtmlChange={onBackChange}
        />,
      )
    })
    const textarea = container.querySelector('textarea')!
    textarea.selectionStart = 2
    textarea.selectionEnd = 2

    const meaningBtn = Array.from(container.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('{{Meaning}}'),
    )
    expect(meaningBtn).toBeDefined()

    await act(async () => {
      meaningBtn?.click()
    })
    expect(onBackChange).toHaveBeenCalledWith('xy{{Meaning}}z')
  })

  it('chèn ở tab css nối chuỗi comment vào sharedCss', async () => {
    const onCssChange = vi.fn()
    await act(async () => {
      root.render(
        <TemplateCodeEditor
          {...baseProps}
          activeTab="css"
          sharedCss=".a{}"
          onSharedCssChange={onCssChange}
        />,
      )
    })
    const kanjiBtn = Array.from(container.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('{{Kanji}}'),
    )
    expect(kanjiBtn).toBeDefined()

    await act(async () => {
      kanjiBtn?.click()
    })
    expect(onCssChange).toHaveBeenCalledWith('.a{}/* {{Kanji}} */')
  })

  it('không có field hiện "Chưa có trường nào"', async () => {
    await act(async () => {
      root.render(<TemplateCodeEditor {...baseProps} fields={[]} />)
    })
    expect(container.textContent).toContain('Chưa có trường nào')
  })

  it('khi readOnly=true, textarea có thuộc tính readonly và không có nút placeholder', async () => {
    for (const tab of ['front', 'back', 'css'] as const) {
      await act(async () => {
        root.render(<TemplateCodeEditor {...baseProps} activeTab={tab} readOnly={true} />)
      })
      const textarea = container.querySelector('textarea')!
      expect(textarea.hasAttribute('readonly')).toBe(true)
      const buttons = Array.from(container.querySelectorAll('button'))
      expect(buttons.some((btn) => btn.textContent?.includes('{{Kanji}}'))).toBe(false)
      expect(buttons.some((btn) => btn.textContent?.includes('{{Meaning}}'))).toBe(false)
    }
  })

  it('mặc định không readonly không textarea nào có thuộc tính readonly', async () => {
    for (const tab of ['front', 'back', 'css'] as const) {
      await act(async () => {
        root.render(<TemplateCodeEditor {...baseProps} activeTab={tab} />)
      })
      const textarea = container.querySelector('textarea')!
      expect(textarea.hasAttribute('readonly')).toBe(false)
    }
  })
})
