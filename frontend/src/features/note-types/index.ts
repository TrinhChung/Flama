import { lazy } from 'react'
export { useNoteTypeManager } from './hooks/useNoteTypeManager'
export { CreateNoteTypeBar } from './components/manager/CreateNoteTypeBar'
export { NoteTypeCard } from './components/manager/NoteTypeCard'
export { getNoteTypeManagerTourSteps } from './components/manager/noteTypeManagerTourSteps'
export type { NoteTypeItem, NoteTypesResponse } from './model/managerTypes'
export type { MappingNoteType } from './hooks/useTemplateMappingDraft'
export { NoteTypeSetupShell } from './components/NoteTypeSetupShell'
export { useTemplateMappingWorkspace } from './hooks/useTemplateMappingWorkspace'
export { TemplateCoherenceBanner } from './components/TemplateCoherenceBanner'
export type { TemplateCoherenceBannerProps } from './components/TemplateCoherenceBanner'
export const NoteTypeFieldsPage = lazy(() => import('./pages/NoteTypeFieldsPage').then((module) => ({ default: module.NoteTypeFieldsPage })))
export const NoteTypeDetailPage = lazy(() => import('./pages/NoteTypeDetailPage').then((module) => ({ default: module.NoteTypeDetailPage })))
export const NoteTypeGuidePage = lazy(() => import('./pages/NoteTypeGuidePage').then((module) => ({ default: module.NoteTypeGuidePage })))
