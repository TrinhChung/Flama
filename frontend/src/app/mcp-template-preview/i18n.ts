/** The MCP resource cannot fetch locale chunks from the web application's origin. */
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import common from '@/shared/config/i18n/locales/en/common.json'
import shell from '@/shared/config/i18n/locales/en/shell.json'

void i18n.use(initReactI18next).init({ resources: { en: { common, shell } }, lng: 'en',
  fallbackLng: 'en', defaultNS: 'common', ns: ['common', 'shell'], initAsync: false,
  interpolation: { escapeValue: false }, react: { useSuspense: false } })

export default i18n
