// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TemplatePreviewApp } from './TemplatePreviewApp'

const calls = vi.hoisted(() => ({ props: null as Record<string, unknown> | null }))
vi.mock('@/entities/flashcard/rendering', () => ({
  renderCardSide: (_template: unknown, _content: unknown, side: string) => ({ html: `<script>bad()</script>${side}` }),
  CardDisplay: (props: Record<string, unknown>) => { calls.props = props; return <div data-testid="sandbox-placeholder" /> },
}))
;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const result = { schema_version: 'template-preview.v1', candidate_hash: 'sha256-candidate',
  renderer_abi: 'flama-client-mustache.v2', checks: { interaction: 'not_run' }, diagnostics: [],
  preview: { template_artifact: { renderer_abi: 'flama-client-mustache.v2', version: 'candidate',
    front_source: '<script>bad()</script>', back_source: '', shared_css: '', front_inline_scripts: [], back_inline_scripts: [], field_defs: [] },
  content_artifact: { renderer_abi: 'flama-client-mustache.v2', field_values: {}, render_context: {}, media: [] } } }

describe('MCP template app', () => {
  let root: ReturnType<typeof createRoot> | undefined
  let container: HTMLDivElement | undefined
  afterEach(() => { act(() => root?.unmount()); container?.remove(); calls.props = null })
  async function mount(value: unknown) {
    container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
    await act(async () => { root!.render(<TemplatePreviewApp initialResult={value} />) })
    return container
  }
  it('passes both compiled faces only to the sandbox component and switches faces', async () => {
    const view = await mount(result)
    expect(view.querySelector('script')).toBeNull()
    expect(calls.props?.frontPayload).toEqual({ html: '<script>bad()</script>front' })
    expect(calls.props?.side).toBe('front')
    await act(async () => { Array.from(view.querySelectorAll('button')).find((b) => b.textContent === 'Back')!.click() })
    expect(calls.props?.side).toBe('back')
    expect(view.textContent).toContain('Interaction test: not run.')
  })
  it('shows malformed tool data as an error without mounting the renderer', async () => {
    const view = await mount({ structuredContent: {} })
    expect(view.querySelector('[role="alert"]')?.textContent).toContain('Invalid')
    expect(calls.props).toBeNull()
  })
  it('shows structured input failures without mounting the card renderer', async () => {
    const view = await mount({ isError: true, structuredContent: { ...result, candidate_hash: null, preview: null,
      diagnostics: [{ code: 'JAVASCRIPT_SYNTAX_ERROR', severity: 'error', stage: 'javascript_syntax',
        source_part: 'back_html', line: 3, column: 16, message: 'Unexpected token ;', suggestions: ['question'] }] } })
    expect(view.textContent).toContain('back_html:3:16')
    expect(view.textContent).toContain('question')
    expect(calls.props).toBeNull()
  })
})
