export type FeedbackCategory = 'bug' | 'feature' | 'ui' | 'other'

export interface TicketReply {
  id: string
  ticket_id: string
  user_id?: string
  sender_name?: string
  message: string
  is_admin_reply?: boolean
  created_at: string
}

export interface TicketItem {
  id: string
  ticket_code: string
  category: string
  title: string
  description: string
  reproduce_steps?: string
  screen_url?: string
  screen_name?: string
  attachment_urls?: string[]
  status: string
  sender_name?: string
  user_email?: string
  created_at: string
  updated_at?: string
  replies?: TicketReply[]
  replies_count?: number
}

export interface SupportDonation {
  configured: boolean
  title: string
  description: string
  account_name: string
  account_number: string
  thank_you_message: string
  qr_image_url: string | null
  limits: {
    min_amount_minor: number
    max_amount_minor: number
    suggested_amounts: number[]
  }
}

export interface CheckoutDetails {
  provider?: string
  checkout_url?: string | null
  payment_link_id?: string | null
  provider_order_code?: string | null
  bank_bin?: string | null
  account_no?: string | null
  account_name?: string | null
  qr_code?: string | null
  provider_status?: string | null
  amount_minor?: number
  currency_code?: string
  payment_reference?: string | null
  merchant_order_code?: string
  expires_at?: string | null
  provider_metadata?: Record<string, any>
}

export interface CheckoutResult {
  checkout_mode?: string
  created?: boolean
  payment_required?: boolean
  checkout_url?: string
  payment_link_id?: string
  provider_order_code?: string
  checkout?: CheckoutDetails
  order?: any
  error?: string
  message?: string
}

export interface DonationStatusResult {
  id?: string | null
  merchant_order_code?: string
  status: string
  status_display?: {
    code: string
    tone: string
    label: string
    headline: string
    description: string
  }
  total_amount_minor?: number
  currency_code?: string
  headline?: string
  message?: string
}
