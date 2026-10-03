import { useEffect, type RefObject } from 'react'
import { storyChapters } from '../data/storyChapters'
import { clamp, emberAt, lightAt, sceneState, storyPosition } from '../lib/storyTimeline'

export type StoryMode = 'pinned' | 'flow' | 'static'

type StoryProgressRefs = {
  rootRef: RefObject<HTMLElement | null>
  sectionRefs: RefObject<(HTMLElement | null)[]>
  sceneRefs: RefObject<(SVGGElement | null)[]>
  emberRef: RefObject<SVGGElement | null>
}

const anchors = storyChapters.map((chapter) => chapter.ember)

/**
 * One rAF-throttled scroll reader drives the whole story. Continuous values are
 * written as CSS custom properties on refs, so React never re-renders per frame.
 */
export function useStoryProgress(
  mode: StoryMode,
  { rootRef, sectionRefs, sceneRefs, emberRef }: StoryProgressRefs,
) {
  useEffect(() => {
    const root = rootRef.current
    if (!root || mode === 'static') return

    let frame = 0
    const flowSections = sectionRefs.current ?? []

    const updatePinned = (viewport: number) => {
      const sections = sectionRefs.current ?? []
      const local = sections.map((section) => {
        if (!section) return -1
        const rect = section.getBoundingClientRect()
        return (viewport * 0.5 - rect.top) / Math.max(rect.height, 1)
      })
      const position = storyPosition(local)
      const active = Math.round(position)

      root.style.setProperty('--story-light', lightAt(position).toFixed(4))

      const scenes = sceneRefs.current ?? []
      scenes.forEach((scene, index) => {
        if (!scene) return
        const { t, v } = sceneState(position, index, scenes.length)
        scene.style.setProperty('--t', t.toFixed(4))
        scene.style.setProperty('--v', v.toFixed(4))
        // Only the current scene and its neighbours stay live.
        scene.dataset.active = Math.abs(index - active) <= 1 && v > 0 ? 'true' : 'false'
      })

      const ember = emberRef.current
      if (ember) {
        const { x, y, size } = emberAt(position, anchors)
        ember.style.setProperty('--ex', x.toFixed(2))
        ember.style.setProperty('--ey', y.toFixed(2))
        ember.style.setProperty('--es', size.toFixed(3))
      }
    }

    const updateFlow = (viewport: number) => {
      for (const section of flowSections) {
        if (!section) continue
        const rect = section.getBoundingClientRect()
        const t = clamp((viewport * 0.9 - rect.top) / Math.max(rect.height * 0.8, 1))
        section.style.setProperty('--t', t.toFixed(4))
      }
    }

    const update = () => {
      frame = 0
      const viewport = window.innerHeight
      if (mode === 'pinned') updatePinned(viewport)
      else updateFlow(viewport)
    }

    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update)
    }

    update()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)

    return () => {
      if (frame) window.cancelAnimationFrame(frame)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      root.style.removeProperty('--story-light')
      for (const section of flowSections) section?.style.removeProperty('--t')
    }
  }, [mode, rootRef, sectionRefs, sceneRefs, emberRef])

  // Ambient loops (flame flicker) pause when the tab is hidden or the art is off screen.
  useEffect(() => {
    const root = rootRef.current
    if (!root) return

    const onVisibility = () => {
      root.dataset.paused = document.hidden ? 'true' : 'false'
    }
    onVisibility()
    document.addEventListener('visibilitychange', onVisibility)

    let observer: IntersectionObserver | undefined
    if ('IntersectionObserver' in window) {
      observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          ;(entry.target as HTMLElement).dataset.offscreen = entry.isIntersecting ? 'false' : 'true'
        }
      })
      root.querySelectorAll('[data-story-art]').forEach((element) => observer?.observe(element))
    }

    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      observer?.disconnect()
    }
  }, [mode, rootRef])
}
