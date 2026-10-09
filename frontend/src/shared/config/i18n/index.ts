import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { DEFAULT_LOCALE, STORAGE_KEY, SUPPORTED_LOCALES, type SupportedLocale } from './constants'
import './types'

import viCommon from './locales/vi/common.json'
import viShell from './locales/vi/shell.json'
import viAuth from './locales/vi/auth.json'
import viLanding from './locales/vi/landing.json'
import viDashboard from './locales/vi/dashboard.json'
import viLegal from './locales/vi/legal.json'
import viMcp from './locales/vi/mcp.json'
import viStudy from './locales/vi/study.json'
import viBrowse from './locales/vi/browse.json'
import viStatistics from './locales/vi/statistics.json'
import viMarketplace from './locales/vi/marketplace.json'
import viLibrary from './locales/vi/library.json'
import viImport from './locales/vi/import.json'
import viSettings from './locales/vi/settings.json'
import viNoteTypes from './locales/vi/note_types.json'
import viCollaboration from './locales/vi/collaboration.json'
import viOrders from './locales/vi/orders.json'
import viSupport from './locales/vi/support.json'
import viWorksheets from './locales/vi/worksheets.json'
import viProfile from './locales/vi/profile.json'
import viWallet from './locales/vi/wallet.json'
import viCardTemplates from './locales/vi/card_templates.json'
import viTemplateMapping from './locales/vi/template_mapping.json'
import viAudio from './locales/vi/audio.json'
import viGuide from './locales/vi/guide.json'
import viOnboarding from './locales/vi/onboarding.json'

import enCommon from './locales/en/common.json'
import enShell from './locales/en/shell.json'
import enAuth from './locales/en/auth.json'
import enLanding from './locales/en/landing.json'
import enDashboard from './locales/en/dashboard.json'
import enLegal from './locales/en/legal.json'
import enMcp from './locales/en/mcp.json'
import enStudy from './locales/en/study.json'
import enBrowse from './locales/en/browse.json'
import enStatistics from './locales/en/statistics.json'
import enMarketplace from './locales/en/marketplace.json'
import enLibrary from './locales/en/library.json'
import enImport from './locales/en/import.json'
import enSettings from './locales/en/settings.json'
import enNoteTypes from './locales/en/note_types.json'
import enCollaboration from './locales/en/collaboration.json'
import enOrders from './locales/en/orders.json'
import enSupport from './locales/en/support.json'
import enWorksheets from './locales/en/worksheets.json'
import enProfile from './locales/en/profile.json'
import enWallet from './locales/en/wallet.json'
import enCardTemplates from './locales/en/card_templates.json'
import enTemplateMapping from './locales/en/template_mapping.json'
import enAudio from './locales/en/audio.json'
import enGuide from './locales/en/guide.json'
import enOnboarding from './locales/en/onboarding.json'

export const resources = {
  vi: {
    common: viCommon,
    shell: viShell,
    auth: viAuth,
    landing: viLanding,
    dashboard: viDashboard,
    legal: viLegal,
    mcp: viMcp,
    study: viStudy,
    browse: viBrowse,
    statistics: viStatistics,
    marketplace: viMarketplace,
    library: viLibrary,
    import: viImport,
    settings: viSettings,
    note_types: viNoteTypes,
    collaboration: viCollaboration,
    orders: viOrders,
    support: viSupport,
    worksheets: viWorksheets,
    profile: viProfile,
    wallet: viWallet,
    card_templates: viCardTemplates,
    template_mapping: viTemplateMapping,
    audio: viAudio,
    guide: viGuide,
    onboarding: viOnboarding,
  },
  en: {
    common: enCommon,
    shell: enShell,
    auth: enAuth,
    landing: enLanding,
    dashboard: enDashboard,
    legal: enLegal,
    mcp: enMcp,
    study: enStudy,
    browse: enBrowse,
    statistics: enStatistics,
    marketplace: enMarketplace,
    library: enLibrary,
    import: enImport,
    settings: enSettings,
    note_types: enNoteTypes,
    collaboration: enCollaboration,
    orders: enOrders,
    support: enSupport,
    worksheets: enWorksheets,
    profile: enProfile,
    wallet: enWallet,
    card_templates: enCardTemplates,
    template_mapping: enTemplateMapping,
    audio: enAudio,
    guide: enGuide,
    onboarding: enOnboarding,
  },
} as const

const getInitialLocale = (): SupportedLocale => {
  if (typeof window !== 'undefined') {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved && (SUPPORTED_LOCALES as readonly string[]).includes(saved)) {
        return saved as SupportedLocale
      }
    } catch {
      // localStorage may fail in restricted environments
    }
  }
  return DEFAULT_LOCALE
}

const initialLang = getInitialLocale()

void i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: initialLang,
    fallbackLng: DEFAULT_LOCALE,
    ns: [
      'common',
      'shell',
      'auth',
      'landing',
      'dashboard',
      'legal',
      'mcp',
      'study',
      'browse',
      'statistics',
      'marketplace',
      'library',
      'import',
      'settings',
      'note_types',
      'collaboration',
      'orders',
      'support',
      'worksheets',
      'profile',
      'wallet',
      'card_templates',
      'template_mapping',
      'audio',
      'guide',
      'onboarding',
    ],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
  })

if (typeof window !== 'undefined') {
  document.documentElement.lang = initialLang
  i18n.on('languageChanged', (lng) => {
    try {
      localStorage.setItem(STORAGE_KEY, lng)
    } catch {
      // ignore
    }
    document.documentElement.lang = lng
  })
}

export default i18n
export { DEFAULT_LOCALE, STORAGE_KEY, SUPPORTED_LOCALES }
export type { SupportedLocale }
