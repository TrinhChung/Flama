// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'
import i18n, { DEFAULT_LOCALE, STORAGE_KEY, SUPPORTED_LOCALES } from './index'

describe('i18n Core Configuration', () => {
  beforeEach(async () => {
    localStorage.clear()
    await i18n.changeLanguage(DEFAULT_LOCALE)
  })

  it('exposes expected constants and supported locales', () => {
    expect(DEFAULT_LOCALE).toBe('vi')
    expect(STORAGE_KEY).toBe('flama_lang')
    expect(SUPPORTED_LOCALES).toEqual(['vi', 'en'])
  })

  it('translates common namespace in Vietnamese by default', () => {
    expect(i18n.language).toBe('vi')
    expect(i18n.t('save')).toBe('Lưu')
    expect(i18n.t('cancel')).toBe('Hủy')
    expect(i18n.t('language.vi')).toBe('Tiếng Việt')
    expect(i18n.t('language.en')).toBe('English')
  })

  it('translates shell namespace in Vietnamese by default', () => {
    expect(i18n.t('header.nav.support', { ns: 'shell' })).toBe('Ủng hộ')
    expect(i18n.t('header.nav.login', { ns: 'shell' })).toBe('Đăng nhập')
    expect(i18n.t('sidebar.group.learning', { ns: 'shell' })).toBe('Học tập')
    expect(i18n.t('page_titles.dashboard', { ns: 'shell' })).toBe('Tổng quan')
  })

  it('translates auth namespace in Vietnamese by default', () => {
    expect(i18n.t('card.badge', { ns: 'auth' })).toBe('Flama Study Platform')
    expect(i18n.t('login.title', { ns: 'auth' })).toBe('Chào mừng trở lại')
    expect(i18n.t('register.title', { ns: 'auth' })).toBe('Tạo tài khoản mới')
    expect(i18n.t('validation.email_required', { ns: 'auth' })).toBe('Vui lòng nhập email.')
  })

  it('switches to English and persists in localStorage and html lang', async () => {
    await i18n.changeLanguage('en')

    expect(i18n.language).toBe('en')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('en')
    expect(document.documentElement.lang).toBe('en')

    // Common
    expect(i18n.t('save')).toBe('Save')
    expect(i18n.t('cancel')).toBe('Cancel')

    // Shell
    expect(i18n.t('header.nav.support', { ns: 'shell' })).toBe('Support')
    expect(i18n.t('header.nav.login', { ns: 'shell' })).toBe('Log in')
    expect(i18n.t('sidebar.group.learning', { ns: 'shell' })).toBe('Learning')
    expect(i18n.t('page_titles.dashboard', { ns: 'shell' })).toBe('Overview')

    // Auth
    expect(i18n.t('login.title', { ns: 'auth' })).toBe('Welcome Back')
    expect(i18n.t('register.title', { ns: 'auth' })).toBe('Create a New Account')
    expect(i18n.t('validation.email_required', { ns: 'auth' })).toBe('Email is required.')
  })

  it('switches back to Vietnamese cleanly', async () => {
    await i18n.changeLanguage('en')
    expect(i18n.language).toBe('en')

    await i18n.changeLanguage('vi')
    expect(i18n.language).toBe('vi')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('vi')
    expect(document.documentElement.lang).toBe('vi')
    expect(i18n.t('save')).toBe('Lưu')
  })
})
