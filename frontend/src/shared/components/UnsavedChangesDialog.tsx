import { useEffect, useRef, useState, type RefObject } from 'react'
import { useBlocker } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export function UnsavedDialog({ open, message, close, discard, proceed, onSave }: {
  open: boolean; message: string; close: () => void; discard: () => void; proceed: () => void; onSave?: () => Promise<void>
}) {
  const { t } = useTranslation('common')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const opener = useRef<HTMLElement | null>(null)
  useEffect(() => { if (open) setError(null) }, [open])
  const save = async () => {
    if (!onSave || saving) return
    setSaving(true); setError(null)
    try { await onSave(); proceed() } catch (cause) {
      setError(cause instanceof Error ? cause.message : t('error'))
    } finally { setSaving(false) }
  }
  return <Dialog open={open} onOpenChange={(next) => { if (!next && !saving) { setError(null); close() } }}>
    <DialogContent onOpenAutoFocus={() => {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    }} onCloseAutoFocus={(event) => {
      if (opener.current?.isConnected) { event.preventDefault(); opener.current.focus() }
    }} onEscapeKeyDown={(event) => { if (saving) event.preventDefault() }} onPointerDownOutside={(event) => { if (saving) event.preventDefault() }}>
      <DialogHeader><DialogTitle>{t('unsaved.title')}</DialogTitle><DialogDescription>{message}</DialogDescription></DialogHeader>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <DialogFooter className="flex-wrap">
        <Button variant="outline" disabled={saving} onClick={close}>{t('unsaved.stay')}</Button>
        <Button variant="ghost" disabled={saving} onClick={discard}>{t('unsaved.discard')}</Button>
        {onSave && <Button disabled={saving} onClick={() => void save()}>{saving ? t('loading') : t('unsaved.save_continue')}</Button>}
      </DialogFooter>
    </DialogContent>
  </Dialog>
}

export function UnsavedRouteGuard({ dirty, message, bypass, onSave, onDiscard }: { dirty: boolean; message: string; bypass: RefObject<boolean>; onSave?: () => Promise<void>; onDiscard?: () => void }) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && !bypass.current && (
    currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search
  ))
  return <UnsavedDialog open={blocker.state === 'blocked'} message={message}
    close={() => blocker.reset?.()} discard={() => { onDiscard?.(); blocker.proceed?.() }} proceed={() => blocker.proceed?.()} onSave={onSave} />
}

