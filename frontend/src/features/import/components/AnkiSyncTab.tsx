import React, { useState, useEffect, useId, useMemo, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type {
  AnkiConnectStatus,
  AnkiNoteInfo,
} from '@/lib/ankiConnectClient'
import {
  ankiConnectClient,
} from '@/lib/ankiConnectClient'
import {
  autoSuggestFieldMapping,
  buildExactAnkiDeckQuery,
  buildExactAnkiModelQuery,
} from '@/lib/ankiSyncEngine'
import { getCsrfToken } from '@/shared/api/client'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import { sanitizeAnkiHtml } from '@/lib/ankiHtmlSanitizer'
import { appApi } from '@/app/api'
import { AnkiDeckSelectCard } from './anki-deck/AnkiDeckSelectCard'
import { AnkiFieldMappingCard } from './anki-deck/AnkiFieldMappingCard'
import { AnkiSyncExecuteCard } from './anki-deck/AnkiSyncExecuteCard'
import { AnkiSyncProgressDialog } from './anki-deck/AnkiSyncProgressDialog'

interface FlamaFieldDef {
  id: string
  name: string
  field_type: string
}

interface FlamaNoteTypeOption {
  id: string
  name: string
  fields: FlamaFieldDef[]
}

interface FlamaTemplate {
  id: string
  name: string
  front_html?: string
  back_html?: string
  shared_css?: string
}

interface FlamaNoteTypeDetail {
  id: string
  name: string
  field_defs?: Array<FlamaFieldDef & { position: number }>
  templates?: FlamaTemplate[]
}

interface PreviewResponse {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

interface AnkiSyncTabProps {
  noteTypeOptions: FlamaNoteTypeOption[]
  flamaUserId: number
  endpoint: string
  connectionStatus: AnkiConnectStatus
  ankiVersion: number | null
}

export const AnkiSyncTab: React.FC<AnkiSyncTabProps> = ({
  noteTypeOptions,
  flamaUserId,
  endpoint,
  connectionStatus,
}) => {
  const queryClient = useQueryClient()
  const workerRef = useRef<Worker | null>(null)

  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate()
      }
    }
  }, [])

  // Step 1: Deck Selection State
  const [decks, setDecks] = useState<string[]>([])
  const [deckSearch, setDeckSearch] = useState('')
  const [selectedDecks, setSelectedDecks] = useState<string[]>([])
  const [deckNoteCounts, setDeckNoteCounts] = useState<Record<string, number>>({})

  // Step 2: Mapping State
  const [selectedDeckName, setSelectedDeckName] = useState<string>('')
  const [targetFlamaDeckName, setTargetFlamaDeckName] = useState<string>('')
  const [selectedAnkiModel, setSelectedAnkiModel] = useState<string>('')
  const [ankiModelOptions, setAnkiModelOptions] = useState<string[]>([])
  const [ankiFields, setAnkiFields] = useState<string[]>([])
  const [selectedFlamaModelId, setSelectedFlamaModelId] = useState<string>('')
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({}) // AnkiField -> FlamaField

  // Step 3: Preview State
  const [previewNotes, setPreviewNotes] = useState<AnkiNoteInfo[]>([])
  const [previewNoteIndex, setPreviewNoteIndex] = useState(0)
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [previewNoteType, setPreviewNoteType] = useState<FlamaNoteTypeDetail | null>(null)
  const [previewTemplateId, setPreviewTemplateId] = useState('')
  const [previewResult, setPreviewResult] = useState<PreviewResponse | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [showPreviewSection, setShowPreviewSection] = useState(false)

  // Step 4: Sync Execution State
  const [syncMode, setSyncMode] = useState<'new_and_changed' | 'only_new' | 'resync_all'>('new_and_changed')
  const [autoSyncMissingNoteTypes, setAutoSyncMissingNoteTypes] = useState(true)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncProgress, setSyncProgress] = useState<{
    phase: string
    totalNotes: number
    processedNotes: number
    totalMedia: number
    processedMedia: number
    message: string
  } | null>(null)
  const [syncReport, setSyncReport] = useState<{
    totalSynced: number
    totalSkipped?: number
    totalMediaDetected?: number
    errors: string[]
  } | null>(null)

  const syncModeSelectId = useId()
  const targetDeckInputId = useId()

  // Auto fetch decks when connected
  useEffect(() => {
    async function fetchDecks() {
      if (connectionStatus === 'Connected') {
        try {
          const deckList = await ankiConnectClient.getDeckNames(endpoint)
          setDecks(deckList)
        } catch (err: any) {
          console.warn('Lỗi lấy danh sách deck:', err)
        }
      }
    }
    fetchDecks()
  }, [connectionStatus, endpoint])

  const [isDeckLoading, setIsDeckLoading] = useState(false)

  // Lazy load note count and NoteType details ONLY when a deck is selected
  useEffect(() => {
    async function loadDeckDetails() {
      if (selectedDecks.length === 0) {
        setSelectedDeckName('')
        setTargetFlamaDeckName('')
        setSelectedAnkiModel('')
        setAnkiModelOptions([])
        setAnkiFields([])
        setSelectedFlamaModelId('')
        setFieldMapping({})
        setPreviewNotes([])
        setPreviewNoteType(null)
        setPreviewResult(null)
        setShowPreviewSection(false)
        return
      }
      const targetDeck = selectedDecks[0]
      setSelectedDeckName(targetDeck)
      setTargetFlamaDeckName(targetDeck)
      setIsDeckLoading(true)

      try {
        const notes = await ankiConnectClient.findNotes(buildExactAnkiDeckQuery(targetDeck), endpoint)
        setDeckNoteCounts((prev) => ({ ...prev, [targetDeck]: notes.length }))

        const availableModels = await ankiConnectClient.getModelNames(endpoint)
        const modelMatches = await ankiConnectClient.multi(
          availableModels.map((modelName) => ({
            action: 'findNotes',
            params: { query: `${buildExactAnkiDeckQuery(targetDeck)} note:${JSON.stringify(modelName)}` },
          })),
          endpoint
        )
        setAnkiModelOptions(
          availableModels.filter((_, index) => Array.isArray(modelMatches[index]) && modelMatches[index].length > 0)
        )

        // Fetch NoteType for deck
        if (notes.length > 0) {
          const sampleInfo = await ankiConnectClient.notesInfo([notes[0]], endpoint)
          if (sampleInfo.length > 0) {
            const modelName = sampleInfo[0].modelName
            setSelectedAnkiModel(modelName)
            const fields = await ankiConnectClient.getModelFieldNames(modelName, endpoint)
            setAnkiFields(fields)

            // Auto suggest mapping for matched/custom Flama NoteType
            let targetFlamaModel = null

            // Check saved custom mapping from LocalStorage
            const savedMappingStr = localStorage.getItem(`anki_nt_map_${modelName}`)
            if (savedMappingStr) {
              try {
                const saved = JSON.parse(savedMappingStr)
                targetFlamaModel = noteTypeOptions.find(
                  (m) => m.id === saved.flamaNoteTypeId || m.name.toLowerCase() === (saved.customFlamaName || '').toLowerCase()
                )
              } catch {}
            }

            // Fall back to exact name match or default NoteType
            if (!targetFlamaModel) {
              targetFlamaModel = noteTypeOptions.find((m) => m.name.toLowerCase() === modelName.toLowerCase())
            }

            if (targetFlamaModel) {
              setSelectedFlamaModelId(targetFlamaModel.id)
              const suggested = autoSuggestFieldMapping(fields, targetFlamaModel.fields)
              setFieldMapping(suggested)
            } else {
              setSelectedFlamaModelId('')
              setFieldMapping(Object.fromEntries(fields.map((fieldName) => [fieldName, fieldName])))
            }
          }
        }
      } catch (err) {
        console.warn('Lỗi lấy thông tin deck:', err)
      }
      setIsDeckLoading(false)
    }
    loadDeckDetails()
  }, [selectedDecks, endpoint, noteTypeOptions])

  // Handle Flama Model Change in Step 2
  const handleFlamaModelChange = (flamaModelId: string) => {
    setSelectedFlamaModelId(flamaModelId)
    const targetModel = noteTypeOptions.find((m) => m.id === flamaModelId)
    if (targetModel && ankiFields.length > 0) {
      const suggested = autoSuggestFieldMapping(ankiFields, targetModel.fields)
      setFieldMapping(suggested)
    }
  }

  // Load Preview Notes (Step 3)
  const loadPreview = async () => {
    if (!selectedDeckName || !selectedFlamaModelId) return
    setIsLoadingPreview(true)
    setShowPreviewSection(true)
    setPreviewError(null)
    try {
      const [notes, noteType] = await Promise.all([
        ankiConnectClient.findNotes(buildExactAnkiModelQuery(selectedDeckName, selectedAnkiModel), endpoint),
        appApi.get<FlamaNoteTypeDetail>(`/note-types/${selectedFlamaModelId}`),
      ])
      if (notes.length > 0) {
        const sample = await ankiConnectClient.notesInfo(notes.slice(0, 5), endpoint)
        const matchingNotes = sample.filter((note) => note.modelName === selectedAnkiModel)
        setPreviewNotes(matchingNotes)
        setPreviewNoteIndex(0)
      }
      setPreviewNoteType(noteType)
      setPreviewTemplateId(noteType.templates?.[0]?.id || '')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không thể tải bản xem trước.'
      setPreviewError(message)
    }
    setIsLoadingPreview(false)
  }

  const handleAnkiModelChange = async (modelName: string) => {
    setSelectedAnkiModel(modelName)
    setIsDeckLoading(true)
    try {
      const fields = await ankiConnectClient.getModelFieldNames(modelName, endpoint)
      setAnkiFields(fields)
      const savedMappingStr = localStorage.getItem(`anki_nt_map_${modelName}`)
      let targetModel = noteTypeOptions.find((item) => item.name.toLowerCase() === modelName.toLowerCase())
      if (savedMappingStr) {
        try {
          const saved = JSON.parse(savedMappingStr)
          targetModel = noteTypeOptions.find((item) => item.id === saved.flamaNoteTypeId) || targetModel
        } catch {
          // Ignore invalid legacy mapping and use the best available match.
        }
      }
      if (targetModel) {
        setSelectedFlamaModelId(targetModel.id)
        setFieldMapping(autoSuggestFieldMapping(fields, targetModel.fields))
      } else {
        setSelectedFlamaModelId('')
        setFieldMapping(Object.fromEntries(fields.map((fieldName) => [fieldName, fieldName])))
      }
      setPreviewNotes([])
      setShowPreviewSection(false)
    } finally {
      setIsDeckLoading(false)
    }
  }

  const activePreviewNote = previewNotes[previewNoteIndex] || null
  const previewTemplates = useMemo(() => previewNoteType?.templates || [], [previewNoteType?.templates])
  const activePreviewTemplate = useMemo(
    () => previewTemplates.find((template) => template.id === previewTemplateId) || previewTemplates[0] || null,
    [previewTemplateId, previewTemplates]
  )

  useEffect(() => {
    if (!showPreviewSection || !activePreviewNote || !previewNoteType || !activePreviewTemplate) {
      setPreviewResult(null)
      return
    }

    let cancelled = false
    const timer = window.setTimeout(async () => {
      setIsLoadingPreview(true)
      setPreviewError(null)
      const fieldValues: Record<string, string> = {}
      for (const [ankiFieldName, field] of Object.entries(activePreviewNote.fields)) {
        const targetFieldName = fieldMapping[ankiFieldName]
        if (targetFieldName && targetFieldName !== 'ignore') {
          fieldValues[targetFieldName] = sanitizeAnkiHtml(field.value || '')
        }
      }

      try {
        const result = await appApi.mutate<PreviewResponse>('/note-types/preview', 'POST', {
          front_html: activePreviewTemplate.front_html || '',
          back_html: activePreviewTemplate.back_html || '',
          shared_css: activePreviewTemplate.shared_css || '',
          fields: previewNoteType.field_defs || [],
          field_values: fieldValues,
        })
        if (!cancelled) setPreviewResult(result)
      } catch (err) {
        if (!cancelled) {
          setPreviewResult(null)
          setPreviewError(err instanceof Error ? err.message : 'Không thể render bản xem trước.')
        }
      } finally {
        if (!cancelled) setIsLoadingPreview(false)
      }
    }, 250)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [activePreviewNote, activePreviewTemplate, fieldMapping, previewNoteType, showPreviewSection])

  // State for sync modal
  const [showSyncModal, setShowSyncModal] = useState(false)

  // Execute Sync
  const handleExecuteSync = async () => {
    if (
      connectionStatus !== 'Connected' ||
      !selectedDeckName ||
      !selectedAnkiModel ||
      (!selectedFlamaModelId && !autoSyncMissingNoteTypes)
    ) {
      alert('Vui lòng chọn Deck và cấu hình ánh xạ trường trước khi thực thi.')
      return
    }

    setIsSyncing(true)
    setShowSyncModal(true)
    setSyncReport(null)

    // Load Note Type mapping from localStorage to bypass localStorage restriction in Worker
    const noteTypeMap: Record<string, string> = {}
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('anki_nt_map_')) {
          const modelName = key.substring('anki_nt_map_'.length)
          const raw = localStorage.getItem(key)
          if (raw) {
            noteTypeMap[modelName] = JSON.parse(raw)?.flamaNoteTypeId || ''
          }
        }
      }
    } catch {
      // LocalStorage error fallback
    }

    try {
      if (workerRef.current) {
        workerRef.current.terminate()
      }

      workerRef.current = new Worker(
        new URL('../../../lib/sync.worker.ts', import.meta.url),
        { type: 'module' }
      )

      const csrfToken = getCsrfToken()

      const syncResultPromise = new Promise<{
        success: boolean
        totalSynced: number
        totalSkipped: number
        totalMediaDetected: number
        errors: string[]
      }>((resolve, reject) => {
        if (!workerRef.current) return reject(new Error('Không thể khởi tạo Worker.'))

        workerRef.current.onmessage = (e) => {
          const { type, payload } = e.data
          if (type === 'PROGRESS') {
            setSyncProgress({
              phase: payload.phase,
              totalNotes: payload.totalNotes,
              processedNotes: payload.processedNotes,
              totalMedia: payload.totalMedia,
              processedMedia: payload.processedMedia,
              message: payload.currentMessage,
            })
          } else if (type === 'COMPLETED') {
            resolve(payload)
          } else if (type === 'ERROR') {
            reject(new Error(payload.message || 'Lỗi đồng bộ dữ liệu.'))
          }
        }

        workerRef.current.onerror = (event) => {
          reject(new Error(event.message || 'Worker đồng bộ đã dừng ngoài dự kiến.'))
        }
        workerRef.current.onmessageerror = () => {
          reject(new Error('Không đọc được phản hồi từ Worker đồng bộ.'))
        }

        workerRef.current.postMessage({
          type: 'START_SYNC',
          payload: {
            deckName: selectedDeckName,
            modelName: selectedAnkiModel,
            fieldMapping,
            syncMode,
            flamaUserId,
            csrfToken,
            options: {
              syncMedia: true,
              targetDeckName: targetFlamaDeckName.trim() || selectedDeckName,
              targetNoteTypeId: selectedFlamaModelId,
              endpoint,
              noteTypeOptions,
              autoSyncMissingNoteTypes,
              noteTypeMap,
            },
          },
        })
      })

      const result = await syncResultPromise

      setSyncReport({
        totalSynced: result.totalSynced,
        totalSkipped: result.totalSkipped,
        totalMediaDetected: result.totalMediaDetected,
        errors: result.errors,
      })

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: bootstrapQueryKey }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['decks'] }),
        queryClient.invalidateQueries({ queryKey: ['import-options'] }),
        queryClient.invalidateQueries({ queryKey: ['stats-overview'] }),
        queryClient.invalidateQueries({ queryKey: ['stats'] }),
        queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
      ])
    } catch (err: any) {
      setSyncReport({
        totalSynced: 0,
        errors: [err?.message || 'Lỗi đồng bộ dữ liệu.'],
      })
    } finally {
      if (workerRef.current) {
        workerRef.current.terminate()
        workerRef.current = null
      }
      setIsSyncing(false)
    }
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Step 1: Select Deck */}
      <AnkiDeckSelectCard
        decks={decks}
        deckSearch={deckSearch}
        setDeckSearch={setDeckSearch}
        selectedDecks={selectedDecks}
        setSelectedDecks={setSelectedDecks}
        deckNoteCounts={deckNoteCounts}
      />

      {/* Step 2: Field & Deck Mapping */}
      {selectedDeckName && (
        <AnkiFieldMappingCard
          isDeckLoading={isDeckLoading}
          selectedAnkiModel={selectedAnkiModel}
          onAnkiModelChange={handleAnkiModelChange}
          ankiModelOptions={ankiModelOptions}
          selectedFlamaModelId={selectedFlamaModelId}
          onFlamaModelChange={handleFlamaModelChange}
          noteTypeOptions={noteTypeOptions}
          targetDeckInputId={targetDeckInputId}
          targetFlamaDeckName={targetFlamaDeckName}
          setTargetFlamaDeckName={setTargetFlamaDeckName}
          ankiFields={ankiFields}
          fieldMapping={fieldMapping}
          setFieldMapping={setFieldMapping}
        />
      )}

      {/* Step 3: Consolidated Execution Panel */}
      <AnkiSyncExecuteCard
        selectedDeckName={selectedDeckName}
        loadPreview={loadPreview}
        isLoadingPreview={isLoadingPreview}
        showPreviewSection={showPreviewSection}
        setShowPreviewSection={setShowPreviewSection}
        activePreviewNote={activePreviewNote}
        previewNotes={previewNotes}
        previewNoteIndex={previewNoteIndex}
        setPreviewNoteIndex={setPreviewNoteIndex}
        previewSide={previewSide}
        setPreviewSide={setPreviewSide}
        previewTemplates={previewTemplates}
        previewTemplateId={previewTemplateId}
        setPreviewTemplateId={setPreviewTemplateId}
        previewResult={previewResult}
        selectedFlamaModelId={selectedFlamaModelId}
        previewNoteType={previewNoteType}
        previewError={previewError}
        syncModeSelectId={syncModeSelectId}
        syncMode={syncMode}
        setSyncMode={setSyncMode}
        autoSyncMissingNoteTypes={autoSyncMissingNoteTypes}
        setAutoSyncMissingNoteTypes={setAutoSyncMissingNoteTypes}
        isSyncing={isSyncing}
        connectionStatus={connectionStatus}
        handleExecuteSync={handleExecuteSync}
        syncProgress={syncProgress}
        syncReport={syncReport}
      />

      {/* Sync Progress Loading Modal Overlay */}
      <AnkiSyncProgressDialog
        showSyncModal={showSyncModal}
        setShowSyncModal={setShowSyncModal}
        isSyncing={isSyncing}
        syncProgress={syncProgress}
        syncReport={syncReport}
        selectedDeckName={selectedDeckName}
      />
    </div>
  )
}

