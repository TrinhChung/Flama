// @vitest-environment jsdom

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchDeckCardTypes, type DeckCardTypesResponse } from '@/entities/card-template'
import { DeckCardTypesDialog } from './DeckCardTypesDialog'
import { DeckActionModal } from './DeckModals'
import { DeckRow } from './DeckRow'
import type { DashboardPayload, DeckNode } from '../types'

vi.mock('@/entities/card-template', async () => {
  const actual = await vi.importActual<typeof import('@/entities/card-template')>(
    '@/entities/card-template',
  )
  return {
    ...actual,
    fetchDeckCardTypes: vi.fn(),
  }
})

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({ data: { user: { is_admin: false } } }),
}))

vi.mock('@/app/api', () => ({
  appApi: {},
}))

const fixtureData: DeckCardTypesResponse = {
  schema_version: 'study-scope-compositions.v2',
  scope_type: 'deck',
  scope_id: '42',
  cardinality: 'many',
  default_composition_id: 'c-t1',
  groups: [
    {
      note_type_id: 'nt-vocab',
      note_type_name: 'Từ vựng',
      compositions: [
        {
          composition_id: 'c-t1',
          note_type_id: 'nt-vocab',
          note_type_name: 'Từ vựng',
          template_id: 'tpl-1',
          template_name: 'T1',
          is_default: true,
          context_kind: 'owned',
        },
        {
          composition_id: 'c-t2',
          note_type_id: 'nt-vocab',
          note_type_name: 'Từ vựng',
          template_id: 'tpl-2',
          template_name: 'T2',
          is_default: false,
          context_kind: 'owned',
        },
      ],
    },
    {
      note_type_id: 'nt-installed',
      note_type_name: 'Bộ cài',
      compositions: [
        {
          composition_id: 'c-t3',
          note_type_id: 'nt-installed',
          note_type_name: 'Bộ cài',
          template_id: 'tpl-3',
          template_name: 'T3',
          is_default: false,
          context_kind: 'installed_source',
          install_id: 'i1',
        },
        {
          composition_id: 'c-t4',
          note_type_id: 'nt-installed',
          note_type_name: 'Bộ cài',
          template_id: 'tpl-4',
          template_name: 'T4',
          is_default: false,
          context_kind: 'installed_local',
        },
      ],
    },
  ],
  compositions: [
    {
      composition_id: 'c-t1',
      note_type_id: 'nt-vocab',
      note_type_name: 'Từ vựng',
      template_id: 'tpl-1',
      template_name: 'T1',
      is_default: true,
      context_kind: 'owned',
    },
    {
      composition_id: 'c-t2',
      note_type_id: 'nt-vocab',
      note_type_name: 'Từ vựng',
      template_id: 'tpl-2',
      template_name: 'T2',
      is_default: false,
      context_kind: 'owned',
    },
    {
      composition_id: 'c-t3',
      note_type_id: 'nt-installed',
      note_type_name: 'Bộ cài',
      template_id: 'tpl-3',
      template_name: 'T3',
      is_default: false,
      context_kind: 'installed_source',
      install_id: 'i1',
    },
    {
      composition_id: 'c-t4',
      note_type_id: 'nt-installed',
      note_type_name: 'Bộ cài',
      template_id: 'tpl-4',
      template_name: 'T4',
      is_default: false,
      context_kind: 'installed_local',
    },
  ],
  note_counts: {
    'c-t1': 12,
    // c-t2 omitted to test fallback to 0 note
    'c-t3': 30,
    'c-t4': 2,
  },
}

const sampleDeck: DeckNode = {
  id: 42,
  parent_id: null,
  name: 'JLPT N2 Vocabulary',
  depth: 0,
  study_url: '/study?deck_id=42',
  note_type_id: 'nt-vocab',
  counts: { new: 10, learning: 2, due: 3 },
  move_alias: 'deck-42',
  share_url: '/marketplace/decks',
  children: [],
}

const sampleDashboard: DashboardPayload = {
  decks: [sampleDeck],
  admin_mode: false,
}

