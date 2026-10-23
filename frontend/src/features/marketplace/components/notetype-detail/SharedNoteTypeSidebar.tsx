import { Check, CheckCircle, Copy, Download, Edit3, EyeOff, Globe, Heart, Loader2, Lock, User } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useTranslation } from 'react-i18next'

interface SharedNoteTypeSidebarProps {
  id: string
  isOwner: boolean
  isInstalled: boolean
  pricingMode?: string
  priceDisplay?: string
  installCount: number
  publishStatus?: 'private' | 'published' | 'unlisted' | 'archived'
  isSaved: boolean
  isCopied: boolean
  authorName: string
  onInstall: () => void
  isInstallPending: boolean
  isInstallUnavailable?: boolean
  onSave: () => void
  isSavePending: boolean
  onCopyLink: () => void
  onUpdatePublishStatus: (status: 'private' | 'published') => void
  isPublishStatusPending: boolean
}

export function SharedNoteTypeSidebar({
  id,
  isOwner,
  isInstalled,
  pricingMode,
  priceDisplay: _priceDisplay,
  publishStatus,
  isSaved,
  isCopied,
  authorName,
  onInstall,
  isInstallPending,
  isInstallUnavailable,
  onSave,
  isSavePending,
  onCopyLink,
  onUpdatePublishStatus,
  isPublishStatusPending,
}: SharedNoteTypeSidebarProps) {
  const { t } = useTranslation('marketplace')

  return (
    <div className="space-y-6">
      <Card className="sticky top-6 border-border shadow-xs overflow-hidden rounded-2xl">
        <div className="h-1.5 w-full bg-primary" />
        <CardHeader className="p-4 sm:p-5 pb-3">
          <CardTitle className="text-base font-bold">
            {t('notetype_detail.sidebar_title', 'Hành động & Cài đặt')}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
          {isOwner ? (
            <div className="space-y-3 p-3 rounded-xl border border-primary/20 bg-primary/5 shadow-2xs">
              <div className="flex items-center justify-between border-b border-primary/10 pb-1.5 mb-1.5">
                <span className="text-[10px] font-black tracking-wider text-muted-foreground uppercase">
                  {t('notetype_detail.author_panel_title', 'Bảng điều khiển Tác giả')}
                </span>
                <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[9px] font-extrabold text-primary">
                  {t('common.author', 'Tác giả')}
                </span>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground font-medium">
                    {t('notetype_detail.share_status', 'Trạng thái chia sẻ:')}
                  </span>
                  {publishStatus === 'published' && (
                    <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold px-2 py-0.5 rounded-md text-[10px]">
                      <Globe className="mr-1 size-3 text-emerald-500" />
                      {t('notetype_detail.status_published', 'Đang hiển thị')}
                    </Badge>
                  )}
                  {publishStatus === 'unlisted' && (
                    <Badge variant="outline" className="border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400 font-bold px-2 py-0.5 rounded-md text-[10px]">
                      <Globe className="mr-1 size-3 text-blue-500" />
                      {t('notetype_detail.status_unlisted', 'Không công khai')}
                    </Badge>
                  )}
                  {publishStatus === 'private' && (
                    <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive font-bold px-2 py-0.5 rounded-md text-[10px]">
                      <Lock className="mr-1 size-3 text-destructive" />
                      {t('notetype_detail.status_private', 'Đã thu hồi (Riêng tư)')}
                    </Badge>
                  )}
                  {publishStatus === 'archived' && (
                    <Badge variant="outline" className="border-slate-500/30 bg-slate-500/10 text-slate-500 font-bold px-2 py-0.5 rounded-md text-[10px]">
                      <Lock className="mr-1 size-3 text-slate-500" />
                      {t('notetype_detail.status_archived', 'Đã lưu trữ')}
                    </Badge>
                  )}
                </div>
              </div>

              <div className="grid gap-2 pt-1">
                {publishStatus === 'published' || publishStatus === 'unlisted' ? (
                  <Button
                    variant="destructive"
                    size="sm"
                    className="w-full font-bold text-xs h-9 rounded-xl flex items-center justify-center gap-1.5"
                    onClick={() => {
                      if (
                        window.confirm(
                          t(
                            'notetype_detail.confirm_revoke',
                            'Bạn có chắc chắn muốn thu hồi loại thẻ này khỏi Marketplace?\n\nNgười dùng khác sẽ không thể tìm thấy hoặc cài đặt loại thẻ này nữa. Những người đã cài đặt trước đó vẫn có thể tiếp tục sử dụng.'
                          )
                        )
                      ) {
                        onUpdatePublishStatus('private')
                      }
                    }}
                    disabled={isPublishStatusPending}
                  >
                    <EyeOff className="size-3.5" />
                    {t('notetype_detail.btn_revoke', 'Thu hồi cấu trúc thẻ')}
                  </Button>
                ) : (
                  <Button
                    variant="default"
                    size="sm"
                    className="w-full font-bold text-xs h-9 rounded-xl flex items-center justify-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                    onClick={() => onUpdatePublishStatus('published')}
                    disabled={isPublishStatusPending}
                  >
                    <Globe className="size-3.5" />
                    {t('notetype_detail.btn_republish', 'Xuất bản lại cấu trúc thẻ')}
                  </Button>
                )}

                <Button
                  variant="outline"
                  size="sm"
                  className="w-full font-bold text-xs h-9 rounded-xl flex items-center justify-center gap-1.5"
                  asChild
                >
                  <Link to={`/marketplace/note-types/publish?id=${id}&edit=1`}>
                    <Edit3 className="size-3.5 text-primary" />
                    {t('notetype_detail.btn_edit_info', 'Chỉnh sửa thông tin')}
                  </Link>
                </Button>
              </div>
            </div>
          ) : isInstalled ? (
            <Button className="w-full h-10 sm:h-11 font-bold text-xs sm:text-sm border-emerald-500/40 text-emerald-600 dark:text-emerald-400 rounded-xl" variant="outline" disabled>
              <CheckCircle className="mr-1.5 size-4" />
              {t('notetype_detail.btn_installed', 'Đã cài đặt cấu trúc thẻ')}
            </Button>
          ) : (
            <Button
              className="w-full h-11 sm:h-12 font-bold text-sm sm:text-base shadow-xs bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl transition-all"
              size="lg"
              onClick={onInstall}
              disabled={isInstallPending || isInstallUnavailable}
            >
              {isInstallPending ? (
                <>
                  <Loader2 className="mr-2 size-5 animate-spin" />
                  {pricingMode === 'paid'
                    ? t('detail.creating_payment', 'Đang tạo thanh toán…')
                    : t('detail.installing', 'Đang cài đặt cấu trúc thẻ…')}
                </>
              ) : (
                <>
                  <Download className="mr-2 size-5" />
                  {pricingMode === 'paid'
                    ? t('notetype_detail.btn_buy', 'Mua Cấu trúc thẻ')
                    : t('notetype_detail.btn_install', 'Tải xuống & Cài đặt')}
                </>
              )}
            </Button>
          )}

          {!isOwner ? (
            <Button
              className="w-full h-9 sm:h-10 font-semibold text-xs sm:text-sm rounded-xl"
              variant="outline"
              size="sm"
              onClick={onSave}
              disabled={isSavePending}
            >
              <Heart
                className={`mr-1.5 size-4 ${
                  isSaved ? 'fill-primary text-primary' : ''
                }`}
              />
              {isSaved
                ? t('notetype_detail.btn_saved', 'Đã lưu')
                : t('notetype_detail.btn_save', 'Lưu cấu trúc thẻ')}
            </Button>
          ) : null}

          <Button
            className="w-full h-9 sm:h-10 font-semibold text-xs sm:text-sm rounded-xl"
            variant="ghost"
            size="sm"
            onClick={onCopyLink}
          >
            {isCopied ? (
              <Check className="mr-1.5 size-4 text-emerald-500" />
            ) : (
              <Copy className="mr-1.5 size-4 text-muted-foreground" />
            )}
            {isCopied
              ? t('notetype_detail.toast_copied', 'Đã sao chép liên kết')
              : t('notetype_detail.btn_copy_link', 'Sao chép link chia sẻ')}
          </Button>

          <div className="pt-3 border-t border-border/60 text-xs text-muted-foreground space-y-1.5">
            <div className="flex items-center gap-2">
              <User className="size-4 text-primary" />
              <span>
                {t('card.author', 'Tác giả')}:{' '}
                <strong className="text-foreground">{authorName}</strong>
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
