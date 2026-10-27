import { BookOpen, HandHeart, Sprout, type LucideIcon } from 'lucide-react'
import { communityActions, storyFaqs } from '../data/storyChapters'

const actionIcons: LucideIcon[] = [BookOpen, HandHeart, Sprout]

/** The calm information block after the story: three actions and a short FAQ. */
export function StoryCommunity() {
  return (
    <section aria-labelledby="story-actions-title" className="bg-background">
      <div className="mx-auto max-w-[1280px] px-5 py-16 sm:px-10 lg:px-16 lg:py-24">
        <h2 id="story-actions-title" className="text-2xl font-bold tracking-tight sm:text-3xl">
          Ba cách tiếp nối ngọn lửa trên Flama
        </h2>
        <ul className="mt-8 grid gap-4 md:grid-cols-3">
          {communityActions.map((action, index) => {
            const Icon = actionIcons[index]
            return (
              <li key={action.title} className="rounded-2xl border border-border bg-secondary/40 p-6">
                <Icon aria-hidden="true" className="size-6 text-primary" />
                <h3 className="mt-4 text-lg font-semibold">{action.title}</h3>
                <p className="mt-2 text-base leading-relaxed text-muted-foreground">{action.description}</p>
              </li>
            )
          })}
        </ul>

        <h2 className="mt-16 text-2xl font-bold tracking-tight sm:text-3xl">Câu hỏi thường gặp</h2>
        <div className="mt-6 divide-y divide-border rounded-2xl border border-border">
          {storyFaqs.map((faq) => (
            <details key={faq.question} className="group px-5 py-1">
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 py-3 text-base font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
                {faq.question}
                <span aria-hidden="true" className="text-xl text-primary transition-transform group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="pb-4 text-base leading-relaxed text-muted-foreground">{faq.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
