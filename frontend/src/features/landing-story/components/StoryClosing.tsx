import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { COMMUNITY_ANCHOR } from '../data/storyChapters'

type StoryClosingProps = {
  signedIn: boolean
}

/** Closing call to action. It stays in the flow and never chases the viewer. */
export function StoryClosing({ signedIn }: StoryClosingProps) {
  return (
    <div className="mt-8 flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        {signedIn ? (
          <Button asChild className="h-12 rounded-full px-6 text-base">
            <Link to="/dashboard">
              Tiếp tục hành trình
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        ) : (
          <Button asChild className="h-12 rounded-full px-6 text-base">
            <Link to="/register">
              Cùng truyền lửa
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        )}
        {signedIn ? (
          <Button asChild variant="ghost" className="h-12 rounded-full px-4 text-base">
            <Link to="/marketplace/decks">Khám phá bộ thẻ cộng đồng</Link>
          </Button>
        ) : (
          <Button asChild variant="ghost" className="h-12 rounded-full px-4 text-base">
            <a href={`#${COMMUNITY_ANCHOR}`}>Khám phá cách Flama kết nối tri thức</a>
          </Button>
        )}
      </div>
      {signedIn ? null : (
        <p className="story-closing-note">
          Bắt đầu bằng việc học, rồi chia sẻ khi bạn sẵn sàng.
        </p>
      )}
    </div>
  )
}
