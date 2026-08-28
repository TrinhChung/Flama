# Task: Shared Deck auto-publish, subscriber auto-update, and conflict resolution

**Target branch:** `develop`

## Goal

Improve Shared Deck version/update behavior so creators and users do not have to manually manage every update.

The feature has two independent opt-in capabilities:

1. **Creator / publisher auto-publish updates** — a publisher can configure a Shared Deck so eligible changes from the source Deck are automatically published as a new Shared Deck revision/version without manually performing the current version-update flow every time.
2. **Subscriber / installed-deck auto-update** — a user who installed/cloned a Shared Deck can choose to automatically receive compatible changes from the original published Deck.

The system must preserve user-owned local changes. If an upstream update conflicts with content the user changed locally, Flama must **not silently overwrite either side**. It must detect the conflict, explain it, and let the user choose what to keep.

The merge model must be designed around **three-way merge using a known synchronized base revision**, not a naive comparison of only the current local and current publisher Deck.

---

## Terminology

Use clear terminology in code and UI.

```text
Source Deck
  = creator-owned Deck used as the source of a Shared Deck

Published revision
  = immutable Shared Deck content snapshot/revision available to subscribers

Installed Deck
  = the user's local Deck created/linked from the Shared Deck

Base revision
  = the exact published revision that the installed Deck was last successfully synchronized against

Upstream
  = the latest published creator revision

Local changes
  = content changes made by the subscriber after the base revision
```

Do not rely only on a human-facing version string. Persist stable revision IDs / ancestry so update and merge behavior is deterministic.

---

## Part A — Creator auto-publish setting

On the creator side, add an option for a published/shared Deck such as:

```text
Automatic updates
[ ] Automatically publish changes from this Deck
```

Suggested explanation:

```text
When enabled, eligible changes made to the source Deck will be published automatically as a new revision of this Shared Deck. Subscribers who enabled automatic updates can receive those changes without waiting for you to manually publish a new version.
```

This setting must be configurable per Shared Deck.

Suggested states:

```text
OFF
- current/manual publication behavior remains unchanged

ON
- source changes are detected
- system creates/publishes a new immutable revision automatically
- linked subscribers are informed through the normal update mechanism
```

### Do not publish on every keystroke

Auto-publish must not create dozens of revisions while the creator edits several notes.

Choose a safe trigger/batching strategy after examining the current Deck edit/save architecture, for example:

- publish after a committed Deck mutation rather than input keystrokes;
- debounce/batch changes for a short period;
- aggregate a group of related mutations into one revision;
- use an explicit save boundary if the current editor already has one.

The implementation must be idempotent. The same source state must not accidentally produce duplicate published revisions because of retries or concurrent workers.

### Changes that may create a revision

At minimum evaluate:

- note added;
- note removed;
- note field value changed;
- note moved if ordering is meaningful;
- note type / field schema changed;
- Deck metadata exposed through Shared Deck changed;
- media/reference changed;
- template/configuration changed if subscribers are expected to inherit it.

Research the current Shared Deck model and explicitly define which properties are **publisher-managed/upstream content** and which properties are not part of synchronization.

### Creator status UI

The creator should be able to see at least:

```text
Automatic updates: ON/OFF
Latest published revision
Last automatic publish time
Pending source changes, if any
Last publish failure, if any
```

If automatic publication fails, keep the last valid published revision active. Do not expose a partially built revision to users.

---

## Part B — User auto-update setting

For a Deck installed from a Shared Deck, add an option such as:

```text
Updates from original Deck
[ ] Automatically apply compatible updates
```

Suggested explanation:

```text
When enabled, Flama automatically applies new changes from the original publisher when they do not conflict with your own edits. If the same content was changed both by you and by the publisher, Flama will ask which version to keep.
```

The user must also have a manual action:

```text
Check for updates
```

and, when an update exists:

```text
Update now
View changes
```

### Recommended default

