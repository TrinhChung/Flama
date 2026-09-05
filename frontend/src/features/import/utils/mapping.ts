import type { FieldMapping, NoteField, ParsedColumn } from '../hooks/useFileImportWizard'

/**
 * Normalizes field or column name for fuzzy matching by lowercasing
 * and stripping spaces, hyphens, and underscores.
 */
export function normalizeFieldName(val: string | null | undefined): string {
  if (!val) return ''
  return val.toLowerCase().replace(/[\s_\-]+/g, '')
}

/**
 * Builds suggested column-to-field mapping:
 * - Pass 1: Match by normalized name (field name == column name or display) if header is present.
 * - Pass 2: Sequential fallback ("xếp lần lượt") for unmapped fields into unused columns in order.
 * - Remaining unmapped fields (if fields > columns) are marked as 'ignore'.
 */
export function buildSuggestedMapping(
  fields: NoteField[],
  columns: ParsedColumn[],
  hasHeader: boolean = true
): Record<string, FieldMapping> {
  const result: Record<string, FieldMapping> = {}
  if (!fields.length || !columns.length) return result

  const sortedFields = [...fields].sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
  const usedColumnIndices = new Set<number>()

  // Pass 1: Auto-match by name if header is present
  if (hasHeader) {
    for (const field of sortedFields) {
      const normFieldName = normalizeFieldName(field.name)
      if (!normFieldName) continue

      // Look for a column whose name or display matches field.name
      const matchedCol = columns.find((col) => {
        if (usedColumnIndices.has(col.index)) return false
        const normColName = normalizeFieldName(col.name)
        const normDisplay = normalizeFieldName(col.display)
        return normColName === normFieldName || (normColName === '' && normDisplay === normFieldName)
      })

      if (matchedCol) {
        result[field.name] = {
          source_type: 'column',
          column_index: matchedCol.index,
          constant_value: '',
        }
        usedColumnIndices.add(matchedCol.index)
      }
    }
  }

  // Pass 2: Sequential fallback ("xếp lần lượt") for unmapped fields
  for (let i = 0; i < sortedFields.length; i++) {
    const field = sortedFields[i]
    if (result[field.name]) continue // already mapped in Pass 1

    let targetColIndex: number | null = null

    // Prefer column at index i if it exists and hasn't been used yet
    if (i < columns.length && !usedColumnIndices.has(columns[i].index)) {
      targetColIndex = columns[i].index
    } else {
      // Find the first unused column
      const nextUnused = columns.find((c) => !usedColumnIndices.has(c.index))
      if (nextUnused) {
        targetColIndex = nextUnused.index
      }
    }

    if (targetColIndex !== null) {
      result[field.name] = {
        source_type: 'column',
        column_index: targetColIndex,
        constant_value: '',
      }
      usedColumnIndices.add(targetColIndex)
    } else {
      // No column available for this field
      result[field.name] = {
        source_type: 'ignore',
        column_index: null,
        constant_value: '',
      }
    }
  }

  return result
}
