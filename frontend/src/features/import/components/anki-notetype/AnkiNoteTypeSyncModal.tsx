import React from 'react'
import { CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface AnkiNoteTypeSyncModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  isSyncing: boolean
  syncLog: string[]
  syncReport: { successCount: number; errors: string[] } | null
}

export const AnkiNoteTypeSyncModal: React.FC<AnkiNoteTypeSyncModalProps> = ({
  open,
  onOpenChange,
  isSyncing,
  syncLog,
  syncReport,
}) => {
  const { t } = useTranslation('import')

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isSyncing) onOpenChange(isOpen)
      }}
    >
      <DialogContent className="sm:max-w-md border-border/80 shadow-2xl rounded-2xl p-6">
        <DialogHeader className="items-center text-center space-y-3">
          <div
            className={`size-14 rounded-full flex items-center justify-center ${
              isSyncing ? 'bg-primary/10 text-primary animate-pulse' : 'bg-emerald-500/10 text-emerald-600'
            }`}
          >
            {isSyncing ? (
              <Loader2 className="size-7 animate-spin text-primary" />
            ) : (
              <CheckCircle2 className="size-7 text-emerald-500" />
            )}
          </div>
          <DialogTitle className="text-base font-bold text-foreground">
            {isSyncing
              ? t('anki_sync.notetypes_tab.sync_modal.syncing_title', 'Đang tiến hành đồng bộ NoteType...')
              : t('anki_sync.notetypes_tab.sync_modal.success_title', 'Hoàn tất đồng bộ!')}
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            {isSyncing
              ? t(
                  'anki_sync.notetypes_tab.sync_modal.syncing_desc',
                  'Vui lòng giữ trình duyệt mở trong khi cấu trúc NoteType và các trường dữ liệu đang được nạp lên Flama.'
                )
              : t(
                  'anki_sync.notetypes_tab.sync_modal.success_desc',
                  'Đã hoàn thành nạp và ánh xạ cấu trúc NoteType.'
                )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="font-mono text-[11px] bg-muted/40 p-3 rounded-xl max-h-40 overflow-y-auto space-y-1 border">
            {syncLog.map((logLine, idx) => (
              <div
                key={idx}
                className={
                  logLine.startsWith('✓')
                    ? 'text-emerald-600 font-semibold'
                    : logLine.startsWith('✗')
                    ? 'text-destructive font-semibold'
                    : 'text-muted-foreground'
                }
              >
                {logLine}
              </div>
            ))}
          </div>

          {syncReport && (
            <Alert
              className={
                syncReport.errors.length === 0
                  ? 'border-emerald-500/40 bg-emerald-500/10'
                  : 'border-destructive/40 bg-destructive/10'
              }
            >
              {syncReport.errors.length === 0 ? (
                <CheckCircle2 className="size-5 text-emerald-600" />
              ) : (
                <AlertTriangle className="size-5 text-destructive" />
              )}
              <AlertTitle className="font-bold text-xs">
                {syncReport.errors.length === 0
                  ? t('anki_sync.notetypes_tab.sync_modal.success_title', 'Thành công!')
                  : t('anki_sync.notetypes_tab.sync_modal.has_errors', 'Có lỗi phát sinh')}
              </AlertTitle>
              <AlertDescription className="mt-1 text-xs space-y-1">
                <div>
                  {t('anki_sync.notetypes_tab.sync_modal.success_count', {
                    count: syncReport.successCount,
                    defaultValue: `Đã nạp thành công ${syncReport.successCount} NoteType lên Flama.`,
                  })}
                </div>
                {syncReport.errors.map((err, idx) => (
                  <div key={idx} className="text-destructive font-mono text-[11px]">
                    • {err}
                  </div>
                ))}
              </AlertDescription>
            </Alert>
          )}
        </div>

        <div className="flex justify-end pt-2">
          <Button
            disabled={isSyncing}
            onClick={() => onOpenChange(false)}
            className="w-full sm:w-auto font-semibold text-xs rounded-xl"
          >
            {isSyncing
              ? t('anki_sync.notetypes_tab.sync_modal.btn_syncing', 'Đang đồng bộ...')
              : t('anki_sync.notetypes_tab.sync_modal.btn_close', 'Đóng cửa sổ')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
