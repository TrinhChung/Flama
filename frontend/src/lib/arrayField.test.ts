import { describe, expect, it } from 'vitest'
import {
  arrayCodeToLines,
  arrayLinesToCode,
  fieldValueEditorText,
  isArrayField,
  isValidArrayJson,
  normalizeArrayFieldValues,
  normalizeArrayValue,
  parseArrayItems,
  parseArrayValue,
  serializeArrayFieldValues,
} from './arrayField'

describe('array field values', () => {
  it('keeps order and repeated translations while trimming empty lines', () => {
    expect(normalizeArrayValue('  ăn \r\n\n dùng   bữa\nĂN\r')).toBe('ăn\ndùng bữa\nĂN')
    expect(normalizeArrayValue('xử lý đồng thời\nkhác\nxử lý đồng thời')).toBe('xử lý đồng thời\nkhác\nxử lý đồng thời')
  })

  it('normalizes json array strings back into lines', () => {
    expect(normalizeArrayValue('["ăn", "dùng bữa"]')).toBe('ăn\ndùng bữa')
    expect(normalizeArrayValue('[\n  "mục 1",\n  "mục 2"\n]')).toBe('mục 1\nmục 2')
  })

  it('preserves nested lists, empty items, duplicates and multiline items in code and API payloads', () => {
    const value = [['a', 'b'], [], '', 'a', 'line 1\nline 2']
    expect(JSON.parse(arrayLinesToCode(value))).toEqual(value)
    expect(parseArrayValue(JSON.stringify(value))).toEqual(value)
    expect(serializeArrayFieldValues(
      { Answer: JSON.stringify(value), Word: '猫' },
      [{ name: 'Answer', field_type: 'array' }, { name: 'Word', field_type: 'text' }],
    )).toEqual({ Answer: value, Word: '猫' })
    expect(serializeArrayFieldValues({ Answer: value }, [{ name: 'Answer', field_type: 'array' }]).Answer).toBe(value)
  })

  it('accepts text and nested lists in JSON code, rejecting objects, numbers and null', () => {
    expect(isValidArrayJson('[["a"], "b"]')).toBe(true)
    for (const invalid of ['[1]', '[null]', '[true]', '[{}]', '[["a", 1]]']) {
      expect(isValidArrayJson(invalid)).toBe(false)
    }
  })

  it('converts legacy lines to native arrays while keeping repeated items', () => {
    expect(serializeArrayFieldValues(
      { Answer: ' a \n\na', Other: ' unchanged ' },
      [{ name: 'Answer', field_type: 'array' }],
    )).toEqual({ Answer: ['a', 'a'], Other: ' unchanged ' })
    expect(normalizeArrayFieldValues(
      { Answer: '[["a", "b"], "c"]' }, [{ name: 'Answer', field_type: 'array' }],
    )).toEqual({ Answer: '[["a", "b"], "c"]' })
  })

  it('shows a stored list one item per line in editors', () => {
    expect(fieldValueEditorText(['ăn', 'dùng bữa'])).toBe('ăn\ndùng bữa')
    expect(fieldValueEditorText([['a', 'b'], ['c']])).toBe('a\nb\nc')
    expect(fieldValueEditorText('ăn\nuống')).toBe('ăn\nuống')
    expect(fieldValueEditorText(null)).toBe('')
  })

  it('converts between lines and code JSON arrays', () => {
    expect(arrayLinesToCode('ăn\ndùng bữa')).toBe('[\n  "ăn",\n  "dùng bữa"\n]')
    expect(arrayLinesToCode(['ăn', 'dùng bữa'])).toBe('[\n  "ăn",\n  "dùng bữa"\n]')
    expect(arrayLinesToCode('đơn mục', false)).toBe('["đơn mục"]')
    expect(arrayLinesToCode('')).toBe('[]')

    expect(arrayCodeToLines('["ăn", "dùng bữa"]')).toBe('ăn\ndùng bữa')
    expect(arrayCodeToLines('[\n  "a",\n  "b"\n]')).toBe('a\nb')

    expect(isValidArrayJson('["ăn", "uống"]')).toBe(true)
    expect(isValidArrayJson('[]')).toBe(true)
    expect(isValidArrayJson('["chưa đóng')).toBe(false)
    expect(isValidArrayJson('text thường')).toBe(false)

    expect(parseArrayItems('ăn\ndùng bữa')).toEqual(['ăn', 'dùng bữa'])
    expect(parseArrayItems(['ăn', 'dùng bữa'])).toEqual(['ăn', 'dùng bữa'])
    expect(parseArrayItems('["ăn", "dùng bữa"]')).toEqual(['ăn', 'dùng bữa'])
    expect(parseArrayItems(null)).toEqual([])
  })

  it('only touches array fields', () => {
    const fields = [{ name: 'Meaning', field_type: 'array' }, { name: 'Note', field_type: 'text' }]
    expect(normalizeArrayFieldValues({ Meaning: ' a \n\na', Note: ' keep \n\n ' }, fields))
      .toEqual({ Meaning: 'a\na', Note: ' keep \n\n ' })
    expect(isArrayField('ARRAY')).toBe(true)
    expect(isArrayField(undefined)).toBe(false)
  })
})

