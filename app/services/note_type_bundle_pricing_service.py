"""Price an author's bundle separately from unchanged third-party licenses."""

from copy import deepcopy

from app.repositories import note_type_bundle_repository as repository


def has_template_access(session, *, user_id, template_id):
    return template_id in repository.licensed_template_ids(session,
        user_id=user_id, template_ids=[template_id])


def pricing_breakdown(session, *, note_type, user_id, release=None):
    from app.services.note_type_release_service import current_release
    release = release or current_release(session, note_type)
    applications = (release.manifest_json.get("applications") or []) if release else []
    # Multiple mappings/occurrences of one definition are one license.
    definitions = {app["template_id"]: app for app in applications}
    rows = repository.template_rows(session, list(definitions))
    sources = repository.release_sources(session,
        [app["template_release_id"] for app in definitions.values()])
    licenses = repository.licensed_template_ids(session,
        user_id=user_id, template_ids=list(definitions))
    templates = []
    for template_id, app in definitions.items():
        row = rows.get(template_id)
        if row is None or sources.get(app["template_release_id"]) != template_id:
            from app.services.note_type_release_service import NoteTypeReleaseError
            raise NoteTypeReleaseError("NOTE_TYPE_RELEASE_INCOMPLETE", "A referenced template publication is unavailable.")
        own = row["owner_user_id"] == note_type.user_id
        entitled = template_id in licenses
        mode = row["pricing_mode"] or "free"
        amount = int(row["price_amount_minor"] or 0) if mode == "paid" else 0
        available = own or entitled or (row["marketplace_status"] == "published"
            and row["archived_at"] is None and row["origin"] == "authored"
            and row["source_template_id"] is None and (mode == "free" or amount > 0))
        templates.append({
            "template_id": template_id, "source_template_id": template_id,
            "template_release_id": app["template_release_id"],
            "name": app.get("template_name") or row["name"],
            "author": {"id": row["owner_user_id"], "username": row["username"]},
            "pricing_mode": mode, "price_amount_minor": amount,
            "charge_amount_minor": amount if not own and not entitled else 0,
            "is_owned_by_author": own, "already_entitled": entitled,
            "available": bool(available),
        })
    bundle = int(note_type.price_amount_minor or 0) if note_type.pricing_mode == "paid" else 0
    extra = sum(item["charge_amount_minor"] for item in templates)
    total = bundle + extra
    return {"bundle_amount_minor": bundle, "template_amount_minor": extra,
        "total_amount_minor": total, "payment_required": total > 0,
        "available": bool(release) and all(item["available"] for item in templates),
        "templates": templates}


def require_available(breakdown):
    from app.services.note_type_release_service import NoteTypeReleaseError
    if not breakdown["available"]:
        raise NoteTypeReleaseError("NOTE_TYPE_TEMPLATE_NOT_AVAILABLE",
            "A referenced template is no longer available for a new license.")
    if breakdown["total_amount_minor"] > 2_147_483_647:
        raise NoteTypeReleaseError("NOTE_TYPE_PRICE_INVALID", "The total price exceeds the supported amount.", status=400)


def require_receipt_access(session, *, note_type, user_id, release, access_granted=False):
    """Paying the bundle licenses its own definitions, never foreign paid ones."""
    from app.services.note_type_release_service import NoteTypeReleaseError
    breakdown = pricing_breakdown(session, note_type=note_type, user_id=user_id, release=release)
    require_available(breakdown)
    if breakdown["bundle_amount_minor"] > 0 and not access_granted:
        raise NoteTypeReleaseError("PAYMENT_REQUIRED", "Payment is required for this Note Type bundle.", status=402)
    if any(item["charge_amount_minor"] > 0 for item in breakdown["templates"]):
        raise NoteTypeReleaseError("PAYMENT_REQUIRED",
            "Payment is required for the paid templates referenced by this Note Type.", status=402)


def order_items_for_bundle(*, note_type, release, breakdown):
    """Freeze the release, each seller and each amount before contacting PayOS."""
    title = release.manifest_json["metadata"]["name"]
    result = [{"product_type": "note_type", "product_ref_id": note_type.id,
        "title_snapshot": title, "amount_minor": breakdown["bundle_amount_minor"],
        "product_snapshot": {"title": title, "pricing_mode": note_type.pricing_mode,
            "source_price_amount_minor": breakdown["bundle_amount_minor"],
            "source_price_integer": breakdown["bundle_amount_minor"],
            "version": release.version_label, "note_type_release_id": release.id,
            "owner_user_id": note_type.user_id, "commerce_version": "note-type-bundle.v1",
            "pricing_breakdown": deepcopy(breakdown)}}]
    for item in breakdown["templates"]:
        # Owners use their existing source definition; no own-source receipt.
        if item["already_entitled"]:
            continue
        result.append({"product_type": "template", "product_ref_id": item["template_id"],
            "title_snapshot": item["name"], "amount_minor": item["charge_amount_minor"],
            "product_snapshot": {"title": item["name"], "pricing_mode": item["pricing_mode"],
                "source_price_amount_minor": item["price_amount_minor"],
                "source_price_integer": item["price_amount_minor"],
                "release_id": item["template_release_id"],
                "owner_user_id": item["author"]["id"], "note_type_bundle_id": note_type.id,
                "note_type_release_id": release.id, "included_in_bundle": item["is_owned_by_author"]}})
    return result