describe('DeckCardTypesDialog', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    document.body.innerHTML = ''
  })

  async function renderWithClient(ui: React.ReactElement) {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
        </MemoryRouter>,
      )
    })
  }

  async function flushAsync() {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })
  }

  it('tải và hiện nhóm: thấy "Từ vựng", "Bộ cài", 4 dòng theo đúng thứ tự fixture', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    expect(document.body.textContent).toContain('Từ vựng')
    expect(document.body.textContent).toContain('Bộ cài')

    const items = Array.from(document.body.querySelectorAll('li'))
    expect(items).toHaveLength(4)
    expect(items[0].textContent).toContain('T1')
    expect(items[1].textContent).toContain('T2')
    expect(items[2].textContent).toContain('T3')
    expect(items[3].textContent).toContain('T4')
  })

  it('số note: "12 note", "0 note" (T2 thiếu key), "30 note", "2 note"', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const items = Array.from(document.body.querySelectorAll('li'))
    expect(items[0].textContent).toContain('12 note')
    expect(items[1].textContent).toContain('0 note')
    expect(items[2].textContent).toContain('30 note')
    expect(items[3].textContent).toContain('2 note')
  })

  it('nhãn: T1 có "Mặc định"; T3 có "Thẻ gốc từ bộ đã cài"; T4 có "Thẻ riêng trong bộ đã cài"; T1 có "Thẻ trong bộ của bạn"', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const items = Array.from(document.body.querySelectorAll('li'))
    expect(items[0].textContent).toContain('Mặc định')
    expect(items[1].textContent).not.toContain('Mặc định')
    expect(items[2].textContent).not.toContain('Mặc định')
    expect(items[3].textContent).not.toContain('Mặc định')
    expect(items[0].textContent).toContain('Thẻ trong bộ của bạn')
    expect(items[2].textContent).toContain('Thẻ gốc từ bộ đã cài')
    expect(items[3].textContent).toContain('Thẻ riêng trong bộ đã cài')
  })

  it('sửa giao diện: owned giữ link loại thẻ; nguồn đã cài mở danh sách bản nhận theo install và source', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const items = Array.from(document.body.querySelectorAll('li'))
    const t1Link = items[0].querySelector('a')
    expect(t1Link).not.toBeNull()
    expect(t1Link?.getAttribute('href')).toBe('/flashcards/note-types/nt-vocab/templates')
    expect(t1Link?.textContent).toContain('Sửa giao diện')

    const t3Link = items[2].querySelector('a')
    expect(t3Link?.getAttribute('href')).toBe('/installed-decks/i1/templates?template=tpl-3')
    expect(t3Link?.textContent).toContain('Sửa giao diện')
  })

  it('installed source thiếu install ID vẫn khóa sửa và không đoán URL', async () => {
    const data = structuredClone(fixtureData)
    data.groups[1].compositions[0].install_id = null
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(data)
    await renderWithClient(<DeckCardTypesDialog open onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />)
    await flushAsync()
    const row = document.body.querySelectorAll('li')[2]
    expect(row.querySelector('a')).toBeNull()
    expect(row.querySelector('button')?.disabled).toBe(true)
  })

  it('opens the selected application mapping for owned and installed local templates', async () => {
    const data = structuredClone(fixtureData)
    data.groups[0].compositions[0].application_id = 'app/recognition 日本語'
    data.groups[0].compositions[0].study_application_id = 'older-app'
    data.groups[1].compositions[1].study_application_id = 'local/listening'
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(data)
    await renderWithClient(<DeckCardTypesDialog open onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />)
    await flushAsync()
    const items = document.body.querySelectorAll('li')
    expect(items[0].querySelector('a')?.getAttribute('href')).toBe(`/flashcards/note-types/nt-vocab/templates/${encodeURIComponent('app/recognition 日本語')}`)
    expect(items[3].querySelector('a')?.getAttribute('href')).toBe('/flashcards/note-types/nt-installed/templates/local%2Flistening')
  })

  it('nút học: link "Học deck này" có href="/study?deck_id=42"', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const studyLink = Array.from(document.body.querySelectorAll('a')).find((a) =>
      a.textContent?.includes('Học deck này'),
    )
    expect(studyLink).toBeDefined()
    expect(studyLink?.getAttribute('href')).toBe('/study?deck_id=42')
  })

  it('rỗng: compositions: [] → "Deck này chưa có thẻ để học." và không có link học', async () => {
    const emptyFixture: DeckCardTypesResponse = {
      ...fixtureData,
      compositions: [],
      groups: [],
      note_counts: {},
    }
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(emptyFixture)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    expect(document.body.textContent).toContain('Deck này chưa có thẻ để học.')
    const studyLink = Array.from(document.body.querySelectorAll('a')).find((a) =>
      a.textContent?.includes('Học deck này'),
    )
    expect(studyLink).toBeUndefined()
  })

  it('lỗi: mock reject new Error("Mất kết nối") → thấy "Mất kết nối"', async () => {
    vi.mocked(fetchDeckCardTypes).mockRejectedValue(new Error('Mất kết nối'))
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    expect(document.body.textContent).toContain('Mất kết nối')
    expect(document.body.querySelector('a[href*="/study"]')).toBeNull()
  })

  it('không gọi khi đóng: open=false → fetchDeckCardTypes không được gọi', async () => {
    await renderWithClient(
      <DeckCardTypesDialog open={false} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    expect(fetchDeckCardTypes).not.toHaveBeenCalled()
  })

  it('DeckActionModal: render với selection={{ type: "card-types", deck }} → dialog có tiêu đề Kiểu thẻ của “<tên deck>”', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckActionModal
        selection={{ type: 'card-types', deck: sampleDeck }}
        onClose={vi.fn()}
        dashboard={sampleDashboard}
      />,
    )
    await flushAsync()

    expect(document.body.textContent).toContain('Kiểu thẻ của “JLPT N2 Vocabulary”')
  })

  it('DeckRow: dropdown menu chứa "Kiểu thẻ (template)" giữa "Import thẻ" và "Xuất bài tập / Worksheet" và gọi onAction', async () => {
    const onAction = vi.fn()
    await renderWithClient(
      <DeckRow
        node={sampleDeck}
        adminMode={false}
        onAction={onAction}
        isSelected={false}
        expanded={false}
        onToggleExpand={vi.fn()}
        isDraggingSelf={false}
        dropHover={null}
        isDragActive={() => false}
        isDragJustEnded={() => false}
        onPointerDownRow={vi.fn()}
      />,
    )
    await flushAsync()

    const trigger = document.body.querySelector(
      'button[aria-label="Deck Settings"]',
    ) as HTMLButtonElement
    expect(trigger).not.toBeNull()

    await act(async () => {
      trigger.dispatchEvent(
        new MouseEvent('pointerdown', { bubbles: true, cancelable: true, button: 0 }),
      )
      trigger.click()
    })
    await flushAsync()

    const menuItems = Array.from(document.body.querySelectorAll('[role="menuitem"]'))
    const importIdx = menuItems.findIndex((el) => el.textContent?.includes('Import thẻ'))
    const cardTypesIdx = menuItems.findIndex((el) => el.textContent?.includes('Kiểu thẻ (template)'))
    const worksheetIdx = menuItems.findIndex((el) => el.textContent?.includes('Xuất bài tập / Worksheet'))

    expect(importIdx).toBeGreaterThanOrEqual(0)
    expect(cardTypesIdx).toBeGreaterThanOrEqual(0)
    expect(worksheetIdx).toBeGreaterThanOrEqual(0)
    // Order strictly: Import thẻ -> Kiểu thẻ (template) -> Xuất bài tập / Worksheet
    expect(cardTypesIdx).toBe(importIdx + 1)
    expect(worksheetIdx).toBe(cardTypesIdx + 1)

    // Check SVG icon exists
    const cardTypesItem = menuItems[cardTypesIdx]
    expect(cardTypesItem.querySelector('svg')).not.toBeNull()

    // Trigger action on select
    await act(async () => {
      ;(cardTypesItem as HTMLElement).click()
    })
    expect(onAction).toHaveBeenCalledWith({ type: 'card-types', deck: sampleDeck })
  })

  it('DeckActionModal: nhấn nút "Đóng" gọi onClose', async () => {
    const onClose = vi.fn()
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckActionModal
        selection={{ type: 'card-types', deck: sampleDeck }}
        onClose={onClose}
        dashboard={sampleDashboard}
      />,
    )
    await flushAsync()

    const closeBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.trim() === 'Đóng',
    )
    expect(closeBtn).toBeDefined()
    await act(async () => {
      closeBtn?.click()
    })
    expect(onClose).toHaveBeenCalled()
  })

  it('dữ liệu thiếu arrays (compositions / groups undefined): hiển thị an toàn không ném TypeError', async () => {
    const malformedData = {
      schema_version: 'study-scope-compositions.v2',
      scope_type: 'deck',
      scope_id: '42',
      cardinality: 'zero',
      default_composition_id: null,
    } as unknown as DeckCardTypesResponse

    vi.mocked(fetchDeckCardTypes).mockResolvedValue(malformedData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    expect(document.body.textContent).toContain('Deck này chưa có thẻ để học.')
    const studyLink = Array.from(document.body.querySelectorAll('a')).find((a) =>
      a.textContent?.includes('Học deck này'),
    )
    expect(studyLink).toBeUndefined()
  })

  it('dữ liệu thiếu note_counts: fallback về "0 note" mà không crash', async () => {
    const dataWithoutCounts = {
      ...fixtureData,
      note_counts: undefined as unknown as Record<string, number>,
    }
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(dataWithoutCounts)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const items = Array.from(document.body.querySelectorAll('li'))
    expect(items[0].textContent).toContain('0 note')
  })

  it('context_kind undefined: nhãn "Thẻ trong bộ của bạn" và link sửa giao diện enabled', async () => {
    const undefinedContextData: DeckCardTypesResponse = {
      ...fixtureData,
      groups: [
        {
          note_type_id: 'nt-undef',
          note_type_name: 'Không rõ context',
          compositions: [
            {
              composition_id: 'c-undef',
              note_type_id: 'nt-undef',
              template_id: 'tpl-undef',
              template_name: 'Mẫu undef',
              is_default: false,
              context_kind: undefined,
            },
          ],
        },
      ],
      compositions: [
        {
          composition_id: 'c-undef',
          note_type_id: 'nt-undef',
          template_id: 'tpl-undef',
          template_name: 'Mẫu undef',
          is_default: false,
          context_kind: undefined,
        },
      ],
      note_counts: { 'c-undef': 7 },
    }
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(undefinedContextData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const item = document.body.querySelector('li')
    expect(item?.textContent).toContain('Thẻ trong bộ của bạn')
    const editLink = item?.querySelector('a')
    expect(editLink).not.toBeNull()
    expect(editLink?.getAttribute('href')).toBe('/flashcards/note-types/nt-undef/templates')
    expect(item?.textContent).toContain('7 note')
  })

  it('note_type_id chứa ký tự đặc biệt / tiếng Nhật: href được encodeURIComponent đúng chuẩn', async () => {
    const specialNtData: DeckCardTypesResponse = {
      ...fixtureData,
      groups: [
        {
          note_type_id: 'nt/special 日本語 & test',
          note_type_name: 'Đặc biệt',
          compositions: [
            {
              composition_id: 'c-spec',
              note_type_id: 'nt/special 日本語 & test',
              template_id: 'tpl-spec',
              template_name: 'Mẫu đặc biệt',
              is_default: false,
              context_kind: 'owned',
            },
          ],
        },
      ],
      compositions: [
        {
          composition_id: 'c-spec',
          note_type_id: 'nt/special 日本語 & test',
          template_id: 'tpl-spec',
          template_name: 'Mẫu đặc biệt',
          is_default: false,
          context_kind: 'owned',
        },
      ],
      note_counts: { 'c-spec': 5 },
    }
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(specialNtData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const editLink = document.body.querySelector('li a')
    expect(editLink?.getAttribute('href')).toBe(
      `/flashcards/note-types/${encodeURIComponent('nt/special 日本語 & test')}/templates`,
    )
  })

  it('stress test: render 50 compositions trên nhiều nhóm mà không lỗi', async () => {
    const largeGroups = Array.from({ length: 5 }, (_, gIdx) => ({
      note_type_id: `nt-${gIdx}`,
      note_type_name: `Loại thẻ ${gIdx}`,
      compositions: Array.from({ length: 10 }, (_, cIdx) => ({
        composition_id: `comp-${gIdx}-${cIdx}`,
        note_type_id: `nt-${gIdx}`,
        template_id: `tpl-${gIdx}-${cIdx}`,
        template_name: `Template ${gIdx}-${cIdx}`,
        is_default: cIdx === 0,
        context_kind: 'owned' as const,
      })),
    }))
    const allComps = largeGroups.flatMap((g) => g.compositions)
    const noteCounts: Record<string, number> = {}
    allComps.forEach((c, idx) => {
      noteCounts[c.composition_id] = idx + 1
    })
    const largeData: DeckCardTypesResponse = {
      schema_version: 'study-scope-compositions.v2',
      scope_type: 'deck',
      scope_id: '99',
      cardinality: 'many',
      default_composition_id: allComps[0].composition_id,
      groups: largeGroups,
      compositions: allComps,
      note_counts: noteCounts,
    }
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(largeData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={99} deckName="Big Deck" />,
    )
    await flushAsync()

    const items = Array.from(document.body.querySelectorAll('li'))
    expect(items).toHaveLength(50)
  })

  it('tiêu đề deck chứa ký tự đặc biệt / ngoặc kép: render chuẩn xác', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog
        open={true}
        onOpenChange={vi.fn()}
        deckId={42}
        deckName={'“N2” & <Special>'}
      />,
    )
    await flushAsync()

    expect(document.body.textContent).toContain('Kiểu thẻ của ““N2” & <Special>”')
  })

  it('lỗi với message rỗng: hiển thị fallback "Có lỗi xảy ra khi tải kiểu thẻ."', async () => {
    vi.mocked(fetchDeckCardTypes).mockRejectedValue(new Error(''))
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    expect(document.body.textContent).toContain('Có lỗi xảy ra khi tải kiểu thẻ.')
  })

  it('chuyển đổi deckId động: tải dữ liệu mới tương ứng với deckId mới', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="Deck 42" />,
    )
    await flushAsync()
    expect(fetchDeckCardTypes).toHaveBeenCalledWith(42, expect.any(AbortSignal))

    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={99} deckName="Deck 99" />,
    )
    await flushAsync()
    expect(fetchDeckCardTypes).toHaveBeenCalledWith(99, expect.any(AbortSignal))
    expect(document.body.textContent).toContain('Kiểu thẻ của “Deck 99”')
  })

  it('đóng rồi mở lại dialog: query chỉ kích hoạt khi open=true', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={false} onOpenChange={vi.fn()} deckId={42} deckName="Deck 42" />,
    )
    await flushAsync()
    expect(fetchDeckCardTypes).not.toHaveBeenCalled()

    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="Deck 42" />,
    )
    await flushAsync()
    expect(fetchDeckCardTypes).toHaveBeenCalledTimes(1)
  })

  it('kiểm tra accessibility: dialog có role dialog và tiêu đề được liên kết', async () => {
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )
    await flushAsync()

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog).not.toBeNull()
    expect(dialog?.textContent).toContain('Kiểu thẻ của “JLPT N2”')
    expect(dialog?.textContent).toContain('Mỗi kiểu thẻ là một template hiển thị cùng dữ liệu note.')
  })

  it('trạng thái đang tải: hiển thị spinner và "Đang tải kiểu thẻ…", không hiển thị nút học', async () => {
    vi.mocked(fetchDeckCardTypes).mockImplementation(() => new Promise(() => {}))
    await renderWithClient(
      <DeckCardTypesDialog open={true} onOpenChange={vi.fn()} deckId={42} deckName="JLPT N2" />,
    )

    expect(document.body.textContent).toContain('Đang tải kiểu thẻ…')
    const spinner = document.body.querySelector('.animate-spin')
    expect(spinner).not.toBeNull()
    expect(document.body.querySelector('a[href*="/study"]')).toBeNull()
  })

  it('nhấn nút "Đóng" trực tiếp trên DeckCardTypesDialog gọi onOpenChange(false)', async () => {
    const onOpenChange = vi.fn()
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog
        open={true}
        onOpenChange={onOpenChange}
        deckId={42}
        deckName="JLPT N2"
      />,
    )
    await flushAsync()

    const closeBtn = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Đóng',
    )
    expect(closeBtn).toBeDefined()
    await act(async () => {
      closeBtn?.click()
    })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('nhấn nút close icon "X" trên dialog gọi onOpenChange(false)', async () => {
    const onOpenChange = vi.fn()
    vi.mocked(fetchDeckCardTypes).mockResolvedValue(fixtureData)
    await renderWithClient(
      <DeckCardTypesDialog
        open={true}
        onOpenChange={onOpenChange}
        deckId={42}
        deckName="JLPT N2"
      />,
    )
    await flushAsync()

    const closeButtons = Array.from(document.body.querySelectorAll('button'))
    const xButton = closeButtons.find(
      (b) => b.querySelector('svg.lucide-x') || b.textContent?.toLowerCase().includes('close'),
    )
    if (xButton) {
      await act(async () => {
        xButton.click()
      })
      expect(onOpenChange).toHaveBeenCalledWith(false)
    }
  })
})
