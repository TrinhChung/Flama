import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import {
  Check,
  Copy,
  KeyRound,
  Plus,
  Share2,
  Users,
  Clock,
  LoaderCircle,
} from 'lucide-react'

import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CreateAccessKeysModal } from './CreateAccessKeysModal'
import { KeyRedemptionsModal } from './KeyRedemptionsModal'

export interface AccessKeyItem {
  id: string
  deck_item_id: string
  key_code: string
  label: string
  status: 'active' | 'revoked' | 'expired'
  max_uses: number | null
  used_count: number
  expires_at: string | null
  access_duration_days: number | null
  created_at: string
  updated_at: string
}

export interface KeyRedemptionItem {
  id: string
  user_id: number
  username: string
  redeemed_at: string
  access_expires_at: string | null
  status: string
}

interface DeckAccessKeysManagerProps {
  deckItemId: string
  deckTitle: string
}

export function DeckAccessKeysManager({ deckItemId, deckTitle }: DeckAccessKeysManagerProps) {
  const { t, i18n } = useTranslation('marketplace')
  const dateLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const queryClient = useQueryClient()
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [selectedKeyForRedemptions, setSelectedKeyForRedemptions] = useState<AccessKeyItem | null>(null)
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null)
  const [copiedLinkId, setCopiedLinkId] = useState<string | null>(null)

  // Form states for creating keys
  const [createCount, setCreateCount] = useState<number>(1)
  const [keyLabel, setKeyLabel] = useState<string>('')
  const [maxUses, setMaxUses] = useState<string>('')
  const [accessDurationDays, setAccessDurationDays] = useState<string>('')
  const [expiresAt, setExpiresAt] = useState<string>('')

  // Query keys
  const keysQuery = useQuery({
    queryKey: ['deck-access-keys', deckItemId],
    queryFn: () => appApi.get<{ keys: AccessKeyItem[] }>(`/api/creator/decks/${deckItemId}/keys`),
    enabled: Boolean(deckItemId),
  })

  const keys = keysQuery.data?.keys || []
  const activeKeysCount = keys.filter((k) => k.status === 'active').length
  const totalUsedCount = keys.reduce((acc, k) => acc + (k.used_count || 0), 0)

  // Query redemptions for a specific key
  const redemptionsQuery = useQuery({
    queryKey: ['deck-key-redemptions', selectedKeyForRedemptions?.id],
    queryFn: () =>
      appApi.get<{ items: KeyRedemptionItem[]; total_count: number }>(
        `/api/creator/keys/${selectedKeyForRedemptions?.id}/redemptions`,
      ),
    enabled: Boolean(selectedKeyForRedemptions),
  })

  // Mutation create keys
  const createMutation = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        count: Number(createCount) || 1,
        label: keyLabel.trim() || undefined,
        max_uses: maxUses ? Number(maxUses) : undefined,
        access_duration_days: accessDurationDays ? Number(accessDurationDays) : undefined,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : undefined,
      }
      return appApi.mutate<{ created_keys: AccessKeyItem[] }>(
        `/api/creator/decks/${deckItemId}/keys`,
        'POST',
        payload,
      )
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['deck-access-keys', deckItemId] })
      setIsCreateModalOpen(false)
      // reset form
      setCreateCount(1)
      setKeyLabel('')
      setMaxUses('')
      setAccessDurationDays('')
      setExpiresAt('')
      toast.success(
        t('keys_manager.toast_created_count', {
          count: data?.created_keys?.length || 1,
          defaultValue: `Đã tạo thành công ${data?.created_keys?.length || 1} mã truy cập mới!`,
        })
      )
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Có lỗi xảy ra khi tạo mã.'))
    },
  })

  // Mutation revoke/restore key
  const toggleStatusMutation = useMutation({
    mutationFn: ({ keyId, newStatus }: { keyId: string; newStatus: 'active' | 'revoked' }) => {
      return appApi.mutate(
        `/api/creator/keys/${keyId}/status`,
        'PATCH',
        { status: newStatus },
      )
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deck-access-keys', deckItemId] })
      toast.success(t('keys_manager.toast_status_updated', 'Đã cập nhật trạng thái mã!'))
    },
    onError: (err: any) => {
      toast.error(err?.message || t('common.error', 'Không thể thay đổi trạng thái mã.'))
    },
  })

  const copyKey = (code: string, id: string) => {
    navigator.clipboard.writeText(code)
    setCopiedKeyId(id)
    toast.success(t('keys_manager.toast_copied_key', 'Đã copy mã key!'))
    setTimeout(() => setCopiedKeyId(null), 2000)
  }

  const copyShareLink = (code: string, id: string) => {
    const inviteUrl = `${window.location.origin}/marketplace/decks/${deckItemId}?key=${code}`
    navigator.clipboard.writeText(inviteUrl)
    setCopiedLinkId(id)
    toast.success(t('keys_manager.toast_copied_link', 'Đã copy link mời kèm mã kích hoạt!'))
    setTimeout(() => setCopiedLinkId(null), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs font-medium">
              {t('keys_manager.stat_total_created', 'Tổng số mã đã tạo')}
            </CardDescription>
            <CardTitle className="text-2xl font-bold font-mono">{keys.length}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold text-emerald-500">{activeKeysCount}</span>{' '}
              {t('keys_manager.stat_active_suffix', 'mã đang mở nhận học viên')}
            </p>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs font-medium">
              {t('keys_manager.stat_used', 'Lượt học viên đã kích hoạt')}
            </CardDescription>
            <CardTitle className="text-2xl font-bold font-mono text-primary">{totalUsedCount}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-xs text-muted-foreground">
              {t('keys_manager.stat_used_desc', 'Tổng số lượt tải về qua mã lớp học')}
            </p>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm flex flex-col justify-between p-4">
          <div>
            <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <KeyRound className="size-4 text-primary" />
              {t('keys_manager.card_issue_title', 'Phát hành mã lớp học')}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {t('keys_manager.card_issue_desc', 'Tạo mã kích hoạt để gửi riêng cho học viên lớp mình tải deck.')}
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => setIsCreateModalOpen(true)}
            className="w-full mt-3 rounded-xl font-semibold gap-1.5 shadow-sm"
          >
            <Plus className="size-4" />
            {t('keys_manager.btn_create', 'Tạo mã truy cập mới')}
          </Button>
        </Card>
      </div>

      {/* Keys Table / List */}
      <div className="rounded-2xl border border-border/80 bg-card/70 backdrop-blur-md overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/20">
          <div>
            <h3 className="font-bold text-sm sm:text-base text-foreground flex items-center gap-2">
              <KeyRound className="size-4 text-primary" />
              {t('keys_manager.list_title', {
                count: keys.length,
                defaultValue: `Danh sách Mã truy cập (${keys.length})`,
              })}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t('keys_manager.list_desc', 'Quản lý, sao chép link mời và bật/tắt quyền kích hoạt cho từng mã')}
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsCreateModalOpen(true)}
            className="rounded-xl gap-1.5 text-xs font-semibold"
          >
            <Plus className="size-3.5" />
            {t('keys_manager.btn_create_more', 'Tạo thêm mã')}
          </Button>
        </div>

        {keysQuery.isLoading ? (
          <div className="flex items-center justify-center p-12 text-muted-foreground">
            <LoaderCircle className="size-6 animate-spin mr-2 text-primary" />
            <span className="text-sm">{t('keys_manager.loading', 'Đang tải danh sách mã...')}</span>
          </div>
        ) : keys.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="mx-auto size-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
              <KeyRound className="size-6" />
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-sm text-foreground">
                {t('keys_manager.empty_title', 'Chưa có mã truy cập nào')}
              </h4>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                {t(
                  'keys_manager.empty_desc',
                  'Tạo mã truy cập đầu tiên để gửi cho học viên trong lớp của bạn tải về và bắt đầu học bài.'
                )}
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => setIsCreateModalOpen(true)}
              className="rounded-xl font-semibold gap-1.5 mt-2"
            >
              <Plus className="size-4" />
              {t('keys_manager.btn_create_first', 'Tạo mã ngay')}
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border/60 bg-muted/40 text-muted-foreground font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">{t('keys_manager.table.code_col', 'Mã kích hoạt (Key Code)')}</th>
                  <th className="py-3 px-4">{t('keys_manager.table.label_col', 'Nhãn / Tên lớp')}</th>
                  <th className="py-3 px-4">{t('keys_manager.table.uses_col', 'Tiến độ sử dụng')}</th>
                  <th className="py-3 px-4">{t('keys_manager.table.expires_col', 'Hạn học / Hạn mã')}</th>
                  <th className="py-3 px-4 text-center">{t('keys_manager.table.status_col', 'Trạng thái')}</th>
                  <th className="py-3 px-4 text-right">{t('keys_manager.table.actions_col', 'Thao tác')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {keys.map((k) => {
                  const isRevoked = k.status === 'revoked'
                  const isExpired = k.status === 'expired'
                  const isFull = k.max_uses !== null && k.used_count >= k.max_uses

                  return (
                    <tr
                      key={k.id}
                      className={`hover:bg-muted/30 transition-colors ${
                        isRevoked || isExpired ? 'opacity-65 bg-muted/10' : ''
                      }`}
                    >
                      {/* Key Code & Quick Copy */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-xs sm:text-sm tracking-wide text-foreground bg-muted/60 px-2 py-1 rounded-lg border border-border/60">
                            {k.key_code}
                          </span>
                          <button
                            type="button"
                            onClick={() => copyKey(k.key_code, k.id)}
                            title="Copy mã key"
                            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                          >
                            {copiedKeyId === k.id ? (
                              <Check className="size-3.5 text-emerald-500" />
                            ) : (
                              <Copy className="size-3.5" />
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={() => copyShareLink(k.key_code, k.id)}
                            title="Copy link mời nhanh"
                            className="p-1 rounded-md text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
                          >
                            {copiedLinkId === k.id ? (
                              <Check className="size-3.5 text-emerald-500" />
                            ) : (
                              <Share2 className="size-3.5" />
                            )}
                          </button>
                        </div>
                      </td>

                      {/* Label / Class note */}
                      <td className="py-3 px-4">
                        <div className="font-medium text-foreground">
                          {k.label || (
                            <span className="text-muted-foreground italic">
                              {t('keys_manager.no_label', 'Không có nhãn')}
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5">
                          {t('keys_manager.created_at', {
                            date: new Date(k.created_at).toLocaleDateString(dateLocale),
                            defaultValue: `Tạo ngày ${new Date(k.created_at).toLocaleDateString(dateLocale)}`,
                          })}
                        </div>
                      </td>

                      {/* Usage */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setSelectedKeyForRedemptions(k)}
                            className="font-mono font-bold text-primary hover:underline flex items-center gap-1"
                            title={t('keys_manager.view_students_title', 'Xem danh sách học viên đã nhập mã')}
                          >
                            <Users className="size-3" />
                            {k.used_count}
                            <span className="text-muted-foreground font-normal">
                              {t('keys_manager.per_uses', {
                                max: k.max_uses ? k.max_uses : '∞',
                                defaultValue: `/ ${k.max_uses ? k.max_uses : '∞'} lượt`,
                              })}
                            </span>
                          </button>
                          {isFull && (
                            <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-600 border-amber-500/20 px-1.5 py-0">
                              {t('keys_manager.status_full', 'Hết lượt')}
                            </Badge>
                          )}
                        </div>
                      </td>

                      {/* Expiration & Duration */}
                      <td className="py-3 px-4">
                        <div className="space-y-0.5">
                          <div className="text-foreground">
                            {k.access_duration_days ? (
                              <span className="font-medium">
                                {t('keys_manager.duration_days', {
                                  days: k.access_duration_days,
                                  defaultValue: `Học trong ${k.access_duration_days} ngày`,
                                })}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">
                                {t('keys_manager.duration_forever', 'Học vĩnh viễn')}
                              </span>
                            )}
                          </div>
                          {k.expires_at ? (
                            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                              <Clock className="size-3" />
                              {t('keys_manager.expires_at', {
                                date: new Date(k.expires_at).toLocaleDateString(dateLocale),
                                defaultValue: `Hạn kích hoạt: ${new Date(k.expires_at).toLocaleDateString(dateLocale)}`,
                              })}
                            </div>
                          ) : (
                            <div className="text-[10px] text-muted-foreground">
                              {t('keys_manager.no_expiration', 'Mã không hết hạn')}
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-4 text-center">
                        {k.status === 'active' && !isFull && (
                          <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[11px]">
                            {t('keys_manager.status_active', 'Đang mở')}
                          </Badge>
                        )}
                        {k.status === 'active' && isFull && (
                          <Badge variant="outline" className="text-[11px] text-amber-600 border-amber-500/30 bg-amber-500/10">
                            {t('keys_manager.status_full', 'Hết lượt')}
                          </Badge>
                        )}
                        {k.status === 'revoked' && (
                          <Badge variant="destructive" className="text-[11px] bg-destructive/15 text-destructive border-destructive/30">
                            {t('keys_manager.status_revoked', 'Đã tắt')}
                          </Badge>
                        )}
                        {k.status === 'expired' && (
                          <Badge variant="secondary" className="text-[11px]">
                            {t('keys_manager.status_expired', 'Hết hạn')}
                          </Badge>
                        )}
                      </td>

                      {/* Action buttons */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setSelectedKeyForRedemptions(k)}
                            className="h-8 px-2 text-xs rounded-lg"
                            title={t('keys_manager.btn_students', 'Học viên')}
                          >
                            <Users className="size-3.5 mr-1" />
                            {t('keys_manager.btn_students', 'Học viên')}
                          </Button>

                          {k.status === 'active' ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => toggleStatusMutation.mutate({ keyId: k.id, newStatus: 'revoked' })}
                              disabled={toggleStatusMutation.isPending}
                              className="h-8 px-2.5 text-xs rounded-lg text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/20"
                              title="Tắt mã này để không cho học viên mới nhập"
                            >
                              {t('keys_manager.btn_revoke', 'Tắt mã')}
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => toggleStatusMutation.mutate({ keyId: k.id, newStatus: 'active' })}
                              disabled={toggleStatusMutation.isPending}
                              className="h-8 px-2.5 text-xs rounded-lg text-emerald-600 hover:text-emerald-600 hover:bg-emerald-500/10 border-emerald-500/20"
                              title="Mở lại mã này"
                            >
                              {t('keys_manager.btn_reactivate', 'Bật lại')}
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal 1: Create Keys */}
      <CreateAccessKeysModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        deckTitle={deckTitle}
        createCount={createCount}
        setCreateCount={setCreateCount}
        maxUses={maxUses}
        setMaxUses={setMaxUses}
        keyLabel={keyLabel}
        setKeyLabel={setKeyLabel}
        accessDurationDays={accessDurationDays}
        setAccessDurationDays={setAccessDurationDays}
        expiresAt={expiresAt}
        setExpiresAt={setExpiresAt}
        onSubmit={() => createMutation.mutate()}
        isPending={createMutation.isPending}
      />

      {/* Modal 2: View Redemptions (Học viên đã nhập mã) */}
      <KeyRedemptionsModal
        isOpen={Boolean(selectedKeyForRedemptions)}
        onClose={() => setSelectedKeyForRedemptions(null)}
        selectedKey={selectedKeyForRedemptions}
        isLoading={redemptionsQuery.isLoading}
        redemptions={redemptionsQuery.data?.items || []}
      />
    </div>
  )
}
