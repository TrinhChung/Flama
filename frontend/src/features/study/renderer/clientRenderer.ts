/**
 * Backward compatibility shim.
 * Canonical implementation moved to Tier 5 FSD entity @/entities/flashcard.
 */
export {
  renderCardSide as renderStudySide,
  patchRenderContext,
  renderMediaHtml,
  escapeHtml,
  LINEBREAK_TOKEN,
} from '@/entities/flashcard/lib/clientRenderer'
