import { GRAMMAR_PRACTICE_COPY, SENTENCE_WRITING_COPY } from '../../../config/writingExercises'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'
import { GenkouyoushiConfig } from './GenkouyoushiConfig'
import { WritingExerciseConfig } from './WritingExerciseConfig'

/** Layout controls for the free-writing templates: sentences, grammar and genkō yōshi. */
export function EssayWritingConfig({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
}: Pick<
  StudioLayoutTabProps,
  'currentTemplate' | 'layoutOptions' | 'setLayoutOptions'
>) {
  if (!currentTemplate) return null

  switch (currentTemplate.id) {
    case 'sentence_writing':
      return <WritingExerciseConfig copy={SENTENCE_WRITING_COPY} layoutOptions={layoutOptions} setLayoutOptions={setLayoutOptions} />
    case 'grammar_practice':
      return <WritingExerciseConfig copy={GRAMMAR_PRACTICE_COPY} layoutOptions={layoutOptions} setLayoutOptions={setLayoutOptions} />
    case 'genkouyoushi':
      return <GenkouyoushiConfig layoutOptions={layoutOptions} setLayoutOptions={setLayoutOptions} />
    default:
      return null
  }
}
