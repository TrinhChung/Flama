import { lazy } from 'react'
export { useTaxonomySchema } from './hooks/useTaxonomySchema'
export { NOTE_TYPE_CATEGORY_PRESETS, TAXONOMY_DIFFICULTIES, getDefaultGoalsForSubject, getDefaultTopicsForSubject } from './utils/publishTaxonomyConstants'
export { PublishNoteTypeSelector } from './components/PublishNoteTypeSelector'
export { SharedNoteTypeSidebar } from './components/notetype-detail/SharedNoteTypeSidebar'
export { SharedNoteTypeReviews } from './components/notetype-detail/SharedNoteTypeReviews'

export const SharedDeckDetailView = lazy(() => import('./ui/SharedDeckDetailView').then((module) => ({ default: module.SharedDeckDetailView })))
export const SharedDecksPage = lazy(() => import('./pages/MarketplacePages').then((module) => ({ default: module.SharedDecksPage })))
export const SharedNoteTypesPage = lazy(() => import('./pages/MarketplacePages').then((module) => ({ default: module.SharedNoteTypesPage })))
export const PaymentResultPage = lazy(() => import('./pages/MarketplacePages').then((module) => ({ default: module.PaymentResultPage })))
export const MarketplacePublishDeckPage = lazy(() => import('./pages/MarketplacePublishDeckPage').then((module) => ({ default: module.MarketplacePublishDeckPage })))
