// @vitest-environment jsdom

import { act, Suspense } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { createInstance, type i18n } from 'i18next'
import { initReactI18next, useTranslation } from 'react-i18next'
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest'
import { createLocaleBackend } from './resourceLoader'
import { changeLanguageSafely, guardNamespaceReadiness, requireTranslationBundles, TranslationLoadError } from './loadGuard'
import { TranslationLoadBoundary } from './TranslationLoadBoundary'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

type Dictionary = Record<string, unknown>
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function importers() {
  return {
    './locales/vi/common.json': vi.fn(async () => ({ default: { save: 'Lưu' } })),
    './locales/en/common.json': vi.fn(async () => ({ default: { save: 'Save' } })),
    './locales/vi/shell.json': vi.fn(async () => ({ default: { title: 'Ứng dụng' } })),
    './locales/en/shell.json': vi.fn(async () => ({ default: { title: 'Application' } })),
    './locales/vi/browse.json': vi.fn(async () => ({ default: { card_table: { status: { new: 'Mới' } } } })),
    './locales/en/browse.json': vi.fn(async () => ({ default: { card_table: { status: { new: 'New' } } } })),
    './locales/vi/audio.json': vi.fn(async () => ({ default: {} })),
    './locales/en/audio.json': vi.fn(async () => ({ default: {} })),
  }
}

async function initialize(loaders: ReturnType<typeof importers>, locale = 'vi') {
  const instance = createInstance().use(createLocaleBackend(loaders)).use(initReactI18next)
  await instance.init({ lng: locale, fallbackLng: 'vi', ns: ['common', 'shell'], defaultNS: 'common', react: { useSuspense: true } })
  return instance
}

