import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

const file = (path: string) => fileURLToPath(new URL(path, import.meta.url))

/** Package the existing renderer host and application into one MCP resource. */
function singleHtmlResource(): Plugin {
  return {
    name: 'flama-mcp-single-html',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const html = bundle['index.html']
      if (!html || html.type !== 'asset') throw new Error('Missing MCP App HTML entry.')
      let source = String(html.source)
      for (const [name, asset] of Object.entries(bundle)) {
        if (name === 'index.html') continue
        if (asset.type === 'chunk') {
          if (!asset.isEntry) throw new Error(`Unexpected external MCP chunk: ${name}`)
          source = source.replace(/<script[^>]*\bsrc="[^"]+"[^>]*><\/script>/,
            () => `<script type="module">${asset.code.replace(/<\/script/gi, '<\\/script')}</script>`)
        } else if (name.endsWith('.css')) {
          source = source.replace(/<link[^>]*\brel="stylesheet"[^>]*>/,
            () => `<style>${String(asset.source).replace(/<\/style/gi, '<\\/style')}</style>`)
        } else throw new Error(`Unexpected external MCP asset: ${name}`)
        delete bundle[name]
      }
      const host = readFileSync(file('../static/js/card_renderer_host.js'), 'utf8')
      source = source.replace('<head>', () => `<head><script>${host.replace(/<\/script/gi, '<\\/script')}</script>`)
      if (/<(?:script|link)[^>]*(?:src|href)="\//.test(source)) throw new Error('MCP resource must be self-contained.')
      html.source = source
    },
  }
}

export default defineConfig({
  root: file('./src/app/mcp-template-preview'), base: './',
  plugins: [react(), tailwindcss(), singleHtmlResource()],
  resolve: { alias: [
    { find: /^@\/shared\/config\/i18n$/, replacement: file('./src/app/mcp-template-preview/i18n.ts') },
    { find: '@', replacement: file('./src') },
  ] },
  build: {
    outDir: file('./dist-mcp'), emptyOutDir: true, sourcemap: false,
    assetsInlineLimit: Infinity, cssCodeSplit: false, modulePreload: false,
    rolldownOptions: { output: { codeSplitting: false } },
  },
})
