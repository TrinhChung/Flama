import { lazy } from 'react'
export const OAuthConsentPage = lazy(() => import('./pages/OAuthConsentPage').then((module) => ({ default: module.OAuthConsentPage })))
