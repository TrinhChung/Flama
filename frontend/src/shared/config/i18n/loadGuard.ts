import type { i18n } from 'i18next'

export class TranslationLoadError extends Error {
  readonly namespaces: readonly string[]
  constructor(namespaces: readonly string[]) {
    super(`Translation bundles unavailable: ${namespaces.join(', ')}`)
    this.name = 'TranslationLoadError'
    this.namespaces = namespaces
  }
}

export function requireTranslationBundles(instance: i18n, namespaces: readonly string[], language = instance.language, allowFallback = true) {
  const languages = allowFallback ? [language, 'vi'] : [language]
  const missing = namespaces.filter(namespace => !languages.some(locale => instance.hasResourceBundle(locale, namespace)))
  if (missing.length) throw new TranslationLoadError(missing)
}

/** i18next treats exhausted backend errors as loaded; React must not render keys. */
export function guardNamespaceReadiness(instance: i18n) {
  const original = instance.hasLoadedNamespace.bind(instance)
  instance.hasLoadedNamespace = (namespace, options) => {
    const ready = original(namespace, options)
    const language = typeof options?.lng === 'string' ? options.lng : options?.lng?.[0] ?? instance.language
    if (ready) {
      requireTranslationBundles(instance, typeof namespace === 'string' ? [namespace] : namespace, language)
    }
    return ready
  }
}

export async function loadRequiredNamespaces(instance: i18n, namespaces: string[]) {
  await instance.loadNamespaces(namespaces)
  requireTranslationBundles(instance, namespaces)
}

/** Download before languageChanged so a failed switch leaves the current UI intact. */
export async function changeLanguageSafely(instance: i18n, language: string) {
  const configured = instance.options.ns
  const namespaces = typeof configured === 'string' ? [configured] : configured ?? ['common']
  const missing = namespaces.filter(namespace => !instance.hasResourceBundle(language, namespace))
  // i18next refuses even reloadResources for permanently failed (-1) reads.
  // Reset only exhausted target entries on an explicit retry; keep pending reads.
  const connector = instance.services.backendConnector as { state?: Record<string, number> } | undefined
  for (const namespace of missing) {
    const key = `${language}|${namespace}`
    if (connector?.state && connector.state[key] < 0) delete connector.state[key]
  }
  if (missing.length) await instance.reloadResources([language], missing)
  requireTranslationBundles(instance, namespaces, language, false)
  await instance.changeLanguage(language)
}
