// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import { distributionApi } from '../api/distributionApi'
import { TemplateDistributionPanel } from './TemplateDistributionPanel'
import type {
  PendingUpdateDto,
  TemplatePublicationDto,
  TemplateReleaseDto,
  TemplateReleasesResponse,
  TemplateSubscriptionDto,
} from '../model/types'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const mockRelease: TemplateReleaseDto = {
  id: 'rel_1',
  template_id: 't1',
  version_id: 'ver_1',
  sequence_no: 1,
  version_label: 'v1.0.0',
  parent_release_id: null,
  publish_mode: 'manual',
  change_note: 'Initial official release',
  created_by_user_id: 1,
  published_at: '2026-10-09T10:00:00Z',
}

const mockPublication: TemplatePublicationDto = {
  template_id: 't1',
  auto_publish_enabled: false,
  current_release: mockRelease,
  current_version_id: 'ver_1',
  has_unpublished_changes: true,
  last_auto_published_at: null,
  last_auto_publish_error: null,
}

const mockReleasesResponse: TemplateReleasesResponse = {
  template_id: 't1',
  source_template_id: 't1',
  items: [mockRelease],
  has_more: false,
}

const mockSubscription: TemplateSubscriptionDto = {
  id: 'sub_1',
  user_id: 2,
  source_template_id: 't_source',
  local_template_id: 't_copy',
  template_id: 't_copy',
  current_version_id: 'ver_copy_1',
  applied_release_id: 'rel_1',
  applied_release: mockRelease,
  current_release: {
    ...mockRelease,
    id: 'rel_2',
    sequence_no: 2,
    version_label: 'v1.1.0',
    change_note: 'New styling and animations',
  },
  update_available: true,
  auto_update_enabled: false,
  pending_update_json: null,
  last_sync_status: 'ready',
  last_synced_at: '2026-10-09T10:00:00Z',
  created_at: '2026-10-09T10:00:00Z',
  updated_at: '2026-10-09T10:00:00Z',
}

async function flush(ms = 20) {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, ms))
  })
}

function findButton(text: string) {
  const item = [...document.querySelectorAll('button')].find((el) => el.textContent?.trim() === text)
  return item
}

