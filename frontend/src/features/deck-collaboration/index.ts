import { lazy } from 'react'

export { BaseOverrideComparisonView } from './components/BaseOverrideComparisonView'
export { DiffWorkspace } from './components/DiffWorkspace'
export { useReleaseBuilder } from './hooks/useReleaseBuilder'
export { useInstalledDeckContentModel } from './hooks/useInstalledDeckContentModel'
export const DeckContributionForm = lazy(() => import('./components/DeckContributionForm').then((module) => ({ default: module.DeckContributionForm })))
export const ChangeRequestDetailView = lazy(() => import('./components/ChangeRequestDetailView').then((module) => ({ default: module.ChangeRequestDetailView })))

// Preserve route-level lazy loading as pages migrate out of legacy locations.
export const InstalledDeckUpdateLegacyPage = lazy(() => import('./pages/InstalledDeckUpdatePage').then((module) => ({ default: module.InstalledDeckUpdatePage })))
export const ChangeRequestInboxPage = lazy(() => import('./pages/ChangeRequestInboxPage').then((module) => ({ default: module.ChangeRequestInboxPage })))
