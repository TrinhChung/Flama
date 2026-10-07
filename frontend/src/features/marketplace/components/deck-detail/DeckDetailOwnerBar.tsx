import { AlertCircle, Clock, Edit3, EyeOff, GitCompare, Globe, Inbox, KeyRound, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useTranslation } from 'react-i18next'
import type { AutoPublishStatus } from '@/features/deck-collaboration/types'

interface DeckDetailOwnerBarProps {
  id: string
  deckSourceDeckId?: number | null
  version?: string
  publishStatus?: 'private' | 'published' | 'unlisted' | 'archived'
  showKeyManager: boolean
  setShowKeyManager: (val: boolean) => void
  onUpdatePublishStatus: (status: 'private' | 'published') => void
  isPublishStatusPending: boolean
  autoPublishData?: AutoPublishStatus | null
  autoPublishMutation: {
    mutate: (enabled: boolean) => void
    isPending: boolean
  }
}

export function DeckDetailOwnerBar({
  id,
  deckSourceDeckId,
  version,
  publishStatus,
  showKeyManager,
  setShowKeyManager,
  onUpdatePublishStatus,
  isPublishStatusPending,
  autoPublishData,
  autoPublishMutation,
}: DeckDetailOwnerBarProps) {
  const { t, i18n } = useTranslation('marketplace')
  const dateLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:flex lg:flex-wrap items-center gap-2 sm:gap-2.5">
        <Button
          variant="secondary"
          size="sm"
          className="h-10 sm:h-10 min-h-[40px] px-4 rounded-xl text-xs font-bold shadow-2xs justify-center"
          asChild
        >
          <Link to={`/creator/decks/${id}/releases/new`}>
            <GitCompare className="mr-1.5 size-3.5 text-primary" />
            {t('detail.owner_admin.release_builder', 'Tạo bản phát hành (Release)')}
          </Link>
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="h-10 sm:h-10 min-h-[40px] px-4 rounded-xl text-xs font-bold justify-center"
          asChild
        >
          <Link to={`/flashcards/change-requests/incoming?deck_item_id=${id}`}>
            <Inbox className="mr-1.5 size-3.5" />
            {t('detail.owner_admin.change_request_inbox', 'Hộp thư góp ý (Change Request)')}
          </Link>
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl justify-center"
          asChild
        >
          <Link to={`/marketplace/decks/publish?deck_id=${deckSourceDeckId}&deck_item_id=${id}&edit=1`}>
            <Edit3 className="mr-1.5 size-3.5 text-primary" />
            {t('publish_deck.title_edit', 'Chỉnh sửa thông tin')}
          </Link>
        </Button>

        <Button
          variant="outline"
          size="sm"
          className={`h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl justify-center transition-all ${
            showKeyManager ? 'bg-primary/10 border-primary text-primary' : ''
          }`}
          onClick={() => setShowKeyManager(!showKeyManager)}
        >
          <KeyRound className="mr-1.5 size-3.5 text-primary" />
          {showKeyManager
            ? t('keys_manager.hide_btn', 'Ẩn Quản lý Mã')
            : t('keys_manager.title', 'Mã lớp học (Keys)')}
        </Button>

        {publishStatus === 'published' || publishStatus === 'unlisted' ? (
          <Button
            variant="destructive"
            size="sm"
            className="h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl justify-center"
            onClick={() => {
              if (
                window.confirm(
                  t(
                    'detail.owner_admin.confirm_revoke',
                    'Bạn có chắc chắn muốn thu hồi bộ thẻ này khỏi Marketplace?\n\nNgười dùng khác sẽ không thể tìm thấy hoặc cài đặt bộ thẻ này nữa.'
                  )
                )
              ) {
                onUpdatePublishStatus('private')
              }
            }}
            disabled={isPublishStatusPending}
          >
            <EyeOff className="mr-1.5 size-3.5" />
            {t('detail.owner_admin.revoke_btn', 'Thu hồi bộ deck')}
          </Button>
        ) : (
          <Button
            variant="default"
            size="sm"
            className="h-10 sm:h-10 min-h-[40px] px-4 font-bold text-xs rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white justify-center"
            onClick={() => onUpdatePublishStatus('published')}
            disabled={isPublishStatusPending}
          >
            <Globe className="mr-1.5 size-3.5" />
            {t('detail.owner_admin.republish_btn', 'Xuất bản lại')}
          </Button>
        )}
      </div>

      {/* Creator Auto-Publish Management Panel */}
      {autoPublishData ? (
        <div className="mt-4 rounded-2xl border border-primary/20 bg-primary/5 p-4 sm:p-4.5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Zap className="size-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-xs sm:text-sm font-bold text-foreground">
                    {t('detail.owner_admin.auto_publish_title', 'Tự động phát hành (Auto-Publish)')}
                  </h4>
                  <Badge
                    variant={autoPublishData.auto_publish_enabled ? 'default' : 'secondary'}
                    className="text-[10px] px-1.5 py-0 font-bold"
                  >
                    {autoPublishData.auto_publish_enabled
                      ? t('common.on', 'BẬT')
                      : t('common.off', 'TẮT')}
                  </Badge>
                </div>
                <p className="text-[11px] sm:text-xs text-muted-foreground leading-normal mt-0.5">
                  {t(
                    'detail.owner_admin.auto_publish_desc',
                    'Khi bật, các thay đổi từ deck gốc sẽ tự động đóng gói thành release mới và thông báo đến người học.'
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-muted-foreground">
                {autoPublishData.auto_publish_enabled
                  ? t('common.enabled', 'Đang bật')
                  : t('common.disabled', 'Đang tắt')}
              </span>
              <Switch
                checked={autoPublishData.auto_publish_enabled}
                disabled={autoPublishMutation.isPending}
                onCheckedChange={(checked) => autoPublishMutation.mutate(checked)}
                aria-label={t('detail.owner_admin.auto_publish_title', 'Tự động phát hành')}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2.5 border-t border-primary/15 text-xs">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Clock className="size-3.5 text-primary shrink-0" />
              <span>
                {t('publish_deck.step4.version_label', 'Phiên bản')}:{' '}
                <strong className="text-foreground">
                  {autoPublishData.current_release?.version_label || version || '1.0.0'}
                </strong>
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <GitCompare className="size-3.5 text-primary shrink-0" />
              <span>
                {t('common.pending', 'Đang chờ')}:{' '}
                <strong className="text-foreground">
                  {autoPublishData.pending_changes_count}{' '}
                  {t('common.changes', 'thay đổi')}
                </strong>
              </span>
            </div>
            {autoPublishData.last_auto_published_at ? (
              <div className="flex items-center gap-1.5 text-muted-foreground truncate">
                <span>
                  {t('detail.owner_admin.published_at', 'Đã phát hành')}:{' '}
                  <strong className="text-foreground">
                    {new Date(autoPublishData.last_auto_published_at).toLocaleString(dateLocale)}
                  </strong>
                </span>
              </div>
            ) : null}
          </div>

          {autoPublishData.last_auto_publish_error ? (
            <div className="flex items-center gap-1.5 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive">
              <AlertCircle className="size-3.5 shrink-0" />
              <span>
                {t('detail.owner_admin.last_error', 'Lỗi phát hành gần nhất')}:{' '}
                {autoPublishData.last_auto_publish_error}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
