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
    <div className="study-card-shell w-full h-full relative min-h-[240px]">
      <div
        className={revealed ? 'hidden' : 'block'}
        aria-hidden={revealed}
      >
        <CardRendererFrame
          cardId={cardId}
          noteId={noteId}
          revealed={false}
          active={!revealed}
          frontPayload={rendered.front}
          scope="deck"
          scopeId={scopeId}
          fieldDefs={template.field_defs}
          fieldValues={content.field_values}
          enableLivePatch
        />
      </div>
      <div
        className={revealed ? 'block' : 'hidden'}
        aria-hidden={!revealed}
      >
        <CardRendererFrame
          cardId={cardId}
          noteId={noteId}
          revealed
          active={revealed}
          backPayload={rendered.back}
          scope="deck"
          scopeId={scopeId}
          fieldDefs={template.field_defs}
          fieldValues={content.field_values}
          enableLivePatch
        />
      </div>
    </div>
  )
}