async function text(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')!.set!.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('TemplateDistributionPanel', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)

    vi.spyOn(distributionApi, 'getPublication').mockResolvedValue(mockPublication)
    vi.spyOn(distributionApi, 'getReleases').mockResolvedValue(mockReleasesResponse)
    vi.spyOn(distributionApi, 'updatePublicationSettings').mockResolvedValue({
      ...mockPublication,
      auto_publish_enabled: true,
    })
    vi.spyOn(distributionApi, 'publishRelease').mockResolvedValue({
      release: {
        ...mockRelease,
        id: 'rel_new',
        sequence_no: 2,
        version_label: 'v1.1.0',
      },
      replayed: false,
    })

    vi.spyOn(distributionApi, 'getSubscription').mockResolvedValue(mockSubscription)
    vi.spyOn(distributionApi, 'updateSubscriptionSettings').mockResolvedValue({
      ...mockSubscription,
      auto_update_enabled: true,
    })
    vi.spyOn(distributionApi, 'prepareUpdate').mockResolvedValue({
      id: 'prep_1',
      from_release_id: 'rel_1',
      to_release_id: 'rel_2',
      expected_local_version_id: 'ver_copy_1',
      status: 'ready',
      conflicts: {},
      mode: 'manual',
    })
    vi.spyOn(distributionApi, 'applyUpdate').mockResolvedValue({
      ...mockSubscription,
      applied_release_id: 'rel_2',
      applied_release: mockSubscription.current_release,
      update_available: false,
      last_sync_status: 'synced',
    })
    vi.spyOn(distributionApi, 'resetToUpstream').mockResolvedValue({
      ...mockSubscription,
      last_sync_status: 'synced',
    })
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    client.clear()
    container.remove()
    document.body.innerHTML = ''
  })

  describe('Author flow (origin !== market_copy)', () => {
    it('renders publication status, current release, and release history', async () => {
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel templateId="t1" origin="authored" />
          </QueryClientProvider>,
        )
      })
      await flush()

      expect(container.textContent).toContain('Quản lý phát hành')
      expect(container.textContent).toContain('v1.0.0')
      expect(container.textContent).toContain('Có thay đổi chưa phát hành')
      expect(container.textContent).toContain('Initial official release')
      expect(distributionApi.getPublication).toHaveBeenCalledWith('t1', expect.anything())
      expect(distributionApi.getReleases).toHaveBeenCalledWith('t1', undefined, expect.anything())
    })

    it('toggles auto-publish switch', async () => {
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel templateId="t1" origin="authored" />
          </QueryClientProvider>,
        )
      })
      await flush()

      const switchBtn = document.querySelector('#auto-publish-switch') as HTMLButtonElement
      expect(switchBtn).not.toBeNull()
      expect(switchBtn.getAttribute('data-state')).toBe('unchecked')

      await act(async () => {
        switchBtn.click()
      })
      await flush()

      expect(distributionApi.updatePublicationSettings).toHaveBeenCalledWith('t1', {
        auto_publish_enabled: true,
      })
      expect(toast.success).toHaveBeenCalledWith('Đã lưu')
    })

    it('opens publish release dialog and publishes a new release', async () => {
      const onSourceChanged = vi.fn()
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel
              templateId="t1"
              origin="authored"
              currentVersionId="ver_current"
              onSourceChanged={onSourceChanged}
            />
          </QueryClientProvider>,
        )
      })
      await flush()

      const publishBtn = findButton('Phát hành phiên bản mới')
      expect(publishBtn).toBeDefined()
      await act(async () => {
        publishBtn!.click()
      })
      await flush()

      // Dialog opens
      expect(document.body.textContent).toContain('Nhãn phiên bản')
      const labelInput = document.querySelector('#release-version-label') as HTMLInputElement
      const noteInput = document.querySelector('#release-change-note') as HTMLTextAreaElement
      expect(labelInput).not.toBeNull()

      await text(labelInput, 'v1.1.0')
      await text(noteInput, 'Release notes for v1.1.0')
      await flush()

      const submitBtn = [...document.querySelectorAll('button')].find(
        (el) => el.getAttribute('type') === 'submit' && el.textContent?.trim() === 'Phát hành',
      )
      expect(submitBtn).toBeDefined()

      await act(async () => {
        submitBtn!.click()
      })
      await flush()

      expect(distributionApi.publishRelease).toHaveBeenCalledWith(
        't1',
        {
          version_label: 'v1.1.0',
          change_note: 'Release notes for v1.1.0',
          expected_current_release_id: 'rel_1',
          expected_current_version_id: 'ver_current',
        },
      )
      expect(toast.success).toHaveBeenCalledWith('Đã phát hành phiên bản v1.1.0 thành công.')
      expect(onSourceChanged).toHaveBeenCalled()
    })
  })

  describe('Subscriber flow (origin === market_copy)', () => {
    it('renders subscription status, update banner, and latest upstream release', async () => {
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel templateId="t_copy" origin="market_copy" />
          </QueryClientProvider>,
        )
      })
      await flush()

      expect(container.textContent).toContain('Cập nhật từ nguồn')
      expect(container.textContent).toContain('Phiên bản đang dùng')
      expect(container.textContent).toContain('Phiên bản nguồn mới nhất')
      expect(container.textContent).toContain('Có bản cập nhật mới!')
      expect(container.textContent).toContain('New styling and animations')
      expect(distributionApi.getSubscription).toHaveBeenCalledWith('t_copy', expect.anything())
    })

    it('toggles auto-update switch', async () => {
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel templateId="t_copy" origin="market_copy" />
          </QueryClientProvider>,
        )
      })
      await flush()

      const switchBtn = document.querySelector('#auto-update-switch') as HTMLButtonElement
      expect(switchBtn).not.toBeNull()

      await act(async () => {
        switchBtn.click()
      })
      await flush()

      expect(distributionApi.updateSubscriptionSettings).toHaveBeenCalledWith('t_copy', {
        auto_update_enabled: true,
      })
      expect(toast.success).toHaveBeenCalledWith('Đã lưu')
    })

    it('prepares and applies update when ready without conflict', async () => {
      const onSourceChanged = vi.fn()
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel
              templateId="t_copy"
              origin="market_copy"
              currentVersionId="ver_copy_1"
              onSourceChanged={onSourceChanged}
            />
          </QueryClientProvider>,
        )
      })
      await flush()

      const updateBtn = findButton('Cập nhật lên bản mới')
      expect(updateBtn).toBeDefined()

      await act(async () => {
        updateBtn!.click()
      })
      await flush()

      expect(distributionApi.prepareUpdate).toHaveBeenCalledWith('t_copy', {
        release_id: 'rel_2',
        expected_applied_release_id: 'rel_1',
        expected_current_version_id: 'ver_copy_1',
      })
      expect(distributionApi.applyUpdate).toHaveBeenCalledWith('t_copy', {
        preparation_id: 'prep_1',
      })
      expect(toast.success).toHaveBeenCalledWith('Đã cập nhật template lên phiên bản mới thành công.')
      expect(onSourceChanged).toHaveBeenCalled()
    })

    it('opens conflict resolution dialog when prepare returns conflicts', async () => {
      const conflictedPending: PendingUpdateDto = {
        id: 'prep_conflict',
        from_release_id: 'rel_1',
        to_release_id: 'rel_2',
        expected_local_version_id: 'ver_copy_1',
        status: 'has_conflict',
        conflicts: {
          front_html: {
            base: '<div>Base</div>',
            local: '<div>Local edited</div>',
            upstream: '<div>Upstream edited</div>',
          },
        },
        mode: 'manual',
      }
      vi.mocked(distributionApi.prepareUpdate).mockResolvedValueOnce(conflictedPending)

      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel
              templateId="t_copy"
              origin="market_copy"
              currentVersionId="ver_copy_1"
            />
          </QueryClientProvider>,
        )
      })
      await flush()

      const updateBtn = findButton('Cập nhật lên bản mới')
      await act(async () => {
        updateBtn!.click()
      })
      await flush()

      expect(document.body.textContent).toContain('Giải quyết xung đột cập nhật')
      expect(document.body.textContent).toContain('HTML Mặt trước')

      // Select 'Dùng bản mới từ tác giả'
      const upstreamChoiceBtn = [...document.querySelectorAll('button')].find(
        (el) => el.textContent?.trim() === 'Dùng bản mới từ tác giả',
      )
      expect(upstreamChoiceBtn).toBeDefined()
      await act(async () => {
        upstreamChoiceBtn!.click()
      })
      await flush()

      // Click 'Áp dụng cập nhật'
      const applyBtn = findButton('Áp dụng cập nhật')
      expect(applyBtn).toBeDefined()
      await act(async () => {
        applyBtn!.click()
      })
      await flush()

      expect(distributionApi.applyUpdate).toHaveBeenCalledWith('t_copy', {
        preparation_id: 'prep_conflict',
        resolutions: {
          front_html: { mode: 'keep_upstream' },
        },
      })
      expect(toast.success).toHaveBeenCalledWith('Đã cập nhật template lên phiên bản mới thành công.')
    })

    it('resets to upstream version with confirmation', async () => {
      const onSourceChanged = vi.fn()
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel
              templateId="t_copy"
              origin="market_copy"
              onSourceChanged={onSourceChanged}
            />
          </QueryClientProvider>,
        )
      })
      await flush()

      const resetBtn = findButton('Khôi phục về bản gốc của tác giả')
      expect(resetBtn).toBeDefined()
      await act(async () => {
        resetBtn!.click()
      })
      await flush()

      // Confirm dialog appears
      expect(document.body.textContent).toContain('Khôi phục về bản gốc của tác giả?')
      const confirmBtn = [...document.querySelectorAll('button')].find(
        (el) => el.textContent?.trim() === 'Khôi phục về bản gốc',
      )
      expect(confirmBtn).toBeDefined()

      await act(async () => {
        confirmBtn!.click()
      })
      await flush()

      expect(distributionApi.resetToUpstream).toHaveBeenCalledWith('t_copy')
      expect(toast.success).toHaveBeenCalledWith('Đã khôi phục về bản gốc của tác giả thành công.')
      expect(onSourceChanged).toHaveBeenCalled()
    })
  })

  describe('Drawer sheet mode', () => {
    it('renders inside Sheet when open and onOpenChange are provided', async () => {
      const onOpenChange = vi.fn()
      await act(async () => {
        root.render(
          <QueryClientProvider client={client}>
            <TemplateDistributionPanel
              templateId="t1"
              origin="authored"
              open={true}
              onOpenChange={onOpenChange}
            />
          </QueryClientProvider>,
        )
      })
      await flush()

      expect(document.body.textContent).toContain('Phân phối & Cập nhật')
      expect(document.body.textContent).toContain('Quản lý phát hành')
    })
  })
})
