// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { withStudyClientPreview } from './clientPreview'

describe('REST preview Study client parity', () => {
  it('keeps legacy-only responses compatible', () => {
    const old = { study_preview: undefined, front_renderer_payload: 'legacy' }
    expect(withStudyClientPreview(old)).toBe(old)
  })
  it('renders artifacts with literal script source while replacing diagnostic server HTML', () => {
    const value = withStudyClientPreview({ front_renderer_payload: 'wrong server rendering',
      study_preview: { preview: {
        template_artifact: { renderer_abi: 'flama-client-mustache.v2', version: 'preview',
          front_source: '{{#options}}<p>{{.}}</p>{{/options}}', back_source: '{{FrontSide}}',
          front_inline_scripts: ['<script>const literal="{{options}}";</script>'], back_inline_scripts: [],
          shared_css: '', field_defs: [{ name: 'options', field_type: 'array' }] },
        content_artifact: { renderer_abi: 'flama-client-mustache.v2', field_values: { options: ['a', 'b'] },
          render_context: { options: ['a', 'b'] }, media: [] },
      } } })
    expect(value.front_renderer_payload).toMatchObject({ html: '<p>a</p><p>b</p><script>const literal="{{options}}";</script>' })
  })
  it('fails on invalid artifacts instead of silently using a misleading server preview', () => {
    expect(() => withStudyClientPreview({ study_preview: { preview: null,
      diagnostics: [{ severity: 'error', message: 'Unsupported helper' }] } })).toThrow('Unsupported helper')
  })
})
