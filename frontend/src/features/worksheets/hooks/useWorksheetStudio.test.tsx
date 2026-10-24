// @vitest-environment jsdom

import { act, useEffect } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useWorksheetStudio,
  type UseWorksheetStudioProps,
  type WorksheetStudioState,
} from './useWorksheetStudio'
import * as worksheetApi from '../api'
import type { DeckWorksheetMeta, WorksheetPreviewResponse, WorksheetTemplate } from '../types'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('useWorksheetStudio', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let latestHook: WorksheetStudioState | null = null

  const mockTemplate: WorksheetTemplate = {
    id: 'kanji_compact',
    name_vi: 'Luyện viết Kanji chuẩn',
    name_en: 'Kanji Stroke Practice',
    description_vi: 'Mẫu chữ Hán chuẩn với sơ đồ nét.',
    description_en: 'Standard Kanji practice.',
    category: 'kanji',
    supported_orientations: ['portrait', 'landscape'],
    default_orientation: 'portrait',
    default_rows_per_page: 5,
    field_slots: [
      {
        key: 'kanji',
        label_vi: 'Trường Kanji',
        label_en: 'Kanji',
        required: true,
      },
    ],
    default_options: {
      grid_style: 'cross',
      trace_count: 2,
      practice_count: 5,
    },
  }

  const mockMeta: DeckWorksheetMeta = {
    deck_id: 1,
    deck_name: 'JLPT N5 Core',
    total_notes: 30,
    note_types: [
      {
        id: 'nt1',
        name: 'Vocabulary Note',
        fields: ['Expression', 'Reading', 'Meaning'],
        note_count: 30,
      },
    ],
    suggested_mappings: {
      kanji: 'Expression',
    },
    templates: [mockTemplate],
  }

  const mockPreviewResponse: WorksheetPreviewResponse = {
    template: mockTemplate,
    deck_id: 1,
    deck_name: 'JLPT N5 Core',
    options: { orientation: 'portrait', rows_per_page: 5 },
    field_mapping: { kanji: 'Expression' },
    total_items: 2,
    total_pages: 1,
    pages: [
      {
        page_number: 1,
        total_pages: 1,
        header: {
          title: 'JLPT N5 Core - Bài tập',
          subtitle: 'Luyện viết mỗi ngày',
          deck_name: 'JLPT N5 Core',
          show_student_info: true,
          show_date: true,
        },
        items: [],
      },
    ],
    warnings: [],
  }

  const defaultProps: UseWorksheetStudioProps = {
    wizardStep: 'studio',
    currentDeckId: 1,
    deckName: 'JLPT N5 Core',
    meta: mockMeta,
    initialTemplateId: 'kanji_compact',
    selectedNoteTypeId: 'nt1',
    scope: 'all',
    limitCount: 10,
  }

  function TestHarness(props: UseWorksheetStudioProps) {
    const hook = useWorksheetStudio(props)
    useEffect(() => {
      latestHook = hook
    })
    return null
  }

  function renderStudioHook(props: Partial<UseWorksheetStudioProps> = {}) {
    const fullProps = { ...defaultProps, ...props }
    act(() => {
      root?.render(<TestHarness {...fullProps} />)
    })
    return fullProps
  }

  beforeEach(() => {
    vi.useFakeTimers()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    latestHook = null
  })

  afterEach(() => {
    if (root && container) {
      act(() => {
        root?.unmount()
      })
      container.remove()
    }
    container = null
    root = null
    latestHook = null
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('sends a Browse selection as Note IDs without converting it to template cards', async () => {
    const preview = vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockResolvedValue(mockPreviewResponse)
    renderStudioHook({ scope: 'selected', initialCardIds: ['note-only'], selectionKind: 'note' })
    await act(async () => { await vi.advanceTimersByTimeAsync(300) })
    expect(preview).toHaveBeenCalledWith(expect.objectContaining({ note_ids: ['note-only'], card_ids: undefined }))
  })

  describe('a. Debounce delay', () => {
    it('does not invoke preview before 300ms, and invokes preview at exactly 300ms', async () => {
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockResolvedValue(mockPreviewResponse)

      renderStudioHook()

      // Immediately after mount: not called, but isGenerating is marked true
      expect(previewSpy).not.toHaveBeenCalled()
      expect(latestHook?.isGenerating).toBe(true)

      // Advance 150ms: still not called
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150)
      })
      expect(previewSpy).not.toHaveBeenCalled()

      // Advance to 299ms: still not called
      await act(async () => {
        await vi.advanceTimersByTimeAsync(149)
      })
      expect(previewSpy).not.toHaveBeenCalled()

      // Advance 1ms more (reaching 300ms): preview is called exactly once
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1)
      })
      expect(previewSpy).toHaveBeenCalledTimes(1)
      expect(latestHook?.previewData).toEqual(mockPreviewResponse)
      expect(latestHook?.isGenerating).toBe(false)
    })

    it('does not schedule preview when wizardStep is not studio or meta is null', async () => {
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockResolvedValue(mockPreviewResponse)

      renderStudioHook({ wizardStep: 'mapping' })

      await act(async () => {
        await vi.advanceTimersByTimeAsync(500)
      })
      expect(previewSpy).not.toHaveBeenCalled()
      expect(latestHook?.isGenerating).toBe(false)
    })
  })

  describe('b. Multiple rapid edits (coalescing)', () => {
    it('coalesces rapid parameter updates into a single debounced API call with latest parameters', async () => {
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockResolvedValue(mockPreviewResponse)

      renderStudioHook()

      // Edit 1 at 100ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100)
      })
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 8 }))
      })
      expect(previewSpy).not.toHaveBeenCalled()

      // Edit 2 at 180ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(80)
      })
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 12 }))
      })
      expect(previewSpy).not.toHaveBeenCalled()

      // Edit 3 at 240ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60)
      })
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 16 }))
      })
      expect(previewSpy).not.toHaveBeenCalled()

      // Advance to 299ms after edit 3 (539ms total)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(299)
      })
      expect(previewSpy).not.toHaveBeenCalled()

      // Advance 1ms more (540ms total, 300ms after edit 3)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1)
      })
      expect(previewSpy).toHaveBeenCalledTimes(1)
      expect(previewSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          options: expect.objectContaining({ rows_per_page: 16 }),
        }),
      )
    })
  })

  describe('c. Unmount cancellation', () => {
    it('cancels pending timer on unmount before 300ms (0 API calls emitted)', async () => {
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockResolvedValue(mockPreviewResponse)

      renderStudioHook()

      // Advance 150ms (before debounce timer expires)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150)
      })
      expect(previewSpy).not.toHaveBeenCalled()

      // Unmount before 300ms
      act(() => {
        root?.unmount()
      })

      // Advance time well beyond 300ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
      expect(previewSpy).not.toHaveBeenCalled()
    })

    it('aborts inflight request signal when unmounted while request is pending', async () => {
      let capturedSignal: AbortSignal | undefined
      vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockImplementation((params) => {
        capturedSignal = params.signal
        return new Promise(() => {}) // pending promise
      })

      renderStudioHook()

      // Advance 300ms so runPreview triggers the API call
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })

      expect(capturedSignal).toBeDefined()
      expect(capturedSignal?.aborted).toBe(false)
      expect(latestHook?.isGenerating).toBe(true)

      // Unmount while request is inflight
      act(() => {
        root?.unmount()
      })

      expect(capturedSignal?.aborted).toBe(true)
    })
  })

  describe('d. Stale response protection', () => {
    it('discards out-of-order resolved requests and does not overwrite latest preview data', async () => {
      let resolveFirst!: (val: WorksheetPreviewResponse) => void
      let resolveSecond!: (val: WorksheetPreviewResponse) => void

      const firstPromise = new Promise<WorksheetPreviewResponse>((res) => {
        resolveFirst = res
      })
      const secondPromise = new Promise<WorksheetPreviewResponse>((res) => {
        resolveSecond = res
      })

      let callCount = 0
      vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockImplementation(() => {
        callCount++
        if (callCount === 1) return firstPromise
        return secondPromise
      })

      renderStudioHook()

      // Trigger first preview at 300ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(1)

      // Parameter update triggers second preview debounce
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 20 }))
      })

      // Advance 300ms to fire second request
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(2)

      const firstResponse: WorksheetPreviewResponse = {
        ...mockPreviewResponse,
        total_items: 10,
      }
      const secondResponse: WorksheetPreviewResponse = {
        ...mockPreviewResponse,
        total_items: 20,
      }

      // Second (newer) request resolves first
      await act(async () => {
        resolveSecond(secondResponse)
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(latestHook?.previewData?.total_items).toBe(20)

      // First (stale, aborted) request resolves later
      await act(async () => {
        resolveFirst(firstResponse)
        await vi.advanceTimersByTimeAsync(0)
      })

      // Latest data remains 20, not overwritten by stale response (10)
      expect(latestHook?.previewData?.total_items).toBe(20)
    })
  })

  describe('e. API error handling', () => {
    it('catches rejected preview requests without throwing unhandled rejections and resets isGenerating to false', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockRejectedValue(new Error('Network offline'))

      renderStudioHook()
      expect(latestHook?.isGenerating).toBe(true)

      // Advance 300ms to fire request and reject
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })

      expect(previewSpy).toHaveBeenCalledTimes(1)
      expect(latestHook?.isGenerating).toBe(false)
      expect(latestHook?.previewData).toBeNull()
      expect(consoleErrorSpy).toHaveBeenCalledWith('Worksheet preview error:', expect.any(Error))
    })

    it('silently ignores AbortError on cancellation without logging console error', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const abortError = new Error('The operation was aborted')
      abortError.name = 'AbortError'
      vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockRejectedValue(abortError)

      renderStudioHook()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })

      expect(latestHook?.isGenerating).toBe(false)
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    })
  })
})
