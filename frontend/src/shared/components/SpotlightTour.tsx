import { useEffect, useState, useRef, useCallback } from 'react'
import { ArrowLeft, ArrowRight, Check, Sparkles, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export interface TourStep {
  target: string // CSS selector e.g. '[data-tour="create-input"]'
  title: string
  content: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
}

interface SpotlightTourProps {
  steps: TourStep[]
  isOpen: boolean
  onClose: () => void
  onComplete?: () => void
}

interface ElementRect {
  top: number
  left: number
  width: number
  height: number
}

export function SpotlightTour({ steps, isOpen, onClose, onComplete }: SpotlightTourProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [rect, setRect] = useState<ElementRect | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 })

  const currentStep = steps[currentStepIndex]

  const updatePosition = useCallback(() => {
    if (!isOpen || !currentStep) return

    const el = document.querySelector(currentStep.target)
    if (!el) {
      setRect(null)
      return
    }

    const r = el.getBoundingClientRect()
    const padding = 8
    const elementRect: ElementRect = {
      top: r.top - padding,
      left: r.left - padding,
      width: r.width + padding * 2,
      height: r.height + padding * 2,
    }

    setRect(elementRect)

    // Calculate tooltip position
    const tooltipWidth = 360
    const tooltipHeight = 200
    const margin = 16

    let top = 0
    let left = 0

    const placement = currentStep.placement || 'bottom'

    if (placement === 'bottom') {
      top = elementRect.top + elementRect.height + margin
      left = elementRect.left + (elementRect.width / 2) - (tooltipWidth / 2)
    } else if (placement === 'top') {
      top = elementRect.top - tooltipHeight - margin
      left = elementRect.left + (elementRect.width / 2) - (tooltipWidth / 2)
    } else if (placement === 'left') {
      top = elementRect.top + (elementRect.height / 2) - (tooltipHeight / 2)
      left = elementRect.left - tooltipWidth - margin
    } else {
      top = elementRect.top + (elementRect.height / 2) - (tooltipHeight / 2)
      left = elementRect.left + elementRect.width + margin
    }

    // Viewport boundaries clamping
    const screenWidth = window.innerWidth
    const screenHeight = window.innerHeight

    if (left < 16) left = 16
    if (left + tooltipWidth > screenWidth - 16) {
      left = screenWidth - tooltipWidth - 16
    }

    if (top < 16) {
      // If overflowing top, flip to bottom
      top = elementRect.top + elementRect.height + margin
    }
    if (top + tooltipHeight > screenHeight - 16) {
      // If overflowing bottom, flip to top
      top = elementRect.top - tooltipHeight - margin
      if (top < 16) top = 16
    }

    setTooltipPos({ top, left })
  }, [isOpen, currentStep])

  useEffect(() => {
    if (!isOpen) return

    setCurrentStepIndex(0)
  }, [isOpen])

  useEffect(() => {
    if (!isOpen || !currentStep) return

    const el = document.querySelector(currentStep.target)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }

    // Allow time for smooth scroll to settle before computing rect
    const timer = setTimeout(() => {
      updatePosition()
    }, 250)

    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)

    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [isOpen, currentStepIndex, currentStep, updatePosition])

  if (!isOpen || !currentStep) return null

  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1)
    } else {
      if (onComplete) onComplete()
      onClose()
    }
  }

  const handlePrev = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1)
    }
  }

  return (
    <div className="fixed inset-0 z-50 pointer-events-auto">
      {/* Dimmed Overlay with Spotlight Box */}
      <svg className="fixed inset-0 size-full pointer-events-none transition-all duration-300">
        <defs>
          <mask id="spotlight-mask">
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            {rect && (
              <rect
                x={rect.left}
                y={rect.top}
                width={rect.width}
                height={rect.height}
                rx="14"
                fill="black"
                className="transition-all duration-300 ease-out"
              />
            )}
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          fill="rgba(0, 0, 0, 0.72)"
          mask="url(#spotlight-mask)"
          className="pointer-events-auto"
        />
      </svg>

      {/* Pulsing Highlight Ring around the targeted element */}
      {rect && (
        <div
          className="fixed rounded-2xl pointer-events-none border-2 border-primary ring-4 ring-primary/30 transition-all duration-300 ease-out animate-pulse"
          style={{
            top: `${rect.top}px`,
            left: `${rect.left}px`,
            width: `${rect.width}px`,
            height: `${rect.height}px`,
          }}
        />
      )}

      {/* Floating Tooltip Card */}
      <div
        ref={tooltipRef}
        className="fixed z-50 w-80 sm:w-96 rounded-2xl border border-primary/30 bg-card p-5 shadow-2xl transition-all duration-300 ease-out animate-in fade-in zoom-in-95"
        style={{
          top: `${tooltipPos.top}px`,
          left: `${tooltipPos.left}px`,
        }}
      >
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-1.5">
            <Badge variant="default" className="text-[11px] font-bold bg-primary text-primary-foreground px-2 py-0.5">
              Bước {currentStepIndex + 1}/{steps.length}
            </Badge>
            <span className="text-[11px] text-muted-foreground font-semibold flex items-center gap-1">
              <Sparkles className="size-3 text-primary" /> Hướng Dẫn Trực Quan
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="size-6 rounded-lg text-muted-foreground hover:text-foreground flex items-center justify-center hover:bg-muted transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-2 mb-5">
          <h4 className="text-sm font-bold text-foreground leading-snug">
            {currentStep.title}
          </h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {currentStep.content}
          </p>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-border/70">
          <div className="flex items-center gap-1">
            {steps.map((_, idx) => (
              <div
                key={idx}
                className={`size-1.5 rounded-full transition-all ${
                  idx === currentStepIndex ? 'w-4 bg-primary' : 'bg-muted-foreground/30'
                }`}
              />
            ))}
          </div>

          <div className="flex items-center gap-2">
            {currentStepIndex > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrev}
                className="h-8 px-2.5 text-xs font-semibold rounded-xl"
              >
                <ArrowLeft className="size-3.5 mr-1" /> Trước
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleNext}
              className="h-8 px-3.5 text-xs font-bold rounded-xl shadow-xs bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {currentStepIndex === steps.length - 1 ? (
                <>
                  <Check className="size-3.5 mr-1" /> Hoàn tất
                </>
              ) : (
                <>
                  Tiếp theo <ArrowRight className="size-3.5 ml-1" />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
