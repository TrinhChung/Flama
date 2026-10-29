import { lazy } from 'react'
export const AnkiSyncPage = lazy(() => import('./pages/AnkiSyncPage').then((module) => ({ default: module.AnkiSyncPage })))
export const FileImportPage = lazy(() => import('./pages/FileImportPage').then((module) => ({ default: module.FileImportPage })))
