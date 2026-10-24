// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import i18n from '@/shared/config/i18n'
import type { HeatmapOverviewData } from '@/shared/types/heatmap'
import { StudyHeatmap } from './StudyHeatmap'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const overview: HeatmapOverviewData = {
  year: 2026,
  today: { date: '2026-10-24', cards: 3, minutes: 1.5, sec_per_card: 30 },
  heatmap: [],
}

describe('StudyHeatmap error state', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  function render(props: Partial<Parameters<typeof StudyHeatmap>[0]>) {
    act(() => {
      root.render(<StudyHeatmap year={2026} onYearChange={() => {}} {...props} />)
    })
  }

  it('says the activity could not be read instead of drawing an empty grid', () => {
    render({ error: new Error('A NOTE authority subject is detached from its live Note.') })

    const alert = container.querySelector('[role="alert"]')
    expect(alert?.textContent).toBe(i18n.t('heatmap.error', { ns: 'dashboard' }))
    expect(container.querySelector('.stats-summary')).toBeNull()
  })

  it('keeps showing data already at hand when a refetch fails', () => {
    render({ overview, error: new Error('Network down') })

    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector('.stats-summary')).not.toBeNull()
  })

  it('shows the skeleton, not the error, while the first request is pending', () => {
    render({ loading: true })

    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector('.stats-summary')).toBeNull()
  })
})
