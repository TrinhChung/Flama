import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { resources } from './testResources'

const sourceRoot = join(dirname(fileURLToPath(import.meta.url)), '../../..')

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.tsx?$/.test(entry.name) && !/\.test\./.test(entry.name) ? [path] : []
  })
}

function resourceAt(locale: 'vi' | 'en', namespace: string, key: string): unknown {
  let value: unknown = resources[locale][namespace as keyof typeof resources.en]
  for (const segment of key.split('.')) {
    if (!value || typeof value !== 'object') return undefined
    value = (value as Record<string, unknown>)[segment]
  }
  return value
}

describe('translation resource contracts', () => {
  it(
    'provides both languages for static keys used by localized components',
    () => {
      const missing: string[] = []
    for (const path of sourceFiles(sourceRoot)) {
      const source = ts.createSourceFile(path, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true)
      const namespaces = new Set<string>()
      const keys: { key: string; returnObjects: boolean }[] = []
      const visit = (node: ts.Node) => {
        if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
          const argument = node.arguments[0]
          if (node.expression.text === 'useTranslation') {
            if (!argument) namespaces.add('common')
            else if (ts.isStringLiteral(argument)) namespaces.add(argument.text)
          }
          if (node.expression.text === 't' && argument && ts.isStringLiteral(argument)) {
            const options = node.arguments[1]
            const returnObjects = !!options && ts.isObjectLiteralExpression(options)
              && options.properties.some((property) => ts.isPropertyAssignment(property)
                && property.name.getText(source) === 'returnObjects'
                && property.initializer.kind === ts.SyntaxKind.TrueKeyword)
            keys.push({ key: argument.text, returnObjects })
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(source)
      // Files with multiple translation scopes require a scope-aware check.
      if (namespaces.size !== 1) continue
      const [defaultNamespace] = namespaces
      for (const { key, returnObjects } of keys) {
        const separator = key.indexOf(':')
        const namespace = separator < 0 ? defaultNamespace : key.slice(0, separator)
        const resourceKey = separator < 0 ? key : key.slice(separator + 1)
        for (const locale of ['vi', 'en'] as const) {
          const value = resourceAt(locale, namespace, resourceKey)
          if (value === undefined || (!returnObjects && typeof value !== 'string')) {
            missing.push(`${locale}:${namespace}:${resourceKey} (${path})`)
          }
        }
      }
    }
    expect([...new Set(missing)]).toEqual([])
  }, 30_000)
})
