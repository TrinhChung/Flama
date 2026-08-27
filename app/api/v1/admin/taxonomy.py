"""Administrative Taxonomy REST API V1 resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from app.api.common import admin_required, error_response
from app.repositories import marketplace_taxonomy_repository
from app.services import marketplace_taxonomy_service
from models import db

admin_taxonomy_bp = Blueprint("api_v1_admin_taxonomy", __name__)


def _payload() -> dict:
    if request.is_json:
        p = request.get_json(silent=True)
        return p if isinstance(p, dict) else {}
    return request.form.to_dict(flat=True)


# --- DOMAINS ---
@admin_taxonomy_bp.get("/domains")
@admin_required
def list_domains():
    include_inactive = request.args.get("include_inactive") == "1"
    domains = marketplace_taxonomy_repository.list_domains(include_inactive=include_inactive)
    return jsonify(
        {
            "domains": [
                {
                    "id": d.id,
                    "label": d.label,
                    "sort_order": d.sort_order,
                    "is_active": d.is_active,
                }
                for d in domains
            ]
        }
    )


@admin_taxonomy_bp.post("/domains")
@admin_required
def create_domain():
    data = _payload()
    domain_id = (data.get("id") or "").strip()
    label = (data.get("label") or "").strip()
    if not domain_id or not label:
        return error_response("VALIDATION_ERROR", "id and label are required.", status=400)

    try:
        domain = marketplace_taxonomy_repository.create_domain(
            domain_id=domain_id,
            label=label,
            sort_order=int(data.get("sort_order", 0)),
            is_active=bool(data.get("is_active", True)),
        )
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return (
        jsonify(
            {
                "domain": {
                    "id": domain.id,
                    "label": domain.label,
                    "sort_order": domain.sort_order,
                    "is_active": domain.is_active,
                }
            }
        ),
        201,
    )


@admin_taxonomy_bp.put("/domains/<domain_id>")
@admin_required
def update_domain(domain_id: str):
    data = _payload()
    domain = marketplace_taxonomy_repository.update_domain(
        domain_id=domain_id,
        label=data.get("label"),
        sort_order=int(data["sort_order"]) if "sort_order" in data else None,
        is_active=bool(data["is_active"]) if "is_active" in data else None,
    )
    if not domain:
        return error_response("NOT_FOUND", "Domain not found.", status=404)

    try:
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return jsonify(
        {
            "domain": {
                "id": domain.id,
                "label": domain.label,
                "sort_order": domain.sort_order,
                "is_active": domain.is_active,
            }
        }
    )


@admin_taxonomy_bp.delete("/domains/<domain_id>")
@admin_required
def delete_domain(domain_id: str):
    success = marketplace_taxonomy_repository.delete_domain(domain_id)
    if not success:
        return error_response("NOT_FOUND", "Domain not found.", status=404)
    db.session.commit()
    marketplace_taxonomy_service.invalidate_taxonomy_cache()
    return jsonify({"success": True})


# --- SUBJECTS ---
@admin_taxonomy_bp.get("/subjects")
@admin_required
def list_subjects():
    domain_id = request.args.get("domain_id")
    include_inactive = request.args.get("include_inactive") == "1"
    subjects = marketplace_taxonomy_repository.list_subjects(
        domain_id=domain_id, include_inactive=include_inactive
    )
    return jsonify(
        {
            "subjects": [
                {
                    "id": s.id,
                    "domain_id": s.domain_id,
                    "label": s.label,
                    "sort_order": s.sort_order,
                    "is_active": s.is_active,
                }
                for s in subjects
            ]
        }
    )


@admin_taxonomy_bp.post("/subjects")
@admin_required
def create_subject():
    data = _payload()
    subject_id = (data.get("id") or "").strip()
    domain_id = (data.get("domain_id") or "").strip()
    label = (data.get("label") or "").strip()
    if not subject_id or not domain_id or not label:
        return error_response("VALIDATION_ERROR", "id, domain_id, and label are required.", status=400)

    try:
        subject = marketplace_taxonomy_repository.create_subject(
            subject_id=subject_id,
            domain_id=domain_id,
            label=label,
            sort_order=int(data.get("sort_order", 0)),
            is_active=bool(data.get("is_active", True)),
        )
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return (
        jsonify(
            {
                "subject": {
                    "id": subject.id,
                    "domain_id": subject.domain_id,
                    "label": subject.label,
                    "sort_order": subject.sort_order,
                    "is_active": subject.is_active,
                }
            }
        ),
        201,
    )


@admin_taxonomy_bp.put("/subjects/<subject_id>")
@admin_required
def update_subject(subject_id: str):
    data = _payload()
    subject = marketplace_taxonomy_repository.update_subject(
        subject_id=subject_id,
        domain_id=data.get("domain_id"),
        label=data.get("label"),
        sort_order=int(data["sort_order"]) if "sort_order" in data else None,
        is_active=bool(data["is_active"]) if "is_active" in data else None,
    )
    if not subject:
        return error_response("NOT_FOUND", "Subject not found.", status=404)

    try:
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return jsonify(
        {
            "subject": {
                "id": subject.id,
                "domain_id": subject.domain_id,
                "label": subject.label,
                "sort_order": subject.sort_order,
                "is_active": subject.is_active,
            }
        }
    )


@admin_taxonomy_bp.delete("/subjects/<subject_id>")
@admin_required
def delete_subject(subject_id: str):
    success = marketplace_taxonomy_repository.delete_subject(subject_id)
    if not success:
        return error_response("NOT_FOUND", "Subject not found.", status=404)
    db.session.commit()
    marketplace_taxonomy_service.invalidate_taxonomy_cache()
    return jsonify({"success": True})


# --- FRAMEWORKS & LEVELS ---
@admin_taxonomy_bp.get("/frameworks")
@admin_required
def list_frameworks():
    subject_id = request.args.get("subject_id")
    include_inactive = request.args.get("include_inactive") == "1"
    frameworks = marketplace_taxonomy_repository.list_frameworks(
        subject_id=subject_id, include_inactive=include_inactive
    )
    return jsonify(
        {
            "frameworks": [
                {
                    "id": f.id,
                    "subject_id": f.subject_id,
                    "label": f.label,
                    "sort_order": f.sort_order,
                    "is_active": f.is_active,
                }
                for f in frameworks
            ]
        }
    )


@admin_taxonomy_bp.post("/frameworks")
@admin_required
def create_framework():
    data = _payload()
    framework_id = (data.get("id") or "").strip()
    subject_id = (data.get("subject_id") or "").strip()
    label = (data.get("label") or "").strip()
    if not framework_id or not subject_id or not label:
        return error_response("VALIDATION_ERROR", "id, subject_id, and label are required.", status=400)

    try:
        framework = marketplace_taxonomy_repository.create_framework(
            framework_id=framework_id,
            subject_id=subject_id,
            label=label,
            sort_order=int(data.get("sort_order", 0)),
            is_active=bool(data.get("is_active", True)),
        )
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return (
        jsonify(
            {
                "framework": {
                    "id": framework.id,
                    "subject_id": framework.subject_id,
                    "label": framework.label,
                    "sort_order": framework.sort_order,
                    "is_active": framework.is_active,
                }
            }
        ),
        201,
    )


@admin_taxonomy_bp.put("/frameworks/<framework_id>")
@admin_required
def update_framework(framework_id: str):
    data = _payload()
    framework = marketplace_taxonomy_repository.update_framework(
        framework_id=framework_id,
        subject_id=data.get("subject_id"),
        label=data.get("label"),
        sort_order=int(data["sort_order"]) if "sort_order" in data else None,
        is_active=bool(data["is_active"]) if "is_active" in data else None,
    )
    if not framework:
        return error_response("NOT_FOUND", "Framework not found.", status=404)

    try:
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return jsonify(
        {
            "framework": {
                "id": framework.id,
                "subject_id": framework.subject_id,
                "label": framework.label,
                "sort_order": framework.sort_order,
                "is_active": framework.is_active,
            }
        }
    )


@admin_taxonomy_bp.delete("/frameworks/<framework_id>")
@admin_required
def delete_framework(framework_id: str):
    success = marketplace_taxonomy_repository.delete_framework(framework_id)
    if not success:
        return error_response("NOT_FOUND", "Framework not found.", status=404)
    db.session.commit()
    marketplace_taxonomy_service.invalidate_taxonomy_cache()
    return jsonify({"success": True})


@admin_taxonomy_bp.get("/framework-levels")
@admin_required
def list_framework_levels():
    framework_id = request.args.get("framework_id")
    subject_id = request.args.get("subject_id")
    include_inactive = request.args.get("include_inactive") == "1"
    levels = marketplace_taxonomy_repository.list_framework_levels(
        framework_id=framework_id, subject_id=subject_id, include_inactive=include_inactive
    )
    return jsonify(
        {
            "levels": [
                {
                    "id": l.id,
                    "framework_id": l.framework_id,
                    "subject_id": l.subject_id,
                    "label": l.label,
                    "difficulty_band": l.difficulty_band,
                    "sort_order": l.sort_order,
                    "is_active": l.is_active,
                }
                for l in levels
            ]
        }
    )


@admin_taxonomy_bp.post("/framework-levels")
@admin_required
def create_framework_level():
    data = _payload()
    level_id = (data.get("id") or "").strip()
    framework_id = (data.get("framework_id") or "").strip()
    subject_id = (data.get("subject_id") or "").strip()
    label = (data.get("label") or "").strip()
    if not level_id or not framework_id or not subject_id or not label:
        return error_response("VALIDATION_ERROR", "id, framework_id, subject_id, label required.", status=400)

    try:
        level = marketplace_taxonomy_repository.create_framework_level(
            level_id=level_id,
            framework_id=framework_id,
            subject_id=subject_id,
            label=label,
            difficulty_band=data.get("difficulty_band", "beginner"),
            sort_order=int(data.get("sort_order", 0)),
            is_active=bool(data.get("is_active", True)),
        )
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return (
        jsonify(
            {
                "level": {
                    "id": level.id,
                    "framework_id": level.framework_id,
                    "subject_id": level.subject_id,
                    "label": level.label,
                    "difficulty_band": level.difficulty_band,
                    "sort_order": level.sort_order,
                    "is_active": level.is_active,
                }
            }
        ),
        201,
    )


@admin_taxonomy_bp.put("/framework-levels/<level_id>")
@admin_required
def update_framework_level(level_id: str):
    data = _payload()
    level = marketplace_taxonomy_repository.update_framework_level(
        level_id=level_id,
        label=data.get("label"),
        difficulty_band=data.get("difficulty_band"),
        sort_order=int(data["sort_order"]) if "sort_order" in data else None,
        is_active=bool(data["is_active"]) if "is_active" in data else None,
    )
    if not level:
        return error_response("NOT_FOUND", "Framework level not found.", status=404)

    try:
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return jsonify(
        {
            "level": {
                "id": level.id,
                "framework_id": level.framework_id,
                "subject_id": level.subject_id,
                "label": level.label,
                "difficulty_band": level.difficulty_band,
                "sort_order": level.sort_order,
                "is_active": level.is_active,
            }
        }
    )


@admin_taxonomy_bp.delete("/framework-levels/<level_id>")
@admin_required
def delete_framework_level(level_id: str):
    success = marketplace_taxonomy_repository.delete_framework_level(level_id)
    if not success:
        return error_response("NOT_FOUND", "Framework level not found.", status=404)
    db.session.commit()
    marketplace_taxonomy_service.invalidate_taxonomy_cache()
    return jsonify({"success": True})


# --- OPTIONS ---
@admin_taxonomy_bp.get("/options")
@admin_required
def list_options():
    option_type = request.args.get("option_type")
    include_inactive = request.args.get("include_inactive") == "1"
    options = marketplace_taxonomy_repository.list_options(
        option_type=option_type, include_inactive=include_inactive
    )
    return jsonify(
        {
            "options": [
                {
                    "id": o.id,
                    "option_type": o.option_type,
                    "label": o.label,
                    "sub_label": o.sub_label,
                    "sort_order": o.sort_order,
                    "is_active": o.is_active,
                }
                for o in options
            ]
        }
    )


@admin_taxonomy_bp.post("/options")
@admin_required
def create_option():
    data = _payload()
    option_id = (data.get("id") or "").strip()
    option_type = (data.get("option_type") or "").strip()
    label = (data.get("label") or "").strip()
    if not option_id or not option_type or not label:
        return error_response("VALIDATION_ERROR", "id, option_type, and label required.", status=400)

    try:
        opt = marketplace_taxonomy_repository.create_option(
            option_id=option_id,
            option_type=option_type,
            label=label,
            sub_label=data.get("sub_label"),
            sort_order=int(data.get("sort_order", 0)),
            is_active=bool(data.get("is_active", True)),
        )
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return (
        jsonify(
            {
                "option": {
                    "id": opt.id,
                    "option_type": opt.option_type,
                    "label": opt.label,
                    "sub_label": opt.sub_label,
                    "sort_order": opt.sort_order,
                    "is_active": opt.is_active,
                }
            }
        ),
        201,
    )


@admin_taxonomy_bp.put("/options/<option_id>")
@admin_required
def update_option(option_id: str):
    data = _payload()
    option_type = data.get("option_type")
    opt = marketplace_taxonomy_repository.update_option(
        option_id=option_id,
        option_type=option_type,
        label=data.get("label"),
        sub_label=data.get("sub_label"),
        sort_order=int(data["sort_order"]) if "sort_order" in data else None,
        is_active=bool(data["is_active"]) if "is_active" in data else None,
    )
    if not opt:
        return error_response("NOT_FOUND", "Option not found.", status=404)

    try:
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return jsonify(
        {
            "option": {
                "id": opt.id,
                "option_type": opt.option_type,
                "label": opt.label,
                "sub_label": opt.sub_label,
                "sort_order": opt.sort_order,
                "is_active": opt.is_active,
            }
        }
    )


@admin_taxonomy_bp.delete("/options/<option_id>")
@admin_required
def delete_option(option_id: str):
    option_type = request.args.get("option_type")
    success = marketplace_taxonomy_repository.delete_option(option_id, option_type=option_type)
    if not success:
        return error_response("NOT_FOUND", "Option not found.", status=404)
    db.session.commit()
    marketplace_taxonomy_service.invalidate_taxonomy_cache()
    return jsonify({"success": True})


@admin_taxonomy_bp.get("/subject-mappings")
@admin_required
def get_subject_mappings():
    subject_id = request.args.get("subject_id")
    option_type = request.args.get("option_type")
    mappings = marketplace_taxonomy_repository.list_subject_option_maps(
        subject_id=subject_id, option_type=option_type
    )
    return jsonify(
        {
            "mappings": [
                {
                    "subject_id": m.subject_id,
                    "option_id": m.option_id,
                    "option_type": m.option_type,
                }
                for m in mappings
            ]
        }
    )


@admin_taxonomy_bp.post("/subject-mappings")
@admin_required
def set_subject_mappings():
    data = _payload()
    subject_id = (data.get("subject_id") or "").strip()
    option_type = (data.get("option_type") or "").strip()
    option_ids = data.get("option_ids") or []
    if not subject_id or not option_type or not isinstance(option_ids, list):
        return error_response("VALIDATION_ERROR", "subject_id, option_type, option_ids required.", status=400)

    try:
        marketplace_taxonomy_repository.set_subject_option_maps(
            subject_id=subject_id,
            option_type=option_type,
            option_ids=[str(i).strip() for i in option_ids],
        )
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return jsonify({"success": True})


@admin_taxonomy_bp.post("/reseed-defaults")
@admin_required
def reseed_defaults():
    try:
        marketplace_taxonomy_service.ensure_default_taxonomy_data(db.session)
        db.session.commit()
        marketplace_taxonomy_service.invalidate_taxonomy_cache()
    except Exception as exc:
        db.session.rollback()
        return error_response("DATABASE_ERROR", str(exc), status=400)

    return jsonify({"success": True, "message": "Default taxonomy data verified and seeded."})

