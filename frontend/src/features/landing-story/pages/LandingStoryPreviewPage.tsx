import { useEffect, useRef } from 'react'
import { ArrowDown } from 'lucide-react'
import { useBootstrap } from '@/shared/api/bootstrap'
import { StoryChapter } from '../components/StoryChapter'
import { StoryClosing } from '../components/StoryClosing'
import { StoryCommunity } from '../components/StoryCommunity'
import { StoryDefs } from '../components/StoryArt'
import { StoryPreviewShell } from '../components/StoryPreviewShell'
import { StoryStage } from '../components/StoryStage'
import { COMMUNITY_ANCHOR, storyChapters } from '../data/storyChapters'
import { useStoryMotionPreference } from '../hooks/useStoryMotionPreference'
import { useStoryProgress, type StoryMode } from '../hooks/useStoryProgress'
import '../styles/story.css'

const PAGE_TITLE = 'Flama · Truyền lửa, cùng mở rộng tri thức (bản xem trước)'

/** Review-only route: keep it out of search results and restore the head on exit. */
function usePreviewDocumentMeta() {
  useEffect(() => {
    const previousTitle = document.title
    document.title = PAGE_TITLE
    const robots = document.createElement('meta')
    robots.name = 'robots'
    robots.content = 'noindex, nofollow'
    document.head.appendChild(robots)
    return () => {
      document.title = previousTitle
      robots.remove()
    }
  }, [])
}

export function LandingStoryPreviewPage() {
  const { data: bootstrap } = useBootstrap()
  const signedIn = Boolean(bootstrap?.user)
  const { motionEnabled, isWide, toggleMotion } = useStoryMotionPreference()
  const mode: StoryMode = !motionEnabled ? 'static' : isWide ? 'pinned' : 'flow'

  const rootRef = useRef<HTMLDivElement>(null)
  const sectionRefs = useRef<(HTMLElement | null)[]>([])
  const sceneRefs = useRef<(SVGGElement | null)[]>([])
  const emberRef = useRef<SVGGElement>(null)

  usePreviewDocumentMeta()
  useStoryProgress(mode, { rootRef, sectionRefs, sceneRefs, emberRef })

  const lastIndex = storyChapters.length - 1

  const chapters = storyChapters.map((chapter, index) => (
    <StoryChapter
      key={`${mode}-${chapter.id}`}
      chapter={chapter}
      index={index}
      mode={mode}
      isHero={index === 0}
      sectionRef={(element) => {
        sectionRefs.current[index] = element
      }}
      before={
        index === 0 ? (
          <p className="story-kicker">Flama · Cùng học, cùng chia sẻ</p>
        ) : undefined
      }
    >
      {index === 0 ? (
        <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
          <a href={`#${COMMUNITY_ANCHOR}`} className="story-link">
            Đến với Flama
          </a>
          <span className="story-hint">
            <ArrowDown aria-hidden="true" className="size-4" />
            Cuộn để theo ngọn lửa
          </span>
        </div>
      ) : null}
      {index === lastIndex ? <StoryClosing signedIn={signedIn} /> : null}
    </StoryChapter>
  ))

  return (
    <div ref={rootRef} className="story-root" data-mode={mode}>
      <StoryDefs />
      <StoryPreviewShell
        signedIn={signedIn}
        motionEnabled={motionEnabled}
        onToggleMotion={toggleMotion}
      >
        <main>
          {mode === 'pinned' ? (
            <div className="story-track mx-auto grid max-w-[1600px] grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-10 px-10 xl:px-16">
              <div>{chapters}</div>
              <div className="story-stage">
                <StoryStage key={mode} sceneRefs={sceneRefs} emberRef={emberRef} />
              </div>
            </div>
          ) : (
            chapters
          )}
          <StoryCommunity />
        </main>
      </StoryPreviewShell>
    </div>
  )
}
