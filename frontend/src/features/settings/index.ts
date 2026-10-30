import { lazy } from 'react'
export const StudyGoalsPage = lazy(() => import('./pages/StudyGoalsPage').then((module) => ({ default: module.StudyGoalsPage })))
export const McpTokensPage = lazy(() => import('./pages/McpTokensPage').then((module) => ({ default: module.McpTokensPage })))
export const YomitanTokensPage = lazy(() => import('./pages/YomitanTokensPage').then((module) => ({ default: module.YomitanTokensPage })))
export const AsbplayerTokensPage = lazy(() => import('./pages/AsbplayerTokensPage').then((module) => ({ default: module.AsbplayerTokensPage })))
