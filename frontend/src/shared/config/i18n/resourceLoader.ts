import type { BackendModule } from 'i18next'

type Dictionary = Record<string, unknown>
type LocaleImporters = Record<string, () => Promise<{ default: Dictionary }>>

const localeImporters = import.meta.glob<{ default: Dictionary }>('./locales/*/*.json')

/** Bundled locale chunks use Vite's hashed URLs; no runtime locale API is needed. */
export function createLocaleBackend(importers: LocaleImporters = localeImporters): BackendModule {
  const pending = new Map<string, Promise<Dictionary>>()
  return {
    type: 'backend',
    init() {},
    read(language, namespace, callback) {
      const path = `./locales/${language}/${namespace}.json`
      const importer = importers[path]
      if (!importer) {
        callback(null, {})
        return
      }
      let request = pending.get(path)
      if (!request) {
        request = importer().then((module) => module.default)
        pending.set(path, request)
        void request.catch(() => pending.delete(path))
      }
      void request.then(
        (dictionary) => callback(null, dictionary),
        (error: unknown) => callback(error instanceof Error ? error : new Error(String(error)), false),
      )
    },
  }
}
