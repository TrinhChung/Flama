// @vitest-environment jsdom

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteNoteTypeTemplate, renameNoteTypeTemplate } from '@/entities/card-template'
import { ApiError } from '@/shared/api/client'
import { toast } from 'sonner'
import { TemplateManagementBar } from './TemplateManagementBar'

vi.mock('@/entities/card-template', () => ({
  renameNoteTypeTemplate: vi.fn(),
  deleteNoteTypeTemplate: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function setNativeInputValue(element: HTMLInputElement, value: string) {
  const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set
  const prototype = Object.getPrototypeOf(element)
  const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set

  if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
    prototypeValueSetter.call(element, value)
  } else if (valueSetter) {
    valueSetter.call(element, value)
  } else {
    element.value = value
  }
  element.dispatchEvent(new Event('input', { bubbles: true }))
  element.dispatchEvent(new Event('change', { bubbles: true }))
}

describe('TemplateManagementBar', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
    vi.mocked(renameNoteTypeTemplate).mockResolvedValue({
      id: 't-2',
      name: 'Nghe',
      note_type_id: 'nt-1',
      position: 1,
      front_html: '',
      back_html: '',
      shared_css: '',
      is_default: false,
    } as any)
    vi.mocked(deleteNoteTypeTemplate).mockResolvedValue({ success: true })
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    document.body.innerHTML = ''
  })

  it('hiện nhãn Mặc định và số note chính xác', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-1', name: 'Card 1', is_default: true }}
            noteCount={12}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    expect(container.textContent).toContain('Mặc định')
    expect(container.textContent).toContain('12 note')

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-1', name: 'Card 1', is_default: true }}
            noteCount={null}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    expect(container.textContent).toContain('… note')
  })

  it('xóa bị khóa khi là template mặc định', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-1', name: 'Card 1', is_default: true }}
            noteCount={10}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    const deleteBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa'),
    ) as HTMLButtonElement
    expect(deleteBtn).toBeDefined()
    expect(deleteBtn.disabled).toBe(true)
    expect(deleteBtn.getAttribute('title')).toBe('Không thể xóa template mặc định.')
  })

  it('xóa bị khóa khi NoteType chỉ có 1 template duy nhất', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-1', name: 'Card 1', is_default: false }}
            noteCount={5}
            templateCount={1}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    const deleteBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa'),
    ) as HTMLButtonElement
    expect(deleteBtn).toBeDefined()
    expect(deleteBtn.disabled).toBe(true)
    expect(deleteBtn.getAttribute('title')).toBe('Loại thẻ cần ít nhất một template.')
  })

  it('đổi tên rỗng hiện thông báo lỗi và không gọi API', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={3}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })

    const renameBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đổi tên'),
    )
    await act(async () => {
      renameBtn?.click()
    })

    const input = document.querySelector<HTMLInputElement>('#template-name-input')
    expect(input).not.toBeNull()

    await act(async () => {
      if (input) {
        setNativeInputValue(input, '   ')
        const form = input.closest('form')
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      }
    })

    expect(document.body.textContent).toContain('Tên template không được để trống.')
    expect(renameNoteTypeTemplate).not.toHaveBeenCalled()
  })

  it('đổi tên trùng tên cũ đóng dialog và không gọi API', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={3}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })

    const renameBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đổi tên'),
    )
    await act(async () => {
      renameBtn?.click()
    })

    const input = document.querySelector<HTMLInputElement>('#template-name-input')
    expect(input).not.toBeNull()

    await act(async () => {
      const form = input?.closest('form')
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    })

    expect(renameNoteTypeTemplate).not.toHaveBeenCalled()
  })

  it('đổi tên thành công gọi API, toast success và callback onRenamed', async () => {
    const onRenamed = vi.fn()
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={3}
            templateCount={2}
            onRenamed={onRenamed}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })

    const renameBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đổi tên'),
    )
    await act(async () => {
      renameBtn?.click()
    })

    const input = document.querySelector<HTMLInputElement>('#template-name-input')
    await act(async () => {
      if (input) {
        setNativeInputValue(input, 'Nghe')
        const form = input.closest('form')
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      }
    })

    await act(async () => {
      await Promise.resolve()
    })

    expect(renameNoteTypeTemplate).toHaveBeenCalledWith('nt-1', 't-2', 'Nghe')
    expect(toast.success).toHaveBeenCalledWith('Đã đổi tên template.')
    expect(onRenamed).toHaveBeenCalledTimes(1)
  })

  it('đổi tên lỗi hiển thị toast error với thông báo thân thiện và giữ dialog mở', async () => {
    vi.mocked(renameNoteTypeTemplate).mockRejectedValueOnce(
      new ApiError('x', 409, 'SHARED_SCHEMA_VERSIONING_REQUIRED'),
    )
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={3}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })

    const renameBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đổi tên'),
    )
    await act(async () => {
      renameBtn?.click()
    })

    const input = document.querySelector<HTMLInputElement>('#template-name-input')
    await act(async () => {
      if (input) {
        setNativeInputValue(input, 'Nghe')
        const form = input.closest('form')
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      }
    })

    await act(async () => {
      await Promise.resolve()
    })

    expect(toast.error).toHaveBeenCalledWith('Không thể đổi tên template', {
      description:
        'Template này đang dùng trong bộ thẻ đã chia sẻ nên chưa thể thêm, xóa hoặc đặt lại. Bạn vẫn có thể sửa nội dung HTML/CSS.',
    })
    expect(document.querySelector('#template-name-input')).not.toBeNull()
  })

  it('xóa thành công gọi deleteNoteTypeTemplate, toast success và callback onDeleted', async () => {
    const onDeleted = vi.fn()
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={7}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={onDeleted}
          />
        </QueryClientProvider>,
      )
    })

    const deleteTrigger = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa'),
    )
    await act(async () => {
      deleteTrigger?.click()
    })

    const confirmBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa template'),
    )
    expect(confirmBtn).toBeDefined()

    await act(async () => {
      confirmBtn?.click()
    })

    await act(async () => {
      await Promise.resolve()
    })

    expect(deleteNoteTypeTemplate).toHaveBeenCalledWith('nt-1', 't-2')
    expect(toast.success).toHaveBeenCalledWith('Đã xóa template.')
    expect(onDeleted).toHaveBeenCalledTimes(1)
    expect(onDeleted).toHaveBeenCalledWith('t-2')
  })

  it('trả null khi template là null', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={null}
            noteCount={null}
            templateCount={0}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    expect(container.innerHTML).toBe('')
  })

  it('đổi tên dài hơn 255 ký tự hiện thông báo lỗi và không gọi API', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={3}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })

    const renameBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đổi tên'),
    )
    await act(async () => {
      renameBtn?.click()
    })

    const input = document.querySelector<HTMLInputElement>('#template-name-input')
    expect(input).not.toBeNull()

    const longName = 'A'.repeat(256)
    await act(async () => {
      if (input) {
        setNativeInputValue(input, longName)
        const form = input.closest('form')
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      }
    })

    expect(document.body.textContent).toContain('Tên template tối đa 255 ký tự.')
    expect(renameNoteTypeTemplate).not.toHaveBeenCalled()
  })

  it('hiện … note khi noteCount là undefined', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-1', name: 'Card 1', is_default: false }}
            noteCount={undefined as unknown as null}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    expect(container.textContent).toContain('… note')
  })

  it('xóa lỗi hiển thị toast error với thông báo thân thiện và giữ dialog mở', async () => {
    vi.mocked(deleteNoteTypeTemplate).mockRejectedValueOnce(
      new ApiError('schema error', 409, 'SHARED_SCHEMA_VERSIONING_REQUIRED'),
    )
    const onDeleted = vi.fn()
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={7}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={onDeleted}
          />
        </QueryClientProvider>,
      )
    })

    const deleteTrigger = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa'),
    )
    await act(async () => {
      deleteTrigger?.click()
    })

    const confirmBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa template'),
    )
    expect(confirmBtn).toBeDefined()

    await act(async () => {
      confirmBtn?.click()
    })

    await act(async () => {
      await Promise.resolve()
    })

    expect(deleteNoteTypeTemplate).toHaveBeenCalledWith('nt-1', 't-2')
    expect(toast.error).toHaveBeenCalledWith('Không thể xóa template', {
      description:
        'Template này đang dùng trong bộ thẻ đã chia sẻ nên chưa thể thêm, xóa hoặc đặt lại. Bạn vẫn có thể sửa nội dung HTML/CSS.',
    })
    expect(onDeleted).not.toHaveBeenCalled()
    // ConfirmDialog stays open
    expect(
      Array.from(document.body.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Xóa template'),
      ),
    ).toBeDefined()
  })

  it('ưu tiên lý do mặc định khi template vừa là mặc định vừa là template duy nhất', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-1', name: 'Card 1', is_default: true }}
            noteCount={1}
            templateCount={1}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })
    const deleteBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xóa'),
    ) as HTMLButtonElement
    expect(deleteBtn).toBeDefined()
    expect(deleteBtn.disabled).toBe(true)
    expect(deleteBtn.getAttribute('title')).toBe('Không thể xóa template mặc định.')
  })

  it('không mở dialog và không gọi API khi noteTypeId rỗng hoặc chỉ có khoảng trắng', async () => {
    for (const emptyId of ['', '   ']) {
      await act(async () => {
        root.render(
          <QueryClientProvider client={queryClient}>
            <TemplateManagementBar
              noteTypeId={emptyId}
              template={{ id: 't-2', name: 'Card 2', is_default: false }}
              noteCount={5}
              templateCount={2}
              onRenamed={vi.fn()}
              onDeleted={vi.fn()}
            />
          </QueryClientProvider>,
        )
      })

      const renameBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Đổi tên'),
      )
      await act(async () => {
        renameBtn?.click()
      })
      expect(document.querySelector('#template-name-input')).toBeNull()
      expect(renameNoteTypeTemplate).not.toHaveBeenCalled()

      const deleteBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Xóa'),
      )
      await act(async () => {
        deleteBtn?.click()
      })
      expect(
        Array.from(document.body.querySelectorAll('button')).find((b) =>
          b.textContent?.includes('Xóa template'),
        ),
      ).toBeUndefined()
      expect(deleteNoteTypeTemplate).not.toHaveBeenCalled()
    }
  })

  it('ẩn nút đóng X khi mutation đổi tên đang trong trạng thái pending', async () => {
    let resolveRename: (value: any) => void = () => {}
    vi.mocked(renameNoteTypeTemplate).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRename = resolve
        }),
    )

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <TemplateManagementBar
            noteTypeId="nt-1"
            template={{ id: 't-2', name: 'Card 2', is_default: false }}
            noteCount={3}
            templateCount={2}
            onRenamed={vi.fn()}
            onDeleted={vi.fn()}
          />
        </QueryClientProvider>,
      )
    })

    const renameBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đổi tên'),
    )
    await act(async () => {
      renameBtn?.click()
    })

    const input = document.querySelector<HTMLInputElement>('#template-name-input')
    await act(async () => {
      if (input) {
        setNativeInputValue(input, 'Tên Mới')
      }
    })

    await act(async () => {
      const form = input?.closest('form')
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    })

    for (let i = 0; i < 5; i++) {
      await act(async () => {
        await new Promise((r) => setTimeout(r, 10))
      })
    }

    expect(renameNoteTypeTemplate).toHaveBeenCalled()

    // While pending, showCloseButton is false so dialog close button is not rendered
    const closeBtn = document.querySelector('[data-slot="dialog-close"]')
    expect(closeBtn).toBeNull()

    // Resolve the mutation
    await act(async () => {
      resolveRename({ id: 't-2', name: 'Tên Mới' })
    })
  })
})
