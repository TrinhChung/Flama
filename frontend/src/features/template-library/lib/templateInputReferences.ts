import Mustache, { type TemplateSpans } from 'mustache'
import type { TemplateInputSpec } from '@/entities/card-template'

export type TemplateInputReferences = {
  front: Set<string>
  back: Set<string>
  unknown: string[]
  parseErrors: string[]
}

// Use the card renderer's parser for sections, triple braces and changed delimiters.
// URL aliases are context keys derived by the renderer from media inputs.
export function templateInputReferences(frontHtml: string, backHtml: string, inputs: TemplateInputSpec[]): TemplateInputReferences {
  const result: TemplateInputReferences = { front: new Set(), back: new Set(), unknown: [], parseErrors: [] }
  const unknown = new Set<string>()
  const resolve = (name: string) => {
    const exact = inputs.find((input) => input.key === name)
    if (exact) return exact.key
    const media = inputs.find((input) => ['image', 'audio', 'diagram'].includes(input.type) && [input.key + '_url', input.key + '_urls'].includes(name))
    return media?.key
  }
  const walk = (tokens: TemplateSpans, references: Set<string>) => {
    for (const token of tokens) {
      if (['name', '&', '#', '^'].includes(token[0])) {
        const name = token[1]
        if (name !== 'FrontSide' && name !== '.') {
          const key = resolve(name)
          if (key) references.add(key)
          else unknown.add(name)
        }
      }
      if (token.length > 4 && Array.isArray(token[4])) walk(token[4], references)
    }
  }
  for (const [side, html] of [['front', frontHtml], ['back', backHtml]] as const) {
    try { walk(Mustache.parse(html), result[side]) }
    catch (error) { result.parseErrors.push(error instanceof Error ? error.message : String(error)) }
  }
  result.unknown = [...unknown]
  return result
}
