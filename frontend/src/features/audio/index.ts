import { lazy } from 'react'
export { LocalAudioDialog } from './components/LocalAudioDialog'
export const DeckAudioGeneratorPage = lazy(() => import('./pages/DeckAudioGeneratorPage').then((module) => ({ default: module.DeckAudioGeneratorPage })))
