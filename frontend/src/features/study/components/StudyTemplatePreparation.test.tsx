// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StudyTemplatePreparation } from './StudyTemplatePreparation'
import type { StudyTemplatePreparationState } from '../hooks/useStudyTemplatePreparation'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

let root: Root | null = null
let container: HTMLDivElement | null = null

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount())
  }
  root = null
  container?.remove()
  container = null
  document.body.replaceChildren()
})

function createMockPreparation(overrides: Partial<StudyTemplatePreparationState> = {}): StudyTemplatePreparationState {
  return {
    availability: {
      schema_version: 'study-scope-compositions.v2',
      scope_type: 'deck',
      scope_id: '12',
      cardinality: 'one',
      default_composition_id: 'comp-1',
      groups: [],
      compositions: [
        {
          composition_id: 'deck:12:note:45:template:99:application:app-77',
          note_type_id: '45',
          note_type_name: 'Japanese Vocab',
          template_id: '99',
          template_name: 'Standard 2-sided',
          is_default: true,
          mode_key: 'flashcard',
          interaction_key: 'review.four-rating',
          trigger_key: 'scheduler.review',
          trigger_contract_version: '1',
          algorithm_key: 'fsrs',
          algorithm_version: '1',
        },
      ],
      note_counts: { 'comp-1': 10 },
      template_inputs: {
        'deck:12:note:45:template:99:application:app-77': {
          input_schema: [
            { key: 'front', label: 'Mặt trước', type: 'text', required: true },
            { key: 'audio', label: 'Âm thanh', type: 'audio', required: false },
          ],
          field_defs: [
            { id: 'f1', name: 'Word', field_type: 'text' },
            { id: 'f2', name: 'Reading', field_type: 'text' },
            { id: 'f3', name: 'Audio Clip', field_type: 'audio' },
          ],
          input_bindings: { front: 'f1', audio: 'f3' },
          warnings: [],
        },
      },
    },
    preset: null,
    compositionId: 'deck:12:note:45:template:99:application:app-77',
    inputBindings: { front: 'f1', audio: 'f3' },
    staleInputs: [],
    remember: false,
    askBeforeStudy: true,
    isLoading: false,
    isSaving: false,
    error: null,
    entry: {
      input_schema: [
        { key: 'front', label: 'Mặt trước', type: 'text', required: true },
        { key: 'audio', label: 'Âm thanh', type: 'audio', required: false },
      ],
      field_defs: [
        { id: 'f1', name: 'Word', field_type: 'text' },
        { id: 'f2', name: 'Reading', field_type: 'text' },
        { id: 'f3', name: 'Audio Clip', field_type: 'audio' },
      ],
      input_bindings: { front: 'f1', audio: 'f3' },
      warnings: [],
    },
    load: vi.fn(),
    submit: vi.fn(),
    selectComposition: vi.fn(),
    changeBindings: vi.fn(),
    setRemember: vi.fn(),
    setAskBeforeStudy: vi.fn(),
    mappingOf: vi.fn(),
    selectionFor: vi.fn(),
    saveBindings: vi.fn(),
    ...overrides,
  }
}

