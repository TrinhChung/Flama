// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import '@/shared/config/i18n'
import type { TemplateLibraryItem } from '@/entities/card-template'
import { TemplateCard } from './TemplateCard'

const sampleTemplate: TemplateLibraryItem = {
  id: 'tmpl-123',
  owner_user_id: 1,
  name: 'Standard Vocabulary Card',
  description: 'Clean modern template for kanji and vocabulary cards.',
  primary_category: null,
  origin: 'authored',
  source_template_id: null,
  source_version_id: null,
  current_version_id: 'v1',
  front_html: '{{Front}}',
  back_html: '{{Back}}',
  shared_css: '',
  archived_at: null,
  created_at: null,
  updated_at: null,
  application_count: 5,
  note_type_count: 2,
  input_schema: [
    { key: 'Front', label: 'Front', type: 'text', required: true },
    { key: 'Back', label: 'Back', type: 'text', required: false },
  ],
}

describe('TemplateCard', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    document.body.innerHTML = ''
  })

  it('renders title, badge mine, usage stats and flama details button', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <TemplateCard template={sampleTemplate} />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Standard Vocabulary Card')
    expect(container.textContent).toContain('Clean modern template for kanji and vocabulary cards.')
    expect(container.textContent).toContain('Của tôi')
    expect(container.textContent).toContain('Dùng ở 2 cấu trúc thẻ · 5 lần gắn')
    expect(container.textContent).toContain('Xem chi tiết')

    // No input schema tokens displayed directly on overview card
    expect(container.querySelectorAll('code')).toHaveLength(0)

    // Button links to template details
    const detailLink = container.querySelector('a[href="/card-templates/tmpl-123"]')
    expect(detailLink).not.toBeNull()
  })

  it('renders received badge and archived badge when applicable', async () => {
    const marketArchived: TemplateLibraryItem = {
      ...sampleTemplate,
      id: 'tmpl-market',
      origin: 'market_copy',
      archived_at: '2026-10-10T00:00:00Z',
      description: '',
      note_type_count: 0,
      application_count: 0,
    }

    await act(async () => {
      root.render(
        <MemoryRouter>
          <TemplateCard template={marketArchived} />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Bản nhận')
    expect(container.textContent).toContain('Đã lưu trữ')
    expect(container.textContent).toContain('Chưa dùng')
    expect(container.textContent).toContain('Chưa có mô tả cho mẫu thẻ này.')
  })
})
