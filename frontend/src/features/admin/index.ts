import { lazy } from 'react'
// Public API of the admin slice; route implementations stay lazily loaded.
export * from './api/analyticsApi'
export * from './api/quotasApi'
export type * from './types/analytics'
export * from './types/quotas'
export const AdminAnalyticsPage = lazy(() => import('./pages/AdminAnalyticsPage').then((module) => ({ default: module.AdminAnalyticsPage })))
export const AdminUsersPage = lazy(() => import('./pages/AdminUsersPage').then((module) => ({ default: module.AdminUsersPage })))
export const AdminPaymentsPage = lazy(() => import('./pages/AdminPaymentsPage').then((module) => ({ default: module.AdminPaymentsPage })))
export const AdminFeesPage = lazy(() => import('./pages/AdminFeesPage').then((module) => ({ default: module.AdminFeesPage })))
export const AdminQuotasPage = lazy(() => import('./pages/AdminQuotasPage').then((module) => ({ default: module.AdminQuotasPage })))
export const AdminTtsPage = lazy(() => import('./pages/AdminTtsPage').then((module) => ({ default: module.AdminTtsPage })))
export const AdminMcpTokensPage = lazy(() => import('./pages/AdminMcpTokensPage').then((module) => ({ default: module.AdminMcpTokensPage })))
export const AdminImageLibraryPage = lazy(() => import('./pages/AdminImageLibraryPage').then((module) => ({ default: module.AdminImageLibraryPage })))
export const AdminPermissionsPage = lazy(() => import('./pages/AdminPermissionsPage').then((module) => ({ default: module.AdminPermissionsPage })))
export const AdminSupportConfigPage = lazy(() => import('./pages/AdminSupportConfigPage').then((module) => ({ default: module.AdminSupportConfigPage })))
export const AdminTicketsPage = lazy(() => import('./pages/AdminTicketsPage').then((module) => ({ default: module.AdminTicketsPage })))
export const AdminTicketDetailPage = lazy(() => import('./pages/AdminTicketDetailPage').then((module) => ({ default: module.AdminTicketDetailPage })))
export const AdminTaxonomyPage = lazy(() => import('./pages/AdminTaxonomyPage').then((module) => ({ default: module.AdminTaxonomyPage })))
