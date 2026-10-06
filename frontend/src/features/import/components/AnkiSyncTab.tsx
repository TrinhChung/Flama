import React, { useState, useEffect, useId, useMemo, useRef } from 'react'
import {
  Search,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Layers,
  ArrowRightLeft,
  Eye,
  Zap,
} from 'lucide-react'
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
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Checkbox } from '@/components/ui/checkbox'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { NoteTypeLivePreview } from '@/features/note-types/components/NoteTypeLivePreview'
import { AnkiDeckTreeView } from './AnkiDeckTreeView'

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
      <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
        <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-card/40">
          <CardTitle className="text-sm font-semibold flex items-center justify-between flex-wrap gap-2">
            <span className="flex items-center gap-2">
              <Layers className="size-4 text-primary shrink-0" /> 1. Chọn Deck Anki đồng bộ
            </span>
            <span className="text-xs text-muted-foreground font-normal">Đã chọn {selectedDecks.length} deck</span>
          </CardTitle>
          <CardDescription className="text-xs">
            Chọn danh mục bộ thẻ Anki bạn muốn nhập hoặc đồng bộ lên Flama.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-4 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              value={deckSearch}
              onChange={(e) => setDeckSearch(e.target.value)}
              placeholder="Tìm kiếm tên deck..."
              className="pl-9 text-xs h-9"
            />
          </div>

          <AnkiDeckTreeView
            decks={decks}
            searchQuery={deckSearch}
            selectedDecks={selectedDecks}
            deckNoteCounts={deckNoteCounts}
            onSelectDeck={(deckName) => {
              if (selectedDecks.includes(deckName)) {
                setSelectedDecks(selectedDecks.filter((item) => item !== deckName))
              } else {
                setSelectedDecks([deckName])
              }
            }}
          />
        </CardContent>
      </Card>

      {/* Step 2: Field & Deck Mapping */}
      {selectedDeckName && (
        <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
          <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-card/40">
            <CardTitle className="text-sm font-semibold flex items-center justify-between flex-wrap gap-2">
              <span className="flex items-center gap-2">
                <ArrowRightLeft className="size-4 text-primary shrink-0" /> 2. Cấu hình Deck &amp; Ánh xạ Trường
              </span>
              {isDeckLoading && (
                <span className="text-xs text-muted-foreground font-normal flex items-center gap-1.5">
                  <Loader2 className="size-3.5 animate-spin" /> Đang đọc thông tin...
                </span>
              )}
            </CardTitle>
            <CardDescription className="text-xs">
              Tùy chỉnh tên Deck đích trên Flama (dùng <code className="font-mono text-primary font-bold">::</code> tạo phân cấp) và ghép các trường.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 sm:p-5 pt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
              <div className="space-y-1">
                <Label className="text-xs font-semibold text-muted-foreground">NoteType Anki gốc</Label>
                <NativeSelect
                  value={selectedAnkiModel}
                  onChange={(event) => void handleAnkiModelChange(event.target.value)}
                  className="h-8 text-xs font-semibold"
                >
                  {ankiModelOptions.map((modelName) => (
                    <option key={modelName} value={modelName}>{modelName}</option>
                  ))}
                </NativeSelect>
              </div>

              <div className="space-y-1">
                <Label className="text-xs font-semibold text-muted-foreground">Flama NoteType đích</Label>
                <NativeSelect
                  value={selectedFlamaModelId}
                  onChange={(e) => handleFlamaModelChange(e.target.value)}
                  className="h-8 text-xs font-semibold text-primary"
                >
                  <option value="">-- Chưa có NoteType tương thích --</option>
                  {noteTypeOptions.map((nt) => (
                    <option key={nt.id} value={nt.id}>
                      {nt.name} ({nt.fields?.length || 0} trường)
                    </option>
                  ))}
                </NativeSelect>
              </div>

              <div className="space-y-1">
                <Label htmlFor={targetDeckInputId} className="text-xs font-semibold text-muted-foreground">
                  Tên Deck Flama đích
                </Label>
                <Input
                  id={targetDeckInputId}
                  value={targetFlamaDeckName}
                  onChange={(e) => setTargetFlamaDeckName(e.target.value)}
                  placeholder="Ví dụ: Tiếng Nhật::JLPT N3::Từ vựng"
                  className="h-8 text-xs font-semibold"
                />
              </div>
            </div>

            {/* Field Mapping Container */}
            <div className="border rounded-xl p-3 bg-card/30 space-y-2">
              <div className="hidden sm:flex items-center justify-between text-xs font-semibold border-b pb-2 text-muted-foreground">
                <span>Trường dữ liệu Anki</span>
                <span>Trường Flama tương ứng</span>
              </div>
              <div className="divide-y divide-border/40">
                {ankiFields.map((ankiField) => {
                  const currentFlamaField = fieldMapping[ankiField] || 'ignore'
                  const targetFlamaModel = noteTypeOptions.find((m) => m.id === selectedFlamaModelId)

                  return (
                    <div
                      key={ankiField}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-4 py-2 border-b border-border/40 last:border-0"
                    >
                      <span className="text-xs font-bold text-foreground truncate max-w-full sm:max-w-xs">
                        {ankiField}
                      </span>
                      <div className="w-full sm:w-64 shrink-0">
                        <NativeSelect
                          value={currentFlamaField}
                          onChange={(e) => setFieldMapping({ ...fieldMapping, [ankiField]: e.target.value })}
                          className="h-8 text-xs font-medium"
                          disabled={!targetFlamaModel}
                        >
                          {!targetFlamaModel && <option value={ankiField}>{ankiField} (sẽ tự tạo)</option>}
                          <option value="ignore">-- Bỏ qua trường này --</option>
                          {targetFlamaModel?.fields.map((ff) => (
                            <option key={ff.id} value={ff.name}>
                              {ff.name} ({ff.field_type})
                            </option>
                          ))}
                        </NativeSelect>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Consolidated Execution Panel */}
      <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
        <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-card/40">
          <CardTitle className="text-sm font-semibold flex items-center justify-between flex-wrap gap-2">
            <span className="flex items-center gap-2">
              <Zap className="size-4 text-primary shrink-0" /> 3. Thực thi đồng bộ (Anki → Flama)
            </span>
            {selectedDeckName && (
              <Button
                size="xs"
                variant="outline"
                onClick={loadPreview}
                disabled={isLoadingPreview}
                className="h-7 text-xs font-medium"
              >
                {isLoadingPreview ? (
                  <Loader2 className="size-3 animate-spin mr-1" />
                ) : (
                  <Eye className="size-3 mr-1 text-primary" />
                )}
                {showPreviewSection ? 'Tải lại Xem trước' : 'Xem trước thẻ mẫu'}
              </Button>
            )}
          </CardTitle>
          <CardDescription className="text-xs">
            Chọn chế độ lọc và hình thức tải media để tiến hành nhập thẻ lên hệ thống.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-4 space-y-4">
          {/* Optional Preview Collapsible Container */}
          {showPreviewSection && (
            <div className="space-y-2 mb-4">
              <div className="flex items-center justify-between text-xs font-bold border-b pb-1.5">
                <div className="flex items-center gap-2">
                  <span>Thẻ Anki #{activePreviewNote?.noteId || '—'}</span>
                  {previewNotes.length > 1 && (
                    <NativeSelect
                      value={String(previewNoteIndex)}
                      onChange={(event) => setPreviewNoteIndex(Number(event.target.value))}
                      className="h-7 w-28 text-[11px]"
                    >
                      {previewNotes.map((note, index) => (
                        <option key={note.noteId} value={index}>Mẫu {index + 1}</option>
                      ))}
                    </NativeSelect>
                  )}
                </div>
                <Button size="xs" variant="ghost" onClick={() => setShowPreviewSection(false)} className="h-6 text-[11px]">
                  Ẩn
                </Button>
              </div>
              <NoteTypeLivePreview
                cardId={`anki-deck-preview-${activePreviewNote?.noteId || 'empty'}`}
                side={previewSide}
                onSideChange={setPreviewSide}
                templates={previewTemplates.map((template) => ({ id: template.id, name: template.name }))}
                selectedTemplateId={previewTemplateId}
                onSelectTemplate={setPreviewTemplateId}
                frontPayload={previewResult?.front_renderer_payload}
                backPayload={previewResult?.back_renderer_payload}
                frontHtml={previewResult?.front_html}
                backHtml={previewResult?.back_html}
                scope="anki_deck_import_preview"
                scopeId={selectedFlamaModelId}
                fieldDefs={previewNoteType?.field_defs || []}
                isLoading={isLoadingPreview}
                error={previewError || (previewNotes.length === 0 ? 'Deck không có thẻ thuộc NoteType Anki đã chọn.' : null)}
                title="Card Review Preview"
                subtitle="Dữ liệu thật sau khi áp dụng ánh xạ trường"
                containerHeightClass="h-[clamp(18rem,48vh,34rem)] min-h-[288px]"
              />
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:gap-4 items-end">
            <div className="space-y-1">
              <Label htmlFor={syncModeSelectId} className="text-xs font-semibold text-muted-foreground">
                Chế độ lọc thẻ
              </Label>
              <NativeSelect
                id={syncModeSelectId}
                value={syncMode}
                onChange={(e) => setSyncMode(e.target.value as any)}
                className="h-8 text-xs w-full font-medium"
              >
                <option value="new_and_changed">Thẻ mới + Thẻ đã thay đổi (Mặc định)</option>
                <option value="only_new">Chỉ thẻ mới chưa có trên Flama</option>
                <option value="resync_all">Đồng bộ lại toàn bộ deck</option>
              </NativeSelect>
            </div>

            <label className="flex items-start gap-2.5 rounded-xl border border-border/70 bg-card/40 p-3 cursor-pointer">
              <Checkbox
                checked={autoSyncMissingNoteTypes}
                onCheckedChange={(checked) => setAutoSyncMissingNoteTypes(Boolean(checked))}
                className="mt-0.5"
              />
              <span className="space-y-0.5">
                <span className="block text-xs font-semibold text-foreground">
                  Tự tạo NoteType còn thiếu trước khi đồng bộ deck
                </span>
                <span className="block text-[11px] leading-relaxed text-muted-foreground">
                  Nếu tắt, chỉ cần một NoteType thiếu hoặc không tương thích thì toàn bộ phiên sẽ bị chặn và không tạo deck/card/media.
                </span>
              </span>
            </label>

          </div>

          <Alert className="border-primary/30 bg-primary/5">
            <CheckCircle2 className="size-4 text-primary" />
            <AlertDescription className="text-xs text-muted-foreground">
              Cấu trúc deck con được giữ theo đường dẫn tương đối. Audio và hình ảnh được kiểm tra, upload theo hash rồi đính vào card qua MediaAsset.
            </AlertDescription>
          </Alert>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-2.5 pt-2">
            <Button
              disabled={
                isSyncing ||
                connectionStatus !== 'Connected' ||
                !selectedDeckName ||
                (!selectedFlamaModelId && !autoSyncMissingNoteTypes)
              }
              onClick={handleExecuteSync}
              className="font-bold text-xs shadow-sm w-full sm:w-auto px-6 h-9 rounded-xl"
            >
              {isSyncing ? <Loader2 className="size-4 animate-spin mr-2" /> : <Zap className="size-4 mr-2" />}
              Bắt đầu đồng bộ deck + media
            </Button>
          </div>

          {isSyncing && syncProgress && (
            <div className="space-y-2 p-3 border rounded-xl bg-muted/30">
              <div className="flex justify-between text-xs font-semibold">
                <span>{syncProgress.message}</span>
                <span>
                  {syncProgress.processedNotes}/{syncProgress.totalNotes} Thẻ
                </span>
              </div>
              <Progress
                value={syncProgress.totalNotes > 0 ? (syncProgress.processedNotes / syncProgress.totalNotes) * 100 : 10}
                className="h-2"
              />
            </div>
          )}

          {syncReport && (
            <Alert className={syncReport.errors.length === 0 ? 'border-primary/40 bg-primary/5' : 'border-destructive/40 bg-destructive/5'}>
              {syncReport.errors.length === 0 ? <CheckCircle2 className="size-5 text-primary" /> : <AlertTriangle className="size-5 text-destructive" />}
              <AlertTitle className="font-bold text-xs">
                {syncReport.errors.length === 0 ? 'Hoàn tất đồng bộ thành công!' : 'Đồng bộ có lỗi xảy ra'}
              </AlertTitle>
              <AlertDescription className="mt-1.5 text-xs space-y-2">
                <div>Đã đồng bộ {syncReport.totalSynced} note lên Flama.</div>
                {Boolean(syncReport.totalSkipped) && (
                  <div>Đã bỏ qua {syncReport.totalSkipped} note không thay đổi.</div>
                )}

                {Boolean(syncReport.totalMediaDetected) && (
                  <div className="text-muted-foreground text-[11px]">
                    Có {syncReport.totalMediaDetected} tham chiếu media được phát hiện nhưng chưa upload.
                  </div>
                )}

                {syncReport.errors.length > 0 && (
                  <div className="max-h-[160px] overflow-y-auto pr-1 mt-1.5 space-y-1 border-t border-destructive/20 pt-1.5">
                    {syncReport.errors.map((err, idx) => (
                      <div key={idx} className="text-destructive font-mono text-[11px] break-words">• {err}</div>
                    ))}
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Sync Progress Loading Modal Overlay */}
      <Dialog
        open={showSyncModal}
        onOpenChange={(open) => {
          if (!isSyncing) setShowSyncModal(open)
        }}
      >
        <DialogContent className="sm:max-w-md border-border/80 shadow-2xl rounded-2xl p-6">
          <DialogHeader className="items-center text-center space-y-3">
            <div className={`size-14 rounded-full flex items-center justify-center ${isSyncing ? 'bg-primary/10 text-primary animate-pulse' : 'bg-emerald-500/10 text-emerald-600'}`}>
              {isSyncing ? <Loader2 className="size-7 animate-spin text-primary" /> : <CheckCircle2 className="size-7 text-emerald-500" />}
            </div>
            <DialogTitle className="text-base font-bold text-foreground">
              {isSyncing
                ? 'Đang tiến hành đồng bộ nội dung thẻ...'
                : 'Hoàn tất đồng bộ!'}
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              {isSyncing
                ? 'Vui lòng giữ trình duyệt mở trong khi dữ liệu đang được nạp lên hệ thống.'
                : `Đã xử lý xong dữ liệu cho bộ thẻ "${selectedDeckName}".`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {syncProgress && (
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-semibold text-foreground">
                  <span className="truncate max-w-[200px]">{syncProgress.message}</span>
                  <span className="shrink-0 font-mono">
                    {syncProgress.processedNotes}/{syncProgress.totalNotes} Thẻ
                  </span>
                </div>
                <Progress
                  value={syncProgress.totalNotes > 0 ? (syncProgress.processedNotes / syncProgress.totalNotes) * 100 : 10}
                  className="h-2 rounded-full"
                />
                {syncProgress.totalMedia > 0 && (
                  <div className="text-[11px] font-mono text-muted-foreground text-right">
                    Upload Media: {syncProgress.processedMedia}/{syncProgress.totalMedia} tệp
                  </div>
                )}
              </div>
            )}

            {syncReport && (
              <Alert className={syncReport.errors.length === 0 ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-destructive/40 bg-destructive/10'}>
                {syncReport.errors.length === 0 ? <CheckCircle2 className="size-5 text-emerald-600" /> : <AlertTriangle className="size-5 text-destructive" />}
                <AlertTitle className="font-bold text-xs">
                  {syncReport.errors.length === 0 ? 'Thành công!' : 'Có lỗi phát sinh'}
                </AlertTitle>
                <AlertDescription className="mt-1 text-xs space-y-2">
                  <div>Đã đồng bộ {syncReport.totalSynced} note lên Flama.</div>
                  {Boolean(syncReport.totalSkipped) && (
                    <div>Đã bỏ qua {syncReport.totalSkipped} note không thay đổi.</div>
                  )}

                  {Boolean(syncReport.totalMediaDetected) && (
                    <div className="text-muted-foreground text-[11px] border-t border-border/60 pt-1.5">
                      Có {syncReport.totalMediaDetected} tham chiếu media chưa được upload.
                    </div>
                  )}

                  {syncReport.errors.length > 0 && (
                    <div className="max-h-[160px] overflow-y-auto pr-1 mt-1.5 space-y-1 border-t border-destructive/20 pt-1.5">
                      {syncReport.errors.map((err, idx) => (
                        <div key={idx} className="text-destructive font-mono text-[11px] break-words">• {err}</div>
                      ))}
                    </div>
                  )}
                </AlertDescription>
              </Alert>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <Button
              disabled={isSyncing}
              onClick={() => setShowSyncModal(false)}
              className="w-full sm:w-auto font-semibold text-xs rounded-xl"
            >
              {isSyncing ? 'Đang đồng bộ...' : 'Đóng cửa sổ'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
