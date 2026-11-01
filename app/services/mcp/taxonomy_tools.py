"""MCP taxonomy management and category authoring tools for administrative users."""

from __future__ import annotations

from typing import Any

from app.repositories import marketplace_taxonomy_repository
from app.services import marketplace_taxonomy_service
from app.utils.permissions import is_admin_user
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.taxonomy import (
    TaxonomyDomain,
    TaxonomyFramework,
    TaxonomyFrameworkLevel,
    TaxonomyOption,
    TaxonomySubject,
)
from models.user import User


def _require_admin(user_id: int | None) -> User:
    """Ensure the user exists and holds admin privileges."""
    if user_id is None:
        raise RequestValidationError(
            "Yêu cầu xác thực tài khoản để thực hiện thao tác này.",
            field="user_id",
            status=401,
            code="UNAUTHENTICATED",
        )
    user = User.query.get(user_id)
    if not is_admin_user(user):
        raise RequestValidationError(
            "Chỉ có quản trị viên (Admin) mới có quyền thực hiện thao tác quản lý danh mục (taxonomy).",
            field="user_id",
            status=403,
            code="FORBIDDEN",
        )
    return user


def create_taxonomy_domain(
    *,
    user_id: int,
    id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
) -> dict[str, Any]:
    """Create a new top-level taxonomy domain."""
    _require_admin(user_id)
    domain_id = id.strip().lower()

    existing = TaxonomyDomain.query.get(domain_id)
    if existing is not None:
        raise RequestValidationError(
            f"Taxonomy domain '{domain_id}' đã tồn tại.",
            field="id",
            status=409,
            code="DUPLICATE_ID",
        )

    domain = marketplace_taxonomy_service.create_domain(
        domain_id=domain_id,
        label=label.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    return {
        "success": True,
        "domain": {
            "id": domain.id,
            "label": domain.label,
            "sort_order": domain.sort_order,
            "is_active": domain.is_active,
        },
    }


def create_taxonomy_subject(
    *,
    user_id: int,
    id: str,
    domain_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
) -> dict[str, Any]:
    """Create a new subject under a taxonomy domain."""
    _require_admin(user_id)
    subject_id = id.strip().lower()
    norm_domain_id = domain_id.strip().lower()

    domain = TaxonomyDomain.query.get(norm_domain_id)
    if domain is None:
        raise RequestValidationError(
            f"Taxonomy domain '{norm_domain_id}' không tồn tại.",
            field="domain_id",
            status=404,
            code="DOMAIN_NOT_FOUND",
        )

    existing = TaxonomySubject.query.get(subject_id)
    if existing is not None:
        raise RequestValidationError(
            f"Taxonomy subject '{subject_id}' đã tồn tại.",
            field="id",
            status=409,
            code="DUPLICATE_ID",
        )

    subject = marketplace_taxonomy_service.create_subject(
        subject_id=subject_id,
        domain_id=norm_domain_id,
        label=label.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    return {
        "success": True,
        "subject": {
            "id": subject.id,
            "domain_id": subject.domain_id,
            "label": subject.label,
            "sort_order": subject.sort_order,
            "is_active": subject.is_active,
        },
    }


def create_taxonomy_framework(
    *,
    user_id: int,
    id: str,
    subject_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
) -> dict[str, Any]:
    """Create a new certification/proficiency framework under a subject."""
    _require_admin(user_id)
    framework_id = id.strip().lower()
    norm_subject_id = subject_id.strip().lower()

    subject = TaxonomySubject.query.get(norm_subject_id)
    if subject is None:
        raise RequestValidationError(
            f"Taxonomy subject '{norm_subject_id}' không tồn tại.",
            field="subject_id",
            status=404,
            code="SUBJECT_NOT_FOUND",
        )

    existing = TaxonomyFramework.query.get(framework_id)
    if existing is not None:
        raise RequestValidationError(
            f"Taxonomy framework '{framework_id}' đã tồn tại.",
            field="id",
            status=409,
            code="DUPLICATE_ID",
        )

    framework = marketplace_taxonomy_service.create_framework(
        framework_id=framework_id,
        subject_id=norm_subject_id,
        label=label.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    return {
        "success": True,
        "framework": {
            "id": framework.id,
            "subject_id": framework.subject_id,
            "label": framework.label,
            "sort_order": framework.sort_order,
            "is_active": framework.is_active,
        },
    }


def create_taxonomy_framework_level(
    *,
    user_id: int,
    id: str,
    framework_id: str,
    subject_id: str,
    label: str,
    difficulty_band: str = "beginner",
    suggested_tags: list[str] | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> dict[str, Any]:
    """Create a new level under a framework and subject."""
    _require_admin(user_id)
    level_id = id.strip().lower()
    norm_framework_id = framework_id.strip().lower()
    norm_subject_id = subject_id.strip().lower()

    framework = TaxonomyFramework.query.get(norm_framework_id)
    if framework is None:
        raise RequestValidationError(
            f"Taxonomy framework '{norm_framework_id}' không tồn tại.",
            field="framework_id",
            status=404,
            code="FRAMEWORK_NOT_FOUND",
        )

    subject = TaxonomySubject.query.get(norm_subject_id)
    if subject is None:
        raise RequestValidationError(
            f"Taxonomy subject '{norm_subject_id}' không tồn tại.",
            field="subject_id",
            status=404,
            code="SUBJECT_NOT_FOUND",
        )

    existing = TaxonomyFrameworkLevel.query.get(level_id)
    if existing is not None:
        raise RequestValidationError(
            f"Taxonomy framework level '{level_id}' đã tồn tại.",
            field="id",
            status=409,
            code="DUPLICATE_ID",
        )

    level = marketplace_taxonomy_service.create_framework_level(
        level_id=level_id,
        framework_id=norm_framework_id,
        subject_id=norm_subject_id,
        label=label.strip(),
        difficulty_band=difficulty_band,
        sort_order=sort_order,
        is_active=is_active,
    )
    if suggested_tags:
        marketplace_taxonomy_repository.update_framework_level(
            level_id=level_id,
            suggested_tags=suggested_tags,
        )
        marketplace_taxonomy_service.invalidate_taxonomy_cache()

    return {
        "success": True,
        "framework_level": {
            "id": level.id,
            "framework_id": level.framework_id,
            "subject_id": level.subject_id,
            "label": level.label,
            "difficulty_band": level.difficulty_band,
            "sort_order": level.sort_order,
            "is_active": level.is_active,
        },
    }


def create_taxonomy_option(
    *,
    user_id: int,
    id: str,
    option_type: str,
    label: str,
    sub_label: str | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> dict[str, Any]:
    """Create a new taxonomy option (topic, learning_goal, format_feature, etc.)."""
    _require_admin(user_id)
    option_id = id.strip().lower()
    norm_type = option_type.strip().lower()
    if norm_type in ("topic", "primary_topic"):
        norm_type = "primary_topic"
    elif norm_type in ("goal", "learning_goal"):
        norm_type = "learning_goal"

    existing = TaxonomyOption.query.filter_by(id=option_id, option_type=norm_type).first()
    if existing is not None:
        raise RequestValidationError(
            f"Taxonomy option '{option_id}' ({norm_type}) đã tồn tại.",
            field="id",
            status=409,
            code="DUPLICATE_ID",
        )

    opt = marketplace_taxonomy_service.create_option(
        option_id=option_id,
        option_type=norm_type,
        label=label.strip(),
        sub_label=sub_label.strip() if sub_label else None,
        sort_order=sort_order,
        is_active=is_active,
    )
    return {
        "success": True,
        "option": {
            "id": opt.id,
            "option_type": opt.option_type,
            "label": opt.label,
            "sub_label": opt.sub_label,
            "sort_order": opt.sort_order,
            "is_active": opt.is_active,
        },
    }


def ensure_taxonomy_category(
    *,
    user_id: int,
    domain_id: str,
    domain_label: str | None = None,
    subject_id: str,
    subject_label: str | None = None,
    framework_id: str | None = None,
    framework_label: str | None = None,
    level_id: str | None = None,
    level_label: str | None = None,
    difficulty_band: str = "beginner",
) -> dict[str, Any]:
    """Ensure an entire taxonomy category hierarchy exists, creating any missing elements."""
    _require_admin(user_id)

    # Seed initial taxonomy tables in database if empty
    marketplace_taxonomy_service.ensure_default_taxonomy_data(db.session)

    norm_domain_id = domain_id.strip().lower()
    norm_subject_id = subject_id.strip().lower()
    norm_framework_id = framework_id.strip().lower() if framework_id else None
    norm_level_id = level_id.strip().lower() if level_id else None

    created_entities: list[str] = []

    # 1. Domain
    domain = TaxonomyDomain.query.get(norm_domain_id)
    if domain is None:
        d_label = (domain_label or norm_domain_id.replace("_", " ").title()).strip()
        domain = marketplace_taxonomy_service.create_domain(
            domain_id=norm_domain_id,
            label=d_label,
            sort_order=50,
            is_active=True,
        )
        created_entities.append(f"domain:{norm_domain_id}")

    # 2. Subject
    subject = TaxonomySubject.query.get(norm_subject_id)
    if subject is None:
        s_label = (subject_label or norm_subject_id.replace("_", " ").title()).strip()
        subject = marketplace_taxonomy_service.create_subject(
            subject_id=norm_subject_id,
            domain_id=domain.id,
            label=s_label,
            sort_order=50,
            is_active=True,
        )
        created_entities.append(f"subject:{norm_subject_id}")

    # 3. Framework (optional)
    framework = None
    if norm_framework_id:
        framework = TaxonomyFramework.query.get(norm_framework_id)
        if framework is None:
            fw_label = (framework_label or norm_framework_id.replace("_", " ").upper()).strip()
            framework = marketplace_taxonomy_service.create_framework(
                framework_id=norm_framework_id,
                subject_id=subject.id,
                label=fw_label,
                sort_order=50,
                is_active=True,
            )
            created_entities.append(f"framework:{norm_framework_id}")

    # 4. Level (optional)
    level = None
    if norm_framework_id and norm_level_id:
        level = TaxonomyFrameworkLevel.query.get(norm_level_id)
        if level is None:
            lvl_label = (level_label or norm_level_id.upper()).strip()
            level = marketplace_taxonomy_service.create_framework_level(
                level_id=norm_level_id,
                framework_id=norm_framework_id,
                subject_id=subject.id,
                label=lvl_label,
                difficulty_band=difficulty_band,
                sort_order=50,
                is_active=True,
            )
            created_entities.append(f"level:{norm_level_id}")

    # 5. Suggested taxonomy_metadata for share_deck
    metadata_snippet: dict[str, Any] = {
        "domain": domain.id,
        "subject": subject.id,
        "difficulty_band": difficulty_band,
    }
    if norm_framework_id:
        metadata_snippet["framework"] = norm_framework_id
    if norm_level_id:
        metadata_snippet["framework_level"] = norm_level_id

    return {
        "success": True,
        "created_entities": created_entities,
        "domain": {"id": domain.id, "label": domain.label},
        "subject": {"id": subject.id, "domain_id": domain.id, "label": subject.label},
        "framework": {"id": framework.id, "label": framework.label} if framework else None,
        "framework_level": {
            "id": level.id,
            "label": level.label,
            "difficulty_band": level.difficulty_band,
        } if level else None,
        "suggested_taxonomy_metadata": metadata_snippet,
    }