For the first implementation, default subscriber auto-update to **OFF** for existing installed Decks unless product requirements explicitly decide otherwise.

Do not unexpectedly change existing users' Deck content after deploying this feature.

For newly installed Decks, the install flow may offer:

```text
Keep this Deck updated automatically
```

but the choice must be visible and understandable.

---

## Provenance and synchronization metadata

A Deck installed from Shared Deck must retain enough provenance to synchronize safely.

At minimum, persist concepts equivalent to:

```text
installed_deck_id
shared_deck_id
source_deck_id / publisher identity where appropriate
last_synced_revision_id
last_seen_revision_id
sync_mode: manual | automatic
sync_status
last_sync_at
pending_conflict_count
```

Individual synchronized entities also need stable identities across revisions.

Do **not** identify notes only by array index, display order, front text, or another editable field.

Use stable upstream entity IDs/mapping so the system can determine that:

```text
Base note N
Local note N
Upstream note N
```

represent the same logical note.

If the current clone architecture generates completely unrelated note IDs, introduce an explicit provenance mapping instead of depending on ID equality.

---

## Three-way merge requirement

Conflict detection must use:

```text
BASE     = content from last successfully synchronized published revision
LOCAL    = user's current installed Deck
UPSTREAM = target published revision
```

For each synchronized entity/field:

```text
LOCAL == BASE and UPSTREAM != BASE
=> upstream-only change
=> safe to apply upstream

LOCAL != BASE and UPSTREAM == BASE
=> local-only change
=> preserve local value

LOCAL == UPSTREAM
=> already equivalent
=> no conflict

LOCAL != BASE and UPSTREAM != BASE and LOCAL != UPSTREAM
=> both changed differently
=> conflict
```

A direct two-way comparison of LOCAL vs UPSTREAM is insufficient because it cannot reliably determine who changed what after the last synchronization point.

---

## Conflict examples

### 1. Same field edited by both sides

```text
BASE:
Meaning = "school"

LOCAL:
Meaning = "trường học"

UPSTREAM:
Meaning = "school / academy"
```

Result:

```text
CONFLICT
```

Show both values and let the user choose.

### 2. Different fields edited

```text
BASE:
Word = 学校
Meaning = school

LOCAL:
Meaning = trường học

UPSTREAM:
Word = 学校（がっこう）
```

If field-level merging is supported and these are independent changes:

```text
Word    <- upstream change
Meaning <- preserve local change
```

No conflict is required merely because the same note was touched on both sides.

Prefer field-level conflict detection over treating the entire note as conflicting whenever technically feasible.

### 3. Publisher changes a note, user did not

Apply automatically.

### 4. User changes a note, publisher did not

Preserve the user's version.

### 5. Publisher adds a new note

Add it to the installed Deck automatically unless another product rule prevents it.

### 6. User adds a local-only note

Preserve it. An upstream update must not delete local-only user content.

### 7. Publisher deletes a note, user did not modify it

The deletion can be applied.

### 8. Publisher deletes a note that user modified locally

This is a conflict.

Offer choices such as:

```text
Keep my note
Accept publisher deletion
```

### 9. User deletes a note that publisher modified

This is also a conflict.

Offer choices such as:

```text
Keep my deletion
Restore publisher version
```

### 10. Same new logical item created independently

Do not guess solely from matching text. Unless there is a reliable identity relationship, preserve both or present a possible-duplicate warning rather than silently merging unrelated entities.

---

## Conflict Resolution UI

When conflicts exist, do not silently choose a winner.

Show a dedicated update/conflict screen.

Example:

```text
Update from creator available
Revision 18 -> Revision 21

12 changes can be applied
2 conflicts need your decision

[Review conflicts]
```

For each conflict:

```text
Card / Note: 学校
Field: Meaning

Your version
----------------
trường học

Creator update
----------------
school / academy

( ) Keep my version
( ) Use creator version
```

