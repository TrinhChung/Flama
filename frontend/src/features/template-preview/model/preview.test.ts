import { describe, expect, it } from 'vitest'
import { parseTemplatePreview } from './preview'

describe('MCP preview envelope', () => {
  it('rejects absent, malformed and incompatible host data', () => {
    for (const value of [null, undefined, {}, { isError: true, structuredContent: 'bad' },
      { schema_version: 'old-preview.v1' }]) expect(() => parseTemplatePreview(value)).toThrow()
  })
  it('keeps compile failures with diagnostics readable without artifacts', () => {
    const result = { schema_version: 'template-preview.v1', candidate_hash: 'sha256-failed',
      renderer_abi: 'flama-client-mustache.v2', checks: { template: 'failed', interaction: 'not_run' },
      diagnostics: [{ code: 'UNSUPPORTED_HELPER', severity: 'error', stage: 'template',
        source_part: 'front_html', message: 'Use sections instead of #each.' }], preview: null }
    expect(parseTemplatePreview({ isError: true, structuredContent: result })).toEqual(result)
  })
})
