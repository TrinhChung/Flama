/**
 * frontend/src/entities/flashcard/model/studySyncEvents.ts
 * Decoupled event hub for study sync notifications without direct imports into features/study.
 */

import type { CardContentUpdate } from './cardContentUpdates'

export type StudyCardUpdateDetail = CardContentUpdate

export interface StudyTemplateUpdateDetail {
  templateId: string
  updated: Record<string, unknown>
}

export const STUDY_CARD_UPDATED_EVENT = 'flama_study_card_updated'
export const STUDY_TEMPLATE_UPDATED_EVENT = 'flama_study_template_updated'
export const STUDY_SYNC_CHANNEL_NAME = 'flama_study_sync_channel'

export function dispatchStudyCardUpdate(detail: StudyCardUpdateDetail): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(STUDY_CARD_UPDATED_EVENT, { detail }),
  )
  try {
    const channel = new BroadcastChannel(STUDY_SYNC_CHANNEL_NAME)
    channel.postMessage({
      type: 'CARD_UPDATED',
      cardId: detail.cardId,
      noteId: detail.noteId || null,
      fieldValues: detail.fieldValues,
      media: detail.media,
    })
    channel.close()
  } catch {
    // BroadcastChannel may be unavailable in restricted environments or tests
  }
}

export function dispatchStudyTemplateUpdate(detail: StudyTemplateUpdateDetail): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(STUDY_TEMPLATE_UPDATED_EVENT, { detail }),
  )
  try {
    const channel = new BroadcastChannel(STUDY_SYNC_CHANNEL_NAME)
    channel.postMessage({
      type: 'TEMPLATE_UPDATED',
      templateId: detail.templateId,
      updated: detail.updated,
    })
    channel.close()
  } catch {
    // BroadcastChannel may be unavailable
  }
}
