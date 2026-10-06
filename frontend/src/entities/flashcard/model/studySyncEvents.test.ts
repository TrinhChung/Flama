// @vitest-environment jsdom

import { describe, expect, it, vi } from 'vitest'
import {
  dispatchStudyCardUpdate,
  dispatchStudyTemplateUpdate,
  STUDY_CARD_UPDATED_EVENT,
  STUDY_TEMPLATE_UPDATED_EVENT,
} from './studySyncEvents'

describe('studySyncEvents', () => {
  it('dispatches custom window event for card updates', () => {
    const handler = vi.fn()
    window.addEventListener(STUDY_CARD_UPDATED_EVENT, handler)

    dispatchStudyCardUpdate({
      cardId: 'card-1',
      noteId: 'note-1',
      fieldValues: { Word: '犬' },
    })

    expect(handler).toHaveBeenCalledTimes(1)
    const event = handler.mock.calls[0][0] as CustomEvent
    expect(event.detail).toEqual({
      cardId: 'card-1',
      noteId: 'note-1',
      fieldValues: { Word: '犬' },
    })

    window.removeEventListener(STUDY_CARD_UPDATED_EVENT, handler)
  })

  it('dispatches custom window event for template updates', () => {
    const handler = vi.fn()
    window.addEventListener(STUDY_TEMPLATE_UPDATED_EVENT, handler)

    dispatchStudyTemplateUpdate({
      templateId: 'tmpl-1',
      updated: { front_html: '<div>{{Word}}</div>' },
    })

    expect(handler).toHaveBeenCalledTimes(1)
    const event = handler.mock.calls[0][0] as CustomEvent
    expect(event.detail).toEqual({
      templateId: 'tmpl-1',
      updated: { front_html: '<div>{{Word}}</div>' },
    })

    window.removeEventListener(STUDY_TEMPLATE_UPDATED_EVENT, handler)
  })
})
