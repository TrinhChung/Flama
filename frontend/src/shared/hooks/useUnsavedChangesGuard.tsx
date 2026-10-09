import { useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { UNSAFE_DataRouterContext } from 'react-router-dom'
import { UnsavedDialog, UnsavedRouteGuard } from '@/shared/components/UnsavedChangesDialog'

/** Protect route exits, local selection changes and browser reloads without discarding a draft on refetch. */
export function useUnsavedChangesGuard(dirty: boolean, message: string, options: { onSave?: () => Promise<void>; onDiscard?: () => void } = {}): {
  requestNavigation: (action: () => void) => void
  confirmDialog: ReactNode
} {
  const router = useContext(UNSAFE_DataRouterContext)
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null)
  const dirtyRef = useRef(dirty)
  const bypass = useRef(false)
  const optionsRef = useRef(options)
  optionsRef.current = options
  dirtyRef.current = dirty
  useEffect(() => {
    if (!dirty) return
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', beforeUnload)
    return () => window.removeEventListener('beforeunload', beforeUnload)
  }, [dirty])
  const requestNavigation = useCallback((action: () => void) => {
    if (!dirtyRef.current) action()
    else setPendingAction(() => action)
  }, [])
  const proceed = () => {
    const action = pendingAction
    setPendingAction(null)
    bypass.current = true
    try { action?.() } finally { queueMicrotask(() => { bypass.current = false }) }
  }
  return {
    requestNavigation,
    confirmDialog: <>
      {router && <UnsavedRouteGuard dirty={dirty} message={message} bypass={bypass} onSave={options.onSave} onDiscard={() => optionsRef.current.onDiscard?.()} />}
      <UnsavedDialog open={Boolean(pendingAction)} message={message}
        close={() => setPendingAction(null)} discard={() => { optionsRef.current.onDiscard?.(); proceed() }} proceed={proceed} onSave={options.onSave} />
    </>,
  }
}
