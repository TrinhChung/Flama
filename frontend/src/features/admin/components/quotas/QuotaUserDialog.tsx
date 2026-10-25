import { ArrowLeft, Save, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useDeleteUserQuota, useQuotaUserDetail, useSaveUserQuota } from '../../api/quotasApi'
import { useQuotaOverrideForm } from '../../hooks/useQuotaOverrideForm'
import { useQuotaUserSearch } from '../../hooks/useQuotaUserSearch'
import type { QuotaPeriod, QuotaUser, QuotaUserKindDetail } from '../../types/quotas'
import {
  QUOTA_KIND_META,
  QUOTA_PERIOD_LABELS,
  QUOTA_PERIODS,
  QUOTA_SOURCE_LABELS,
  formatLocalDate,
  formatQuotaAmount,
  formatQuotaLimit,
  quotaUserLabel,
} from './quotaFormat'

function UserSearch({ onSelect }: { onSelect: (user: QuotaUser) => void }) {
  const search = useQuotaUserSearch()
  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
        <Input
          autoFocus
          value={search.input}
          onChange={(event) => search.setInput(event.target.value)}
          placeholder="Tìm theo username, email hoặc tên hiển thị…"
          className="pl-8"
          aria-label="Tìm người dùng"
        />
      </div>
      {search.term.length < 2 ? (
        <p className="text-xs text-muted-foreground">Nhập ít nhất 2 ký tự.</p>
      ) : search.isSearching && search.results.length === 0 ? (
        <p className="text-xs text-muted-foreground">Đang tìm…</p>
      ) : search.results.length === 0 ? (
        <p className="text-xs text-muted-foreground">Không tìm thấy người dùng phù hợp.</p>
      ) : (
        <ul className="max-h-72 divide-y overflow-y-auto rounded-md border">
          {search.results.map((user) => (
            <li key={user.id}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-muted/60"
                onClick={() => onSelect(user)}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">{quotaUserLabel(user)}</span>
                  <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
                </span>
                {user.role_name && <Badge variant="outline">{user.role_name}</Badge>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function OverrideForm({ userId, detail }: { userId: number; detail: QuotaUserKindDetail }) {
  const form = useQuotaOverrideForm(detail)
  const saveMutation = useSaveUserQuota()
  const deleteMutation = useDeleteUserQuota()
  const unit = detail.unit
  const unitLabel = unit === 'MB' ? 'MB' : 'request'
  const kindKey = detail.kind

  const save = () => {
    if (!form.isValid) {
      toast.error('Hạn mức phải là số nguyên không âm, hoặc chọn Không giới hạn.')
      return
    }
    saveMutation.mutate(
      { userId, kind: detail.kind, payload: form.payload },
      {
        onSuccess: (data) => toast.success(data.message || 'Đã lưu quota riêng.'),
        onError: (error: Error) => toast.error(error.message || 'Không thể lưu quota riêng.'),
      },
    )
  }

  const remove = () =>
    deleteMutation.mutate(
      { userId, kind: detail.kind },
      {
        onSuccess: (data) => toast.success(data.message || 'Đã xoá quota riêng.'),
        onError: (error: Error) => toast.error(error.message || 'Không thể xoá quota riêng.'),
      },
    )

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-2 rounded-lg border bg-muted/30 p-3 text-sm sm:grid-cols-2">
        <div>
          <p className="text-xs text-muted-foreground">Đang áp dụng</p>
          <p className="font-semibold">
            {formatQuotaLimit(detail.effective.limit_value, unit, detail.effective.period)}
          </p>
          <p className="text-xs text-muted-foreground">
            {QUOTA_SOURCE_LABELS[detail.effective.source]}
            {detail.effective.source === 'override' && ` · hết hạn: ${formatLocalDate(detail.effective.expires_on)}`}
            {' · '}
            {detail.effective.enforce ? 'đang chặn' : 'chỉ theo dõi'}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Đã dùng</p>
          <p className="tabular-nums">
            Ngày {formatQuotaAmount(detail.usage.day, unit)} · Tháng {formatQuotaAmount(detail.usage.month, unit)}
          </p>
          <p className="text-xs text-muted-foreground tabular-nums">Năm {formatQuotaAmount(detail.usage.year, unit)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`override-limit-${kindKey}`}>Hạn mức ({unitLabel})</Label>
          <Input
            id={`override-limit-${kindKey}`}
            type="number"
            min={0}
            inputMode="numeric"
            value={form.unlimited ? '' : form.limit}
            placeholder={form.unlimited ? '∞' : '0'}
            disabled={form.unlimited}
            onChange={(event) => form.setLimit(event.target.value)}
          />
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
            <Checkbox
              checked={form.unlimited}
              onCheckedChange={(checked) => form.setUnlimited(checked === true)}
              aria-label="Không giới hạn"
            />
            Không giới hạn
          </label>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`override-period-${kindKey}`}>Chu kỳ</Label>
          <NativeSelect
            id={`override-period-${kindKey}`}
            value={form.period}
            onChange={(event) => form.setPeriod(event.target.value as QuotaPeriod | 'policy')}
            className="h-9 w-full"
          >
            <NativeSelectOption value="policy">Theo chính sách chung</NativeSelectOption>
            {QUOTA_PERIODS.map((period) => (
              <NativeSelectOption key={period} value={period}>
                Theo {QUOTA_PERIOD_LABELS[period]}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`override-expires-${kindKey}`}>Áp dụng đến hết ngày</Label>
          <Input
            id={`override-expires-${kindKey}`}
            type="date"
            value={form.expiresOn}
            onChange={(event) => form.setExpiresOn(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">Để trống: không thời hạn. Hết hạn sẽ quay về mặc định của vai trò.</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`override-note-${kindKey}`}>Ghi chú</Label>
          <Input
            id={`override-note-${kindKey}`}
            value={form.note}
            maxLength={255}
            placeholder="Vd: lớp học thử tháng 11"
            onChange={(event) => form.setNote(event.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        {detail.override && (
          <Button
            variant="outline"
            className="gap-1.5 text-destructive"
            onClick={remove}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="size-3.5" /> Xoá quota riêng
          </Button>
        )}
        <Button className="gap-1.5" onClick={save} disabled={saveMutation.isPending}>
          <Save className="size-3.5" />
          {saveMutation.isPending ? 'Đang lưu…' : detail.override ? 'Cập nhật quota riêng' : 'Cấp quota riêng'}
        </Button>
      </div>
    </div>
  )
}

function UserQuotaDetail({ userId }: { userId: number }) {
  const query = useQuotaUserDetail(userId)
  if (query.isPending) return <PageLoading label="Đang tải quota của người dùng…" />
  if (query.error) return <PageError error={query.error} />
  const { user, quotas } = query.data
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">{quotaUserLabel(user)}</span>
        {user.email && <span className="text-muted-foreground">{user.email}</span>}
        {user.role_name && <Badge variant="outline">{user.role_name}</Badge>}
        {user.is_admin && <Badge variant="destructive">Admin · không giới hạn</Badge>}
      </div>
      <Tabs defaultValue="api" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          {quotas.map((quota) => (
            <TabsTrigger key={quota.kind} value={quota.kind} className="gap-1.5 text-xs sm:text-sm">
              {QUOTA_KIND_META[quota.kind].short}
              {quota.override && <span className="size-1.5 rounded-full bg-primary" aria-label="có quota riêng" />}
            </TabsTrigger>
          ))}
        </TabsList>
        {quotas.map((quota) => (
          <TabsContent key={quota.kind} value={quota.kind}>
            <OverrideForm userId={user.id} detail={quota} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}

export function QuotaUserDialog({
  open,
  userId,
  onOpenChange,
  onSelectUser,
}: {
  open: boolean
  userId: number | null
  onOpenChange: (open: boolean) => void
  onSelectUser: (userId: number | null) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {userId !== null && (
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                onClick={() => onSelectUser(null)}
                aria-label="Chọn người dùng khác"
              >
                <ArrowLeft className="size-4" />
              </Button>
            )}
            Quota riêng của người dùng
          </DialogTitle>
          <DialogDescription>
            Nâng (hoặc giới hạn) hạn mức API, MCP và upload cho một người, có thể kèm ngày hết hạn.
          </DialogDescription>
        </DialogHeader>
        {userId === null ? (
          <UserSearch onSelect={(user) => onSelectUser(user.id)} />
        ) : (
          <UserQuotaDetail userId={userId} />
        )}
      </DialogContent>
    </Dialog>
  )
}
