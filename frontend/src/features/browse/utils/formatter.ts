import i18n from '@/shared/config/i18n'

export function statusLabel(status: string) {
  if (status === 'new') return i18n.t('browse:card_table.status.new')
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return i18n.t('browse:card_table.status.learning')
  }
  if (status === 'due' || status === 'review') return i18n.t('browse:card_table.status.due')
  return status || i18n.t('browse:card_table.status.other')
}

export function statusVariant(status: string) {
  if (status === 'due' || status === 'review') return 'destructive' as const
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return 'outline' as const
  }
  return 'secondary' as const
}
