import { useTranslation } from 'react-i18next'
import { Info, KeyRound, LoaderCircle, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface CreateAccessKeysModalProps {
  isOpen: boolean
  onClose: () => void
  deckTitle: string
  createCount: number
  setCreateCount: (count: number) => void
  maxUses: string
  setMaxUses: (val: string) => void
  keyLabel: string
  setKeyLabel: (val: string) => void
  accessDurationDays: string
  setAccessDurationDays: (val: string) => void
  expiresAt: string
  setExpiresAt: (val: string) => void
  onSubmit: () => void
  isPending: boolean
}

export function CreateAccessKeysModal({
  isOpen,
  onClose,
  deckTitle,
  createCount,
  setCreateCount,
  maxUses,
  setMaxUses,
  keyLabel,
  setKeyLabel,
  accessDurationDays,
  setAccessDurationDays,
  expiresAt,
  setExpiresAt,
  onSubmit,
  isPending,
}: CreateAccessKeysModalProps) {
  const { t } = useTranslation('marketplace')

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg">
            <KeyRound className="size-5 text-primary" />
            {t('keys_manager.create_modal.title', 'Tạo mã truy cập lớp học')}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {t('keys_manager.create_modal.desc', {
              title: deckTitle,
              defaultValue: `Mã này sẽ cấp quyền tải và học bộ thẻ "${deckTitle}" cho học viên của bạn.`,
            })}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 text-xs sm:text-sm">
          {/* Count */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="create-count" className="text-xs font-semibold">
                {t('keys_manager.create_modal.count_label', 'Số lượng mã cần tạo')}
              </Label>
              <Input
                id="create-count"
                type="number"
                min="1"
                max="50"
                value={createCount}
                onChange={(e) => setCreateCount(Math.max(1, Math.min(50, Number(e.target.value))))}
                className="rounded-xl h-10 font-mono text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="max-uses" className="text-xs font-semibold">
                {t('keys_manager.create_modal.max_uses_label', 'Giới hạn lượt dùng / mã')}
              </Label>
              <Input
                id="max-uses"
                type="number"
                min="1"
                placeholder={t('keys_manager.create_modal.max_uses_placeholder', 'Để trống = Không giới hạn')}
                value={maxUses}
                onChange={(e) => setMaxUses(e.target.value)}
                className="rounded-xl h-10 font-mono text-sm"
              />
            </div>
          </div>

          {/* Label / Class name */}
          <div className="space-y-1.5">
            <Label htmlFor="key-label" className="text-xs font-semibold">
              {t('keys_manager.create_modal.label_name', 'Ghi chú / Tên lớp học')}
            </Label>
            <Input
              id="key-label"
              placeholder={t('keys_manager.create_modal.label_placeholder', 'VD: Lớp N3 K14, Học viên Nguyễn Văn A...')}
              value={keyLabel}
              onChange={(e) => setKeyLabel(e.target.value)}
              className="rounded-xl h-10"
            />
          </div>

          {/* Access duration & Expiration */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="duration-days" className="text-xs font-semibold">
                {t('keys_manager.create_modal.duration_label', 'Thời lượng học (ngày)')}
              </Label>
              <Input
                id="duration-days"
                type="number"
                min="1"
                placeholder={t('keys_manager.create_modal.duration_placeholder', 'Để trống = Vĩnh viễn')}
                value={accessDurationDays}
                onChange={(e) => setAccessDurationDays(e.target.value)}
                className="rounded-xl h-10 font-mono text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="key-expires" className="text-xs font-semibold">
                {t('keys_manager.create_modal.expiry_label', 'Hạn chót nhập mã')}
              </Label>
              <Input
                id="key-expires"
                type="date"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                className="rounded-xl h-10 text-xs"
              />
            </div>
          </div>

          <div className="rounded-xl bg-primary/5 border border-primary/20 p-3 text-xs text-muted-foreground flex items-start gap-2">
            <Info className="size-4 text-primary shrink-0 mt-0.5" />
            <div>
              {t(
                'keys_manager.create_modal.hint',
                'Học viên chỉ cần nhập mã này hoặc truy cập link mời để tự động cài đặt deck vào thư viện mà không cần tìm kiếm trên Marketplace.'
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            className="rounded-xl"
          >
            {t('keys_manager.create_modal.btn_cancel', 'Hủy')}
          </Button>
          <Button
            type="button"
            onClick={onSubmit}
            disabled={isPending}
            className="rounded-xl font-semibold gap-1.5"
          >
            {isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <Plus className="size-4" />
            )}
            {t('keys_manager.create_modal.btn_submit', 'Xác nhận tạo mã')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
