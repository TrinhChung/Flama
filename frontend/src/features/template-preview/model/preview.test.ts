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
  it('hydrates UI-only artifacts without replacing model-visible identity or checks', () => {
    const summary = { schema_version: 'template-preview.v1', candidate_hash: 'sha256-candidate',
      renderer_abi: 'flama-client-mustache.v2', checks: { interaction: 'not_run' }, diagnostics: [], preview: null }
    const preview = { template_artifact: { renderer_abi: 'flama-client-mustache.v2', version: 'candidate',
      front_source: '<p>Preview only</p>', back_source: '', shared_css: '', front_inline_scripts: [], back_inline_scripts: [], field_defs: [] },
      content_artifact: { renderer_abi: 'flama-client-mustache.v2', field_values: {}, render_context: {}, media: [] } }
    expect(parseTemplatePreview({ structuredContent: summary, _meta: { 'flama/template-preview': {
      candidate_hash: 'sha256-candidate', preview, checks: { interaction: 'passed' } } } })).toMatchObject({
      preview, checks: { interaction: 'not_run' } })
    expect(parseTemplatePreview({ structuredContent: summary, _meta: { 'flama/template-preview': {
      candidate_hash: 'different-candidate', preview } } }).preview).toBeNull()
  })
  it('accepts input failures with no candidate and preserves locations and suggestions', () => {
    const data = { schema_version: 'template-preview.v1', candidate_hash: null,
      renderer_abi: 'flama-client-mustache.v2', checks: { input: 'failed', javascript_syntax: 'not_run' },
      diagnostics: [{ code: 'INVALID_PARAMS', severity: 'error', stage: 'input', source_part: 'input_schema',
        message: 'Supply input_schema.', line: null, column: null, suggestions: [] }], preview: null }
    expect(parseTemplatePreview({ isError: true, structuredContent: data })).toEqual(data)
  })
})
