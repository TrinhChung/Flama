import React, { useState, useRef, useCallback, useEffect } from 'react'

export function useBrowseEditorResize() {
  const [editorWidth, setEditorWidth] = useState(() => {
    try {
      const saved = localStorage.getItem('flama:browse:editor-width')
      if (saved) return Number(saved)
    } catch {}
    return 320 // default width
  })
  const isResizing = useRef(false)
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth < 768
    }
    return false
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    const media = window.matchMedia('(max-width: 767px)')
    const listener = () => setIsMobile(media.matches)
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isResizing.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isResizing.current) return
      const newWidth = window.innerWidth - moveEvent.clientX
      const minWidth = 280
      const maxWidth = Math.min(800, window.innerWidth * 0.6)
      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setEditorWidth(newWidth)
        try {
          localStorage.setItem('flama:browse:editor-width', String(newWidth))
        } catch {}
      }
    }

    const handleMouseUp = () => {
      isResizing.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }, [])

  return {
    editorWidth,
    isMobile,
    handleMouseDown,
  }
}
