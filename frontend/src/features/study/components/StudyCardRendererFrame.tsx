import { useMemo } from 'react'
import { CardRendererFrame } from './CardRendererFrame'
import { renderStudySide } from '../renderer/clientRenderer'
import type {
  StudyContentArtifact,
  StudyTemplateArtifact,
} from '../types'

type StudyCardRendererFrameProps = {
  cardId: string
  noteId?: string | null
  revealed: boolean
  template: StudyTemplateArtifact
  content: StudyContentArtifact
  scopeId?: string | null
}

export function StudyCardRendererFrame({
  cardId,
  noteId,
  revealed,
  template,
  content,
  scopeId,
}: StudyCardRendererFrameProps) {
  const rendered = useMemo(() => {
    try {
      return {
        front: renderStudySide(template, content, 'front'),
        back: renderStudySide(template, content, 'back'),
        error: null,
      }
    } catch (error) {
      return {
        front: null,
        back: null,
        error: error instanceof Error ? error.message : 'Không thể render thẻ.',
      }
    }
  }, [template, content])

  if (rendered.error || !rendered.front || !rendered.back) {
    return (
      <div className="p-6 text-center text-sm text-destructive" role="alert">
        {rendered.error || 'Không thể render thẻ.'}
      </div>
    )
  }

  return (
    <CardRendererFrame
      cardId={cardId}
      noteId={noteId}
      revealed={revealed}
      frontPayload={rendered.front}
      backPayload={rendered.back}
      scope="deck"
      scopeId={scopeId}
      fieldDefs={template.field_defs}
      fieldValues={content.field_values}
    />
  )
}
