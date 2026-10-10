import { describe, expect, it } from 'vitest'
import { isAnswersField, normalizeAnswersFieldValues, normalizeAnswersValue } from './answersField'

describe('answers field values', () => {
  it('keeps one trimmed answer per line without empties or duplicates', () => {
    expect(normalizeAnswersValue('  ăn \r\n\n dùng   bữa\nĂN\r')).toBe('ăn\ndùng bữa')
  })

  it('only touches answers fields', () => {
    const fields = [{ name: 'Meaning', field_type: 'answers' }, { name: 'Note', field_type: 'text' }]
    expect(normalizeAnswersFieldValues({ Meaning: ' a \n\na', Note: ' keep \n\n ' }, fields))
      .toEqual({ Meaning: 'a', Note: ' keep \n\n ' })
    expect(isAnswersField('ANSWERS')).toBe(true)
    expect(isAnswersField(undefined)).toBe(false)
  })
})
