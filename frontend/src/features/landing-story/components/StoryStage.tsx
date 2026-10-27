import type { CSSProperties, RefObject } from 'react'
import { storyChapters } from '../data/storyChapters'
import { Ember } from './StoryArt'
import { StoryScene } from './StoryScenes'

type StoryStageProps = {
  sceneRefs: RefObject<(SVGGElement | null)[]>
  emberRef: RefObject<SVGGElement | null>
}

const firstEmber = storyChapters[0].ember

/** Sticky desktop stage: every scene layered on one canvas, one ember on top. */
export function StoryStage({ sceneRefs, emberRef }: StoryStageProps) {
  return (
    <svg
      viewBox="0 0 800 600"
      preserveAspectRatio="xMidYMid meet"
      className="story-art block h-auto w-full"
      data-story-art
      aria-hidden="true"
      focusable="false"
    >
      {storyChapters.map((chapter, index) => (
        <g
          key={chapter.id}
          ref={(element) => {
            if (sceneRefs.current) sceneRefs.current[index] = element
          }}
          className="story-scene"
          data-active={index === 0 ? 'true' : 'false'}
          style={{ '--t': 0.4, '--v': index === 0 ? 1 : 0 } as CSSProperties}
        >
          <StoryScene index={index} />
        </g>
      ))}
      <Ember emberRef={emberRef} x={firstEmber.x} y={firstEmber.y} size={firstEmber.size} />
    </svg>
  )
}

type StorySceneArtProps = {
  index: number
  /** Fixed progress for static mode; omit to inherit `--t` from the chapter section. */
  progress?: number
}

/** One chapter's keyframe, used by mobile flow and the static fallback. */
export function StorySceneArt({ index, progress }: StorySceneArtProps) {
  const ember = storyChapters[index].ember
  const style = { '--v': 1, ...(progress === undefined ? {} : { '--t': progress }) } as CSSProperties
  return (
    <svg
      viewBox="0 0 800 600"
      preserveAspectRatio="xMidYMid meet"
      className="story-art block h-auto w-full"
      data-story-art
      aria-hidden="true"
      focusable="false"
    >
      <g className="story-scene" style={style}>
        <StoryScene index={index} />
        <Ember x={ember.x} y={ember.y} size={ember.size} />
      </g>
    </svg>
  )
}
