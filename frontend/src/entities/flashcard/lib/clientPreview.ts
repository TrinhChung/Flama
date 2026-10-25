import { renderCardSide } from './clientRenderer'
import type { CardRenderContent, CardRenderTemplate } from '../model/types'

/** REST keeps legacy HTML, while modern preview callers render Study artifacts. */
export function withStudyClientPreview<T extends { study_preview?: unknown }>(response: T): T {
  if (!response.study_preview) return response
  const envelope = response.study_preview as {
    preview?: { template_artifact: CardRenderTemplate; content_artifact: CardRenderContent } | null
    diagnostics?: Array<{ severity: string; message: string }>
  }
  if (!envelope.preview) {
    const message = envelope.diagnostics?.filter((d) => d.severity === 'error').map((d) => d.message).join(' ')
    throw new Error(message || 'Template preview could not compile for Study.')
  }
  const { template_artifact: template, content_artifact: content } = envelope.preview
  return { ...response,
    front_renderer_payload: renderCardSide(template, content, 'front'),
    back_renderer_payload: renderCardSide(template, content, 'back'),
  }
}
