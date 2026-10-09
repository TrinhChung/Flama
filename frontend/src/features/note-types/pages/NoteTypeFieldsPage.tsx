import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faArrowLeft, faCode } from '@fortawesome/free-solid-svg-icons'
import { toast } from 'sonner'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

import { useNoteTypeFields } from '../hooks/useNoteTypeFields'
import { FieldListCard } from '../components/fields/FieldListCard'
import { AddFieldCard } from '../components/fields/AddFieldCard'
import { EditFieldCard } from '../components/fields/EditFieldCard'

export function NoteTypeFieldsPage() {
  const { t } = useTranslation('note_types')
  const {
    noteTypeId,
    query,
    detailQuery,
    fields,
    selectedField,
    selectedFieldId,
    setSelectedFieldId,
    isAddingField,
    setIsAddingField,
    editName,
    setEditName,
    editType,
    setEditType,
    editRequired,
    setEditRequired,
    editIdentity,
    setEditIdentity,
    newName,
    setNewName,
    newType,
    setNewType,
    editFormRef,
    scrollToFormOnMobile,
    createMutation,
    updateMutation,
    deleteMutation,
    reorderMutation,
    handleDragStart,
    handleDrop,
    handleMoveUp,
    handleMoveDown,
  } = useNoteTypeFields()

  if (query.isPending) return <PageLoading label={t('fields.loading')} />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const noteTypeName = detailQuery.data?.name || 'NoteType'

  return (
    <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />

      <PageHeader
        title={noteTypeName}
        description={t('fields.header.description')}
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl gap-1.5">
              <Link to="/flashcards/note-types">
                <FontAwesomeIcon icon={faArrowLeft} className="text-xs" /> {t('fields.header.back_btn')}
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl gap-1.5">
              <Link to={`/flashcards/note-types/${noteTypeId}`}>
                <FontAwesomeIcon icon={faCode} className="text-xs" /> {t('fields.header.edit_templates_btn')}
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-6 md:grid-cols-12">
        {/* Left Column: Drag-and-drop / Touch-reorder Field List */}
        <div className="md:col-span-5">
          <FieldListCard
            fields={fields}
            selectedFieldId={selectedFieldId}
            isAddingField={isAddingField}
            onSelectField={(id) => {
              setIsAddingField(false)
              setSelectedFieldId(id)
              scrollToFormOnMobile()
            }}
            onStartAddField={() => {
              setIsAddingField(true)
              setSelectedFieldId(null)
              setNewName('')
              setNewType('text')
              scrollToFormOnMobile()
            }}
            onDragStart={handleDragStart}
            onDrop={handleDrop}
            onMoveUp={handleMoveUp}
            onMoveDown={handleMoveDown}
            isReordering={reorderMutation.isPending}
          />
        </div>

        {/* Right Column: Field Property Form / Add Field Form */}
        <div ref={editFormRef} className="md:col-span-7">
          {isAddingField ? (
            <AddFieldCard
              newName={newName}
              onNewNameChange={setNewName}
              newType={newType}
              onNewTypeChange={setNewType}
              isPending={createMutation.isPending}
              onCancel={() => {
                setIsAddingField(false)
                if (fields.length) setSelectedFieldId(fields[0].id)
              }}
              onSubmit={(e) => {
                e.preventDefault()
                if (!newName.trim()) {
                  toast.error(t('fields.messages.name_required'))
                  return
                }
                createMutation.mutate({
                  name: newName.trim(),
                  field_type: newType,
                  required: false,
                  identity_role: null,
                })
              }}
            />
          ) : selectedField ? (
            <EditFieldCard
              selectedField={selectedField}
              editName={editName}
              onEditNameChange={setEditName}
              editType={editType}
              onEditTypeChange={setEditType}
              editRequired={editRequired}
              onEditRequiredChange={setEditRequired}
              editIdentity={editIdentity}
              onEditIdentityChange={setEditIdentity}
              isUpdating={updateMutation.isPending}
              isDeleting={deleteMutation.isPending}
              onDelete={() => {
                if (
                  window.confirm(
                    t('fields.edit_card.confirm_delete', { name: selectedField.name }),
                  )
                ) {
                  deleteMutation.mutate(selectedField.id)
                }
              }}
              onSubmit={(e) => {
                e.preventDefault()
                if (!editName.trim()) {
                  toast.error(t('fields.messages.name_empty'))
                  return
                }
                updateMutation.mutate({
                  name: editName.trim(),
                  field_type: editIdentity ? 'text' : editType,
                  required: editIdentity ? true : editRequired,
                  identity_role: editIdentity ? 'primary' : null,
                })
              }}
            />
          ) : (
            <Card className="border-dashed border-border bg-muted/20 h-full flex flex-col items-center justify-center p-10 text-center rounded-2xl">
              <p className="text-sm font-semibold text-muted-foreground">
                {t('fields.empty_selection')}
              </p>
            </Card>
          )}
        </div>
      </div>
    </Page>
  )
}
