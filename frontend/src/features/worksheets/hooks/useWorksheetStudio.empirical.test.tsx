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

describe('Empirical Challenge: Worksheet Debounce, Fake Timers & Stress Harness', () => {
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

  const createMockPreviewResponse = (overrides: Partial<WorksheetPreviewResponse> = {}): WorksheetPreviewResponse => ({
    template: mockTemplate,
    deck_id: 1,
    deck_name: 'JLPT N5 Core',
    options: { orientation: 'portrait', rows_per_page: 5 },
    field_mapping: { kanji: 'Expression' },
    total_items: 10,
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
    ...overrides,
  })

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

  // =========================================================================
  // CHALLENGE 1: Debounce Boundary Precision (299ms vs 300ms)
  // =========================================================================
  describe('Challenge 1: Debounce Boundary Precision', () => {
    it('verifies t = 299ms triggers 0 network calls and t = 300ms triggers exactly 1 call', async () => {
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockResolvedValue(createMockPreviewResponse())

      renderStudioHook()

      // At t = 0ms: not called
      expect(previewSpy).toHaveBeenCalledTimes(0)
      expect(latestHook?.isGenerating).toBe(true)

      // At t = 100ms: not called
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100)
      })
      expect(previewSpy).toHaveBeenCalledTimes(0)

      // At t = 200ms: not called
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100)
      })
      expect(previewSpy).toHaveBeenCalledTimes(0)

      // At t = 299ms: strictly zero calls
      await act(async () => {
        await vi.advanceTimersByTimeAsync(99)
      })
      expect(previewSpy).toHaveBeenCalledTimes(0)
      expect(latestHook?.isGenerating).toBe(true)
      expect(latestHook?.previewData).toBeNull()

      // At t = 300ms (1ms step): exactly 1 call triggered
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1)
      })
      expect(previewSpy).toHaveBeenCalledTimes(1)
      expect(latestHook?.isGenerating).toBe(false)
      expect(latestHook?.previewData).not.toBeNull()

      // Advance further by 500ms (t = 800ms): remains exactly 1 call
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500)
      })
      expect(previewSpy).toHaveBeenCalledTimes(1)
    })
  })

  // =========================================================================
  // CHALLENGE 2: Stress Flood with 50 Rapid Edits within 200ms
  // =========================================================================
  describe('Challenge 2: Stress Flood with 50 Rapid Edits within 200ms', () => {
    it('coalesces 50 rapid parameter changes into exactly 1 API call after 300ms of quiet', async () => {
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockResolvedValue(createMockPreviewResponse({ total_items: 60 }))

      renderStudioHook()

      // Rapidly fire 50 parameter changes spaced 4ms apart (total 200ms)
      for (let i = 1; i <= 50; i++) {
        await act(async () => {
          await vi.advanceTimersByTimeAsync(4)
        })
        act(() => {
          latestHook?.setLayoutOptions((prev) => ({
            ...prev,
            rows_per_page: 10 + i,
          }))
        })
        expect(previewSpy).toHaveBeenCalledTimes(0)
      }

      // After 50 edits (elapsed ~200ms), advance 299ms from the last event
      await act(async () => {
        await vi.advanceTimersByTimeAsync(299)
      })
      expect(previewSpy).toHaveBeenCalledTimes(0)

      // Advance 1ms more (reaching 300ms from the 50th edit): exactly 1 call emitted
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1)
      })
      expect(previewSpy).toHaveBeenCalledTimes(1)
      expect(previewSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          options: expect.objectContaining({ rows_per_page: 60 }),
        }),
      )

      // Advance by another 1000ms: no rogue calls dispatched
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
      expect(previewSpy).toHaveBeenCalledTimes(1)
    })
  })

  // =========================================================================
  // CHALLENGE 3: Unmount & Signal Abort Handling
  // =========================================================================
  describe('Challenge 3: Unmount & Signal Abort Handling', () => {
    it('aborts active fetch signal on unmount and prevents unmounted state updates', async () => {
      let capturedSignal: AbortSignal | undefined
      let resolveFetch!: (val: WorksheetPreviewResponse) => void

      const pendingPromise = new Promise<WorksheetPreviewResponse>((res) => {
        resolveFetch = res
      })

      vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockImplementation((params) => {
        capturedSignal = params.signal
        return pendingPromise
      })

      renderStudioHook()

      // Advance 300ms to dispatch the fetch
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })

      expect(capturedSignal).toBeDefined()
      expect(capturedSignal?.aborted).toBe(false)
      expect(latestHook?.isGenerating).toBe(true)

      // Unmount component while fetch is inflight
      act(() => {
        root?.unmount()
      })

      // Signal must be immediately marked aborted
      expect(capturedSignal?.aborted).toBe(true)

      // Resolve the inflight fetch after unmount: must not throw unmounted state warning
      await act(async () => {
        resolveFetch(createMockPreviewResponse({ total_items: 999 }))
        await vi.advanceTimersByTimeAsync(0)
      })

      // Ensure no unhandled exception or post-unmount crash
      expect(capturedSignal?.aborted).toBe(true)
    })

    it('cancels pending debounce timer when unmounted before 300ms without firing API call', async () => {
      const previewSpy = vi
        .spyOn(worksheetApi, 'generateWorksheetPreview')
        .mockResolvedValue(createMockPreviewResponse())

      renderStudioHook()

      // Advance 250ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(250)
      })
      expect(previewSpy).toHaveBeenCalledTimes(0)

      // Unmount before debounce timer fires
      act(() => {
        root?.unmount()
      })

      // Advance 1000ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
      expect(previewSpy).toHaveBeenCalledTimes(0)
    })
  })

  // =========================================================================
  // CHALLENGE 4: Out-of-Order Stale Response Protection & Error Races
  // =========================================================================
  describe('Challenge 4: Out-of-Order Stale Response Protection & Error Races', () => {
    it('discards stale response when slow request 1 resolves after faster request 2', async () => {
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

      // Trigger Request 1 at t = 300ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(1)

      // Parameter change at t = 350ms
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 25 }))
      })

      // Advance 300ms to trigger Request 2 at t = 650ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(2)

      // Request 2 (fast) resolves first with total_items = 25
      await act(async () => {
        resolveSecond(createMockPreviewResponse({ total_items: 25 }))
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(latestHook?.previewData?.total_items).toBe(25)
      expect(latestHook?.isGenerating).toBe(false)

      // Request 1 (stale, slow) resolves later with total_items = 5
      await act(async () => {
        resolveFirst(createMockPreviewResponse({ total_items: 5 }))
        await vi.advanceTimersByTimeAsync(0)
      })

      // Verify stale response did NOT overwrite latest data
      expect(latestHook?.previewData?.total_items).toBe(25)
    })

    it('3-tier race: Request 3 resolves first, Request 2 resolves second, Request 1 resolves last', async () => {
      let resolve1!: (val: WorksheetPreviewResponse) => void
      let resolve2!: (val: WorksheetPreviewResponse) => void
      let resolve3!: (val: WorksheetPreviewResponse) => void

      const p1 = new Promise<WorksheetPreviewResponse>((r) => { resolve1 = r })
      const p2 = new Promise<WorksheetPreviewResponse>((r) => { resolve2 = r })
      const p3 = new Promise<WorksheetPreviewResponse>((r) => { resolve3 = r })

      let callCount = 0
      vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockImplementation(() => {
        callCount++
        if (callCount === 1) return p1
        if (callCount === 2) return p2
        return p3
      })

      renderStudioHook()

      // Request 1 triggers at 300ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(1)

      // Edit to schedule Request 2
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 20 }))
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(2)

      // Edit to schedule Request 3
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 30 }))
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(3)

      // Inverted resolution order: 3 -> 2 -> 1
      await act(async () => {
        resolve3(createMockPreviewResponse({ total_items: 300 }))
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(latestHook?.previewData?.total_items).toBe(300)

      await act(async () => {
        resolve2(createMockPreviewResponse({ total_items: 200 }))
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(latestHook?.previewData?.total_items).toBe(300)

      await act(async () => {
        resolve1(createMockPreviewResponse({ total_items: 100 }))
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(latestHook?.previewData?.total_items).toBe(300)
    })

    it('slow request 1 does not overwrite error state if newer request 2 failed', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => {})
      let resolve1!: (val: WorksheetPreviewResponse) => void
      let reject2!: (err: Error) => void

      const p1 = new Promise<WorksheetPreviewResponse>((r) => { resolve1 = r })
      const p2 = new Promise<WorksheetPreviewResponse>((_, rej) => { reject2 = rej })

      let callCount = 0
      vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockImplementation(() => {
        callCount++
        if (callCount === 1) return p1
        return p2
      })

      renderStudioHook()

      // Request 1 triggers at 300ms
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(1)

      // Trigger Request 2
      act(() => {
        latestHook?.setLayoutOptions((prev) => ({ ...prev, rows_per_page: 50 }))
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300)
      })
      expect(callCount).toBe(2)

      // Request 2 rejects with 500 Server Error
      await act(async () => {
        reject2(new Error('Internal Server Error 500'))
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(latestHook?.isGenerating).toBe(false)
      expect(latestHook?.previewData).toBeNull()

      // Request 1 resolves with old valid data
      await act(async () => {
        resolve1(createMockPreviewResponse({ total_items: 10 }))
        await vi.advanceTimersByTimeAsync(0)
      })

      // Old aborted request 1 must NOT restore previewData
      expect(latestHook?.previewData).toBeNull()
    })
  })
})
