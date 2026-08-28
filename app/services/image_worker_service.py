"""Image worker execution engine for asynchronous downloading, sanitizing and conversion."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.services.image_processor import process_image_preset
from app.services.image_queue_service import pop_image_job
from app.services.image_security_service import ImageSecurityError, validate_image_security
from app.services.remote_image_fetcher import fetch_remote_image
from app.validators import RequestValidationError, resolve_safe_storage_path
from models import db
from models.image_asset import ImageAsset

logger = logging.getLogger(__name__)


def process_single_image_asset(
    asset_id: str,
    *,
    upload_root: Path,
    max_retries: int = 3,
    timeout_seconds: float = 10.0,
    max_bytes: int = 15 * 1024 * 1024,
    max_pixels: int = 25_000_000,
) -> ImageAsset | None:
    """Download, validate, resize, and persist an ImageAsset asynchronously."""
    asset = ImageAsset.query.get(asset_id)
    if asset is None:
        logger.warning("Worker skipped missing ImageAsset: %s", asset_id)
        return None

    if asset.processing_status in {"ready", "rejected"}:
        return asset

    if asset.retry_count >= max_retries:
        asset.processing_status = "failed"
        asset.last_error = f"Exceeded maximum retry attempts ({max_retries})."
        db.session.commit()
        return asset

    asset.processing_status = "processing"
    db.session.commit()

    raw_bytes: bytes | None = None
    original_filename = asset.original_filename or "image"
    resolved_root = upload_root.resolve()

    try:
        # Step 1: Obtain source bytes
        if asset.source_type == "external_url" or (asset.source_url and not asset.storage_path):
            try:
                remote_payload = fetch_remote_image(
                    asset.source_url,
                    max_bytes=max_bytes,
                    timeout_seconds=timeout_seconds,
                    max_redirects=3,
                )
                raw_bytes = remote_payload.content
                original_filename = remote_payload.filename
                asset.original_mime_type = remote_payload.mime_type
            except RequestValidationError as exc:
                asset.retry_count += 1
                asset.last_error = f"Fetch failed: {exc}"
                asset.processing_status = "failed"
                db.session.commit()
                logger.warning("Failed to fetch remote image for asset %s: %s", asset_id, exc)
                return asset
        elif asset.storage_path:
            full_path = resolve_safe_storage_path(
                upload_root=resolved_root,
                relative_path=Path(asset.storage_path),
            )
            if full_path.exists() and full_path.is_file():
                raw_bytes = full_path.read_bytes()

        if not raw_bytes:
            asset.retry_count += 1
            asset.last_error = "No source image data available to process."
            asset.processing_status = "failed"
            db.session.commit()
            return asset

        asset.original_size_bytes = len(raw_bytes)

        # Step 2: Validate security & raster integrity
        try:
            detected_mime, orig_w, orig_h = validate_image_security(
                raw_bytes,
                filename=original_filename,
                max_bytes=max_bytes,
                max_pixels=max_pixels,
                user_id=asset.owner_user_id,
                source_url=asset.source_url,
            )
            asset.original_mime_type = detected_mime
            asset.original_width = orig_w
            asset.original_height = orig_h
        except ImageSecurityError as sec_err:
            asset.security_status = "blocked"
            asset.security_reason = str(sec_err)
            asset.processing_status = "rejected"
            asset.last_error = str(sec_err)
            db.session.commit()
            logger.warning("ImageAsset %s rejected due to security violation: %s", asset_id, sec_err)
            return asset

        # Step 3: Process and optimize according to preset
        processed = process_image_preset(
            raw_bytes,
            preset_name=asset.preset,
            usage_type=asset.usage_type,
        )

        # Step 4: Persist to managed storage
        relative_path = Path("assets") / asset.id / f"{processed.sha256[:16]}.webp"
        managed_file_path = resolve_safe_storage_path(
            upload_root=resolved_root,
            relative_path=relative_path,
        )
        managed_file_path.parent.mkdir(parents=True, exist_ok=True)
        managed_file_path.write_bytes(processed.content)

        # Step 5: Atomic update
        asset.storage_path = str(relative_path).replace("\\", "/")
        asset.managed_url = f"/media/asset/{asset.id}"
        asset.display_url = asset.managed_url
        asset.output_mime_type = processed.mime_type
        asset.output_width = processed.width
        asset.output_height = processed.height
        asset.output_size_bytes = processed.size_bytes
        asset.sha256 = processed.sha256
        asset.processing_status = "ready"
        asset.security_status = "safe"
        asset.processed_at = datetime.utcnow()
        asset.last_error = None
        db.session.commit()

        logger.info(
            "ImageAsset %s successfully processed and replaced with managed URL %s (%sx%s, %d bytes)",
            asset.id,
            asset.managed_url,
            processed.width,
            processed.height,
            processed.size_bytes,
        )
        return asset

    except Exception as exc:
        db.session.rollback()
        asset.retry_count += 1
        asset.last_error = str(exc)
        if asset.retry_count >= max_retries:
            asset.processing_status = "failed"
        else:
            asset.processing_status = "pending"
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
        logger.exception("Unexpected error processing ImageAsset %s: %s", asset_id, exc)
        return asset


def drain_image_queue(
    *,
    upload_root: Path,
    max_jobs: int = 100,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Process pending jobs from the queue until exhausted or max_jobs reached."""
    processed_count = 0
    failed_count = 0
    rejected_count = 0

    while processed_count + failed_count + rejected_count < max_jobs:
        job = pop_image_job(timeout=0)
        if not job:
            break
        asset_id = str(job.get("asset_id") or "").strip()
        if not asset_id:
            continue
        result = process_single_image_asset(
            asset_id,
            upload_root=upload_root,
            max_retries=max_retries,
        )
        if result is None:
            failed_count += 1
        elif result.processing_status == "ready":
            processed_count += 1
        elif result.processing_status == "rejected":
            rejected_count += 1
        else:
            failed_count += 1

    return {
        "processed_count": processed_count,
        "failed_count": failed_count,
        "rejected_count": rejected_count,
    }
