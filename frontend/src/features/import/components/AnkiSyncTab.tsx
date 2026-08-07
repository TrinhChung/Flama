import React, { useState, useEffect, useId } from 'react'
import {
  RefreshCw,
  Search,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Layers,
  ArrowRightLeft,
  Eye,
  Zap,
  Wifi,
  WifiOff,
} from 'lucide-react'
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
} from '@/lib/ankiSyncEngine'
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
}

export const AnkiSyncTab: React.FC<AnkiSyncTabProps> = ({ noteTypeOptions }) => {
  const flamaConnect = useFlamaConnect()

  // Connection State
  const [endpoint, setEndpoint] = useState('http://127.0.0.1:8765')
  const [connectionStatus, setConnectionStatus] = useState<AnkiConnectStatus>('Anki is not running')
  const [ankiVersion, setAnkiVersion] = useState<number | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [isCheckingConn, setIsCheckingConn] = useState(false)

  // Step 1: Deck Selection State
  const [decks, setDecks] = useState<string[]>([])
  const [deckSearch, setDeckSearch] = useState('')
  const [selectedDecks, setSelectedDecks] = useState<string[]>([])
  const [deckNoteCounts, setDeckNoteCounts] = useState<Record<string, number>>({})

  // Step 2: Mapping State
  const [selectedDeckName, setSelectedDeckName] = useState<string>('')
  const [selectedAnkiModel, setSelectedAnkiModel] = useState<string>('')
  const [ankiFields, setAnkiFields] = useState<string[]>([])
  const [selectedFlamaModelId, setSelectedFlamaModelId] = useState<string>('')
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({}) // AnkiField -> FlamaField

  // Step 3: Preview State
  const [previewNotes, setPreviewNotes] = useState<AnkiNoteInfo[]>([])
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)

  // Step 4: Sync Execution State
  const [syncMode, setSyncMode] = useState<'new_and_changed' | 'only_new' | 'resync_all'>('new_and_changed')
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncProgress, setSyncProgress] = useState<{
    phase: string
    totalNotes: number
    processedNotes: number
    totalMedia: number
    processedMedia: number
    message: string
  } | null>(null)
  const [syncReport, setSyncReport] = useState<{ totalSynced: number; errors: string[] } | null>(null)

  const endpointInputId = useId()
  const syncModeSelectId = useId()

  // 1. Connection Health Check
  const checkAnkiConnection = async () => {
    setIsCheckingConn(true)
    setConnectionError(null)
    const result = await ankiConnectClient.checkConnection(endpoint)
    setConnectionStatus(result.status)
    if (result.version) setAnkiVersion(result.version)
    if (result.error) setConnectionError(result.error)

    if (result.status === 'Connected') {
      try {
        const deckList = await ankiConnectClient.getDeckNames(endpoint)
        setDecks(deckList)
      } catch (err: any) {
        setConnectionError(err.message || 'Không thể lấy danh sách deck từ Anki.')
      }
    }
    setIsCheckingConn(false)
  }

  useEffect(() => {
    checkAnkiConnection()
  }, [])

  const [isDeckLoading, setIsDeckLoading] = useState(false)

  // 2. Lazy load note count and NoteType details ONLY when a deck is selected
  useEffect(() => {
    async function loadDeckDetails() {
      if (selectedDecks.length === 0) return
      const targetDeck = selectedDecks[0]
      setSelectedDeckName(targetDeck)
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

            // 1. Check saved custom mapping from LocalStorage
            const savedMappingStr = localStorage.getItem(`anki_nt_map_${modelName}`)
            if (savedMappingStr) {
              try {
                const saved = JSON.parse(savedMappingStr)
                targetFlamaModel = noteTypeOptions.find(
                  (m) => m.id === saved.flamaNoteTypeId || m.name.toLowerCase() === (saved.customFlamaName || '').toLowerCase()
                )
              } catch {}
            }

            // 2. Fall back to exact name match or default NoteType
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
  }, [selectedDecks])

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

    const key = flamaConnect.getValidKey() || 'web_session'
    const account = flamaConnect.account || {
      userId: 1,
      username: 'web_user',
      displayName: 'Web User',
      workspace: 'default',
      importPermission: true,
      uploadLimit: 10000,
    }

    try {
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
        }
      )

      setSyncReport({
        totalSynced: result.totalSynced,
        errors: result.errors,
      })
    } catch (err: any) {
      setSyncReport({
        totalSynced: 0,
        errors: [err?.message || 'Lỗi đồng bộ dữ liệu.'],
      })
    }
    setIsSyncing(false)
  }

  return (
    <div className="space-y-6">
      {/* Connection Header Bar */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden bg-card/60">
        <CardContent className="p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={`size-10 rounded-xl flex items-center justify-center shrink-0 ${
              connectionStatus === 'Connected' ? 'bg-emerald-500/15 text-emerald-600' : 'bg-destructive/15 text-destructive'
            }`}>
              {connectionStatus === 'Connected' ? <Wifi className="size-5" /> : <WifiOff className="size-5" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-foreground">AnkiConnect Endpoint</span>
                {connectionStatus === 'Connected' ? (
                  <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[11px]">
                    Connected (v{ankiVersion})
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="text-[11px]">
                    {connectionStatus}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {connectionError || 'Ứng dụng sẽ đọc trực tiếp dữ liệu thẻ từ Anki Desktop qua giao thức AnkiConnect local.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto">
            <div className="w-48">
              <Input
                id={endpointInputId}
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="http://127.0.0.1:8765"
                className="h-8 text-xs font-mono"
              />
            </div>
            <Button size="sm" variant="outline" onClick={checkAnkiConnection} disabled={isCheckingConn}>
              {isCheckingConn ? <Loader2 className="size-3.5 animate-spin mr-1" /> : <RefreshCw className="size-3.5 mr-1" />}
              Kiểm tra
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Step 1: Select Deck */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b bg-card/50">
          <CardTitle className="text-sm font-semibold flex items-center justify-between">
            <span className="flex items-center gap-2"><Layers className="size-4 text-primary" /> 1. Chọn Deck Anki đồng bộ</span>
            <span className="text-xs text-muted-foreground font-normal">Đã chọn {selectedDecks.length} deck</span>
          </CardTitle>
          <CardDescription className="text-xs">
            Chọn danh mục bộ thẻ Anki bạn muốn nhập hoặc đồng bộ lên Flama.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4 space-y-3">
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

      {/* Step 2: Field Mapping */}
      {selectedDeckName && (
        <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
          <CardHeader className="pb-3 border-b bg-card/50">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <ArrowRightLeft className="size-4 text-primary" /> 2. Ánh xạ trường dữ liệu (Anki → Flama)
              </span>
              {isDeckLoading && (
                <span className="text-xs text-muted-foreground font-normal flex items-center gap-1.5">
                  <Loader2 className="size-3.5 animate-spin" /> Đang đọc thông tin deck...
                </span>
              )}
            </CardTitle>
            <CardDescription className="text-xs">
              Ghép các trường của NoteType trong Anki tương ứng với cấu trúc thẻ trên Flama.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-xs font-semibold text-muted-foreground">Anki NoteType</Label>
                <Input value={selectedAnkiModel || 'Basic'} disabled className="h-8 text-xs font-semibold bg-muted/40" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs font-semibold text-muted-foreground">Flama NoteType đích</Label>
                <NativeSelect
                  value={selectedFlamaModelId}
                  onChange={(e) => handleFlamaModelChange(e.target.value)}
                  className="h-8 text-xs"
                >
                  {noteTypeOptions.map((nt) => (
                    <option key={nt.id} value={nt.id}>
                      {nt.name}
                    </option>
                  ))}
                </NativeSelect>
              </div>
            </div>

            <div className="border rounded-xl p-3 bg-card/40 space-y-2">
              <div className="flex items-center justify-between text-xs font-semibold border-b pb-2 text-muted-foreground">
                <span>Trường dữ liệu Anki</span>
                <span>Trường Flama tương ứng</span>
              </div>
              {ankiFields.map((ankiField) => {
                const currentFlamaField = fieldMapping[ankiField] || 'ignore'
                const targetFlamaModel = noteTypeOptions.find((m) => m.id === selectedFlamaModelId)

                return (
                  <div key={ankiField} className="flex items-center justify-between gap-4 py-1">
                    <span className="text-xs font-bold text-foreground">{ankiField}</span>
                    <div className="w-56">
                      <NativeSelect
                        value={currentFlamaField}
                        onChange={(e) => setFieldMapping({ ...fieldMapping, [ankiField]: e.target.value })}
                        className="h-7 text-xs"
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
          </CardContent>
        </Card>
      )}

      {/* Step 3: Preview */}
      {selectedDeckName && (
        <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
          <CardHeader className="pb-3 border-b bg-card/50 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Eye className="size-4 text-primary" /> 3. Xem trước nội dung mẫu (Preview)
              </CardTitle>
              <CardDescription className="text-xs">
                Rà soát thẻ mẫu sau khi đã chuyển đổi HTML, định dạng Ruby và media.
              </CardDescription>
            </div>
            <Button size="sm" variant="outline" onClick={loadPreview} disabled={isLoadingPreview}>
              {isLoadingPreview ? <Loader2 className="size-3.5 animate-spin mr-1" /> : <Eye className="size-3.5 mr-1" />}
              Tải xem trước
            </Button>
          </CardHeader>
          <CardContent className="pt-4 space-y-3">
            {previewNotes.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">Nhấn "Tải xem trước" để hiển thị mẫu thẻ.</p>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {previewNotes.map((note) => (
                  <div key={note.noteId} className="p-3 border rounded-xl bg-card/40 space-y-2">
                    <div className="flex items-center justify-between border-b pb-1.5 text-xs">
                      <span className="font-mono text-muted-foreground">ID Thẻ: #{note.noteId}</span>
                      <Badge variant="outline" className="bg-primary/5 text-primary text-[10px]">Mới (New)</Badge>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {Object.entries(note.fields).map(([fieldName, fieldObj]) => (
                        <div key={fieldName} className="p-2 border rounded bg-background/50 space-y-1">
                          <span className="font-bold text-[11px] text-muted-foreground block">{fieldName}</span>
                          <div
                            className="text-foreground prose prose-sm max-w-none text-xs"
                            dangerouslySetInnerHTML={{ __html: sanitizeAnkiHtml(fieldObj.value) }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 4: Sync Execution */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b bg-card/50">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Zap className="size-4 text-primary" /> 4. Thực thi đồng bộ (Anki → Flama)
          </CardTitle>
          <CardDescription className="text-xs">
            Chọn chế độ và tiến hành upload thẻ &amp; media thông qua phiên Flama Connect đã xác thực.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <Label htmlFor={syncModeSelectId} className="text-xs font-semibold">Chế độ đồng bộ</Label>
              <NativeSelect
                id={syncModeSelectId}
                value={syncMode}
                onChange={(e) => setSyncMode(e.target.value as any)}
                className="h-8 text-xs w-64"
              >
                <option value="new_and_changed">Thẻ mới + Thẻ đã thay đổi (Mặc định)</option>
                <option value="only_new">Chỉ thẻ mới chưa có trên Flama</option>
                <option value="resync_all">Đồng bộ lại toàn bộ deck</option>
              </NativeSelect>
            </div>

            <Button
              disabled={isSyncing || !selectedDeckName}
              onClick={handleExecuteSync}
              className="font-semibold shadow-sm w-full sm:w-auto"
            >
              {isSyncing ? <Loader2 className="size-4 animate-spin mr-2" /> : <Zap className="size-4 mr-2" />}
              Bắt đầu đồng bộ Anki → Flama
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
              <AlertDescription className="mt-1 text-xs space-y-1">
                <div>Đã nạp thành công {syncReport.totalSynced} thẻ lên Flama Cloud.</div>
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
            <div className={`size-16 rounded-full flex items-center justify-center ${isSyncing ? 'bg-primary/10 text-primary animate-pulse' : 'bg-emerald-500/10 text-emerald-600'}`}>
              {isSyncing ? <Loader2 className="size-8 animate-spin text-primary" /> : <CheckCircle2 className="size-8 text-emerald-500" />}
            </div>
            <DialogTitle className="text-base font-bold text-foreground">
              {isSyncing ? 'Đang tiến hành đồng bộ Anki → Flama...' : 'Hoàn tất đồng bộ!'}
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              {isSyncing
                ? 'Vui lòng giữ trình duyệt mở trong khi dữ liệu thẻ và file media đang được nạp lên hệ thống.'
                : `Đã xử lý xong dữ liệu cho bộ thẻ "${selectedDeckName}".`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {syncProgress && (
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-semibold text-foreground">
                  <span className="truncate max-w-[220px]">{syncProgress.message}</span>
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
                <AlertDescription className="mt-1 text-xs space-y-1">
                  <div>Đã đồng bộ {syncReport.totalSynced} thẻ lên Flama.</div>
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