Where useful, also show the base value:

```text
Previous synchronized value
----------------
school
```

Actions:

```text
Keep mine
Use publisher version
Apply this choice to similar conflicts
Review next
Apply update
Cancel
```

For note deletion conflicts, use wording appropriate to deletion rather than pretending both sides contain a field value.

### Batch resolution

For many conflicts, support efficient actions such as:

```text
Keep all my changes
Use publisher version for all conflicts
```

but require an explicit confirmation because these actions can discard data.

---

## Atomicity and safety

A synchronization operation must not leave the installed Deck in a partially corrupted state.

Recommended behavior:

1. Load/construct merge plan from BASE + LOCAL + target UPSTREAM revision.
2. Validate all entity mappings and schema changes.
3. Detect conflicts.
4. If user input is required, persist a pending merge/conflict state without destructively changing the Deck.
5. After conflicts are resolved, apply the complete merge transactionally.
6. Advance `last_synced_revision_id` only after the merge commits successfully.

Do not mark a revision synchronized before all selected changes are successfully applied.

If applying non-conflicting changes before conflict resolution is considered, document why and guarantee retry/rollback behavior. The safer initial implementation is to calculate the entire merge first and commit after conflict resolution.

---

## Multiple missed revisions

A user may be several publisher revisions behind.

Example:

```text
User base: revision 10
Publisher latest: revision 17
```

The system must be able to update without forcing the user to manually apply revisions 11, 12, 13, ... one by one.

Preferred model:

```text
BASE     = revision 10 snapshot
LOCAL    = current installed Deck
UPSTREAM = revision 17 snapshot
```

Then calculate one merge to the target revision while preserving ancestry/audit information.

If schema migrations require sequential application, keep that implementation detail internal; the UX should still present one coherent update operation.

---

## User study state must not be overwritten

Shared Deck content synchronization must be separated from user-specific learning state.

Publisher updates must not overwrite/reset user-owned state such as, as applicable to the current Flama schema:

- review history;
- SRS scheduling state;
- due dates;
- ease/stability/difficulty values;
- learning progress;
- answer statistics;
- favorites/bookmarks;
- personal learning flags;
- user-specific study settings;
- other local metadata that is not publisher-owned Deck content.

A content update must not make a studied Deck look newly installed unless the publisher actually introduces new cards/content that require their own initial study state.

For a newly added upstream note/card, initialize only the new user's study state according to normal Flama rules.

---

## Deck schema / Note Type changes

Schema changes need explicit handling because they can affect many notes.

Research and define merge behavior for:

- add field;
- remove field;
- rename field;
- reorder fields;
- change Note Type;
- template/front/back rendering changes;
- media references;
- card-generation rules.

A field rename should not accidentally look like `delete old field + add unrelated new field` if Flama can maintain a stable field identity.

If the publisher deletes a field containing local user edits, treat that as a conflict or require explicit confirmation rather than dropping the data.

When a schema update is not safely mergeable automatically, mark the update as requiring review.

---

## Creator controls and compatibility

The creator's auto-publish option and the user's auto-update option are independent.

Examples:

```text
Creator auto-publish OFF
User auto-update ON
=> user automatically receives updates whenever creator manually publishes a revision

Creator auto-publish ON
User auto-update OFF
=> revisions are published automatically, but user chooses when to apply them

Creator auto-publish ON
User auto-update ON
=> end-to-end automatic flow when there is no conflict

Any conflict
=> stop automatic destructive merge and request user decision
```

Do not require creator auto-publish for subscriber auto-update to function.

---

## Notifications and update indicators

Installed Deck UI should expose update state without being noisy.

Possible states:

```text
Up to date
Update available
Updating
Conflict requires review
Update failed
Auto-update disabled
```

Useful locations:

- Deck list badge/icon;
- installed Deck detail/settings;
- notification center if available;
- Shared Deck installation management screen.

