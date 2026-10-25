/** Lightweight public rendering entry; avoids editor and locale bootstrapping. */
export { renderCardSide } from './lib/clientRenderer'
export { withStudyClientPreview } from './lib/clientPreview'
export { CardDisplay } from './ui/CardDisplay'
export { CardRendererFrame } from './ui/CardRendererFrame'
export type { CardRenderTemplate, CardRenderContent } from './model/types'
