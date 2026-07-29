// @vitest-environment jsdom
/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'

describe('card renderer host viewport modes', () => {
  afterEach(() => {
    document.body.replaceChildren()
    delete window.FlamaCardRendererHost
  })

  it('preserves template viewport-height styles in fill-height mode', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(
      iframe,
      { fillHeight: true },
    )

    controller.render(
      { html: '<div style="height:100vh">Centered card</div>' },
      { padding: '0' },
    )

    expect(iframe.style.height).toBe('100%')
    expect(iframe.srcdoc).toContain(
      '#flama-card-root { min-height: 100%; height: 100%;',
    )
    expect(iframe.srcdoc).not.toContain(
      '#flama-card-root [style*="height:100vh"]',
    )

    controller.destroy()
  })

  it('retains the viewport-height guard for auto-height embeds', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(
      iframe,
      { autoHeight: true },
    )

    controller.render({ html: '<div style="height:100vh">Card</div>' })

    expect(iframe.style.height).toBe('180px')
    expect(iframe.srcdoc).toContain(
      '#flama-card-root [style*="height:100vh"]',
    )

    controller.destroy()
  })
})
