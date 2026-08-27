export type ProfileUserRole = {
  id: number
  code: string
  name: string
  description?: string | null
  is_admin: boolean
}

export type ProfileUser = {
  id: number
  username: string
  email: string
  timezone: string
  is_admin: boolean
  is_disabled: boolean
  created_at: string | null
  role: ProfileUserRole | null
}

export type ProfileEarnings = {
  total_gross_amount_minor: number
  total_gross_display: string
  total_platform_fee_amount_minor: number
  total_platform_fee_display: string
  total_net_amount_minor: number
  total_net_display: string
  total_sales_count: number
}

export type ProfileWallet = {
  balance_amount_minor: number
  balance_amount_display: string
  currency_code: string
  platform_fee_percent: number
  is_custom_fee: boolean
  payout_enabled: boolean
  payout_status_message: string
  earnings: ProfileEarnings
}

export type ProfileResponse = {
  user: ProfileUser
  wallet: ProfileWallet
}

export type ProfileTransaction = {
  id: string
  transaction_type: string
  transaction_type_label: string
  gross_amount_minor: number
  gross_amount_display: string
  platform_fee_percent: number
  platform_fee_amount_minor: number
  platform_fee_amount_display: string
  net_amount_minor: number
  net_amount_display: string
  balance_after_minor: number
  balance_after_display: string
  description: string
  buyer_user_id: number | null
  buyer_username: string
  payment_order_id: string | null
  merchant_order_code: string | null
  payment_order_item_id: string | null
  created_at: string | null
}

export type ProfileTransactionsResponse = {
  items: ProfileTransaction[]
  total: number
  page: number
  per_page: number
  pages: number
}
