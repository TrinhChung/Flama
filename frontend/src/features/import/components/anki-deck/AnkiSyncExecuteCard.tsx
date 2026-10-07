import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  Loader2,
  Zap,
} from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Progress } from '@/components/ui/progress'
import { AnkiCardPreviewSection } from './AnkiCardPreviewSection'

interface AnkiSyncExecuteCardProps {
  selectedDeckName: string
  loadPreview: () => void
  isLoadingPreview: boolean
  showPreviewSection: boolean
  setShowPreviewSection: (val: boolean) => void
  activePreviewNote: any
  previewNotes: any[]
  previewNoteIndex: number
  setPreviewNoteIndex: (val: number) => void
  previewSide: 'front' | 'back'
  setPreviewSide: (val: 'front' | 'back') => void
  previewTemplates: any[]
  previewTemplateId: string
  setPreviewTemplateId: (val: string) => void
  previewResult: any
  selectedFlamaModelId: string
  previewNoteType: any
  previewError: string | null
  syncModeSelectId: string
  syncMode: 'new_and_changed' | 'only_new' | 'resync_all'
  setSyncMode: (mode: 'new_and_changed' | 'only_new' | 'resync_all') => void
  autoSyncMissingNoteTypes: boolean
  setAutoSyncMissingNoteTypes: (val: boolean) => void
  isSyncing: boolean
  connectionStatus: string
  handleExecuteSync: () => void
  syncProgress: any
  syncReport: any
}

export function AnkiSyncExecuteCard({
  selectedDeckName,
  loadPreview,
  isLoadingPreview,
  showPreviewSection,
  setShowPreviewSection,
  activePreviewNote,
  previewNotes,
  previewNoteIndex,
  setPreviewNoteIndex,
  previewSide,
  setPreviewSide,
  previewTemplates,
  previewTemplateId,
  setPreviewTemplateId,
  previewResult,
  selectedFlamaModelId,
  previewNoteType,
  previewError,
  syncModeSelectId,
  syncMode,
  setSyncMode,
  autoSyncMissingNoteTypes,
  setAutoSyncMissingNoteTypes,
  isSyncing,
  connectionStatus,
  handleExecuteSync,
  syncProgress,
  syncReport,
}: AnkiSyncExecuteCardProps) {
  return (
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
        <AnkiCardPreviewSection
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
          isLoadingPreview={isLoadingPreview}
          previewError={previewError}
        />

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
            className="font-bold text-xs shadow-xs w-full sm:w-auto px-6 h-9 rounded-xl"
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
                  {syncReport.errors.map((err: string, idx: number) => (
                    <div key={idx} className="text-destructive font-mono text-[11px] break-words">• {err}</div>
                  ))}
                </div>
              )}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