For automatic updates with no conflict, a lightweight record such as:

```text
Updated from creator: revision 20 -> 21
```

is sufficient.

For conflicts, use a stronger actionable notification.

---

## Update history / auditability

Keep an update history for each installed Shared Deck.

At minimum record:

```text
from_revision_id
to_revision_id
started_at
completed_at
mode: manual | automatic
result: success | conflict | failed | cancelled
number_of_changes
number_of_conflicts
```

Where appropriate also retain conflict-resolution decisions long enough to support debugging/audit.

The creator should also have a publish history showing automatic vs manual revisions.

---

## Reverting and recovery

Before applying a destructive publisher update, ensure a recovery path exists.

At minimum evaluate one of:

- transactional rollback;
- previous synchronized snapshot retained for recovery;
- Deck revision history allowing restore;
- undo update action for a limited history window.

A failed update must not require the user to reconstruct their local edits manually.

---

## Concurrency

Protect against cases such as:

- creator source changes while an auto-publish job is running;
- two auto-publish jobs race;
- user edits an installed Deck while an update job is calculating/applying;
- manual `Update now` and background auto-update start simultaneously;
- user opens the same installed Deck on multiple sessions/devices;
- a retry processes the same target revision twice.

Use revision checks, locking/optimistic concurrency, idempotency keys, or equivalent mechanisms consistent with the current architecture.

Never apply a merge plan that was calculated against stale LOCAL state without revalidation.

---

## Background processing

If Shared Decks can be large, update detection / diff / snapshot / merge planning may be too expensive for a synchronous request.

Research current job infrastructure and move heavy work to a background queue if necessary.

Requirements:

- bounded work per job;
- retry-safe/idempotent processing;
- no duplicate revisions;
- no duplicate updates;
- observable failures;
- avoid N subscribers causing N expensive full-Deck copies at publish time when a shared immutable revision/diff can be reused.

Prefer computing publisher revision data once and reusing it across subscribers.

---

## Data model direction

Do not finalize schema names without examining current models, but the design should support concepts similar to:

```text
shared_deck
shared_deck_revision
shared_deck_revision_item / snapshot representation
installed_shared_deck_link
installed_entity_provenance
sync/update job
merge conflict
merge resolution
```

Important architectural rule:

```text
Published revision is immutable.
```

Do not mutate old revisions in place, because subscribers need a reliable BASE snapshot for conflict detection and reproducible merges.

If the existing Shared Deck versioning system already provides immutable snapshots, reuse it rather than introducing a parallel version store.

---

## API expectations

Exact endpoints depend on the current architecture, but the backend needs operations equivalent to:

```text
Creator:
- get/update auto-publish setting
- inspect publication status/history
- publish pending source changes manually when desired

Subscriber:
- get installed Deck update status
- get available target revision
- preview diff/merge
- enable/disable auto-update
- start manual update
- get conflicts
- submit conflict resolutions
- finalize/apply merge
- inspect update history
```

All update/merge authority must be enforced server-side.

Do not trust client-supplied ownership, source revision ancestry, or arbitrary note mappings.

---

## Permissions

Creator-only actions:

- enable/disable source Deck auto-publish;
- publish a new revision;
- inspect creator publication status.

Subscriber actions only for their own installed Deck:

- enable/disable auto-update;
- request/update preview;
- resolve their merge conflicts;
- apply/cancel update.

A subscriber must never be able to mutate the creator's source Deck or published immutable revision through update APIs.

---

## Performance requirements

The feature must not reintroduce Shared Deck clone/update load problems.

Evaluate:

- revision storage size;
- full snapshots vs structural deltas;
- efficient lookup of stable entity IDs;
- batching note changes;
- large Deck merge cost;
- concurrent subscriber updates;
- media deduplication;
- database query count;
- transaction size;
- queue backpressure.

Do not eagerly materialize a separate full publisher snapshot for every subscriber if one immutable published revision can be referenced by many installed Decks.

