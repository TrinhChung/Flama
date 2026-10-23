"""Read legacy receipt lineage without assigning a fictitious release base."""

from app.repositories import legacy_template_provenance_repository as repository


def legacy_reference(session, template_id, *, current_read=False):
    local = repository.template(session, template_id, current_read=current_read)
    if local is None:
        return None
    installs = repository.candidate_installs(session, template_id, current_read=current_read)
    if not installs:
        return None
    candidates = []
    for install in installs:
        local_ids = repository.active_template_ids(session, install["installed_note_type_id"], current_read=current_read)
        source_ids = repository.active_template_ids(session, install["source_note_type_id"], current_read=current_read)
        explicit_source = local.get("source_template_id")
        # A reviewed pointer survives changes in the source's active mapping.
        source_id = explicit_source or (source_ids[0] if len(local_ids) == len(source_ids) == 1 else None)
        source = repository.template(session, source_id, current_read=current_read) if source_id else None
        if source is None or source_id == local["id"] or source.get("origin") == "market_copy" or source.get("source_template_id"):
            source_id, source = None, None
        candidates.append({
            "template_id": local["id"], "source_template_id": source_id,
            "source_owner_user_id": source.get("owner_user_id") if source else None,
            "user_id": install["user_id"], "install_id": install["id"],
            "source_note_type_id": install["source_note_type_id"],
            "installed_note_type_id": install["installed_note_type_id"],
            "legacy_unpinned": True,
            "confidence": "unique_install_copy" if source_id else "ambiguous_install_copy",
        })
    if len({item["source_template_id"] for item in candidates}) > 1:
        candidates[0].update(source_template_id=None, source_owner_user_id=None, confidence="ambiguous_install_copy")
    return candidates[0]


def is_received_template(session, row_or_id):
    row = row_or_id if isinstance(row_or_id, dict) else repository.template(session, row_or_id)
    if row is None:
        return False
    return bool(row.get("origin") == "market_copy" or row.get("source_template_id")
        or repository.candidate_installs(session, row["id"]))


def legacy_subscription(session, *, user_id, template_id):
    """A read-only distribution state for editable, unpinned local content."""
    from app.repositories import template_release_repository as releases
    local = repository.template(session, template_id)
    if local is None or local["owner_user_id"] != int(user_id):
        return None
    reference = legacy_reference(session, template_id)
    if reference is None:
        return None
    source_id = reference.get("source_template_id")
    publication = releases.publication(session, source_id) if source_id else None
    head_id = (publication or {}).get("current_release_id")
    head = releases.release(session, head_id, source_id) if head_id else None
    return {
        "id": None, "template_id": local["id"], "local_template_id": local["id"],
        "source_template_id": source_id, "current_version_id": local.get("current_version_id"),
        "legacy_unpinned": True, "legacy_install_id": reference["install_id"],
        "applied_release_id": None, "seen_release_id": None,
        "applied_release": None, "current_release": head,
        "update_available": False, "auto_update_enabled": False,
        "pending_update_json": None, "last_sync_status": "legacy_unpinned",
        "template": {**local, "origin": "market_copy", "source_template_id": source_id},
        "requires_new_canonical_receipt": bool(source_id),
    }
