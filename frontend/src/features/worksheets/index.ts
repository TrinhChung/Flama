import { lazy } from 'react'
// Public API of the worksheets slice. The eager studio stays out of this barrel
// so every consumer remains code-split behind `LazyDeckWorksheetModal`.
export type * from './types'
export type { DeckWorksheetModalProps } from './components/DeckWorksheetModal'
export type { WizardStepId } from './config/wizardSteps'
export { LazyDeckWorksheetModal } from './components/LazyDeckWorksheetModal'
export const WorksheetsPage = lazy(() => import('./pages/WorksheetsPage').then((module) => ({ default: module.WorksheetsPage })))
