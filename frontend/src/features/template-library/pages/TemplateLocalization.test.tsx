// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { fetchTemplateLibrary, type TemplateLibraryItem } from '@/entities/card-template'
import { TemplateLibraryPage } from './TemplateLibraryPage'
import { CreateTemplateDialog } from '../components/CreateTemplateDialog'
import { FieldMappingEditor } from '../components/FieldMappingEditor'
import type { MappingIssue } from '../lib/fieldMapping'
import { TemplateVersionHistorySheet } from '@/features/template-versions'

vi.mock('@/entities/card-template', async (original) => ({
  ...await original<typeof import('@/entities/card-template')>(),
  fetchTemplateLibrary: vi.fn(),
}))

const sampleTemplate: TemplateLibraryItem = {
  id: 'template-loc-1',
  owner_user_id: 1,
  name: 'English Biology Card',
  description: 'Bilingual testing card',
  primary_category: 'Science',
  origin: 'market_copy',
  source_template_id: null,
  source_version_id: null,
  current_version_id: 'v1',
  front_html: '{{Front}}',
  back_html: '{{Back}}',
  shared_css: '',
  archived_at: '2026-10-09T00:00:00Z',
  created_at: null,
  updated_at: null,
  application_count: 3,
  note_type_count: 2,
  input_schema: [
    { key: 'Front', label: 'Front', type: 'text', required: true },
    { key: 'Back', label: 'Back', type: 'text', required: false },
  ],
}

async function flush(ms = 20) {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms))
  })
}

describe('Card Template Ecosystem Localization (vi & en)', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient

  beforeEach(async () => {
    vi.clearAllMocks()
    await act(async () => {
      await i18n.changeLanguage('vi')
    })
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    client.clear()
    container.remove()
    document.body.innerHTML = ''
    await act(async () => {
      await i18n.changeLanguage('vi')
    })
  })

  it('renders TemplateLibraryPage in Vietnamese by default and switches instantly to English', async () => {
    vi.mocked(fetchTemplateLibrary).mockResolvedValue({
      schema_version: 'template-library.v2',
      items: [sampleTemplate],
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <TemplateLibraryPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })
    await flush()

    // Assert Vietnamese UI strings
    expect(container.textContent).toContain('Giao diện thẻ')
    expect(container.textContent).toContain('Tạo mẫu mới')
    expect(container.textContent).toContain('Bản nhận')
    expect(container.textContent).toContain('Đã lưu trữ')
    expect(container.textContent).toContain('Dùng ở 2 cấu trúc thẻ · 3 lần gắn')
    expect(container.textContent).toContain('Tất cả')
    expect(container.textContent).toContain('Của tôi')
    expect(container.textContent).toContain('Mẫu độc lập')

    // Switch to English dynamically
    await act(async () => {
      await i18n.changeLanguage('en')
    })
    await flush()

    // Assert English UI strings
    expect(container.textContent).toContain('Card Templates')
    expect(container.textContent).toContain('Create new template')
    expect(container.textContent).toContain('Marketplace copy')
    expect(container.textContent).toContain('Archived')
    expect(container.textContent).toContain('Used in 2 note type(s) · 3 attachment(s)')
    expect(container.textContent).toContain('All')
    expect(container.textContent).toContain('Mine')
    expect(container.textContent).toContain('Standalone templates')
  })

  it('renders CreateTemplateDialog in English when locale is en', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <CreateTemplateDialog open={true} onOpenChange={vi.fn()} />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })
    await flush()

    expect(document.body.textContent).toContain('Create new template')
    expect(document.body.textContent).toContain('Create a standalone card template reusable across note types.')
    expect(document.body.textContent).toContain('Template name')
    expect(document.body.textContent).toContain('Description')
    expect(document.body.textContent).toContain('Cancel')
    expect(document.body.textContent).toContain('Create template')
  })

  it('renders FieldMappingEditor issue messages in English when locale is en', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    const inputs = [
      { key: 'Front', label: 'Front', type: 'text' as const, required: true },
      { key: 'Back', label: 'Back', type: 'text' as const, required: false },
    ]
    const fields = [
      { id: 'f1', name: 'Word', field_type: 'text' as const },
      { id: 'f2', name: 'Audio', field_type: 'audio' as const },
    ]
    const bindings = { Front: null, Back: null }
    const issues: MappingIssue[] = [
      { kind: 'unbound', key: 'Front', required: true, blocking: false },
      { kind: 'unbound', key: 'Back', required: false, blocking: false },
    ]

    await act(async () => {
      root.render(
        <FieldMappingEditor
          inputs={inputs}
          fields={fields}
          bindings={bindings}
          onChange={vi.fn()}
          issues={issues}
        />,
      )
    })
    await flush()

    expect(container.textContent).toContain('Recommended')
    expect(container.textContent).toContain('Recommended input is unmapped; template can still be used.')
    expect(container.textContent).toContain('This input will render empty.')
  })

  it('renders TemplateVersionHistorySheet in English when locale is en', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    const source = {
      listKey: ['versions', 't1'],
      detailKey: (id: string) => ['version', 't1', id],
      list: vi.fn().mockResolvedValue({
        schema_version: 'template-versions.v2',
        template_id: 't1',
        current_version_id: 'v1',
        items: [
          {
            id: 'v1',
            template_id: 't1',
            version_no: 1,
            content_hash: 'hash1',
            change_note: 'Initial import',
            origin: 'market_copy',
            created_at: '2026-10-09T00:00:00Z',
            created_by: { id: 1, username: 'creator' },
            is_current: true,
            front_html: '{{Front}}',
            back_html: '{{Back}}',
            shared_css: '',
            input_schema: [],
          },
        ],
      }),
      get: vi.fn(),
      restore: vi.fn(),
    }

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <TemplateVersionHistorySheet
            open={true}
            onOpenChange={vi.fn()}
            source={source}
            current={{ front_html: '{{Front}}', back_html: '{{Back}}', shared_css: '' }}
            onRestored={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    await flush()

    expect(document.body.textContent).toContain('Version History')
    expect(document.body.textContent).toContain('Every saved content change creates a version.')
    expect(document.body.textContent).toContain('Current')
    expect(document.body.textContent).toContain('Marketplace copy')
  })
})
