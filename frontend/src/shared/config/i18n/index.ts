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

import enCommon from './locales/en/common.json'
import enShell from './locales/en/shell.json'
import enAuth from './locales/en/auth.json'
import enLanding from './locales/en/landing.json'
import enDashboard from './locales/en/dashboard.json'
import enLegal from './locales/en/legal.json'
import enMcp from './locales/en/mcp.json'

export const resources = {
  vi: {
    common: viCommon,
    shell: viShell,
    auth: viAuth,
    landing: viLanding,
    dashboard: viDashboard,
    legal: viLegal,
    mcp: viMcp,
  },
  en: {
    common: enCommon,
    shell: enShell,
    auth: enAuth,
    landing: enLanding,
    dashboard: enDashboard,
    legal: enLegal,
    mcp: enMcp,
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
    ns: ['common', 'shell', 'auth', 'landing', 'dashboard', 'legal', 'mcp'],
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
