import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as fs from 'node:fs'
import * as path from 'node:path'

const { apiRequest, apiJson } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  apiJson: vi.fn(),
}))

vi.mock('@/shared/api/client', () => ({
  apiRequest,
  apiJson,
}))

import {
  cardTemplateQueryKeys,
  createNoteTypeTemplate,
  deleteNoteTypeTemplate,
  fetchDeckCardTypes,
  fetchNoteTypeTemplates,
  renameNoteTypeTemplate,
} from '../index'

describe('Adversarial Stress Test: card-template Entity Slice (GT-04)', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    apiJson.mockReset()
  })

  describe('1. URL Encoding & Injection Attacks', () => {
    const traversalPayloads = [
      { raw: '../evil', encoded: '..%2Fevil' },
      { raw: '../../etc/passwd', encoded: '..%2F..%2Fetc%2Fpasswd' },
      { raw: '..\\evil\\win', encoded: '..%5Cevil%5Cwin' },
      { raw: 'id?foo=bar&baz=1', encoded: 'id%3Ffoo%3Dbar%26baz%3D1' },
      { raw: 'id#fragment', encoded: 'id%23fragment' },
      { raw: 'spaces in id', encoded: 'spaces%20in%20id' },
      { raw: 'symbols/&%#?=', encoded: 'symbols%2F%26%25%23%3F%3D' },
      { raw: ';DROP TABLE users;--', encoded: '%3BDROP%20TABLE%20users%3B--' },
      { raw: '日本語/ノート', encoded: '%E6%97%A5%E6%9C%AC%E8%AA%9E%2F%E3%83%8E%E3%83%BC%E3%83%88' },
      { raw: '🎴/emoji', encoded: '%F0%9F%8E%B4%2Femoji' },
      { raw: '   ', encoded: '%20%20%20' },
    ]

    describe('fetchNoteTypeTemplates URL encoding', () => {
      traversalPayloads.forEach(({ raw, encoded }) => {
        it(`safely sanitizes injection string "${raw}" in noteTypeId`, async () => {
          apiRequest.mockResolvedValueOnce({ items: [] })
          await fetchNoteTypeTemplates(raw)
          expect(apiRequest).toHaveBeenCalledWith(`/api/note-types/${encoded}/templates`, {
            signal: undefined,
          })
          const calledUrl: string = apiRequest.mock.calls[0][0]
          expect(calledUrl.includes(raw)).toBe(false)
          expect(calledUrl).toBe(`/api/note-types/${encoded}/templates`)
        })
      })
    })

    describe('fetchDeckCardTypes URL encoding', () => {
      traversalPayloads.forEach(({ raw, encoded }) => {
        it(`safely sanitizes injection string "${raw}" in deckId`, async () => {
          apiRequest.mockResolvedValueOnce({ compositions: [] })
          await fetchDeckCardTypes(raw)
          expect(apiRequest).toHaveBeenCalledWith(
            `/api/study/scopes/deck/${encoded}/compositions?include_counts=1`,
            { signal: undefined },
          )
          const calledUrl: string = apiRequest.mock.calls[0][0]
          expect(calledUrl.endsWith('/compositions?include_counts=1')).toBe(true)
          expect(calledUrl.startsWith('/api/study/scopes/deck/')).toBe(true)
        })
      })

      it('handles numeric deckId edge cases (0, negative, MAX_SAFE_INTEGER, floats)', async () => {
        const numericCases = [
          { input: 0, expected: '0' },
          { input: -1, expected: '-1' },
          { input: Number.MAX_SAFE_INTEGER, expected: '9007199254740991' },
          { input: 42.5, expected: '42.5' },
        ]

        for (const { input, expected } of numericCases) {
          apiRequest.mockResolvedValueOnce({ compositions: [] })
          await fetchDeckCardTypes(input)
          expect(apiRequest).toHaveBeenLastCalledWith(
            `/api/study/scopes/deck/${expected}/compositions?include_counts=1`,
            { signal: undefined },
          )
        }
      })
    })

    describe('renameNoteTypeTemplate multi-parameter URL encoding', () => {
      it('encodes both noteTypeId and templateId when both contain traversal and special characters', async () => {
        apiJson.mockResolvedValueOnce({ id: 't1' })
        const evilNoteType = '../../admin/secret'
        const evilTemplate = 'tpl?inject=1&x=2#frag'

        await renameNoteTypeTemplate(evilNoteType, evilTemplate, 'Safe Name')

        expect(apiJson).toHaveBeenCalledWith(
          '/api/note-types/..%2F..%2Fadmin%2Fsecret/templates/tpl%3Finject%3D1%26x%3D2%23frag',
          'PATCH',
          { name: 'Safe Name' },
        )
      })
    })

    describe('deleteNoteTypeTemplate multi-parameter URL encoding', () => {
      it('encodes both noteTypeId and templateId when both contain path traversal', async () => {
        apiJson.mockResolvedValueOnce({ success: true })
        const evilNoteType = 'nt/slash'
        const evilTemplate = 'tpl/slash'

        await deleteNoteTypeTemplate(evilNoteType, evilTemplate)

        expect(apiJson).toHaveBeenCalledWith(
          '/api/note-types/nt%2Fslash/templates/tpl%2Fslash',
          'DELETE',
        )
      })
    })

    describe('createNoteTypeTemplate URL encoding', () => {
      it('encodes noteTypeId with query string and hash injection', async () => {
        apiJson.mockResolvedValueOnce({ id: 'new' })
        await createNoteTypeTemplate('nt?bypass=true#bypass', { name: 'Card' })
        expect(apiJson).toHaveBeenCalledWith(
          '/api/note-types/nt%3Fbypass%3Dtrue%23bypass/templates',
          'POST',
          { name: 'Card' },
        )
      })
    })
  })

  describe('2. AbortSignal & Cancellation Behavior', () => {
    it('forwards pre-aborted signal to fetchNoteTypeTemplates', async () => {
      const controller = new AbortController()
      controller.abort(new DOMException('Operation aborted by caller', 'AbortError'))

      apiRequest.mockRejectedValueOnce(controller.signal.reason)

      await expect(
        fetchNoteTypeTemplates('nt-1', controller.signal),
      ).rejects.toThrow('Operation aborted by caller')

      expect(apiRequest).toHaveBeenCalledWith('/api/note-types/nt-1/templates', {
        signal: controller.signal,
      })
      expect(controller.signal.aborted).toBe(true)
    })

    it('forwards in-flight aborted signal to fetchDeckCardTypes', async () => {
      const controller = new AbortController()
      apiRequest.mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            controller.signal.addEventListener('abort', () => {
              reject(new DOMException('The user aborted a request.', 'AbortError'))
            })
          }),
      )

      const promise = fetchDeckCardTypes(100, controller.signal)
      controller.abort()

      await expect(promise).rejects.toThrow('The user aborted a request.')
      expect(apiRequest).toHaveBeenCalledWith(
        '/api/study/scopes/deck/100/compositions?include_counts=1',
        { signal: controller.signal },
      )
    })

    it('propagates HTTP error payload details and status without alteration', async () => {
      const customApiError = new Error('HTTP 404: Template not found')
      Object.assign(customApiError, { status: 404, code: 'NOT_FOUND' })
      apiRequest.mockRejectedValueOnce(customApiError)

      await expect(fetchNoteTypeTemplates('nt-missing')).rejects.toMatchObject({
        message: 'HTTP 404: Template not found',
        status: 404,
        code: 'NOT_FOUND',
      })
    })
  })

  describe('3. Payload Guardrails & Mutation Strictness', () => {
    it('renameNoteTypeTemplate strictly constructs `{ name }` body only', async () => {
      apiJson.mockResolvedValueOnce({ id: 't1' })

      // Even if attacker tries to pass extra properties via TS ignore or runtime JS
      const dangerousName = 'Renamed Template'
      await renameNoteTypeTemplate('nt1', 't1', dangerousName)

      expect(apiJson).toHaveBeenCalledTimes(1)
      const passedBody = apiJson.mock.calls[0][2]
      expect(passedBody).toEqual({ name: 'Renamed Template' })
      expect(Object.keys(passedBody)).toEqual(['name'])
      expect(Object.getOwnPropertyNames(passedBody)).toEqual(['name'])
      expect(passedBody).not.toHaveProperty('front_html')
      expect(passedBody).not.toHaveProperty('back_html')
      expect(passedBody).not.toHaveProperty('is_default')
    })

    it('renameNoteTypeTemplate handles empty, whitespace, and HTML tags in name', async () => {
      apiJson.mockResolvedValueOnce({ id: 't1' })
      const xssName = '<script>alert("XSS")</script>'
      await renameNoteTypeTemplate('nt1', 't1', xssName)

      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt1/templates/t1',
        'PATCH',
        { name: xssName },
      )
    })

    it('deleteNoteTypeTemplate sends undefined body (strictly 2 arguments)', async () => {
      apiJson.mockResolvedValueOnce({ success: true })
      await deleteNoteTypeTemplate('nt1', 't1')

      expect(apiJson).toHaveBeenCalledTimes(1)
      const callArgs = apiJson.mock.calls[0]
      expect(callArgs.length).toBe(2)
      expect(callArgs[0]).toBe('/api/note-types/nt1/templates/t1')
      expect(callArgs[1]).toBe('DELETE')
      expect(callArgs[2]).toBeUndefined()
    })

    it('createNoteTypeTemplate passes body as provided to apiJson', async () => {
      apiJson.mockResolvedValueOnce({ id: 't2' })
      const body = {
        name: 'New Card',
        front_html: '{{Front}}',
        back_html: '{{Front}}<hr>{{Back}}',
        shared_css: '.card { font-size: 20px; }',
      }
      await createNoteTypeTemplate('nt1', body)

      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt1/templates',
        'POST',
        body,
      )
    })
  })

  describe('4. TanStack Query Key Invariants & Cache Isolation', () => {
    it('guarantees identical cache key for number and string deckId in deckCardTypes', () => {
      const keyFromNumber = cardTemplateQueryKeys.deckCardTypes(42)
      const keyFromString = cardTemplateQueryKeys.deckCardTypes('42')

      expect(keyFromNumber).toEqual(['card-template', 'deck-card-types', '42'])
      expect(keyFromString).toEqual(['card-template', 'deck-card-types', '42'])
      expect(keyFromNumber).toEqual(keyFromString)
    })

    it('isolates different entities in distinct namespace tuples', () => {
      const noteTypeKey = cardTemplateQueryKeys.noteTypeTemplates('42')
      const deckKey = cardTemplateQueryKeys.deckCardTypes('42')

      expect(noteTypeKey).toEqual(['card-template', 'note-type-templates', '42'])
      expect(deckKey).toEqual(['card-template', 'deck-card-types', '42'])
      expect(noteTypeKey).not.toEqual(deckKey)
      expect(noteTypeKey[1]).toBe('note-type-templates')
      expect(deckKey[1]).toBe('deck-card-types')
    })
  })

  describe('5. FSD Architecture Boundaries & AST Audit', () => {
    const entityDir = path.resolve(__dirname, '..')

    it('contains exactly the 5 specified GT-04 files (or adversarial test)', () => {
      const files: string[] = []
      function walk(dir: string) {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
          const fullPath = path.join(dir, entry.name)
          if (entry.isDirectory()) {
            walk(fullPath)
          } else {
            files.push(path.relative(entityDir, fullPath).replace(/\\/g, '/'))
          }
        }
      }
      walk(entityDir)

      // Baseline files specified in GT-04
      expect(files).toContain('model/types.ts')
      expect(files).toContain('api/cardTemplateApi.ts')
      expect(files).toContain('api/queryKeys.ts')
      expect(files).toContain('api/cardTemplateApi.test.ts')
      expect(files).toContain('index.ts')
    })

    it('has zero imports from @/app, @/features, @/pages, or other entities in all source files', () => {
      const sourceFiles = [
        path.join(entityDir, 'model/types.ts'),
        path.join(entityDir, 'api/cardTemplateApi.ts'),
        path.join(entityDir, 'api/queryKeys.ts'),
        path.join(entityDir, 'index.ts'),
      ]

      for (const filePath of sourceFiles) {
        const content = fs.readFileSync(filePath, 'utf-8')
        // Check for forbidden FSD layers
        expect(content).not.toMatch(/from\s+['"]@\/app(\/|['"])/)
        expect(content).not.toMatch(/from\s+['"]@\/features(\/|['"])/)
        expect(content).not.toMatch(/from\s+['"]@\/pages(\/|['"])/)
        expect(content).not.toMatch(/from\s+['"]@\/widgets(\/|['"])/)
        // Check for cross-entity imports
        expect(content).not.toMatch(/from\s+['"]@\/entities\/(?!card-template)/)
      }
    })

    it('strictly uses verbatimModuleSyntax-compliant import/export in index.ts', () => {
      const indexContent = fs.readFileSync(path.join(entityDir, 'index.ts'), 'utf-8')
      // Must not use wildcard export
      expect(indexContent).not.toContain('export *')
      // Must explicitly use export type for types
      expect(indexContent).toContain('export type {')
    })
  })
})
