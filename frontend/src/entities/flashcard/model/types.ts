/**
 * frontend/src/entities/flashcard/model/types.ts
 * Flashcard Domain Entities, Payloads, Slot Interfaces & Frame Communication Contracts.
 */

import type React from 'react'

// ============================================================================
// 1. Domain Entities & Definitions
// ============================================================================

export interface FieldDef {
  id?: string
  name: string
  field_type: string
  required?: boolean
  position?: number
}

export interface CardMediaArtifact {
  id: string
  field_name: string
  filename: string
  mime_type: string
  sha256: string
  proxy_url: string
}

/** Only the inputs consumed by the renderer; study wire schemas stay in Study. */
export interface CardRenderTemplate {
  renderer_abi: string
  version: string
  front_source: string
  back_source: string
  front_inline_scripts: string[]
  back_inline_scripts: string[]
  shared_css: string
  field_defs: FieldDef[]
}

export interface CardRenderContent {
  renderer_abi: string
  field_values: Record<string, string>
  render_context: Record<string, unknown>
  media: CardMediaArtifact[]
}

// ============================================================================
// 2. Renderer Payloads
// ============================================================================

export interface CardRenderPayload {
  html: string
  allowed_media_urls: string[]
  allowed_audio_urls: string[]
  allowed_audio_asset_ids?: string[]
  template_key?: string
  shell_key?: string
  has_inline_script?: boolean
  supports_live_patch?: boolean
}

export type RendererSidePayload = CardRenderPayload

// ============================================================================
// 3. PostMessage Communication Protocol Contracts
// ============================================================================

export const FLAMA_RENDERER_CHANNEL = 'flama-card-renderer' as const

// ============================================================================
// 4. Abstract Slots for Extensibility (R2 Open Boundary)
// ============================================================================

export interface CardRendererSlotContext {
  /** Unique ID of the card being rendered */
  cardId?: string | null
  /** Unique ID of the note if applicable */
  noteId?: string | null
  /** Current active side */
  side: 'front' | 'back'
  /** Helper flag indicating if current side is back */
  isBack: boolean
  /** Helper flag indicating if answer is revealed */
  isRevealed: boolean
  /** Operational scope (e.g., 'deck', 'note_type_live_preview', 'shared_deck_preview') */
  scope?: string
  /** Scope identifier (e.g., deckId, noteTypeId) */
  scopeId?: string | null
  /** Field values of the card */
  fieldValues?: Record<string, string>
  /** Active payload object sent to the renderer */
  activeFacePayload?: unknown
  /** Helper action to toggle between front and back */
  toggleSide?: () => void
}

export type SlotRenderer =
  | React.ReactNode
  | ((context: CardRendererSlotContext) => React.ReactNode)

export interface CardRendererSlots {
  /** Slot rendered directly above the card viewport frame */
  header?: SlotRenderer
  /** Slot rendered directly below the card viewport frame */
  footer?: SlotRenderer
  /** Floating toolbar positioned at the corner of the card viewport */
  toolbar?: SlotRenderer
  /** Transparent overlay rendered on top of the iframe surface */
  overlay?: SlotRenderer
  /** Fallback slot rendered when no payload or card is provided */
  emptyState?: SlotRenderer

  // Extended aliases for backward / variant compatibility
  topToolbar?: React.ReactNode
  bottomToolbar?: React.ReactNode
  errorFallback?: (error: Error | string) => React.ReactNode
  loadingFallback?: React.ReactNode
}

// ============================================================================
// 5. Component Props Contracts
// ============================================================================

export interface CardRendererFrameProps {
  cardId?: string | null
  noteId?: string | null
  revealed: boolean
  frontPayload?: unknown
  backPayload?: unknown
  frontHtml?: string
  backHtml?: string
  scope?: string
  scopeId?: string | null
  fieldDefs?: unknown[]
  fieldValues?: Record<string, string>
  active?: boolean
  enableLivePatch?: boolean
  fillHeight?: boolean
  className?: string
  slots?: CardRendererSlots
  headerSlot?: SlotRenderer
  footerSlot?: SlotRenderer
  toolbarSlot?: SlotRenderer
  overlaySlot?: SlotRenderer
}

export interface CardDisplayProps {
  cardId?: string | null
  noteId?: string | null
  side: 'front' | 'back'
  frontPayload?: unknown
  backPayload?: unknown
  frontHtml?: string
  backHtml?: string
  scope?: string
  scopeId?: string | null
  fieldDefs?: unknown[]
  fieldValues?: Record<string, string>
  enableLivePatch?: boolean
  className?: string
  slots?: CardRendererSlots
  headerSlot?: SlotRenderer
  footerSlot?: SlotRenderer
  toolbarSlot?: SlotRenderer
  overlaySlot?: SlotRenderer
}
