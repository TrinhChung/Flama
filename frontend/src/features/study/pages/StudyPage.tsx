import { useEffect, useRef, useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'
import { useBootstrap } from '@/shared/api/bootstrap'

type Rating = 'again' | 'hard' | 'good' | 'easy'

type StudyPayload = {
  card_id: string | null
  rendered_front_html?: string
  rendered_back_html?: string
  intervals_preview?: Record<Rating, { label?: string }>
  new_count?: number
  learn_count?: number
  due_count?: number
  session_state?: string
  next_due_at?: string | null
  message?: string
}

type AnswerResponse = {
  success: boolean
  next_card_payload: StudyPayload | null
}

const ratings: Array<{
  value: Rating
  label: string
  variant: React.ComponentProps<typeof Button>['variant']
  icon?: boolean
}> = [
  { value: 'again', label: 'Again', variant: 'destructive', icon: true },
  { value: 'hard', label: 'Hard', variant: 'outline' },
  { value: 'good', label: 'Good', variant: 'secondary' },
  { value: 'easy', label: 'Easy', variant: 'default' },
]

export function StudyPage() {
  const [searchParams] = useSearchParams()
  const deckId = searchParams.get('deck_id')
  const bootstrap = useBootstrap().data
  const queryClient = useQueryClient()
  const [revealed, setRevealed] = useState(false)
  const startedAtRef = useRef(Date.now())
  const queryKey = ['study', 'next', deckId] as const

  const studyQuery = useQuery({
    queryKey,
    queryFn: () =>
      appApi.get<StudyPayload>('/api/study/next', {
        scope: 'deck',
        scope_id: deckId,
      }),
    enabled: Boolean(deckId),
  })
  const card = studyQuery.data

  useEffect(() => {
    startedAtRef.current = Date.now()
    setRevealed(false)
  }, [card?.card_id])

  const answerMutation = useMutation({
    mutationFn: (rating: Rating) => {
      if (!card?.card_id) throw new Error('Không có thẻ để chấm.')
      return appApi.mutate<AnswerResponse>(
        `/api/study/${card.card_id}/answer`,
        'POST',
        {
          rating,
          scope: 'deck',
          scope_id: deckId,
          timezone: bootstrap?.user?.timezone,
          duration_ms: Math.max(0, Date.now() - startedAtRef.current),
        },
      )
    },
    onSuccess: (result) => {
      if (result.next_card_payload) {
        queryClient.setQueryData(queryKey, result.next_card_payload)
      } else {
        queryClient.invalidateQueries({ queryKey })
      }
      setRevealed(false)
    },
  })

  if (!deckId) {
    return (
      <Page className="max-w-4xl">
        <PageHeader
          title="Phiên học"
          description="Chọn một deck từ dashboard để bắt đầu."
        />
        <EmptyState
          title="Chưa chọn deck"
          description="Phiên học cần một deck cụ thể để giữ đúng scope scheduler."
          action={<Button asChild><Link to="/dashboard">Về dashboard</Link></Button>}
        />
      </Page>
    )
  }

  if (studyQuery.isPending) {
    return <PageLoading label="Đang chuẩn bị phiên học…" />
  }
  if (studyQuery.error) return <Page><PageError error={studyQuery.error} /></Page>

  const remaining =
    Number(card?.new_count || 0) +
    Number(card?.learn_count || 0) +
    Number(card?.due_count || 0)

  return (
    <Page className="max-w-4xl">
      <PageHeader
        title="Phiên học"
        description={`Deck #${deckId}`}
        actions={<Badge variant="secondary">Còn {remaining} thẻ</Badge>}
      />

      {answerMutation.error ? <PageError error={answerMutation.error} /> : null}

      {card?.card_id ? (
        <Card className="min-h-105 shadow-lg">
          <CardContent className="flex min-h-105 flex-col items-stretch justify-center p-8 md:p-12">
            <div
              className="study-card-content text-center"
              dangerouslySetInnerHTML={{
                __html: revealed
                  ? card.rendered_back_html || ''
                  : card.rendered_front_html || '',
              }}
            />
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title={card?.session_state === 'waiting' ? 'Đang chờ thẻ kế tiếp' : 'Không còn thẻ'}
          description={
            card?.message ||
            (card?.next_due_at
              ? `Thẻ kế tiếp đến hạn lúc ${new Date(card.next_due_at).toLocaleString('vi-VN')}.`
              : 'Deck này chưa có thẻ đến hạn để học.')
          }
          action={<Button asChild variant="outline"><Link to="/dashboard">Về dashboard</Link></Button>}
        />
      )}

      {card?.card_id && !revealed ? (
        <Button size="lg" onClick={() => setRevealed(true)}>
          Hiện đáp án
        </Button>
      ) : null}

      {card?.card_id && revealed ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {ratings.map((rating) => (
            <Button
              key={rating.value}
              size="lg"
              variant={rating.variant}
              disabled={answerMutation.isPending}
              onClick={() => answerMutation.mutate(rating.value)}
            >
              {rating.icon ? <RotateCcw /> : null}
              {rating.label}
              {card.intervals_preview?.[rating.value]?.label
                ? ` · ${card.intervals_preview[rating.value].label}`
                : ''}
            </Button>
          ))}
        </div>
      ) : null}
    </Page>
  )
}
