import { lazy } from 'react'
export const WalletPage = lazy(() => import('./pages/WalletPage').then((module) => ({ default: module.WalletPage })))
