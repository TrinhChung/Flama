export type NoteWriteRevisionSnapshot = {
  content_revision?: number
  field_schema_revision?: number
  overlay_revision?: number
  deck_install_id?: string
}

export function noteWritePreconditions(snapshot?: NoteWriteRevisionSnapshot | null) {
  if (snapshot?.deck_install_id && Number.isSafeInteger(snapshot.overlay_revision)) {
    return { expected_overlay_revision: snapshot.overlay_revision }
  }
  return {
    ...(Number.isSafeInteger(snapshot?.content_revision)
      ? { expected_content_revision: snapshot!.content_revision } : {}),
    ...(Number.isSafeInteger(snapshot?.field_schema_revision)
      ? { expected_field_schema_revision: snapshot!.field_schema_revision } : {}),
  }
}