describe('StudyTemplatePreparation', () => {
  it('renders preparation header, deck name, and back to dashboard link', async () => {
    const prep = createMockPreparation()
    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    expect(container?.textContent).toContain('Chuẩn bị phiên học')
    expect(container?.textContent).toContain('JLPT N5')

    const backLinks = Array.from(container?.querySelectorAll('a') ?? []).filter((a) =>
      a.textContent?.includes('Quay về Dashboard'),
    )
    expect(backLinks.length).toBe(1)
    expect(backLinks[0].getAttribute('href')).toBe('/dashboard')
  })

  it('renders the 2 buttons: "Chọn các trường truyền vào" and "Thiết lập mapping Note Type"', async () => {
    const prep = createMockPreparation()
    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    const buttons = Array.from(container?.querySelectorAll('button') ?? [])
    const selectFieldsBtn = buttons.find((b) => b.textContent?.includes('Chọn các trường truyền vào'))
    expect(selectFieldsBtn).toBeDefined()

    const mappingLink = Array.from(container?.querySelectorAll('a') ?? []).find((a) =>
      a.textContent?.includes('Thiết lập mapping Note Type'),
    )
    expect(mappingLink).toBeDefined()
    expect(mappingLink?.getAttribute('href')).toContain('/flashcards/note-types/45/templates/app-77')
    expect(mappingLink?.getAttribute('target')).toBe('_blank')
  })

  it('opens dialog when clicking "Chọn các trường truyền vào" and toggling off sets binding to null', async () => {
    const prep = createMockPreparation()
    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    const selectFieldsBtn = Array.from(container?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Chọn các trường truyền vào'),
    )
    await act(async () => {
      selectFieldsBtn?.click()
    })

    // Dialog should be open
    expect(document.body.textContent).toContain('Chọn các trường truyền vào template')
    expect(document.body.textContent).toContain('Mặt trước')
    expect(document.body.textContent).toContain('Âm thanh')

    // Find audio checkbox and uncheck it
    const checkboxes = Array.from(document.body.querySelectorAll('input[type="checkbox"]')) as HTMLInputElement[]
    // Find checkbox for audio (the one whose parent label has Âm thanh)
    const audioCheckbox = checkboxes.find((cb) => {
      const label = cb.closest('label')
      return label?.textContent?.includes('Âm thanh')
    })
    expect(audioCheckbox).toBeDefined()
    expect(audioCheckbox?.checked).toBe(true)

    // Uncheck audio
    await act(async () => {
      audioCheckbox?.click()
    })

    // Expect changeBindings to be called with audio: null
    expect(prep.changeBindings).toHaveBeenCalledWith(
      expect.objectContaining({
        front: 'f1',
        audio: null,
      }),
    )
  })

  it('clicking "Không truyền trường nào" sets all inputs to null', async () => {
    const prep = createMockPreparation()
    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    const selectFieldsBtn = Array.from(container?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Chọn các trường truyền vào'),
    )
    await act(async () => {
      selectFieldsBtn?.click()
    })

    const deselectAllBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Không truyền trường nào'),
    )
    expect(deselectAllBtn).toBeDefined()

    await act(async () => {
      deselectAllBtn?.click()
    })

    expect(prep.changeBindings).toHaveBeenCalledWith({
      front: null,
      audio: null,
    })
  })

  it('clicking "Chọn tất cả" restores valid target fields', async () => {
    const prep = createMockPreparation({
      inputBindings: { front: null, audio: null },
    })
    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    const selectFieldsBtn = Array.from(container?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Chọn các trường truyền vào'),
    )
    await act(async () => {
      selectFieldsBtn?.click()
    })

    const selectAllBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Chọn tất cả'),
    )
    expect(selectAllBtn).toBeDefined()

    await act(async () => {
      selectAllBtn?.click()
    })

    expect(prep.changeBindings).toHaveBeenCalledWith(
      expect.objectContaining({
        front: 'f1',
        audio: 'f3',
      }),
    )
  })

  it('renders mapping URL without composite ID even when composition has compatibility ID', async () => {
    const prep = createMockPreparation({
      availability: {
        schema_version: 'study-scope-compositions.v2',
        scope_type: 'deck',
        scope_id: '12',
        cardinality: 'one',
        default_composition_id: 'comp:notetype:45:template:99',
        groups: [],
        compositions: [
          {
            composition_id: 'comp:notetype:45:template:99',
            note_type_id: '45',
            note_type_name: 'Japanese Vocab',
            template_id: '99',
            template_name: 'Standard 2-sided',
            is_default: true,
            mode_key: 'flashcard',
            interaction_key: 'review.four-rating',
            trigger_key: 'scheduler.review',
            trigger_contract_version: '1',
            algorithm_key: 'fsrs',
            algorithm_version: '1',
            application_id: 'comp:notetype:45:template:99',
            study_application_id: 'app-real-uuid',
          },
        ],
        note_counts: { 'comp-1': 10 },
        template_inputs: {},
      },
      compositionId: 'comp:notetype:45:template:99',
    })
    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    const mappingLink = container?.querySelector('a[href*="/templates/"]') as HTMLAnchorElement | null
    expect(mappingLink).not.toBeNull()
    expect(mappingLink?.getAttribute('href')).toBe('/flashcards/note-types/45/templates/app-real-uuid')
    expect(mappingLink?.getAttribute('href')).not.toContain('comp:')
  })

  it('pre-selects the template in the dropdown and enables immediate start with onStart', async () => {
    const handleStart = vi.fn()
    const prep = createMockPreparation({
      compositionId: 'deck:12:note:45:template:99:application:app-77',
      remember: true,
      askBeforeStudy: true,
    })

    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={handleStart} />
        </BrowserRouter>,
      )
    })

    const select = container?.querySelector('#study-template-choice') as HTMLSelectElement | null
    expect(select?.value).toBe('deck:12:note:45:template:99:application:app-77')

    const startButton = Array.from(container?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Bắt đầu học'),
    ) as HTMLButtonElement | undefined
    expect(startButton).toBeDefined()
    expect(startButton?.disabled).toBe(false)

    await act(async () => {
      startButton?.click()
    })
    expect(handleStart).toHaveBeenCalledTimes(1)
  })

  it('toggles remember checkbox and calls setRemember', async () => {
    const prep = createMockPreparation({
      remember: true,
    })

    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    const rememberCheckbox = Array.from(container?.querySelectorAll('input[type="checkbox"]') ?? []).find((cb) => {
      const label = cb.closest('label')
      return label?.textContent?.includes('Ghi nhớ cho bộ thẻ này')
    }) as HTMLInputElement | undefined

    expect(rememberCheckbox).toBeDefined()
    expect(rememberCheckbox?.checked).toBe(true)

    await act(async () => {
      rememberCheckbox?.click()
    })
    expect(prep.setRemember).toHaveBeenCalledWith(false)
  })

  it('renders responsive bounded viewport container with scrollable body and pinned footer action', async () => {
    const prep = createMockPreparation()

    await act(async () => {
      root?.render(
        <BrowserRouter>
          <StudyTemplatePreparation preparation={prep} deckName="JLPT N5" onStart={vi.fn()} />
        </BrowserRouter>,
      )
    })

    const outerContainer = container?.firstElementChild as HTMLElement
    expect(outerContainer.className).toContain('overflow-y-auto')
    expect(outerContainer.className).toContain('h-[100dvh]')

    const mainCard = container?.querySelector('main') as HTMLElement
    expect(mainCard).not.toBeNull()
    expect(mainCard.className).toContain('flex-col')
    expect(mainCard.className).toContain('overflow-hidden')

    const startButton = Array.from(container?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Bắt đầu học'),
    ) as HTMLButtonElement | undefined
    expect(startButton).toBeDefined()
    const footer = startButton?.parentElement
    expect(footer?.className).toContain('shrink-0')
    expect(footer?.className).toContain('border-t')
  })
})
