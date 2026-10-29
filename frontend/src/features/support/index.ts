import { lazy } from 'react'
export const FeedbackPage = lazy(() => import('./pages/FeedbackPage').then((module) => ({ default: module.FeedbackPage })))
export const UserTicketDetailPage = lazy(() => import('./pages/UserTicketDetailPage').then((module) => ({ default: module.UserTicketDetailPage })))
