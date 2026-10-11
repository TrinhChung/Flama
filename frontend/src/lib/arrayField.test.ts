import { describe, expect, it } from 'vitest'
import { fieldValueEditorText, isArrayField, normalizeArrayFieldValues, normalizeArrayValue } from './arrayField'

describe('array field values', () => {
  it('keeps order and repeated translations while trimming empty lines', () => {
    expect(normalizeArrayValue('  ăn \r\n\n dùng   bữa\nĂN\r')).toBe('ăn\ndùng bữa\nĂN')
    expect(normalizeArrayValue('xử lý đồng thời\nkhác\nxử lý đồng thời')).toBe('xử lý đồng thời\nkhác\nxử lý đồng thời')
  })

  it('shows a stored list one item per line in editors', () => {
    expect(fieldValueEditorText(['ăn', 'dùng bữa'])).toBe('ăn\ndùng bữa')
    expect(fieldValueEditorText([['a', 'b'], ['c']])).toBe('a\nb\nc')
    expect(fieldValueEditorText('ăn\nuống')).toBe('ăn\nuống')
    expect(fieldValueEditorText(null)).toBe('')
  })

  it('only touches array fields', () => {
    const fields = [{ name: 'Meaning', field_type: 'array' }, { name: 'Note', field_type: 'text' }]
    expect(normalizeArrayFieldValues({ Meaning: ' a \n\na', Note: ' keep \n\n ' }, fields))
      .toEqual({ Meaning: 'a\na', Note: ' keep \n\n ' })
    expect(isArrayField('ARRAY')).toBe(true)
    expect(isArrayField(undefined)).toBe(false)
  })
})
