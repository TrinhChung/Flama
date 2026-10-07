import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'

interface SyncProgressState {
  totalNotes: number
  processedNotes: number
  totalMedia: number
  processedMedia: number
  message: string
}

interface SyncReportState {
  totalSynced: number
  totalSkipped?: number
  totalMediaDetected?: number
  errors: string[]
}

interface AnkiSyncProgressDialogProps {
  showSyncModal: boolean
  setShowSyncModal: (val: boolean) => void
  isSyncing: boolean
  syncProgress: SyncProgressState | null
  syncReport: SyncReportState | null
  selectedDeckName: string
}

export function AnkiSyncProgressDialog({
  showSyncModal,
  setShowSyncModal,
  isSyncing,
  syncProgress,
  syncReport,
  selectedDeckName,
}: AnkiSyncProgressDialogProps) {
  const { t } = useTranslation('import')

  return (
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
              ? t('anki_sync.decks_tab.progress_modal_title', { defaultValue: 'Đang tiến hành đồng bộ nội dung thẻ...' })
              : t('anki_sync.decks_tab.sync_complete', { defaultValue: 'Hoàn tất đồng bộ!' })}
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
                <div>
                  {t('anki_sync.decks_tab.report_success', {
                    count: syncReport.totalSynced,
                    defaultValue: `Đã đồng bộ ${syncReport.totalSynced} note lên Flama.`,
                  })}
                </div>
                {Boolean(syncReport.totalSkipped) && (
                  <div>
                    {t('anki_sync.decks_tab.report_skipped', {
                      count: syncReport.totalSkipped,
                      defaultValue: `Đã bỏ qua ${syncReport.totalSkipped} note không thay đổi.`,
                    })}
                  </div>
                )}

                {Boolean(syncReport.totalMediaDetected) && (
                  <div className="text-muted-foreground text-[11px] border-t border-border/60 pt-1.5">
                    {t('anki_sync.decks_tab.report_media', {
                      count: syncReport.totalMediaDetected,
                      defaultValue: `Có ${syncReport.totalMediaDetected} tham chiếu media chưa được upload.`,
                    })}
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
  )
}
