// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import '@/shared/config/i18n'
import {
  ProfileEditPasswordTab,
  type ProfileEditPasswordTabProps,
} from './ProfileEditPasswordTab'

describe('ProfileEditPasswordTab (react-hook-form + zod)', () => {
  let root: Root
  let container: HTMLDivElement
  let onSaveMock: ReturnType<typeof vi.fn<ProfileEditPasswordTabProps['onSave']>>
  let onCancelMock: ReturnType<typeof vi.fn<ProfileEditPasswordTabProps['onCancel']>>
  let setFieldErrorsMock: ReturnType<typeof vi.fn<ProfileEditPasswordTabProps['setFieldErrors']>>

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    onSaveMock = vi.fn<ProfileEditPasswordTabProps['onSave']>()
    onCancelMock = vi.fn<ProfileEditPasswordTabProps['onCancel']>()
    setFieldErrorsMock = vi.fn<ProfileEditPasswordTabProps['setFieldErrors']>()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.unstubAllGlobals()
  })

  it('renders password fields correctly', async () => {
    await act(async () => {
      root.render(
        <ProfileEditPasswordTab
          isPending={false}
          fieldErrors={{}}
          setFieldErrors={setFieldErrorsMock}
          onCancel={onCancelMock}
          onSave={onSaveMock}
        />
      )
    })

    expect(container.querySelector('#profile-cur-pw')).not.toBeNull()
    expect(container.querySelector('#profile-new-pw')).not.toBeNull()
    expect(container.querySelector('#profile-conf-pw')).not.toBeNull()
  })

  function setInputValue(input: HTMLInputElement, value: string) {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value'
    )?.set
    setter?.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }

  it('submits successfully when form has valid inputs', async () => {
    await act(async () => {
      root.render(
        <ProfileEditPasswordTab
          isPending={false}
          fieldErrors={{}}
          setFieldErrors={setFieldErrorsMock}
          onCancel={onCancelMock}
          onSave={onSaveMock}
        />
      )
    })

    const curInput = container.querySelector<HTMLInputElement>('#profile-cur-pw')!
    const newInput = container.querySelector<HTMLInputElement>('#profile-new-pw')!
    const confInput = container.querySelector<HTMLInputElement>('#profile-conf-pw')!
    const form = container.querySelector('form')!

    await act(async () => {
      setInputValue(curInput, 'currentPass123')
      setInputValue(newInput, 'newStrongPass456')
      setInputValue(confInput, 'newStrongPass456')
    })

    await act(async () => {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      await new Promise((r) => setTimeout(r, 100))
    })

    expect(onSaveMock).toHaveBeenCalledWith({
      current_password: 'currentPass123',
      new_password: 'newStrongPass456',
      confirm_password: 'newStrongPass456',
    })
  })

  it('displays server-side fieldErrors when passed down', async () => {
    await act(async () => {
      root.render(
        <ProfileEditPasswordTab
          isPending={false}
          fieldErrors={{ current_password: 'Mật khẩu hiện tại không chính xác' }}
          setFieldErrors={setFieldErrorsMock}
          onCancel={onCancelMock}
          onSave={onSaveMock}
        />
      )
    })

    expect(container.textContent).toContain('Mật khẩu hiện tại không chính xác')
  })
})