---

## Product edge cases

Define behavior for at least:

- Shared Deck unpublished/removed by creator;
- creator deletes source Deck;
- subscriber detaches/unlinks installed Deck from original;
- subscriber intentionally wants a permanently independent copy;
- paid Shared Deck access/revocation if applicable;
- subscriber skips an update;
- subscriber disables auto-update after conflicts appear;
- publisher rolls back to older content and publishes again;
- user is offline/background job cannot notify them immediately;
- Deck contains unsupported/corrupt note/media data;
- publisher changes visibility/price/license independent of content revision.

A user must be able to convert/detach an installed Deck into an independent local Deck if that behavior fits current product rules. Once detached, upstream synchronization/provenance should stop cleanly.

---

## UX summary

### Creator

```text
Shared Deck settings

Automatic publication
[x] Automatically publish source Deck changes

Latest revision: 21
Last published: 2026-08-28 12:30

[View update history]
```

### Subscriber — no conflicts

```text
Updates from original Deck
[x] Automatically apply compatible updates

Status: Up to date
Last update: revision 20 -> 21
```

### Subscriber — conflict

```text
Creator update needs your review

Revision 21 -> 22
2 conflicts found

[Review conflicts]
```

After resolution:

```text
[Apply update]
```

---

## Testing

Add automated tests for at least:

### Creator auto-publish

- OFF keeps manual behavior;
- ON creates revision after eligible source mutation;
- repeated job/retry does not create duplicate revision;
- multiple rapid mutations are batched according to chosen strategy;
- failed publication leaves previous revision valid;
- only owner can change the setting.

### Subscriber update

- manual update with no local changes;
- automatic update with no local changes;
- local-only edit preserved;
- upstream-only edit applied;
- both sides change same field differently -> conflict;
- both sides make same final value -> no conflict;
- independent fields merge safely;
- upstream added note appears locally;
- local-only note preserved;
- upstream delete untouched note;
- upstream delete locally edited note -> conflict;
- local delete + upstream edit -> conflict;
- user chooses Keep mine;
- user chooses Use publisher version;
- update across multiple missed revisions;
- conflict cancellation leaves Deck unchanged;
- retry does not apply update twice;
- stale merge plan is rejected/recalculated after concurrent local edit;
- study/SRS progress remains unchanged for existing cards;
- new upstream cards receive only newly initialized study state;
- permissions prevent cross-user Deck mutation.

### Schema changes

- add field;
- rename field with stable identity if supported;
- remove untouched field;
- remove locally modified field -> review/conflict;
- template/card-generation change according to defined sync scope.

---

## Acceptance criteria

This task is complete when:

- A Shared Deck publisher can enable/disable automatic publication of source Deck changes.
- Automatic publication creates reliable immutable revisions without duplicate version spam.
- A user with an installed Shared Deck can enable/disable automatic updates independently of the publisher setting.
- Users can manually check/apply updates even when auto-update is disabled.
- Installed Decks persist their last synchronized base revision and stable upstream provenance.
- Update calculation uses BASE + LOCAL + UPSTREAM semantics.
- Non-conflicting upstream changes can be merged while local-only changes are preserved.
- Conflicting changes are never silently overwritten.
- The user gets a conflict-resolution UI that clearly shows their value and the publisher's value and can choose which one to keep.
- Add/delete/edit conflicts are handled explicitly.
- Local-only notes are preserved.
- User study/SRS/progress data is never reset by publisher content synchronization.
- Multiple missed revisions can be updated through one coherent user flow.
- Synchronization is transactional/retry-safe and advances `last_synced_revision_id` only after success.
- Creator and subscriber update history/status are visible enough to diagnose what happened.
- Large Deck and concurrent update behavior is covered by performance/concurrency design and tests.
- Existing Shared Deck/manual update behavior remains compatible for users who do not enable the new options.
