import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Check,
  Copy,
  KeyRound,
  Plus,
  Share2,
  Users,
  Clock,
  LoaderCircle,
  Info,
} from 'lucide-react'

import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
      return appApi.mutate(`/api/creator/decks/${deckItemId}/keys`, 'POST', payload)
    },
    onSuccess: () => {
      toast.success('Tạo mã truy cập thành công!')
      setIsCreateModalOpen(false)
      // Reset form
      setCreateCount(1)
      setKeyLabel('')
      setMaxUses('')
      setAccessDurationDays('')
      setExpiresAt('')
      queryClient.invalidateQueries({ queryKey: ['deck-access-keys', deckItemId] })
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Không thể tạo mã truy cập. Vui lòng thử lại.')
    },
  })

  // Mutation toggle status (active / revoked)
  const toggleStatusMutation = useMutation({
    mutationFn: ({ keyId, newStatus }: { keyId: string; newStatus: 'active' | 'revoked' }) =>
      appApi.mutate(`/api/creator/keys/${keyId}`, 'PATCH', { status: newStatus }),
    onSuccess: (_, variables) => {
      toast.success(
        variables.newStatus === 'active'
          ? 'Đã kích hoạt lại mã truy cập.'
          : 'Đã vô hiệu hóa mã truy cập.',
      )
      queryClient.invalidateQueries({ queryKey: ['deck-access-keys', deckItemId] })
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Thao tác thất bại.')
    },
  })

  const copyKey = (code: string, id: string) => {
    navigator.clipboard.writeText(code)
    setCopiedKeyId(id)
    toast.success(`Đã copy mã: ${code}`)
    setTimeout(() => setCopiedKeyId(null), 2000)
  }

  const copyShareLink = (code: string, id: string) => {
    const origin = window.location.origin
    const url = `${origin}/shared/decks/${deckItemId}?code=${encodeURIComponent(code)}`
    navigator.clipboard.writeText(url)
    setCopiedLinkId(id)
    toast.success('Đã copy link mời kèm mã kích hoạt!')
    setTimeout(() => setCopiedLinkId(null), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs font-medium">Tổng số mã đã tạo</CardDescription>
            <CardTitle className="text-2xl font-bold font-mono">{keys.length}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold text-emerald-500">{activeKeysCount}</span> mã đang mở nhận học viên
            </p>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs font-medium">Lượt học viên đã kích hoạt</CardDescription>
            <CardTitle className="text-2xl font-bold font-mono text-primary">{totalUsedCount}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-xs text-muted-foreground">Tổng số lượt tải về qua mã lớp học</p>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 backdrop-blur-sm shadow-sm flex flex-col justify-between p-4">
          <div>
            <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <KeyRound className="size-4 text-primary" />
              Phát hành mã lớp học
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Tạo mã kích hoạt để gửi riêng cho học viên lớp mình tải deck.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => setIsCreateModalOpen(true)}
            className="w-full mt-3 rounded-xl font-semibold gap-1.5 shadow-sm"
          >
            <Plus className="size-4" />
            Tạo mã truy cập mới
          </Button>
        </Card>
      </div>

      {/* Keys Table / List */}
      <div className="rounded-2xl border border-border/80 bg-card/70 backdrop-blur-md overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/20">
          <div>
            <h3 className="font-bold text-sm sm:text-base text-foreground flex items-center gap-2">
              <KeyRound className="size-4 text-primary" />
              Danh sách Mã truy cập ({keys.length})
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Quản lý, sao chép link mời và bật/tắt quyền kích hoạt cho từng mã
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsCreateModalOpen(true)}
            className="rounded-xl gap-1.5 text-xs font-semibold"
          >
            <Plus className="size-3.5" />
            Tạo thêm mã
          </Button>
        </div>

        {keysQuery.isLoading ? (
          <div className="flex items-center justify-center p-12 text-muted-foreground">
            <LoaderCircle className="size-6 animate-spin mr-2 text-primary" />
            <span className="text-sm">Đang tải danh sách mã...</span>
          </div>
        ) : keys.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="mx-auto size-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
              <KeyRound className="size-6" />
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-sm text-foreground">Chưa có mã truy cập nào</h4>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                Tạo mã truy cập đầu tiên để gửi cho học viên trong lớp của bạn tải về và bắt đầu học bài.
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => setIsCreateModalOpen(true)}
              className="rounded-xl font-semibold gap-1.5 mt-2"
            >
              <Plus className="size-4" />
              Tạo mã ngay
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border/60 bg-muted/40 text-muted-foreground font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Mã kích hoạt (Key Code)</th>
                  <th className="py-3 px-4">Nhãn / Tên lớp</th>
                  <th className="py-3 px-4">Tiến độ sử dụng</th>
                  <th className="py-3 px-4">Hạn học / Hạn mã</th>
                  <th className="py-3 px-4 text-center">Trạng thái</th>
                  <th className="py-3 px-4 text-right">Thao tác</th>
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
                          {k.label || <span className="text-muted-foreground italic">Không có nhãn</span>}
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5">
                          Tạo ngày {new Date(k.created_at).toLocaleDateString('vi-VN')}
                        </div>
                      </td>

                      {/* Usage */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setSelectedKeyForRedemptions(k)}
                            className="font-mono font-bold text-primary hover:underline flex items-center gap-1"
                            title="Xem danh sách học viên đã nhập mã"
                          >
                            <Users className="size-3" />
                            {k.used_count}
                            <span className="text-muted-foreground font-normal">
                              / {k.max_uses ? k.max_uses : '∞'} lượt
                            </span>
                          </button>
                          {isFull && (
                            <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-600 border-amber-500/20 px-1.5 py-0">
                              Đã hết lượt
                            </Badge>
                          )}
                        </div>
                      </td>

                      {/* Expiration & Duration */}
                      <td className="py-3 px-4">
                        <div className="space-y-0.5">
                          <div className="text-foreground">
                            {k.access_duration_days ? (
                              <span className="font-medium">Học trong {k.access_duration_days} ngày</span>
                            ) : (
                              <span className="text-muted-foreground">Học vĩnh viễn</span>
                            )}
                          </div>
                          {k.expires_at ? (
                            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                              <Clock className="size-3" />
                              Hạn kích hoạt: {new Date(k.expires_at).toLocaleDateString('vi-VN')}
                            </div>
                          ) : (
                            <div className="text-[10px] text-muted-foreground">Mã không hết hạn</div>
                          )}
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-4 text-center">
                        {k.status === 'active' && !isFull && (
                          <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[11px]">
                            Đang mở
                          </Badge>
                        )}
                        {k.status === 'active' && isFull && (
                          <Badge variant="outline" className="text-[11px] text-amber-600 border-amber-500/30 bg-amber-500/10">
                            Hết lượt
                          </Badge>
                        )}
                        {k.status === 'revoked' && (
                          <Badge variant="destructive" className="text-[11px] bg-destructive/15 text-destructive border-destructive/30">
                            Đã tắt
                          </Badge>
                        )}
                        {k.status === 'expired' && (
                          <Badge variant="secondary" className="text-[11px]">
                            Hết hạn
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
                            title="Xem học viên"
                          >
                            <Users className="size-3.5 mr-1" />
                            Học viên
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
                              Tắt mã
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
                              Bật lại
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
      <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base sm:text-lg">
              <KeyRound className="size-5 text-primary" />
              Tạo mã truy cập lớp học
            </DialogTitle>
            <DialogDescription className="text-xs">
              Mã này sẽ cấp quyền tải và học bộ thẻ &quot;{deckTitle}&quot; cho học viên của bạn.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs sm:text-sm">
            {/* Count */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="create-count" className="text-xs font-semibold">
                  Số lượng mã cần tạo
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
                  Giới hạn lượt dùng / mã
                </Label>
                <Input
                  id="max-uses"
                  type="number"
                  min="1"
                  placeholder="Để trống = Không giới hạn"
                  value={maxUses}
                  onChange={(e) => setMaxUses(e.target.value)}
                  className="rounded-xl h-10 font-mono text-sm"
                />
              </div>
            </div>

            {/* Label / Class name */}
            <div className="space-y-1.5">
              <Label htmlFor="key-label" className="text-xs font-semibold">
                Ghi chú / Tên lớp học
              </Label>
              <Input
                id="key-label"
                placeholder="VD: Lớp N3 K14, Học viên Nguyễn Văn A..."
                value={keyLabel}
                onChange={(e) => setKeyLabel(e.target.value)}
                className="rounded-xl h-10"
              />
            </div>

            {/* Access duration & Expiration */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="duration-days" className="text-xs font-semibold">
                  Thời lượng học (ngày)
                </Label>
                <Input
                  id="duration-days"
                  type="number"
                  min="1"
                  placeholder="Để trống = Vĩnh viễn"
                  value={accessDurationDays}
                  onChange={(e) => setAccessDurationDays(e.target.value)}
                  className="rounded-xl h-10 font-mono text-sm"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="key-expires" className="text-xs font-semibold">
                  Hạn chót nhập mã
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
                Học viên chỉ cần nhập mã này hoặc truy cập link mời để tự động cài đặt deck vào thư viện mà không cần tìm kiếm trên Marketplace.
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsCreateModalOpen(false)}
              className="rounded-xl"
            >
              Hủy
            </Button>
            <Button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending}
              className="rounded-xl font-semibold gap-1.5"
            >
              {createMutation.isPending ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Plus className="size-4" />
              )}
              Xác nhận tạo mã
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal 2: View Redemptions (Học viên đã nhập mã) */}
      <Dialog
        open={Boolean(selectedKeyForRedemptions)}
        onOpenChange={(open) => !open && setSelectedKeyForRedemptions(null)}
      >
        <DialogContent className="sm:max-w-lg rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Users className="size-5 text-primary" />
              Danh sách Học viên đã kích hoạt mã
            </DialogTitle>
            <DialogDescription className="text-xs font-mono text-foreground font-semibold">
              Mã: {selectedKeyForRedemptions?.key_code} ({selectedKeyForRedemptions?.label || 'Chưa đặt tên'})
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-80 overflow-y-auto divide-y divide-border/40 py-2">
            {redemptionsQuery.isLoading ? (
              <div className="flex items-center justify-center p-8 text-muted-foreground">
                <LoaderCircle className="size-5 animate-spin mr-2 text-primary" />
                <span className="text-xs">Đang tải danh sách học viên...</span>
              </div>
            ) : (redemptionsQuery.data?.items || []).length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground">
                Chưa có học viên nào kích hoạt mã này.
              </div>
            ) : (
              (redemptionsQuery.data?.items || []).map((r) => (
                <div key={r.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-semibold text-foreground">{r.username}</div>
                    <div className="text-[10px] text-muted-foreground">
                      Kích hoạt lúc: {new Date(r.redeemed_at).toLocaleString('vi-VN')}
                    </div>
                  </div>
                  <div className="text-right">
                    {r.access_expires_at ? (
                      <Badge variant="outline" className="text-[10px]">
                        Hạn học: {new Date(r.access_expires_at).toLocaleDateString('vi-VN')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-emerald-600 bg-emerald-500/10">
                        Vĩnh viễn
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
              onClick={() => setSelectedKeyForRedemptions(null)}
              className="rounded-xl w-full"
            >
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
