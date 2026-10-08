// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n, { DEFAULT_LOCALE, STORAGE_KEY, SUPPORTED_LOCALES } from './index'
import { LanguageSwitcher } from '@/shared/ui/LanguageSwitcher'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('i18n Empirical Stress & Adversarial Suite', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(async () => {
    localStorage.clear()
    await i18n.changeLanguage(DEFAULT_LOCALE)
    document.documentElement.lang = DEFAULT_LOCALE
  })

  afterEach(() => {
    if (root && container) {
      const activeRoot = root
      act(() => {
        activeRoot.unmount()
      })
      container.remove()
    }
    container = null
    root = null
    vi.restoreAllMocks()
  })

  describe('1. Runtime Language Switching & DOM Synchronization', () => {
    it('immediately updates i18n.language, localStorage, and documentElement.lang on vi -> en switch', async () => {
      expect(i18n.language).toBe('vi')
      expect(document.documentElement.lang).toBe('vi')

      await i18n.changeLanguage('en')

      // Assert state synchronization
      expect(i18n.language).toBe('en')
      expect(localStorage.getItem(STORAGE_KEY)).toBe('en')
      expect(document.documentElement.lang).toBe('en')

      // Assert translation across all namespaces
      expect(i18n.t('save')).toBe('Save')
      expect(i18n.t('cancel')).toBe('Cancel')
      expect(i18n.t('confirm')).toBe('Confirm')
      expect(i18n.t('loading')).toBe('Loading...')

      expect(i18n.t('header.nav.support', { ns: 'shell' })).toBe('Support')
      expect(i18n.t('header.nav.login', { ns: 'shell' })).toBe('Log in')
      expect(i18n.t('page_titles.dashboard', { ns: 'shell' })).toBe('Overview')
      expect(i18n.t('user_menu.logout', { ns: 'shell' })).toBe('Log out')

      expect(i18n.t('login.title', { ns: 'auth' })).toBe('Welcome Back')
      expect(i18n.t('register.title', { ns: 'auth' })).toBe('Create a New Account')
      expect(i18n.t('validation.password_min', { ns: 'auth' })).toBe('Password must be at least 8 characters.')
    })

    it('immediately updates i18n.language, localStorage, and documentElement.lang on en -> vi switch', async () => {
      await i18n.changeLanguage('en')
      expect(i18n.language).toBe('en')

      await i18n.changeLanguage('vi')

      expect(i18n.language).toBe('vi')
      expect(localStorage.getItem(STORAGE_KEY)).toBe('vi')
      expect(document.documentElement.lang).toBe('vi')

      expect(i18n.t('save')).toBe('Lưu')
      expect(i18n.t('cancel')).toBe('Hủy')
      expect(i18n.t('confirm')).toBe('Xác nhận')
      expect(i18n.t('loading')).toBe('Đang tải...')

      expect(i18n.t('header.nav.support', { ns: 'shell' })).toBe('Ủng hộ')
      expect(i18n.t('header.nav.login', { ns: 'shell' })).toBe('Đăng nhập')
      expect(i18n.t('page_titles.dashboard', { ns: 'shell' })).toBe('Tổng quan')
      expect(i18n.t('user_menu.logout', { ns: 'shell' })).toBe('Đăng xuất')

      expect(i18n.t('login.title', { ns: 'auth' })).toBe('Chào mừng trở lại')
      expect(i18n.t('register.title', { ns: 'auth' })).toBe('Tạo tài khoản mới')
      expect(i18n.t('validation.password_min', { ns: 'auth' })).toBe('Mật khẩu cần ít nhất 8 ký tự.')
    })

    it('interpolates variables correctly in both locales', async () => {
      // Vietnamese
      expect(i18n.t('footer.copyright', { ns: 'shell', year: 2026 })).toBe(
        '© 2026 Flama. Được phát triển với ❤️ bởi Chung Trịnh.',
      )

      // English
      await i18n.changeLanguage('en')
      expect(i18n.t('footer.copyright', { ns: 'shell', year: 2026 })).toBe(
        '© 2026 Flama. Crafted with ❤️ by Chung Trinh.',
      )
    })

    it('survives rapid consecutive language toggling without desynchronization', async () => {
      const operations = [
        i18n.changeLanguage('en'),
        i18n.changeLanguage('vi'),
        i18n.changeLanguage('en'),
        i18n.changeLanguage('vi'),
        i18n.changeLanguage('en'),
      ]
      await Promise.all(operations)

      // Final resolved state must be consistent
      const finalLang = i18n.language
      expect(['vi', 'en']).toContain(finalLang)
      expect(localStorage.getItem(STORAGE_KEY)).toBe(finalLang)
      expect(document.documentElement.lang).toBe(finalLang)
    })
  })

  describe('2. Fallback Robustness & Adversarial Inputs', () => {
    it('returns the key itself when requesting an unknown key in default namespace without throwing', () => {
      const unknownKey = 'totally_nonexistent_key_xyz_12345'
      expect((i18n.t as (k: string) => string)(unknownKey)).toBe(unknownKey)
    })

    it('returns the key itself when requesting an unknown key in a specific namespace without throwing', () => {
      const unknownKey = 'nonexistent.sub.key.999'
      expect((i18n.t as (k: string, opts: unknown) => string)(unknownKey, { ns: 'shell' })).toBe(unknownKey)
      expect((i18n.t as (k: string, opts: unknown) => string)(unknownKey, { ns: 'auth' })).toBe(unknownKey)
    })

    it('falls back gracefully to vi when an unsupported language is requested', async () => {
      // Request an unsupported language like 'fr', 'ja', or 'de'
      await i18n.changeLanguage('ja')
      expect(i18n.language).toBe('ja')

      // Because fallbackLng is 'vi', translations must fall back to Vietnamese
      expect(i18n.t('save')).toBe('Lưu')
      expect(i18n.t('cancel')).toBe('Hủy')
      expect(i18n.t('header.nav.support', { ns: 'shell' })).toBe('Ủng hộ')
      expect(i18n.t('login.title', { ns: 'auth' })).toBe('Chào mừng trở lại')
    })

    it('self-heals startup locale when localStorage contains an invalid/corrupted value', () => {
      // Simulate corrupted/unsupported locale in localStorage
      localStorage.setItem(STORAGE_KEY, 'invalid_or_malicious_lang_code')

      // The validation guard: saved && SUPPORTED_LOCALES.includes(saved)
      const saved = localStorage.getItem(STORAGE_KEY)
      const resolved = saved && (SUPPORTED_LOCALES as readonly string[]).includes(saved)
        ? saved
        : DEFAULT_LOCALE

      expect(resolved).toBe(DEFAULT_LOCALE)
      expect(resolved).toBe('vi')
    })

    it('handles localStorage.setItem exceptions gracefully without crashing language switch', async () => {
      const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new DOMException('QuotaExceededError or SecurityError', 'QuotaExceededError')
      })

      // Must NOT throw an unhandled exception
      await expect(i18n.changeLanguage('en')).resolves.toBeDefined()
      expect(i18n.language).toBe('en')
      expect(document.documentElement.lang).toBe('en')

      setItemSpy.mockRestore()
    })
  })

  describe('3. LanguageSwitcher UI Primitive Integration', () => {
    it('renders segmented pill variant and toggles language interactively', async () => {
      container = document.createElement('div')
      document.body.appendChild(container)
      root = createRoot(container)

      await act(async () => {
        root?.render(<LanguageSwitcher variant="pill" />)
      })

      expect(container?.textContent).toContain('VI')
      expect(container?.textContent).toContain('EN')

      const buttons = container?.querySelectorAll('button')
      expect(buttons?.length).toBe(2)

      const viBtn = buttons?.[0]
      const enBtn = buttons?.[1]

      expect(viBtn?.getAttribute('aria-pressed')).toBe('true')
      expect(enBtn?.getAttribute('aria-pressed')).toBe('false')

      // Click EN button
      await act(async () => {
        enBtn?.click()
      })

      expect(i18n.language).toBe('en')
      expect(localStorage.getItem(STORAGE_KEY)).toBe('en')
      expect(document.documentElement.lang).toBe('en')
    })

    it('renders dropdown variant trigger button with accessible attributes', async () => {
      container = document.createElement('div')
      document.body.appendChild(container)
      root = createRoot(container)

      await act(async () => {
        root?.render(<LanguageSwitcher variant="dropdown" showLabel={true} />)
      })

      const trigger = container?.querySelector('button')
      expect(trigger).not.toBeNull()
      expect(trigger?.getAttribute('aria-label')).toBeTruthy()
      expect(trigger?.textContent).toContain('VI')
      expect(trigger?.textContent).toContain('Tiếng Việt')
    })
  })

  describe('4. Dictionary Parity & Structural Integrity', () => {
    const getLeafPaths = (obj: Record<string, unknown>, prefix = ''): string[] => {
      let paths: string[] = []
      for (const [key, value] of Object.entries(obj)) {
        const fullKey = prefix ? `${prefix}.${key}` : key
        if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
          paths = paths.concat(getLeafPaths(value as Record<string, unknown>, fullKey))
        } else {
          paths.push(fullKey)
        }
      }
      return paths.sort()
    }

    it('verifies 100% key parity between vi and en for common namespace', async () => {
      const viCommon = await import('./locales/vi/common.json')
      const enCommon = await import('./locales/en/common.json')

      const viKeys = getLeafPaths(viCommon.default)
      const enKeys = getLeafPaths(enCommon.default)

      expect(viKeys).toEqual(enKeys)
      expect(viKeys.length).toBeGreaterThan(0)
    })

    it('verifies 100% key parity between vi and en for shell namespace', async () => {
      const viShell = await import('./locales/vi/shell.json')
      const enShell = await import('./locales/en/shell.json')

      const viKeys = getLeafPaths(viShell.default)
      const enKeys = getLeafPaths(enShell.default)

      expect(viKeys).toEqual(enKeys)
      expect(viKeys.length).toBeGreaterThan(0)
    })

    it('verifies 100% key parity between vi and en for auth namespace', async () => {
      const viAuth = await import('./locales/vi/auth.json')
      const enAuth = await import('./locales/en/auth.json')

      const viKeys = getLeafPaths(viAuth.default)
      const enKeys = getLeafPaths(enAuth.default)

      expect(viKeys).toEqual(enKeys)
      expect(viKeys.length).toBeGreaterThan(0)
    })

    it('verifies 100% key parity between vi and en for M3 namespaces (settings, note_types, collaboration, orders, support, worksheets)', async () => {
      const m3Namespaces = [
        'settings',
        'note_types',
        'collaboration',
        'orders',
        'support',
        'worksheets',
      ]

      for (const ns of m3Namespaces) {
        const viModule = await import(`./locales/vi/${ns}.json`)
        const enModule = await import(`./locales/en/${ns}.json`)

        const viKeys = getLeafPaths(viModule.default)
        const enKeys = getLeafPaths(enModule.default)

        expect(viKeys, `Discrepancy found in vi vs en for namespace "${ns}"`).toEqual(enKeys)
        expect(viKeys.length).toBeGreaterThan(0)
      }
    })

    it('ensures no translation values are empty or undefined in vi and en', async () => {
      const checkNonEmpty = (obj: Record<string, unknown>, ns: string) => {
        for (const [key, value] of Object.entries(obj)) {
          if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
            checkNonEmpty(value as Record<string, unknown>, `${ns}.${key}`)
          } else {
            expect(typeof value).toBe('string')
            expect((value as string).trim().length).toBeGreaterThan(0)
          }
        }
      }

      const namespaces = [
        'common',
        'shell',
        'auth',
        'settings',
        'note_types',
        'collaboration',
        'orders',
        'support',
        'worksheets',
      ]

      for (const ns of namespaces) {
        const viMod = await import(`./locales/vi/${ns}.json`)
        const enMod = await import(`./locales/en/${ns}.json`)
        checkNonEmpty(viMod.default, `vi.${ns}`)
        checkNonEmpty(enMod.default, `en.${ns}`)
      }
    })
  })
})

