import React, { useState, useEffect, useId } from 'react'
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
import { useFlamaConnect } from '@/context/FlamaConnectContext'
import type {
  AnkiConnectStatus,
  AnkiNoteInfo,
} from '@/lib/ankiConnectClient'
import {
  ankiConnectClient,
} from '@/lib/ankiConnectClient'
import {
  autoSuggestFieldMapping,
  executeAnkiSync,
  executeAnkiMediaSync,
} from '@/lib/ankiSyncEngine'
import { ensureFlamaConnectKey } from '@/lib/ensureFlamaConnectKey'
import {
  sanitizeAnkiHtml,
} from '@/lib/ankiHtmlSanitizer'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
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

interface AnkiSyncTabProps {
  noteTypeOptions: FlamaNoteTypeOption[]
  endpoint: string
  connectionStatus: AnkiConnectStatus
  ankiVersion: number | null
}

export const AnkiSyncTab: React.FC<AnkiSyncTabProps> = ({
  noteTypeOptions,
  endpoint,
  connectionStatus,
}) => {
  const queryClient = useQueryClient()
  const flamaConnect = useFlamaConnect()

  // Step 1: Deck Selection State
  const [decks, setDecks] = useState<string[]>([])
  const [deckSearch, setDeckSearch] = useState('')
  const [selectedDecks, setSelectedDecks] = useState<string[]>([])
  const [deckNoteCounts, setDeckNoteCounts] = useState<Record<string, number>>({})

  // Step 2: Mapping State
  const [selectedDeckName, setSelectedDeckName] = useState<string>('')
  const [targetFlamaDeckName, setTargetFlamaDeckName] = useState<string>('')
  const [selectedAnkiModel, setSelectedAnkiModel] = useState<string>('')
  const [ankiFields, setAnkiFields] = useState<string[]>([])
  const [selectedFlamaModelId, setSelectedFlamaModelId] = useState<string>('')
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({}) // AnkiField -> FlamaField

  // Step 3: Preview State
  const [previewNotes, setPreviewNotes] = useState<AnkiNoteInfo[]>([])
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [showPreviewSection, setShowPreviewSection] = useState(false)

  // Step 4: Sync Execution State
  const [syncMode, setSyncMode] = useState<'new_and_changed' | 'only_new' | 'resync_all'>('new_and_changed')
  const [syncMediaOption, setSyncMediaOption] = useState<'vocab_only' | 'vocab_and_media'>('vocab_only')
  const [isSyncing, setIsSyncing] = useState(false)
  const [isSyncingMedia, setIsSyncingMedia] = useState(false)
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
    totalMediaDetected?: number
    mediaSyncedCount?: number
    errors: string[]
  } | null>(null)

  const syncModeSelectId = useId()
  const syncMediaSelectId = useId()
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
      if (selectedDecks.length === 0) return
      const targetDeck = selectedDecks[0]
      setSelectedDeckName(targetDeck)
      setTargetFlamaDeckName(targetDeck)
      setIsDeckLoading(true)

      try {
        const notes = await ankiConnectClient.findNotes(`deck:"${targetDeck}"`, endpoint)
        setDeckNoteCounts((prev) => ({ ...prev, [targetDeck]: notes.length }))

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
              targetFlamaModel = noteTypeOptions.find((m) => m.name.toLowerCase() === modelName.toLowerCase()) || noteTypeOptions[0]
            }

            if (targetFlamaModel) {
              setSelectedFlamaModelId(targetFlamaModel.id)
              const suggested = autoSuggestFieldMapping(fields, targetFlamaModel.fields)
              setFieldMapping(suggested)
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
    if (!selectedDeckName) return
    setIsLoadingPreview(true)
    setShowPreviewSection(true)
    try {
      const notes = await ankiConnectClient.findNotes(`deck:"${selectedDeckName}"`, endpoint)
      if (notes.length > 0) {
        const sample = await ankiConnectClient.notesInfo(notes.slice(0, 5), endpoint)
        setPreviewNotes(sample)
      }
    } catch (err) {
      console.warn('Lỗi lấy preview:', err)
    }
    setIsLoadingPreview(false)
  }

  // State for sync modal
  const [showSyncModal, setShowSyncModal] = useState(false)

  // Execute Sync
  const handleExecuteSync = async () => {
    if (!selectedDeckName || !selectedAnkiModel) {
      alert('Vui lòng chọn Deck và cấu hình ánh xạ trường trước khi thực thi.')
      return
    }

    setIsSyncing(true)
    setShowSyncModal(true)
    setSyncReport(null)

    try {
      const key = await ensureFlamaConnectKey(flamaConnect)
      const account = flamaConnect.account || {
        userId: 1,
        username: 'web_user',
        displayName: 'Web User',
        workspace: 'default',
        importPermission: true,
        uploadLimit: 10000,
      }

      const result = await executeAnkiSync(
        selectedDeckName,
        selectedAnkiModel,
        fieldMapping,
        syncMode,
        key,
        account,
        (progress) => {
          setSyncProgress({
            phase: progress.phase,
            totalNotes: progress.totalNotes,
            processedNotes: progress.processedNotes,
            totalMedia: progress.totalMedia,
            processedMedia: progress.processedMedia,
            message: progress.currentMessage,
          })
        },
        {
          syncMedia: syncMediaOption === 'vocab_and_media',
          targetDeckName: targetFlamaDeckName.trim() || selectedDeckName,
        }
      )

      setSyncReport({
        totalSynced: result.totalSynced,
        totalMediaDetected: result.totalMediaDetected,
        errors: result.errors,
      })

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['bootstrap'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['decks'] }),
        queryClient.invalidateQueries({ queryKey: ['import-options'] }),
        queryClient.invalidateQueries({ queryKey: ['stats-overview'] }),
      ])
    } catch (err: any) {
      setSyncReport({
        totalSynced: 0,
        errors: [err?.message || 'Lỗi đồng bộ dữ liệu.'],
      })
    }
    setIsSyncing(false)
  }

  // Execute Deferred Media Sync
  const handleSyncMediaOnly = async () => {
    if (!selectedDeckName) return

    setIsSyncingMedia(true)
    setIsSyncing(true)
    setShowSyncModal(true)

    try {
      const key = await ensureFlamaConnectKey(flamaConnect)
      const mediaResult = await executeAnkiMediaSync(
        selectedDeckName,
        key,
        (progress) => {
          setSyncProgress({
            phase: progress.phase,
            totalNotes: progress.totalNotes,
            processedNotes: progress.processedNotes,
            totalMedia: progress.totalMedia,
            processedMedia: progress.processedMedia,
            message: progress.currentMessage,
          })
        }
      )

      setSyncReport((prev) => ({
        totalSynced: prev?.totalSynced || 0,
        totalMediaDetected: prev?.totalMediaDetected,
        mediaSyncedCount: mediaResult.syncedMediaCount,
        errors: [...(prev?.errors || []), ...mediaResult.errors],
      }))
    } catch (err: any) {
      setSyncReport((prev) => ({
        totalSynced: prev?.totalSynced || 0,
        errors: [...(prev?.errors || []), err?.message || 'Lỗi tải media.'],
      }))
    }
    setIsSyncing(false)
    setIsSyncingMedia(false)
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
                <Input value={selectedAnkiModel || 'Basic'} disabled className="h-8 text-xs font-semibold bg-muted/40" />
              </div>

              <div className="space-y-1">
                <Label className="text-xs font-semibold text-muted-foreground">Flama NoteType đích</Label>
                <NativeSelect
                  value={selectedFlamaModelId}
                  onChange={(e) => handleFlamaModelChange(e.target.value)}
                  className="h-8 text-xs font-semibold text-primary"
                >
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
                        >
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
          {showPreviewSection && previewNotes.length > 0 && (
            <div className="p-3 border rounded-xl bg-card/40 space-y-2 mb-4">
              <div className="flex items-center justify-between text-xs font-bold border-b pb-1.5">
                <span>Mẫu thẻ xem trước ({previewNotes.length} thẻ)</span>
                <Button size="xs" variant="ghost" onClick={() => setShowPreviewSection(false)} className="h-6 text-[11px]">
                  Ẩn
                </Button>
              </div>
              <div className="grid grid-cols-1 gap-2.5 max-h-60 overflow-y-auto pr-1">
                {previewNotes.map((note) => (
                  <div key={note.noteId} className="p-2.5 border rounded-lg bg-background/60 space-y-1.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-mono text-muted-foreground">ID Thẻ: #{note.noteId}</span>
                      <Badge variant="outline" className="text-[9px] py-0 px-1 font-normal">
                        New
                      </Badge>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {Object.entries(note.fields).map(([fieldName, fieldObj]) => (
                        <div key={fieldName} className="p-1.5 border rounded bg-muted/20">
                          <span className="font-bold text-[10px] text-muted-foreground block">{fieldName}</span>
                          <div
                            className="text-foreground prose prose-sm max-w-none text-xs truncate"
                            dangerouslySetInnerHTML={{ __html: sanitizeAnkiHtml(fieldObj.value) }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 items-end">
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

            <div className="space-y-1">
              <Label htmlFor={syncMediaSelectId} className="text-xs font-semibold text-muted-foreground">
                Cơ chế nạp Media (Ảnh/Âm thanh)
              </Label>
              <NativeSelect
                id={syncMediaSelectId}
                value={syncMediaOption}
                onChange={(e) => setSyncMediaOption(e.target.value as any)}
                className="h-8 text-xs w-full font-semibold text-primary"
              >
                <option value="vocab_only">⚡ Bulk Tốc độ cao: Chỉ Từ vựng (Media tải sau)</option>
                <option value="vocab_and_media">📦 Đầy đủ: Từ vựng + Tải luôn Ảnh &amp; Âm thanh</option>
              </NativeSelect>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-2.5 pt-2">
            {selectedDeckName && (
              <Button
                variant="outline"
                size="sm"
                disabled={isSyncing || isSyncingMedia}
                onClick={handleSyncMediaOnly}
                className="font-semibold text-xs text-amber-700 dark:text-amber-300 border-amber-500/30 hover:bg-amber-500/10 h-9 rounded-xl w-full sm:w-auto px-4"
              >
                {isSyncingMedia ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Zap className="size-3.5 mr-1.5 text-amber-500" />}
                Tải lại riêng Media (Ảnh &amp; Âm thanh)
              </Button>
            )}

            <Button
              disabled={isSyncing || !selectedDeckName}
              onClick={handleExecuteSync}
              className="font-bold text-xs shadow-sm w-full sm:w-auto px-6 h-9 rounded-xl"
            >
              {isSyncing ? <Loader2 className="size-4 animate-spin mr-2" /> : <Zap className="size-4 mr-2" />}
              {syncMediaOption === 'vocab_only' ? 'Bắt đầu Bulk Sync Từ Vựng' : 'Bắt đầu Đồng bộ Đầy đủ'}
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
                <div>Đã nạp thành công {syncReport.totalSynced} thẻ từ vựng lên Flama Cloud.</div>

                {syncReport.totalMediaDetected !== undefined && syncReport.totalMediaDetected > 0 && (
                  <div className="pt-1 flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-border/60">
                    <span className="text-muted-foreground text-[11px]">
                      Phát hiện <strong>{syncReport.totalMediaDetected}</strong> file Media liên kết.
                    </span>
                    <Button
                      size="xs"
                      variant="outline"
                      disabled={isSyncingMedia}
                      onClick={handleSyncMediaOnly}
                      className="h-7 text-xs font-semibold text-amber-700 border-amber-500/40 hover:bg-amber-50 dark:text-amber-300 rounded-lg shrink-0"
                    >
                      {isSyncingMedia ? <Loader2 className="size-3 animate-spin mr-1" /> : <Zap className="size-3 mr-1 text-amber-500" />}
                      {syncReport.mediaSyncedCount !== undefined
                        ? `Đã đồng bộ (${syncReport.mediaSyncedCount}/${syncReport.totalMediaDetected}) Media`
                        : `Đồng bộ tiếp ${syncReport.totalMediaDetected} Media`}
                    </Button>
                  </div>
                )}

                {syncReport.errors.map((err, idx) => (
                  <div key={idx} className="text-destructive font-mono text-[11px]">• {err}</div>
                ))}
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
                ? isSyncingMedia
                  ? 'Đang nạp file Ảnh & Âm thanh (Media)...'
                  : 'Đang tiến hành Bulk Sync thẻ từ vựng...'
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
                  <div>Đã đồng bộ {syncReport.totalSynced} thẻ từ vựng lên Flama.</div>

                  {syncReport.totalMediaDetected !== undefined && syncReport.totalMediaDetected > 0 && (
                    <div className="pt-1.5 flex flex-col items-start gap-2 border-t border-emerald-500/20">
                      <span className="text-muted-foreground text-[11px]">
                        Phát hiện {syncReport.totalMediaDetected} file Ảnh &amp; Âm thanh.
                      </span>
                      <Button
                        size="xs"
                        variant="secondary"
                        disabled={isSyncingMedia}
                        onClick={handleSyncMediaOnly}
                        className="w-full h-8 text-xs font-bold bg-amber-500 text-slate-950 hover:bg-amber-400 rounded-lg shadow-xs"
                      >
                        {isSyncingMedia ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Zap className="size-3.5 mr-1.5" />}
                        {syncReport.mediaSyncedCount !== undefined
                          ? `Đã nạp ${syncReport.mediaSyncedCount}/${syncReport.totalMediaDetected} file Media`
                          : `Đồng bộ tiếp ${syncReport.totalMediaDetected} file Media`}
                      </Button>
                    </div>
                  )}

                  {syncReport.errors.map((err, idx) => (
                    <div key={idx} className="text-destructive font-mono text-[11px]">• {err}</div>
                  ))}
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
