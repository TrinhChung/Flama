import { useTranslation } from 'react-i18next'
import { LoaderCircle, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { AccessKeyItem, KeyRedemptionItem } from './DeckAccessKeysManager'

interface KeyRedemptionsModalProps {
  isOpen: boolean
  onClose: () => void
  selectedKey: AccessKeyItem | null
  isLoading: boolean
  redemptions: KeyRedemptionItem[]
}

export function KeyRedemptionsModal({
  isOpen,
  onClose,
  selectedKey,
  isLoading,
  redemptions,
}: KeyRedemptionsModalProps) {
  const { t, i18n } = useTranslation('marketplace')
  const dateLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg rounded-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Users className="size-5 text-primary" />
            {t('keys_manager.redemptions_modal.title', 'Danh sách Học viên đã kích hoạt mã')}
          </DialogTitle>
          <DialogDescription className="text-xs font-mono text-foreground font-semibold">
            {t('keys_manager.redemptions_modal.code_label', {
              code: selectedKey?.key_code || '',
              label: selectedKey?.label || t('keys_manager.redemptions_modal.unnamed', 'Chưa đặt tên'),
              defaultValue: `Mã: ${selectedKey?.key_code} (${selectedKey?.label || 'Chưa đặt tên'})`,
            })}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-80 overflow-y-auto divide-y divide-border/40 py-2">
          {isLoading ? (
            <div className="flex items-center justify-center p-8 text-muted-foreground">
              <LoaderCircle className="size-5 animate-spin mr-2 text-primary" />
              <span className="text-xs">
                {t('keys_manager.redemptions_modal.loading', 'Đang tải danh sách học viên...')}
              </span>
            </div>
          ) : redemptions.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted-foreground">
              {t('keys_manager.redemptions_modal.empty', 'Chưa có học viên nào kích hoạt mã này.')}
            </div>
          ) : (
            redemptions.map((r) => (
              <div key={r.id} className="py-2.5 flex items-center justify-between text-xs">
                <div>
                  <div className="font-semibold text-foreground">{r.username}</div>
                  <div className="text-[10px] text-muted-foreground">
                    {t('keys_manager.redemptions_modal.redeemed_at', {
                      date: new Date(r.redeemed_at).toLocaleString(dateLocale),
                      defaultValue: `Kích hoạt lúc: ${new Date(r.redeemed_at).toLocaleString(dateLocale)}`,
                    })}
                  </div>
                </div>
                <div className="text-right">
                  {r.access_expires_at ? (
                    <Badge variant="outline" className="text-[10px]">
                      {t('keys_manager.redemptions_modal.access_expires', {
                        date: new Date(r.access_expires_at).toLocaleDateString(dateLocale),
                        defaultValue: `Hạn học: ${new Date(r.access_expires_at).toLocaleDateString(dateLocale)}`,
                      })}
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px] text-emerald-600 bg-emerald-500/10">
                      {t('keys_manager.redemptions_modal.forever', 'Vĩnh viễn')}
                    </Badge>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            className="rounded-xl w-full"
          >
            {t('keys_manager.redemptions_modal.btn_close', 'Đóng')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
