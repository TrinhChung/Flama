import type { SupportedLocale } from './constants'
import type { I18nResources } from './types'

// Imported only in test mode. Production must never include this eager glob.
const dictionaries = import.meta.glob('./locales/*/*.json', { eager: true, import: 'default' })

export const resources = { vi: {}, en: {} } as Record<SupportedLocale, I18nResources & ResourceLanguage>
for (const [path, dictionary] of Object.entries(dictionaries)) {
  const match = path.match(/\/locales\/(vi|en)\/([^/]+)\.json$/)
  if (!match) continue
  const locale = match[1] as SupportedLocale
  const namespace = match[2] as keyof I18nResources
  ;(resources[locale] as Record<string, unknown>)[namespace] = dictionary
}
import type { ResourceLanguage } from 'i18next'