describe('production locale delivery', () => {
  let root: Root | undefined
  let container: HTMLDivElement | undefined
  afterEach(async () => {
    if (root) await act(async () => root?.unmount())
    container?.remove()
    root = undefined
    container = undefined
  })
  afterAll(() => vi.unstubAllEnvs())

  it('initializes the real production configuration with only shell and common dictionaries', async () => {
    vi.stubEnv('MODE', 'production')
    const module = await import('./index')
    await module.i18nReady
    expect(module.default.options.ns).toEqual(['common', 'shell'])
    expect(module.default.hasResourceBundle('vi', 'common')).toBe(true)
    expect(module.default.hasResourceBundle('vi', 'shell')).toBe(true)
    expect(module.default.hasResourceBundle('vi', 'browse')).toBe(false)
    expect(module.default.hasResourceBundle('en', 'common')).toBe(false)
    await module.default.loadNamespaces(['browse', 'onboarding'])
    expect(module.default.t('browse:card_table.status.new')).toBe('Mới')
    expect(module.default.hasResourceBundle('vi', 'onboarding')).toBe(true)
    expect(module.default.hasResourceBundle('vi', 'audio')).toBe(false)
    await module.default.changeLanguage('en')
    const { SUBJECT_OPTIONS } = await import('@/features/onboarding/constants')
    expect(SUBJECT_OPTIONS[0].title).toBe(module.default.getResource('en', 'onboarding', 'subjects.japanese.title'))
    expect(SUBJECT_OPTIONS[0].title).not.toBe('Tiếng Nhật')
    vi.unstubAllEnvs()
  })

  it('loads only requested namespaces and the Vietnamese fallback for English', async () => {
    const loaders = importers()
    const instance = await initialize(loaders, 'en')
    expect(instance.t('save')).toBe('Save')
    expect(loaders['./locales/en/common.json']).toHaveBeenCalledTimes(1)
    expect(loaders['./locales/vi/common.json']).toHaveBeenCalledTimes(1)
    expect(loaders['./locales/en/browse.json']).not.toHaveBeenCalled()
    expect(loaders['./locales/en/audio.json']).not.toHaveBeenCalled()
    await Promise.all([instance.loadNamespaces('browse'), instance.loadNamespaces('browse')])
    expect(instance.t('browse:card_table.status.new')).toBe('New')
    expect(loaders['./locales/en/browse.json']).toHaveBeenCalledTimes(1)
    expect(loaders['./locales/vi/browse.json']).toHaveBeenCalledTimes(1)
    expect(loaders['./locales/en/audio.json']).not.toHaveBeenCalled()
  })

  it('keeps the old language visible until every requested target namespace has loaded', async () => {
    const loaders = importers()
    const pending = deferred<{ default: Dictionary }>()
    loaders['./locales/en/browse.json'].mockImplementation(() => pending.promise as ReturnType<typeof loaders['./locales/en/browse.json']>)
    const instance = await initialize(loaders)
    await instance.loadNamespaces('browse')
    const languageChanged = vi.fn(() => instance.t('browse:card_table.status.new'))
    instance.on('languageChanged', languageChanged)
    const switching = instance.changeLanguage('en')
    await Promise.resolve()
    expect(instance.language).toBe('vi')
    expect(instance.t('browse:card_table.status.new')).toBe('Mới')
    expect(languageChanged).not.toHaveBeenCalled()
    pending.resolve({ default: { card_table: { status: { new: 'New' } } } })
    await switching
    expect(instance.language).toBe('en')
    expect(languageChanged.mock.results[0]?.value).toBe('New')
  })

  it('shows the existing loading fallback instead of translation keys on a cold namespace', async () => {
    const loaders = importers()
    const pending = deferred<{ default: Dictionary }>()
    loaders['./locales/vi/browse.json'].mockImplementation(() => pending.promise as ReturnType<typeof loaders['./locales/vi/browse.json']>)
    const instance = await initialize(loaders)
    function ColdPage({ language }: { language: i18n }) {
      const { t } = useTranslation('browse', { i18n: language })
      return <span>{t('card_table.status.new')}</span>
    }
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(<Suspense fallback={<span>Loading page</span>}><ColdPage language={instance} /></Suspense>)
    })
    expect(container.textContent).toBe('Loading page')
    await act(async () => { pending.resolve({ default: { card_table: { status: { new: 'Mới' } } } }) })
    expect(container.textContent).toBe('Mới')
  })

  it('uses Vietnamese when a requested English dictionary cannot be downloaded', async () => {
    const loaders = importers()
    loaders['./locales/en/browse.json'].mockRejectedValue(new Error('chunk unavailable'))
    const instance = await initialize(loaders, 'en')
    await instance.loadNamespaces('browse')
    expect(instance.t('browse:card_table.status.new')).toBe('Mới')
  })

  it('rejects startup readiness when both locale and fallback shell bundles fail', async () => {
    const loaders = importers()
    loaders['./locales/en/shell.json'].mockRejectedValue(new Error('offline'))
    loaders['./locales/vi/shell.json'].mockRejectedValue(new Error('offline'))
    const instance = await initialize(loaders, 'en')
    expect(() => requireTranslationBundles(instance, ['common', 'shell'])).toThrow(TranslationLoadError)
  })

  it('shows a retry state when both route dictionaries fail instead of rendering keys', async () => {
    const loaders = importers()
    loaders['./locales/en/browse.json'].mockRejectedValue(new Error('offline'))
    loaders['./locales/vi/browse.json'].mockRejectedValue(new Error('offline'))
    const instance = await initialize(loaders, 'en')
    await instance.loadNamespaces('browse')
    guardNamespaceReadiness(instance)
    function FailedPage() {
      const { t } = useTranslation('browse', { i18n: instance })
      return <span>{t('card_table.status.new')}</span>
    }
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      await act(async () => root?.render(<TranslationLoadBoundary><Suspense fallback="Loading"><FailedPage /></Suspense></TranslationLoadBoundary>))
      expect(container.querySelector('[role="alert"]')).toBeTruthy()
      expect(container.textContent).toContain('Thử lại / Retry')
      expect(container.textContent).not.toContain('card_table.status.new')
    } finally { errors.mockRestore() }
  })

  it('preserves the old language and dictionaries when switching downloads fail', async () => {
    const loaders = importers()
    const instance = await initialize(loaders)
    await instance.loadNamespaces('browse')
    loaders['./locales/en/browse.json'].mockRejectedValue(new Error('offline'))
    const changed = vi.fn()
    instance.on('languageChanged', changed)
    await expect(changeLanguageSafely(instance, 'en')).rejects.toBeInstanceOf(TranslationLoadError)
    expect(instance.language).toBe('vi')
    expect(instance.t('browse:card_table.status.new')).toBe('Mới')
    expect(changed).not.toHaveBeenCalled()
  })

  it('retries a failed target dictionary when the connection recovers', async () => {
    const loaders = importers()
    const instance = await initialize(loaders)
    await instance.loadNamespaces('browse')
    loaders['./locales/en/browse.json'].mockRejectedValueOnce(new Error('offline'))
    await expect(changeLanguageSafely(instance, 'en')).rejects.toBeInstanceOf(TranslationLoadError)
    expect(instance.language).toBe('vi')
    await changeLanguageSafely(instance, 'en')
    expect(instance.language).toBe('en')
    expect(instance.t('browse:card_table.status.new')).toBe('New')
    expect(loaders['./locales/en/browse.json']).toHaveBeenCalledTimes(2)
  })
})
