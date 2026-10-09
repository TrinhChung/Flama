import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { ConfirmDialog } from '@/shared/ui'
import { TemplateDiffView, type CardTemplateItem, type TemplateSources } from '@/entities/card-template'
import type { TemplateVersionSource } from '../model/types'

export type TemplateVersionHistorySheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  source: TemplateVersionSource
  current: TemplateSources
  onRestored: (template: CardTemplateItem) => void | Promise<void>
  onRestorePendingChange?: (pending: boolean) => void
}

const originLabels: Record<string, string> = {
  backfill: 'Bản ghi ban đầu', create: 'Tạo mới', edit: 'Chỉnh sửa',
  reset: 'Đặt lại mặc định', restore: 'Khôi phục', apply: 'Áp dụng từ thư viện',
  fork: 'Tạo bản riêng', market_copy: 'Bản nhận marketplace', update: 'Cập nhật từ tác giả',
}
const message = (error: unknown) => error instanceof Error ? error.message : 'Đã có lỗi xảy ra. Vui lòng thử lại.'
const formatDate = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function TemplateVersionHistorySheet({ open, onOpenChange, source, current, onRestored, onRestorePendingChange }: TemplateVersionHistorySheetProps) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const list = useQuery({ queryKey: source.listKey, queryFn: ({ signal }) => source.list(signal), enabled: open })
  const detail = useQuery({
    queryKey: source.detailKey(selectedId ?? ''),
    queryFn: ({ signal }) => source.get(selectedId!, signal),
    enabled: open && Boolean(selectedId),
  })
  const selected = list.data?.items.find((item) => item.id === selectedId)
  const restore = useMutation({
    mutationFn: (version: { id: string; version_no: number }) => source.restore(version.id),
    onMutate: () => { onRestorePendingChange?.(true) },
    onSuccess: async (template, version) => {
      // A route/template switch unmounts this keyed sheet. Never apply its late response.
      if (!active.current) return
      await onRestored(template)
      if (!active.current) return
      toast.success(`Đã khôi phục phiên bản ${version.version_no}.`)
      setConfirmOpen(false)
      await queryClient.invalidateQueries({ queryKey: source.listKey })
    },
    onError: (error) => {
      if (active.current) toast.error('Không thể khôi phục', { description: message(error) })
    },
    onSettled: () => { if (active.current) onRestorePendingChange?.(false) },
  })

  return (
    <Sheet open={open} onOpenChange={(next) => {
      if (restore.isPending) return
      if (!next) { setSelectedId(null); setConfirmOpen(false) }
      onOpenChange(next)
    }}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Lịch sử phiên bản</SheetTitle>
          <SheetDescription>Mỗi lần lưu thay đổi nội dung tạo một phiên bản. Khôi phục sẽ tạo phiên bản mới, không xóa lịch sử.</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 p-4 pt-0">
          {list.isPending && <p role="status">Đang tải lịch sử…</p>}
          {list.error && <p role="alert">{message(list.error)}</p>}
          {list.data?.items.length === 0 && <p>Chưa có phiên bản nào.</p>}
          <div className="space-y-2">
            {list.data?.items.map((version) => (
              <button key={version.id} type="button" disabled={restore.isPending} aria-pressed={selectedId === version.id}
                onClick={() => setSelectedId(version.id)}
                className={`w-full rounded-xl border p-3 text-left space-y-1 ${selectedId === version.id ? 'border-primary bg-primary/5' : 'border-border bg-card'}`}>
                <span className="flex flex-wrap items-center gap-2 font-semibold">Phiên bản {version.version_no}{version.is_current && <Badge variant="secondary">Hiện tại</Badge>}</span>
                <span className="block text-xs text-muted-foreground">{formatDate(version.created_at)} · {Object.hasOwn(originLabels, version.origin) ? originLabels[version.origin] : version.origin}{version.created_by && ` · ${version.created_by.username}`}</span>
                {version.change_note && <span className="block text-sm break-words">{version.change_note}</span>}
              </button>
            ))}
          </div>
          {selectedId && detail.isPending && <p role="status">Đang tải phiên bản…</p>}
          {selectedId && detail.error && <p role="alert">{message(detail.error)}</p>}
          {selected && detail.data?.id === selectedId && (
            <>
              <TemplateDiffView before={detail.data} after={current} beforeLabel={`Phiên bản ${selected.version_no}`} afterLabel="Trình soạn hiện tại" />
              {!selected.is_current && <Button disabled={restore.isPending} onClick={() => setConfirmOpen(true)}>Khôi phục phiên bản này</Button>}
            </>
          )}
        </div>
        <ConfirmDialog open={confirmOpen} onOpenChange={setConfirmOpen} title={`Khôi phục phiên bản ${selected?.version_no}?`}
          description="Nội dung chưa lưu trong trình soạn sẽ được thay bằng phiên bản này. Lịch sử cũ vẫn được giữ."
          confirmText="Khôi phục" isLoading={restore.isPending} onConfirm={() => { if (selected) restore.mutate(selected) }} />
      </SheetContent>
    </Sheet>
  )
}
