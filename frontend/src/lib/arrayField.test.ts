import { describe, expect, it } from 'vitest'
import { isArrayField, normalizeArrayFieldValues, normalizeArrayValue } from './arrayField'

describe('array field values', () => {
  it('keeps one trimmed item per line without empties or duplicates', () => {
    expect(normalizeArrayValue('  ăn \r\n\n dùng   bữa\nĂN\r')).toBe('ăn\ndùng bữa')
  })

  it('only touches array fields', () => {
    const fields = [{ name: 'Meaning', field_type: 'array' }, { name: 'Note', field_type: 'text' }]
    expect(normalizeArrayFieldValues({ Meaning: ' a \n\na', Note: ' keep \n\n ' }, fields))
      .toEqual({ Meaning: 'a', Note: ' keep \n\n ' })
    expect(isArrayField('ARRAY')).toBe(true)
    expect(isArrayField(undefined)).toBe(false)
  })
})
