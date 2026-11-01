import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { resolveMediaUrl } from '@/shared/config/env'
import { cn } from '@/lib/utils'
import type { ChangeRequestActor } from '../../types'

function contributorName(actor: ChangeRequestActor): string {
  return actor.display_name?.trim() || actor.username
}

/** Who sent the contribution: owners decide how much to trust it by name. */
export function ContributorIdentity({
  actor,
  caption,
  size = 'md',
}: {
  actor: ChangeRequestActor
  caption?: string | null
  size?: 'sm' | 'md'
}) {
  const name = contributorName(actor)
  const showHandle = name !== actor.username
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <Avatar className={cn('rounded-lg', size === 'sm' ? 'size-7' : 'size-9')}>
        {actor.avatar_url ? <AvatarImage src={resolveMediaUrl(actor.avatar_url)} alt="" className="object-cover" /> : null}
        <AvatarFallback className="rounded-lg bg-primary/10 font-bold text-primary">
          {name.charAt(0).toUpperCase()}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0">
        <p className={cn('truncate font-semibold', size === 'sm' ? 'text-sm' : 'text-base')}>
          {name}
          {showHandle ? (
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">@{actor.username}</span>
          ) : null}
        </p>
        {caption ? <p className="truncate text-xs text-muted-foreground">{caption}</p> : null}
      </div>
    </div>
  )
}
