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
import type marketplace from './locales/vi/marketplace.json'
import type library from './locales/vi/library.json'
import type imports from './locales/vi/import.json'
import type settings from './locales/vi/settings.json'
import type note_types from './locales/vi/note_types.json'
import type collaboration from './locales/vi/collaboration.json'
import type orders from './locales/vi/orders.json'
import type support from './locales/vi/support.json'
import type worksheets from './locales/vi/worksheets.json'

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
  marketplace: typeof marketplace
  library: typeof library
  import: typeof imports
  settings: typeof settings
  note_types: typeof note_types
  collaboration: typeof collaboration
  orders: typeof orders
  support: typeof support
  worksheets: typeof worksheets
}

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common'
    resources: I18nResources
  }
}
