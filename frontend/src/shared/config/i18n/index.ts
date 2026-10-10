import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { DEFAULT_LOCALE, STORAGE_KEY, SUPPORTED_LOCALES, type SupportedLocale } from './constants'
import { createLocaleBackend } from './resourceLoader'
import { guardNamespaceReadiness, requireTranslationBundles } from './loadGuard'
import './types'

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
// Existing component and validation tests can read dictionaries synchronously.
// Vite removes this entire branch, including its import, from production builds.
const testResources = import.meta.env.MODE === 'test'
  ? (await import('./testResources')).resources
  : undefined

export const i18nReady = i18n
  .use(createLocaleBackend())
  .use(initReactI18next)
  .init({
    ...(testResources ? { resources: testResources } : {}),
    lng: initialLang,
    fallbackLng: DEFAULT_LOCALE,
    load: 'languageOnly',
    ns: testResources ? Object.keys(testResources.vi) : ['common', 'shell'],
    defaultNS: 'common',
    initAsync: false,
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: true,
    },
  }).then((translate) => {
    requireTranslationBundles(i18n, ['common', 'shell'])
    guardNamespaceReadiness(i18n)
    return translate
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
