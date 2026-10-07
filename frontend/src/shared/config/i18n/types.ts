import type common from './locales/vi/common.json'
import type shell from './locales/vi/shell.json'
import type auth from './locales/vi/auth.json'
import type landing from './locales/vi/landing.json'
import type dashboard from './locales/vi/dashboard.json'
import type legal from './locales/vi/legal.json'
import type mcp from './locales/vi/mcp.json'
import type study from './locales/vi/study.json'
import type browse from './locales/vi/browse.json'
import type statistics from './locales/vi/statistics.json'

export interface I18nResources {
  common: typeof common
  shell: typeof shell
  auth: typeof auth
  landing: typeof landing
  dashboard: typeof dashboard
  legal: typeof legal
  mcp: typeof mcp
  study: typeof study
  browse: typeof browse
  statistics: typeof statistics
}

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common'
    resources: I18nResources
  }
}
