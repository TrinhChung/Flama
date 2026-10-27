import type { CSSProperties, ReactNode, Ref } from 'react'
import { cn } from '@/lib/utils'
import type { StoryChapter as StoryChapterData } from '../data/storyChapters'
import type { StoryMode } from '../hooks/useStoryProgress'
import { StorySceneArt } from './StoryStage'

type StoryChapterProps = {
  chapter: StoryChapterData
  index: number
  mode: StoryMode
  sectionRef: Ref<HTMLElement>
  /** Hero chapter renders its title as the page `h1`. */
  isHero?: boolean
  before?: ReactNode
  children?: ReactNode
}

const panelTone = {
  dark: 'story-panel-dark',
  dusk: 'story-panel-dusk',
  light: 'story-panel-light',
} as const

const STATIC_PROGRESS = 0.65

export function StoryChapter({
  chapter,
  index,
  mode,
  sectionRef,
  isHero = false,
  before,
  children,
}: StoryChapterProps) {
  const Heading = isHero ? 'h1' : 'h2'
  const pinned = mode === 'pinned'
  const headingId = `story-${chapter.id}-title`

  const text = (
    <div className={cn('story-panel', panelTone[chapter.tone], pinned && 'story-panel-card', isHero && 'story-panel-hero')}>
      {before}
      <p className="story-eyebrow" aria-hidden="true">
        {chapter.number}
      </p>
      <Heading id={headingId} className={isHero ? 'story-hero-title' : 'story-chapter-title'}>
        {chapter.title}
      </Heading>
      {chapter.lines.map((line) => (
        <p key={line} className="story-chapter-line">
          {line}
        </p>
      ))}
      {children}
    </div>
  )

  if (pinned) {
    return (
      <section
        ref={sectionRef}
        id={chapter.id}
        aria-labelledby={headingId}
        tabIndex={-1}
        className="story-chapter py-[12svh]"
        style={{ minHeight: `${chapter.span}svh` } as CSSProperties}
      >
        {text}
      </section>
    )
  }

  // Flow (mobile) and static modes: art and words together in the page flow.
  // Static mode alternates sides on wide screens; mobile stacks art above text.
  return (
    <section
      ref={sectionRef}
      id={chapter.id}
      aria-labelledby={headingId}
      tabIndex={-1}
      className={cn('story-chapter story-chapter-flow', `story-section-${chapter.tone}`)}
    >
      <div
        className={cn(
          'mx-auto grid max-w-[1280px] items-center gap-6 px-5 py-12 sm:px-10 lg:gap-12 lg:px-16 lg:py-20',
          index % 2 === 0
            ? 'lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]'
            : 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:[&>*:first-child]:order-2',
        )}
      >
        <StorySceneArt index={index} progress={mode === 'static' ? STATIC_PROGRESS : undefined} />
        {text}
      </div>
    </section>
  )
}
