import { beforeEach, describe, expect, it, vi } from 'vitest'
const { apiRequest, apiJson } = vi.hoisted(() => ({ apiRequest: vi.fn(), apiJson: vi.fn() }))
vi.mock('@/shared/api/client', () => ({ apiRequest, apiJson }))
import { getBaseOverrideComparison, keepBaseOverride, resetBaseOverride } from './baseComparisonApi'

describe('Base comparison API contract', () => {
  beforeEach(() => { apiRequest.mockReset(); apiJson.mockReset() })
  it('encodes install identity and forwards cancellation and opaque cursor', async () => {
    const signal = new AbortController().signal
    apiRequest.mockResolvedValue({ items: [] })
    await getBaseOverrideComparison('install/one', 'a+b/=', signal)
    expect(apiRequest).toHaveBeenCalledWith('/api/marketplace/installations/install%2Fone/base-overrides?limit=50&cursor=a%2Bb%2F%3D', { signal })
  })
  it('deletes one identity override using its expected overlay revision', async () => {
    await resetBaseOverride('install/one', 'override/one', 12)
    expect(apiJson).toHaveBeenCalledWith('/api/marketplace/installations/install%2Fone/overrides/override%2Fone', 'DELETE', { expected_overlay_revision: 12 })
  })
  it('acknowledges only the displayed Base and overlay revisions', async () => {
    await keepBaseOverride('install/one', 'override/one', 12, 'base-hash')
    expect(apiJson).toHaveBeenCalledWith('/api/marketplace/installations/install%2Fone/overrides/override%2Fone/keep', 'POST', {
      expected_overlay_revision: 12, expected_base_hash: 'base-hash',
    })
  })
})
