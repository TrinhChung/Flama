/**
 * frontend/src/features/study/renderer/studyRendererAdapter.ts
 * Adapter bridging Study session artifacts (StudyTemplateArtifact + StudyContentArtifact)
 * to canonical CardRenderPayload required by @/entities/flashcard.
 */
import type { CardRenderPayload } from '@/entities/flashcard'
import type { StudyContentArtifact, StudyTemplateArtifact } from '../types'
import { renderCardSide } from '@/entities/flashcard/lib/clientRenderer'

/**
 * Adapts study session artifacts into canonical CardRenderPayload for front or back side.
 */
export function adaptStudySessionToRenderPayload(
  template: StudyTemplateArtifact,
  content: StudyContentArtifact,
  side: 'front' | 'back',
): CardRenderPayload {
  return renderCardSide(template, content, side)
}
