import { describe, expect, it } from 'vitest'
import { isArrayField, normalizeArrayFieldValues, normalizeArrayValue } from './arrayField'

describe('array field values', () => {
  it('keeps order and repeated translations while trimming empty lines', () => {
    expect(normalizeArrayValue('  ăn \r\n\n dùng   bữa\nĂN\r')).toBe('ăn\ndùng bữa\nĂN')
    expect(normalizeArrayValue('xử lý đồng thời\nkhác\nxử lý đồng thời')).toBe('xử lý đồng thời\nkhác\nxử lý đồng thời')
  })

  it('only touches array fields', () => {
    const fields = [{ name: 'Meaning', field_type: 'array' }, { name: 'Note', field_type: 'text' }]
    expect(normalizeArrayFieldValues({ Meaning: ' a \n\na', Note: ' keep \n\n ' }, fields))
      .toEqual({ Meaning: 'a\na', Note: ' keep \n\n ' })
    expect(isArrayField('ARRAY')).toBe(true)
    expect(isArrayField(undefined)).toBe(false)
  })
})
