import '@/shared/config/i18n'
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
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

const message = (error: unknown) => error instanceof Error ? error.message : 'Đã có lỗi xảy ra. Vui lòng thử lại.'
const formatDate = (value: string, lang: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(lang === 'en' ? 'en-US' : 'vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function TemplateVersionHistorySheet({ open, onOpenChange, source, current, onRestored, onRestorePendingChange }: TemplateVersionHistorySheetProps) {
  const { t, i18n } = useTranslation('card_templates')
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
      toast.success(t('history.toast_success', { version: version.version_no }))
      setConfirmOpen(false)
      await queryClient.invalidateQueries({ queryKey: source.listKey })
    },
    onError: (error) => {
      if (active.current) toast.error(t('history.toast_error'), { description: message(error) })
    },
    onSettled: () => { if (active.current) onRestorePendingChange?.(false) },
  })

  const getOriginLabel = (origin: string) => {
    switch (origin) {
      case 'backfill': return t('history.origins.backfill')
      case 'create': return t('history.origins.create')
      case 'edit': return t('history.origins.edit')
      case 'reset': return t('history.origins.reset')
      case 'restore': return t('history.origins.restore')
      case 'apply': return t('history.origins.apply')
      case 'fork': return t('history.origins.fork')
      case 'market_copy': return t('history.origins.market_copy')
      case 'update': return t('history.origins.update')
      default: return origin
    }
  }

  return (
    <Sheet open={open} onOpenChange={(next) => {
      if (restore.isPending) return
      if (!next) { setSelectedId(null); setConfirmOpen(false) }
      onOpenChange(next)
    }}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{t('history.title')}</SheetTitle>
          <SheetDescription>{t('history.description')}</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 p-4 pt-0">
          {list.isPending && <p role="status">{t('history.loading')}</p>}
          {list.error && <p role="alert">{message(list.error)}</p>}
          {list.data?.items.length === 0 && <p>{t('history.empty')}</p>}
          <div className="space-y-2">
            {list.data?.items.map((version) => (
              <button key={version.id} type="button" disabled={restore.isPending} aria-pressed={selectedId === version.id}
                onClick={() => setSelectedId(version.id)}
                className={`w-full rounded-xl border p-3 text-left space-y-1 ${selectedId === version.id ? 'border-primary bg-primary/5' : 'border-border bg-card'}`}>
                <span className="flex flex-wrap items-center gap-2 font-semibold">{t('history.version_label', { version: version.version_no })}{version.is_current && <Badge variant="secondary">{t('history.badge_current')}</Badge>}</span>
                <span className="block text-xs text-muted-foreground">{formatDate(version.created_at, i18n.language)} · {getOriginLabel(version.origin)}{version.created_by && ` · ${version.created_by.username}`}</span>
                {version.change_note && <span className="block text-sm break-words">{version.change_note}</span>}
              </button>
            ))}
          </div>
          {selectedId && detail.isPending && <p role="status">{t('history.loading_detail')}</p>}
          {selectedId && detail.error && <p role="alert">{message(detail.error)}</p>}
          {selected && detail.data?.id === selectedId && (
            <>
              <TemplateDiffView before={detail.data} after={current} beforeLabel={t('history.before_label', { version: selected.version_no })} afterLabel={t('history.after_label')} />
              {!selected.is_current && <Button disabled={restore.isPending} onClick={() => setConfirmOpen(true)}>{t('history.restore_button')}</Button>}
            </>
          )}
        </div>
        <ConfirmDialog open={confirmOpen} onOpenChange={setConfirmOpen} title={t('history.confirm_title', { version: selected?.version_no })}
          description={t('history.confirm_desc')}
          confirmText={t('history.confirm_btn')} isLoading={restore.isPending} onConfirm={() => { if (selected) restore.mutate(selected) }} />
      </SheetContent>
    </Sheet>
  )
}
