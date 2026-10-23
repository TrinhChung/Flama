import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { cardTemplateQueryKeys, fetchLibraryTemplate, updateLibraryTemplate, templateListingValidationError, TEMPLATE_MIN_PRICE, type TemplateWriteBody } from '@/entities/card-template'
import { fetchTemplateListing, templateMarketQueryKeys, updateTemplateListing } from '../api/templateMarketApi'
import type { MarketTemplatePricing, TemplateListingStatus } from '../model/types'

export function useTemplateListingForm(templateId: string, onDone: () => void, onTemplateChanged?: () => void) {
  const { t } = useTranslation('marketplace')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const listingQuery = useQuery({
    queryKey: templateMarketQueryKeys.listing(templateId),
    queryFn: ({ signal }) => fetchTemplateListing(templateId, signal),
  })
  const templateQuery = useQuery({
    queryKey: cardTemplateQueryKeys.libraryDetail(templateId),
    queryFn: ({ signal }) => fetchLibraryTemplate(templateId, signal),
  })
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [pricing, setPricing] = useState<MarketTemplatePricing>('free')
  const [price, setPrice] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const initialized = useRef(false)
  const listing = listingQuery.data
  const template = templateQuery.data
  useEffect(() => {
    if (initialized.current || !listing || !template) return
    initialized.current = true
    setDescription(template.description || '')
    setCategory(template.primary_category || '')
    setPricing(listing.pricing_mode)
    setPrice(listing.pricing_mode === 'paid' ? String(listing.price_amount_minor) : '')
  }, [listing, template])

  const mutation = useMutation({
    mutationFn: async (status: TemplateListingStatus) => {
      let templateChanged = false
      if (status === 'published' && template) {
        const metadata: TemplateWriteBody = {}
        if (description.trim() !== (template.description || '')) metadata.description = description.trim()
        if (category.trim() !== (template.primary_category || '')) metadata.primary_category = category.trim() || null
        if (Object.keys(metadata).length) {
          await updateLibraryTemplate(templateId, metadata)
          templateChanged = true
        }
      }
      const body = status === 'published'
        ? { marketplace_status: status, pricing_mode: pricing, price_amount_minor: pricing === 'paid' ? Number(price) : 0 }
        : { marketplace_status: status }
      return { listing: await updateTemplateListing(templateId, body), templateChanged }
    },
    onSuccess: ({ listing: saved, templateChanged }) => {
      queryClient.setQueryData(templateMarketQueryKeys.listing(templateId), saved)
      void queryClient.invalidateQueries({ queryKey: templateMarketQueryKeys.all })
      void queryClient.invalidateQueries({ queryKey: ['card-template'] })
      if (templateChanged) onTemplateChanged?.()
      if (saved.marketplace_status === 'published') {
        toast.success(t('templates.publish.toast_published'), {
          action: { label: t('templates.publish.view_on_market'), onClick: () => navigate(`/marketplace/templates/${encodeURIComponent(templateId)}`) },
        })
      } else {
        toast.success(t('templates.publish.toast_unlisted'))
      }
      onDone()
    },
    onError: (error: Error) => setFormError(error.message),
  })

  const submit = () => {
    setFormError(null)
    const validationError = templateListingValidationError({ description, primary_category: category, pricing_mode: pricing, price_amount_minor: Number(price) })
    if (validationError === 'description') return setFormError(t('templates.publish.error_description'))
    if (validationError === 'category') return setFormError(t('templates.publish.error_category'))
    if (validationError === 'price') {
      return setFormError(t('templates.publish.error_price', { min: TEMPLATE_MIN_PRICE.toLocaleString('vi-VN') }))
    }
    mutation.mutate('published')
  }

  return { listingQuery, templateQuery, listing, template, description, setDescription, category, setCategory, pricing, setPricing, price, setPrice, formError, mutation, submit }
}
