import { useEffect, useRef } from 'react'
import {
  resolveReviewAction,
  type ReviewAction,
  type ReviewRating,
} from '../interactions/reviewInteraction'

// Radix keeps an open menu or dialog in the DOM under these roles; keys typed
// there belong to it, not to the card behind it.
const OPEN_OVERLAY_SELECTOR = '[role="dialog"], [role="alertdialog"], [role="menu"]'

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
  // A button or link keeps its native Space/Enter only when the learner reached
  // it with Tab. Focus left there by a mouse click, or handed back by a closing
  // menu or dialog, must not swallow the study shortcuts.
  const tabPendingRef = useRef(false)
  const tabFocusedRef = useRef<EventTarget | null>(null)

  useEffect(() => {
    if (leaseConflict || hasReceipt || isQuickEditOpen) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Tab') {
        tabPendingRef.current = true
        return
      }

      const activeEl = document.activeElement as HTMLElement | null
      const activeTag = (activeEl?.tagName || '').toLowerCase()
      if (
        event.defaultPrevented
        || event.isComposing
        || event.repeat
        || activeTag === 'input'
        || activeTag === 'textarea'
        || activeTag === 'select'
        || activeEl?.isContentEditable
        || document.querySelector(OPEN_OVERLAY_SELECTOR)
      ) return

      const onControl = activeTag === 'button' || activeTag === 'a'
      const tabFocusedControl = onControl && activeEl === tabFocusedRef.current
      const claim = () => {
        event.preventDefault()
        if (onControl && !tabFocusedControl) activeEl?.blur()
      }

      const code = event.code
      const key = event.key

      const isUndo = (
        (event.ctrlKey || event.metaKey) && (key === 'z' || key === 'Z' || code === 'KeyZ')
      ) || (
        !event.ctrlKey && !event.metaKey && !event.altKey && (key === 'z' || key === 'Z' || code === 'KeyZ')
      )

      if (isUndo) {
        claim()
        void onUndo()
        return
      }

      if (event.altKey || event.ctrlKey || event.metaKey) return

      const isEditKey = key === 'e' || key === 'E' || code === 'KeyE'
      if (isEditKey) {
        claim()
        onOpenEdit()
        return
      }

      const isSpaceOrEnter = code === 'Space' || key === ' ' || key === 'Spacebar' || code === 'Enter' || key === 'Enter'
      const isFullscreenKey = key === 'f' || key === 'F' || code === 'KeyF'

      if (isSpaceOrEnter) {
        if (tabFocusedControl) return
        claim()
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
          claim()
          void onReviewAction(resolveReviewAction(rating))
        } else if (isFullscreenKey) {
          claim()
          onToggleFullscreen()
        }
      } else if (isFullscreenKey) {
        claim()
        onToggleFullscreen()
      }
    }

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key === 'Tab') tabPendingRef.current = false
    }

    const handleFocusIn = (event: FocusEvent) => {
      tabFocusedRef.current = tabPendingRef.current ? event.target : null
      tabPendingRef.current = false
    }

    const handleFocusBack = () => {
      const activeEl = document.activeElement as HTMLElement | null
      const activeTag = (activeEl?.tagName || '').toLowerCase()
      if (activeTag === 'button' || activeTag === 'a') {
        activeEl?.blur()
      }
    }

    // Capture runs before React handlers, so a focused Radix trigger cannot turn
    // Space/Enter into "open menu" before the shortcut claims the key.
    window.addEventListener('keydown', handleKeyDown, true)
    window.addEventListener('keyup', handleKeyUp)
    window.addEventListener('focusin', handleFocusIn)
    window.addEventListener('focus', handleFocusBack)
    return () => {
      window.removeEventListener('keydown', handleKeyDown, true)
      window.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('focusin', handleFocusIn)
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
