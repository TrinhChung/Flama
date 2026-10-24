/** One cache identity for the Note detail used by the editor and its tools. */
export const browseQueryKeys = {
  noteTypes: ['note-types', 'browse', 'compact'] as const,
  detail: (noteId: string | null | undefined) => ['browse', 'card-detail', noteId] as const,
}
