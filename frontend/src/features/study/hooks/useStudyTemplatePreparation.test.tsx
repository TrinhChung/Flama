// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useStudyTemplatePreparation, type StudyTemplatePreparationState } from './useStudyTemplatePreparation'
import type { StudyTemplateInputsResponse, StudyTemplatePreset } from '@/entities/card-template'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  fetchInputs: vi.fn(),
  fetchPreset: vi.fn(),
  savePreset: vi.fn(),
}))

vi.mock('@/entities/card-template', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/entities/card-template')>()
  return {
    ...actual,
    fetchStudyTemplateInputs: mocks.fetchInputs,
    fetchStudyTemplatePreset: mocks.fetchPreset,
    saveStudyTemplatePreset: mocks.savePreset,
  }
})

let root: Root | null = null
let container: HTMLDivElement | null = null
let latest: StudyTemplatePreparationState

function Harness({ deckId }: { deckId: string | null }) {
  latest = useStudyTemplatePreparation(deckId)
  return null
}

async function renderHarness(deckId = '12') {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(<Harness deckId={deckId} />)
  })
}

const mockInputsResponse: StudyTemplateInputsResponse = {
  schema_version: 'study-scope-compositions.v2',
  scope_type: 'deck',
  scope_id: '12',
  cardinality: 'many',
  default_composition_id: 'comp-1',
  groups: [],
  compositions: [
    {
      composition_id: 'comp-1',
      note_type_id: 'nt-1',
      note_type_name: 'Kanji',
      template_id: 't-1',
      template_name: 'Recognition',
      is_default: true,
      mode_key: 'flashcard',
      interaction_key: 'review.four-rating',
      trigger_key: 'scheduler.review',
      trigger_contract_version: '1',
      algorithm_key: 'fsrs',
      algorithm_version: '1',
    },
    {
      composition_id: 'comp-2',
      note_type_id: 'nt-1',
      note_type_name: 'Kanji',
      template_id: 't-2',
      template_name: 'Production',
      is_default: false,
      mode_key: 'flashcard',
      interaction_key: 'review.four-rating',
      trigger_key: 'scheduler.review',
      trigger_contract_version: '1',
      algorithm_key: 'fsrs',
      algorithm_version: '1',
    },
  ],
  note_counts: { 'comp-1': 10, 'comp-2': 10 },
  template_inputs: {
    'comp-1': {
      input_schema: [{ key: 'front', label: 'Front', type: 'text', required: true }],
      field_defs: [{ id: 'f1', name: 'Kanji', field_type: 'text' }],
      input_bindings: { front: 'f1' },
      warnings: [],
    },
    'comp-2': {
      input_schema: [{ key: 'front', label: 'Meaning', type: 'text', required: true }],
      field_defs: [{ id: 'f2', name: 'Meaning', field_type: 'text' }],
      input_bindings: { front: 'f2' },
      warnings: [],
    },
  },
}

describe('useStudyTemplatePreparation', () => {
  beforeEach(() => {
    window.localStorage.clear()
    mocks.fetchInputs.mockReset().mockResolvedValue(mockInputsResponse)
    mocks.fetchPreset.mockReset().mockResolvedValue(null)
    mocks.savePreset.mockReset().mockResolvedValue({})
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

  it('defaults remember to true and pre-selects the first template when no preset exists', async () => {
    await renderHarness()
    await act(async () => {
      await latest.load()
    })

    expect(latest.remember).toBe(true)
    expect(latest.compositionId).toBe('comp-1')
    expect(latest.entry).toBeDefined()
  })

  it('pre-selects the saved composition when preset exists and sets remember to true', async () => {
    const preset: StudyTemplatePreset = {
      selected_compositions: ['comp-2'],
      input_bindings: { 'comp-2': { front: 'f2' } },
      ask_before_study: true,
      stale_compositions: [],
    }
    mocks.fetchPreset.mockResolvedValue(preset)

    await renderHarness()
    await act(async () => {
      await latest.load()
    })

    expect(latest.remember).toBe(true)
    expect(latest.compositionId).toBe('comp-2')
    expect(latest.inputBindings).toEqual({ front: 'f2' })
  })

  it('pre-selects from localStorage when no server preset exists', async () => {
    window.localStorage.setItem('flama:study_composition:12', 'comp-2')

    await renderHarness()
    await act(async () => {
      await latest.load()
    })

    expect(latest.compositionId).toBe('comp-2')
  })

  it('submits and saves preset to server and localStorage when remember is true', async () => {
    await renderHarness()
    await act(async () => {
      await latest.load()
    })

    expect(latest.compositionId).toBe('comp-1')
    let selection
    await act(async () => {
      selection = await latest.submit()
    })

    expect(selection).toEqual({
      compositionId: 'comp-1',
      inputBindings: { front: 'f1' },
    })
    expect(mocks.savePreset).toHaveBeenCalledWith('12', {
      selected_compositions: ['comp-1'],
      input_bindings: { 'comp-1': { front: 'f1' } },
      ask_before_study: true,
    })
    expect(window.localStorage.getItem('flama:study_composition:12')).toBe('comp-1')
  })

  it('does not save preset or keep in localStorage when remember is unchecked', async () => {
    window.localStorage.setItem('flama:study_composition:12', 'comp-1')

    await renderHarness()
    await act(async () => {
      await latest.load()
    })

    act(() => {
      latest.setRemember(false)
    })

    let selection
    await act(async () => {
      selection = await latest.submit()
    })

    expect(selection).toEqual({
      compositionId: 'comp-1',
      inputBindings: { front: 'f1' },
    })
    expect(mocks.savePreset).not.toHaveBeenCalled()
    expect(window.localStorage.getItem('flama:study_composition:12')).toBeNull()
  })

  it('does not block study even if saving preset throws an error', async () => {
    mocks.savePreset.mockRejectedValue(new Error('Network error'))

    await renderHarness()
    await act(async () => {
      await latest.load()
    })

    let selection
    await act(async () => {
      selection = await latest.submit()
    })

    expect(selection).toEqual({
      compositionId: 'comp-1',
      inputBindings: { front: 'f1' },
    })
  })
})
