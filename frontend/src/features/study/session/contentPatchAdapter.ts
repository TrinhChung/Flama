/**
 * frontend/src/features/study/session/contentPatchAdapter.ts
 * Pure card content patch adapter for study sessions.
 * Deduplicates logic between useStudySession (updateCardContent) and sessionStore (updateCardFieldValuesInSessions).
 */
import type { PersistedStudySession } from './sessionStore'
import type { StudyMediaArtifact, StudyTemplateArtifact } from '../types'
import { patchRenderContext } from '../renderer/clientRenderer'
import { canonicalDigest } from './canonicalDigest'

export interface ContentPatchOptions {
  noteId?: string | null
  media?: StudyMediaArtifact[]
}

export interface ContentPatchResult {
  updated: boolean
  nextSession: PersistedStudySession
  affectedCardIds: string[]
}

function projectedFieldUpdates(
  values: Record<string, unknown>,
  template: StudyTemplateArtifact | undefined,
): Record<string, unknown> {
  const projection = template?.binding_projection
  if (!projection) return values
  const updates = { ...values }
  const fieldsById = new Map(projection.field_defs.map((field) => [field.id, field]))
  for (const key of Object.keys(projection.input_bindings)) {
    delete updates[key]
    delete updates[`${key}_url`]
    delete updates[`${key}_urls`]
  }
  for (const [key, fieldId] of Object.entries(projection.input_bindings)) {
    const source = fieldId === null ? undefined : fieldsById.get(fieldId)
    if (!source) updates[key] = ''
    else if (Object.hasOwn(values, source.name)) updates[key] = values[source.name]
  }
  return updates
}

/**
 * Pure function that applies updated field values and synthesized media to a study session.
 * Does not mutate the input session object.
 */
export function applyCardContentPatch(
  current: PersistedStudySession,
  cardId: string,
  newFieldValues: Record<string, unknown>,
  options?: ContentPatchOptions,
): ContentPatchResult {
  const targetCards = current.snapshot.cards.filter(
    (c) => c.card_id === cardId || (options?.noteId && c.note_id === options.noteId),
  )
  if (targetCards.length === 0) {
    return { updated: false, nextSession: current, affectedCardIds: [] }
  }

  const updatedContents = { ...current.snapshot.contents }
  const updatedCards = [...current.snapshot.cards]
  const affectedCardIds: string[] = []
  let hasChanges = false

  for (const card of targetCards) {
    const contentKey = card.content_key
    const template = current.snapshot.templates[card.template_key]
    const existingContent = updatedContents[contentKey]
    if (!existingContent) continue
    const projectedUpdates = projectedFieldUpdates(newFieldValues, template)

    // 1. Merge media assets
    const combinedMedia: StudyMediaArtifact[] =
      options?.media && options.media.length > 0
        ? [...options.media]
        : [...(existingContent.media || [])]

    // 2. Synthesize proxy URLs found in newFieldValues not yet in combinedMedia
    const existingProxyUrls = new Set(combinedMedia.map((m) => m.proxy_url))
    for (const [fieldName, val] of Object.entries(newFieldValues)) {
      if (typeof val === 'string') {
        const matches = val.match(/\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/g)
        if (matches) {
          for (const pUrl of matches) {
            if (!existingProxyUrls.has(pUrl)) {
              const assetId = pUrl.replace('/media/proxy/', '')
              const lk = fieldName.toLowerCase()
              const isAudio = lk.includes('audio') || lk.includes('sound') || lk.includes('voice')
              combinedMedia.push({
                id: assetId,
                field_name: fieldName,
                filename: `${assetId}`,
                mime_type: isAudio ? 'audio/mpeg' : 'image/jpeg',
                sha256: '',
                proxy_url: pUrl,
              })
              existingProxyUrls.add(pUrl)
            }
          }
        }
      }
    }

    // 3. Merge field values
    const mergedFieldValues = {
      ...existingContent.field_values,
      ...projectedUpdates,
    }

    // 4. Patch render context
    const nextRenderContext = patchRenderContext(
      existingContent.render_context || {},
      projectedUpdates,
      template?.field_defs,
      combinedMedia,
    )

    // 5. Compute canonical digest
    const nextVersion = canonicalDigest({
      schema_version: 'study-content.v1',
      renderer_abi: existingContent.renderer_abi,
      note_id: existingContent.note_id,
      ...(template?.binding_projection ? { field_defs: template.field_defs } : {}),
      field_values: mergedFieldValues,
      media: combinedMedia,
    })
    const newContentKey = `${existingContent.id}:${nextVersion}`

    updatedContents[newContentKey] = {
      ...existingContent,
      version: nextVersion,
      field_values: mergedFieldValues,
      render_context: nextRenderContext,
      media: combinedMedia,
    }

    for (let i = 0; i < updatedCards.length; i++) {
      if (updatedCards[i].card_id === card.card_id) {
        updatedCards[i] = {
          ...updatedCards[i],
          content_key: newContentKey,
        }
        affectedCardIds.push(card.card_id)
      }
    }
    hasChanges = true
  }

  if (!hasChanges) {
    return { updated: false, nextSession: current, affectedCardIds: [] }
  }

  const nextSession: PersistedStudySession = {
    ...current,
    snapshot: {
      ...current.snapshot,
      cards: updatedCards,
      contents: updatedContents,
    },
    updated_at_ms: Date.now(),
  }

  return { updated: true, nextSession, affectedCardIds }
}
