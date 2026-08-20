"""Application services for admin screens migrating from HTML forms to REST."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import current_app, url_for
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError

from app.repositories import image_library_repository
from app.services import (
    image_library_service,
    support_donation_service,
    tts_provider_service,
)
from app.validators import RequestValidationError, escape_like_pattern
from app.validators.image_library import parse_enabled_value
from models import db
from models.shared_image_asset import SharedImageAsset
from models.support_donation_config import SupportDonationConfig
from models.tts_provider_config import TtsProviderConfig


class AdminRestApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field


def get_tts_provider(provider_id: int) -> TtsProviderConfig | None:
    return db.session.get(TtsProviderConfig, int(provider_id))


def get_image_asset(asset_id: str) -> SharedImageAsset | None:
    return image_library_repository.get_by_id(asset_id)


def serialize_tts_provider(row: TtsProviderConfig) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "provider_name": str(row.provider_name or ""),
        "provider_type": str(row.provider_type or ""),
        "base_url": str(row.base_url or "") or None,
        "requires_api_key": bool(row.requires_api_key),
        "is_active": bool(row.is_active),
        "shared_config": tts_provider_service.loads_json_map(row.shared_config_json),
        "provider_config": tts_provider_service.loads_json_map(row.provider_config_json),
        "default_settings": tts_provider_service.loads_json_map(
            row.default_settings_json
        ),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_tts_providers(
    *,
    search_term: str,
    active_filter: str,
    provider_type_filter: str,
) -> dict[str, Any]:
    query = TtsProviderConfig.query
    if search_term:
        escaped = escape_like_pattern(search_term)
        like_pattern = f"%{escaped}%"
        query = query.filter(
            or_(
                TtsProviderConfig.provider_name.ilike(like_pattern, escape="\\"),
                TtsProviderConfig.provider_type.ilike(like_pattern, escape="\\"),
            )
        )
    if active_filter == "active":
        query = query.filter(TtsProviderConfig.is_active.is_(True))
    elif active_filter == "inactive":
        query = query.filter(TtsProviderConfig.is_active.is_(False))
    if provider_type_filter:
        query = query.filter(
            TtsProviderConfig.provider_type == provider_type_filter
        )

    rows = query.order_by(
        TtsProviderConfig.updated_at.desc(),
        TtsProviderConfig.id.desc(),
    ).all()
    provider_types = [
        value
        for (value,) in (
            db.session.query(TtsProviderConfig.provider_type)
            .distinct()
            .filter(
                TtsProviderConfig.provider_type.isnot(None),
                TtsProviderConfig.provider_type != "",
            )
            .order_by(TtsProviderConfig.provider_type.asc())
            .all()
        )
        if value
    ]
    return {
        "items": [serialize_tts_provider(row) for row in rows],
        "summary": {
            "total_count": TtsProviderConfig.query.count(),
            "active_count": TtsProviderConfig.query.filter(
                TtsProviderConfig.is_active.is_(True)
            ).count(),
            "requires_key_count": TtsProviderConfig.query.filter(
                TtsProviderConfig.requires_api_key.is_(True)
            ).count(),
            "filtered_count": len(rows),
        },
        "provider_type_options": provider_types,
        "filters": {
            "q": search_term,
            "active": active_filter,
            "provider_type": provider_type_filter,
        },
    }


def save_tts_provider(
    *,
    actor_user_id: int,
    payload: dict[str, Any],
    row: TtsProviderConfig | None,
) -> TtsProviderConfig:
    parser_payload = {
        "provider_name": payload.get("provider_name"),
        "provider_type": payload.get("provider_type"),
        "base_url": payload.get("base_url"),
        "requires_api_key": payload.get("requires_api_key"),
        "is_active": payload.get("is_active"),
        "shared_config_json": _json_text(
            payload.get("shared_config", payload.get("shared_config_json"))
        ),
        "provider_config_json": _json_text(
            payload.get("provider_config", payload.get("provider_config_json"))
        ),
        "default_settings_json": _json_text(
            payload.get("default_settings", payload.get("default_settings_json"))
        ),
    }
    parsed, errors = tts_provider_service.parse_provider_form_payload(
        parser_payload,
        for_update=row is not None,
    )
    if errors:
        raise AdminRestApiError(
            "VALIDATION_ERROR",
            "; ".join(errors),
            status=400,
        )

    duplicate_query = TtsProviderConfig.query.filter(
        func.lower(TtsProviderConfig.provider_type)
        == parsed.provider_type.lower()
    )
    if row is not None:
        duplicate_query = duplicate_query.filter(TtsProviderConfig.id != row.id)
    if duplicate_query.first() is not None:
        raise AdminRestApiError(
            "CONFLICT",
            "A provider with this provider_type already exists.",
            status=409,
            field="provider_type",
        )

    if row is None:
        row = TtsProviderConfig(created_by_admin_id=actor_user_id)
        db.session.add(row)
    row.provider_name = parsed.provider_name
    row.provider_type = parsed.provider_type
    row.base_url = parsed.base_url
    row.requires_api_key = parsed.requires_api_key
    row.is_active = parsed.is_active
    row.shared_config_json = tts_provider_service.dumps_json_map(parsed.shared_config)
    row.provider_config_json = tts_provider_service.dumps_json_map(
        parsed.provider_config
    )
    row.default_settings_json = tts_provider_service.dumps_json_map(
        parsed.default_settings
    )
    row.updated_by_admin_id = actor_user_id
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise AdminRestApiError(
            "DB_ERROR",
            "Could not save the TTS provider.",
            status=500,
        ) from exc
    return row


def delete_tts_provider(row: TtsProviderConfig) -> None:
    try:
        db.session.delete(row)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise AdminRestApiError(
            "DB_ERROR",
            "Could not delete the TTS provider.",
            status=500,
        ) from exc


def serialize_support_donation_config(
    row: SupportDonationConfig | None,
) -> dict[str, Any]:
    return {
        "id": int(row.id) if row is not None else None,
        "title": (
            str(row.title or support_donation_service.DEFAULT_TITLE)
            if row is not None
            else support_donation_service.DEFAULT_TITLE
        ),
        "description": (
            str(row.description or support_donation_service.DEFAULT_DESCRIPTION)
            if row is not None
            else support_donation_service.DEFAULT_DESCRIPTION
        ),
        "account_name": str(row.account_name or "") if row is not None else "",
        "account_number": str(row.account_number or "") if row is not None else "",
        "thank_you_message": (
            str(row.thank_you_message or support_donation_service.DEFAULT_THANK_YOU)
            if row is not None
            else support_donation_service.DEFAULT_THANK_YOU
        ),
        "qr_image_url": (
            url_for("main.support_donation_qr_image")
            if row is not None and row.qr_image_storage_path
            else None
        ),
        "qr_image_filename": (
            str(row.qr_image_filename or "") or None if row is not None else None
        ),
        "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
    }


def save_support_donation_config(
    *,
    actor_user_id: int,
    payload: dict[str, Any],
    uploaded_file: Any,
) -> SupportDonationConfig:
    parsed, errors = support_donation_service.parse_form_payload(payload)
    max_bytes = min(
        int(
            current_app.config.get(
                "FLASHCARD_MEDIA_MAX_BYTES",
                support_donation_service.DEFAULT_QR_MAX_BYTES,
            )
        ),
        support_donation_service.DEFAULT_QR_MAX_BYTES,
    )
    validated_upload, upload_errors = support_donation_service.validate_qr_upload(
        uploaded_file,
        max_bytes=max_bytes,
        scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
        scan_enabled=bool(
            current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)
        ),
    )
    errors.extend(upload_errors)
    if errors:
        raise AdminRestApiError(
            "VALIDATION_ERROR",
            "; ".join(errors),
            status=400,
        )

    row = support_donation_service.get_latest_config()
    if row is None:
        row = SupportDonationConfig()
        db.session.add(row)
    row.title = parsed.title
    row.description = parsed.description
    row.account_name = parsed.account_name
    row.account_number = parsed.account_number
    row.thank_you_message = parsed.thank_you_message
    row.updated_by_admin_id = actor_user_id

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    old_storage_path = str(row.qr_image_storage_path or "").strip() or None
    new_storage_path: str | None = None
    obsolete_storage_path: str | None = None
    if validated_upload is not None:
        try:
            storage_path, filename, mime_type = (
                support_donation_service.persist_qr_upload(
                    validated_upload=validated_upload,
                    upload_root=upload_root,
                )
            )
        except RequestValidationError as exc:
            raise AdminRestApiError(
                exc.code,
                str(exc),
                status=exc.status,
                field=exc.field,
            ) from exc
        row.qr_image_storage_path = storage_path
        row.qr_image_filename = filename
        row.qr_image_mime_type = mime_type
        new_storage_path = storage_path
        if old_storage_path and old_storage_path != storage_path:
            obsolete_storage_path = old_storage_path
    elif support_donation_service.is_truthy(payload.get("remove_qr_image")):
        row.qr_image_storage_path = None
        row.qr_image_filename = None
        row.qr_image_mime_type = None
        obsolete_storage_path = old_storage_path

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        if new_storage_path:
            support_donation_service.remove_qr_file(
                upload_root=upload_root,
                storage_path=new_storage_path,
            )
        raise AdminRestApiError(
            "DB_ERROR",
            "Could not save the donation configuration.",
            status=500,
        ) from exc
    if obsolete_storage_path:
        support_donation_service.remove_qr_file(
            upload_root=upload_root,
            storage_path=obsolete_storage_path,
        )
    return row


def serialize_image_asset(row: SharedImageAsset) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "asset_id": str(row.id),
        "image_key": str(row.image_key or ""),
        "name": str(row.image_key or ""),
        "description": str(row.description or ""),
        "filename": str(row.filename or "") or None,
        "mime_type": str(row.mime_type or "") or None,
        "size_bytes": int(row.size_bytes or 0),
        "sha256": str(row.sha256 or "") or None,
        "is_enabled": bool(row.is_enabled),
        "status": "enabled" if row.is_enabled else "disabled",
        "has_file": bool(row.storage_path),
        "file_exists": bool(row.storage_path),
        "tags": list(row.tags or []),
        "source_url": str(row.source_url or "") or None,
        "url": url_for("image_library.image_content", image_key=row.image_key),
        "preview_url": url_for("image_library.admin_preview", asset_id=row.id),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_image_assets(
    *,
    search_term: str = "",
    tag: str | None = None,
    status: str = "",
    page: int = 1,
    per_page: int = 24,
) -> dict[str, Any]:
    result = image_library_repository.list_assets(
        search_term=search_term,
        tag=tag,
        status=status,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [serialize_image_asset(row) for row in result.items],
        "page": result.page,
        "per_page": result.per_page,
        "total": result.total,
        "pages": result.total_pages,
        "has_prev": result.has_prev,
        "has_next": result.has_next,
        "summary": image_library_repository.count_summary(),
        "filters": {"q": search_term, "tag": tag or "", "status": status or "all"},
    }


def save_image_asset(
    *,
    actor_user_id: int,
    payload: dict[str, Any],
    uploaded_file: Any = None,
    row: SharedImageAsset | None = None,
) -> SharedImageAsset:
    try:
        validated_upload = image_library_service.prepare_image_upload(
            uploaded_file,
            source_url=str(payload.get("source_url") or ""),
            file_data=payload.get("file_data") or payload.get("file") or None,
            filename=str(payload.get("filename") or "") or None,
            max_bytes=int(
                current_app.config.get(
                    "IMAGE_LIBRARY_MAX_BYTES",
                    current_app.config.get(
                        "FLASHCARD_MEDIA_MAX_BYTES",
                        5 * 1024 * 1024,
                    ),
                )
            ),
            max_pixels=int(
                current_app.config.get("IMAGE_LIBRARY_MAX_PIXELS", 25_000_000)
            ),
            remote_timeout_seconds=float(
                current_app.config.get(
                    "IMAGE_LIBRARY_REMOTE_FETCH_TIMEOUT_SECONDS",
                    6,
                )
            ),
            remote_max_redirects=int(
                current_app.config.get(
                    "IMAGE_LIBRARY_REMOTE_FETCH_MAX_REDIRECTS",
                    3,
                )
            ),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(
                current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)
            ),
        )
        tags_val = payload.get("tags")
        source_url_val = payload.get("source_url")
        raw_key = payload.get("image_key") or payload.get("name") or ""
        if row is None:
            return image_library_service.create_image(
                image_key=raw_key,
                description=payload.get("description") or "",
                is_enabled=parse_enabled_value(
                    payload.get("is_enabled") if "is_enabled" in payload else (payload.get("status") == "enabled" if "status" in payload else None),
                    default=True if ("status" in payload or "is_enabled" in payload) else False,
                ),
                tags=tags_val,
                source_url=source_url_val,
                validated_upload=validated_upload,
                upload_root=Path(
                    current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
                ).resolve(),
                actor_user_id=actor_user_id,
            )
        return image_library_service.update_image(
            row=row,
            description=(
                payload.get("description")
                if "description" in payload
                else row.description or ""
            ),
            is_enabled=parse_enabled_value(
                payload.get("is_enabled") if "is_enabled" in payload else (payload.get("status") == "enabled" if "status" in payload else None),
                default=bool(row.is_enabled),
            ),
            tags=tags_val if "tags" in payload else None,
            source_url=source_url_val if "source_url" in payload else None,
            validated_upload=validated_upload,
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ).resolve(),
            actor_user_id=actor_user_id,
        )
    except RequestValidationError as exc:
        raise AdminRestApiError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc
    except image_library_service.ImageLibraryConflictError as exc:
        raise AdminRestApiError(
            "CONFLICT",
            "image_key already exists.",
            status=409,
            field="image_key",
        ) from exc
    except image_library_service.ImageLibraryPersistenceError as exc:
        raise AdminRestApiError(
            "DB_ERROR",
            "Could not save the image asset.",
            status=500,
        ) from exc


def delete_image_asset(
    *,
    actor_user_id: int,
    row: SharedImageAsset,
) -> None:
    try:
        image_library_service.delete_image(
            row=row,
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ).resolve(),
            actor_user_id=actor_user_id,
        )
    except image_library_service.ImageLibraryPersistenceError as exc:
        raise AdminRestApiError(
            "DB_ERROR",
            "Could not delete image library entry.",
            status=500,
        ) from exc


def set_image_asset_enabled(
    *,
    actor_user_id: int,
    row: SharedImageAsset,
    is_enabled: bool,
) -> SharedImageAsset:
    try:
        return image_library_service.set_enabled(
            row=row,
            is_enabled=is_enabled,
            actor_user_id=actor_user_id,
        )
    except image_library_service.ImageLibraryPersistenceError as exc:
        raise AdminRestApiError(
            "DB_ERROR",
            "Could not update the image status.",
            status=500,
        ) from exc


def _json_text(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")
