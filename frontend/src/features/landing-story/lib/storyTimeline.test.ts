import { describe, expect, it } from 'vitest'
import {
  LAST_CHAPTER_STOP,
  emberAt,
  lightAt,
  sceneState,
  storyPosition,
} from './storyTimeline'

describe('storyPosition', () => {
  it('starts at zero before the first chapter reaches the reading line', () => {
    expect(storyPosition([-0.2, -1.4, -2.6])).toBe(0)
  })

  it('combines the active chapter index with its local progress', () => {
    expect(storyPosition([1.4, 0.25, -0.8])).toBeCloseTo(1.25)
  })

  it('stops inside the last chapter so the closing stays still', () => {
    expect(storyPosition([3, 2, 1.5])).toBe(2 + LAST_CHAPTER_STOP)
    expect(storyPosition([2.9, 1.9, 0.95])).toBe(2 + LAST_CHAPTER_STOP)
  })
})

describe('sceneState', () => {
  it('shows the first scene immediately', () => {
    expect(sceneState(0, 0, 9).v).toBe(1)
  })

  it('brings the next scene in before the current one leaves', () => {
    const outgoing = sceneState(0.9, 0, 9)
    const incoming = sceneState(0.9, 1, 9)
    expect(outgoing.v).toBeGreaterThan(0)
    expect(incoming.v).toBeGreaterThan(0)
  })

  it('keeps the last scene visible at the end', () => {
    expect(sceneState(8 + LAST_CHAPTER_STOP, 8, 9).v).toBe(1)
  })
})

describe('emberAt', () => {
  const anchors = [
    { x: 0, y: 0, size: 1 },
    { x: 100, y: 50, size: 2 },
  ]

  it('holds at the chapter anchor', () => {
    expect(emberAt(0.5, anchors)).toEqual({ x: 0, y: 0, size: 1 })
  })

  it('arrives at the next anchor when the handoff completes', () => {
    const ember = emberAt(1, anchors)
    expect(ember.x).toBeCloseTo(100)
    expect(ember.y).toBeCloseTo(50)
  })
})

describe('lightAt', () => {
  it('moves from dark to light across the middle of the journey', () => {
    expect(lightAt(1)).toBe(0)
    expect(lightAt(7)).toBe(1)
  })
})
