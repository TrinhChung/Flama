import '@/shared/config/i18n'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { CardDisplay } from './CardDisplay'
import { adaptStudySessionToRenderPayload } from '../renderer/studyRendererAdapter'
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
  const { t } = useTranslation('study')

  const rendered = useMemo(() => {
    try {
      return {
        front: adaptStudySessionToRenderPayload(template, content, 'front'),
        back: adaptStudySessionToRenderPayload(template, content, 'back'),
        error: null,
      }
    } catch (error) {
      return {
        front: null,
        back: null,
        error: error instanceof Error ? error.message : t('renderer.render_error'),
      }
    }
  }, [template, content, t])

  if (rendered.error || !rendered.front || !rendered.back) {
    return (
      <div className="p-6 text-center text-sm text-destructive" role="alert">
        {rendered.error || t('renderer.render_error')}
      </div>
    )
  }

  return (
    <CardDisplay
      cardId={cardId}
      noteId={noteId}
      side={revealed ? 'back' : 'front'}
      frontPayload={rendered.front}
      backPayload={rendered.back}
      scope="deck"
      scopeId={scopeId}
      fieldDefs={template.field_defs}
      fieldValues={content.field_values}
    />
  )
}
