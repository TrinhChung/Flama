import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '@/shared/api/client'
import {
  TAXONOMY_DOMAINS as FALLBACK_DOMAINS,
  TAXONOMY_SUBJECTS as FALLBACK_SUBJECTS,
  TAXONOMY_DIFFICULTIES as FALLBACK_DIFFICULTIES,
  TAXONOMY_FRAMEWORKS as FALLBACK_FRAMEWORKS,
  getGoalsForSubject as fallbackGoalsForSubject,
  getTopicsForSubject as fallbackTopicsForSubject,
} from '../utils/publishTaxonomyConstants'

export type TaxonomyDomainItem = {
  id: string
  label: string
}

export type TaxonomySubjectItem = {
  id: string
  label: string
  domain: string
}

export type TaxonomyOptionItem = {
  id: string
  label: string
  sub?: string
}

export type TaxonomyFrameworkLevelItem = {
  id: string
  label: string
  difficulty_band: 'beginner' | 'intermediate' | 'advanced'
  suggestedTags?: string[]
}

export type TaxonomyFrameworkItem = {
  id: string
  label: string
  levels: TaxonomyFrameworkLevelItem[]
}

export type TaxonomySubjectPack = {
  frameworks: TaxonomyFrameworkItem[]
  learning_goals: TaxonomyOptionItem[]
  primary_topics: TaxonomyOptionItem[]
  format_features: TaxonomyOptionItem[]
}

export type TaxonomySchemaResponse = {
  content_type: string
  domains: TaxonomyDomainItem[]
  subjects: TaxonomySubjectItem[]
  difficulty_bands: TaxonomyOptionItem[]
  audiences: TaxonomyOptionItem[]
  learning_goals: TaxonomyOptionItem[]
  primary_topics: TaxonomyOptionItem[]
  format_features: TaxonomyOptionItem[]
  best_used_for: TaxonomyOptionItem[]
  subject_packs: Record<string, TaxonomySubjectPack>
}

export function useTaxonomySchema(contentType: 'deck_marketplace_item' | 'note_type' = 'deck_marketplace_item') {
  const query = useQuery({
    queryKey: ['taxonomy-schema', contentType],
    queryFn: () => apiRequest<TaxonomySchemaResponse>(`/api/marketplace/taxonomy/schema?content_type=${contentType}`),
    staleTime: 1000 * 60 * 30, // 30 minutes
  })

  const schema = query.data

  const domains = schema?.domains && schema.domains.length > 0 ? schema.domains : FALLBACK_DOMAINS
  
  const subjectsByDomain = (domainId: string): TaxonomySubjectItem[] => {
    if (schema?.subjects && schema.subjects.length > 0) {
      return schema.subjects.filter((s) => s.domain === domainId)
    }
    return FALLBACK_SUBJECTS[domainId]
      ? FALLBACK_SUBJECTS[domainId].map((s) => ({ ...s, domain: domainId }))
      : FALLBACK_SUBJECTS.other.map((s) => ({ ...s, domain: domainId }))
  }

  const frameworksForSubject = (subjectId: string): TaxonomyFrameworkItem[] => {
    if (schema?.subject_packs && schema.subject_packs[subjectId]) {
      return schema.subject_packs[subjectId].frameworks || []
    }
    return (FALLBACK_FRAMEWORKS[subjectId] || []) as TaxonomyFrameworkItem[]
  }

  const goalsForSubject = (subjectId: string, domainId?: string): TaxonomyOptionItem[] => {
    if (schema?.subject_packs && schema.subject_packs[subjectId]?.learning_goals?.length) {
      return schema.subject_packs[subjectId].learning_goals
    }
    return fallbackGoalsForSubject(subjectId, domainId)
  }

  const topicsForSubject = (subjectId: string, domainId?: string): TaxonomyOptionItem[] => {
    if (schema?.subject_packs && schema.subject_packs[subjectId]?.primary_topics?.length) {
      return schema.subject_packs[subjectId].primary_topics
    }
    return fallbackTopicsForSubject(subjectId, domainId)
  }

  const difficulties = schema?.difficulty_bands && schema.difficulty_bands.length > 0
    ? schema.difficulty_bands
    : FALLBACK_DIFFICULTIES

  return {
    isLoading: query.isLoading,
    schema,
    domains,
    subjectsByDomain,
    frameworksForSubject,
    goalsForSubject,
    topicsForSubject,
    difficulties,
  }
}
