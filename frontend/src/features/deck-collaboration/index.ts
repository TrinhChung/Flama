import { lazy } from 'react'

export { BaseOverrideComparisonView } from './components/BaseOverrideComparisonView'
export { DiffWorkspace } from './components/DiffWorkspace'
export { useReleaseBuilder } from './hooks/useReleaseBuilder'
export { useInstalledDeckContentModel } from './hooks/useInstalledDeckContentModel'

// Preserve route-level lazy loading as pages migrate out of legacy locations.
export const InstalledDeckUpdateLegacyPage = lazy(() => import('./pages/InstalledDeckUpdatePage').then((module) => ({ default: module.InstalledDeckUpdatePage })))
export const DeckChangeRequestPage = lazy(() => import('./pages/DeckChangeRequestPage').then((module) => ({ default: module.DeckChangeRequestPage })))
export const ChangeRequestInboxPage = lazy(() => import('./pages/ChangeRequestInboxPage').then((module) => ({ default: module.ChangeRequestInboxPage })))
export const ChangeRequestDetailPage = lazy(() => import('./pages/ChangeRequestDetailPage').then((module) => ({ default: module.ChangeRequestDetailPage })))
