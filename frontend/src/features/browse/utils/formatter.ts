export function statusLabel(status: string) {
  if (status === 'new') return 'Mới'
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return 'Đang học'
  }
  if (status === 'due' || status === 'review') return 'Đến hạn'
  return status || 'Khác'
}

export function statusVariant(status: string) {
  if (status === 'due' || status === 'review') return 'destructive' as const
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return 'outline' as const
  }
  return 'secondary' as const
}
