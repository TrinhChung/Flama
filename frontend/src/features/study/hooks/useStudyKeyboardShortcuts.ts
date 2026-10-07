import { useEffect } from 'react'
import {
  resolveReviewAction,
  type ReviewAction,
  type ReviewRating,
} from '../interactions/reviewInteraction'

export type UseStudyKeyboardShortcutsOptions = {
  cardId?: string | null
  revealed: boolean
  isQuickEditOpen: boolean
  leaseConflict: boolean
  hasReceipt: boolean
  onReveal: () => void
  onReviewAction: (action: ReviewAction) => void
  onUndo: () => void | Promise<void>
  onOpenEdit: () => void
  onToggleFullscreen: () => void
}

export function useStudyKeyboardShortcuts({
  cardId,
  revealed,
  isQuickEditOpen,
  leaseConflict,
  hasReceipt,
  onReveal,
  onReviewAction,
  onUndo,
  onOpenEdit,
  onToggleFullscreen,
}: UseStudyKeyboardShortcutsOptions) {
  useEffect(() => {
    if (leaseConflict || hasReceipt || isQuickEditOpen) return

    const handleKeyDown = (event: KeyboardEvent) => {
      const activeEl = document.activeElement
      const activeTag = (activeEl?.tagName || '').toLowerCase()
      if (
        event.defaultPrevented
        || event.isComposing
        || event.repeat
        || activeTag === 'input'
        || activeTag === 'textarea'
        || activeTag === 'select'
        || (activeEl as HTMLElement)?.isContentEditable
      ) return

      const code = event.code
      const key = event.key

      const isUndo = (
        (event.ctrlKey || event.metaKey) && (key === 'z' || key === 'Z' || code === 'KeyZ')
      ) || (
        !event.ctrlKey && !event.metaKey && !event.altKey && (key === 'z' || key === 'Z' || code === 'KeyZ')
      )

      if (isUndo) {
        event.preventDefault()
        void onUndo()
        return
      }

      if (
        event.altKey
        || event.ctrlKey
        || event.metaKey
        || activeTag === 'button'
        || activeTag === 'a'
      ) return

      const isEditKey = key === 'e' || key === 'E' || code === 'KeyE'
      if (isEditKey) {
        event.preventDefault()
        onOpenEdit()
        return
      }

      const isSpaceOrEnter = code === 'Space' || key === ' ' || key === 'Spacebar' || code === 'Enter' || key === 'Enter'
      const isFullscreenKey = key === 'f' || key === 'F' || code === 'KeyF'

      if (isSpaceOrEnter) {
        event.preventDefault()
        if (!cardId) return
        if (!revealed) onReveal()
        else void onReviewAction(resolveReviewAction('good'))
      } else if (revealed) {
        const ratingByKey: Record<string, ReviewRating> = {
          '1': 'again',
          '2': 'hard',
          '3': 'good',
          '4': 'easy',
        }
        const codeMap: Record<string, string> = {
          Digit1: '1',
          Numpad1: '1',
          Digit2: '2',
          Numpad2: '2',
          Digit3: '3',
          Numpad3: '3',
          Digit4: '4',
          Numpad4: '4',
        }
        const mappedKey = codeMap[code] ?? key
        const rating = ratingByKey[mappedKey]
        if (rating) {
          event.preventDefault()
          void onReviewAction(resolveReviewAction(rating))
        } else if (isFullscreenKey) {
          event.preventDefault()
          onToggleFullscreen()
        }
      } else if (isFullscreenKey) {
        event.preventDefault()
        onToggleFullscreen()
      }
    }

    const handleFocusBack = () => {
      const activeEl = document.activeElement as HTMLElement | null
      const activeTag = (activeEl?.tagName || '').toLowerCase()
      if (activeTag === 'button' || activeTag === 'a') {
        activeEl?.blur()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('focus', handleFocusBack)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('focus', handleFocusBack)
    }
  }, [
    cardId,
    hasReceipt,
    isQuickEditOpen,
    leaseConflict,
    onOpenEdit,
    onReveal,
    onReviewAction,
    onToggleFullscreen,
    onUndo,
    revealed,
  ])
}
