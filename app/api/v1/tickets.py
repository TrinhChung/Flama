from __future__ import annotations

from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required

from app.services import support_ticket_service
from app.services.support_ticket_service import TicketServiceError
from app.utils.permissions import is_admin_user

tickets_bp = Blueprint("tickets", __name__)


def _get_upload_root() -> Path:
    return Path(current_app.config.get("FLASHCARD_MEDIA_UPLOAD_ROOT", "instance/uploads")).resolve()


@tickets_bp.post("/tickets/upload-image")
def upload_ticket_image():
    file_obj = request.files.get("file")
    if not file_obj:
        return jsonify({"error": "No file uploaded", "message": "Vui lòng chọn tập tin ảnh."}), 400

    try:
        url = support_ticket_service.save_ticket_attachment(
            file_storage=file_obj,
            upload_root=_get_upload_root(),
        )
        return jsonify({"url": url})
    except TicketServiceError as exc:
        return jsonify({"error": "UploadFailed", "message": exc.message}), exc.status_code
    except Exception as exc:
        return jsonify({"error": "InternalError", "message": str(exc)}), 500


@tickets_bp.get("/tickets/attachments/<filename>")
def serve_ticket_attachment(filename: str):
    try:
        full_path = support_ticket_service.resolve_attachment_file_path(
            filename=filename,
            upload_root=_get_upload_root(),
        )
        if not full_path.exists() or not full_path.is_file():
            return jsonify({"error": "NotFound", "message": "Không tìm thấy tập tin."}), 404

        ext = full_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        mimetype = mime_types.get(ext, "application/octet-stream")
        response = send_file(full_path, mimetype=mimetype, conditional=True, max_age=86400)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except TicketServiceError as exc:
        return jsonify({"error": "InvalidPath", "message": exc.message}), exc.status_code
    except Exception:
        return jsonify({"error": "NotFound", "message": "Không tìm thấy tập tin."}), 404


@tickets_bp.post("/tickets")
def create_ticket():
    data = request.get_json(silent=True) or {}

    user_id = current_user.id if current_user.is_authenticated else None
    user_email = current_user.email if current_user.is_authenticated else data.get("user_email")
    sender_name = current_user.username if current_user.is_authenticated else data.get("sender_name")

    try:
        ticket = support_ticket_service.create_ticket(
            user_id=user_id,
            user_email=user_email,
            sender_name=sender_name,
            category=data.get("category", "bug"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            reproduce_steps=data.get("reproduce_steps"),
            screen_url=data.get("screen_url"),
            screen_name=data.get("screen_name"),
            attachment_urls=data.get("attachment_urls"),
        )
        return jsonify({"message": "Tạo ticket thành công", "item": ticket.to_dict(include_replies=True)}), 201
    except TicketServiceError as exc:
        return jsonify({"error": "ValidationError", "message": exc.message}), exc.status_code
    except Exception as exc:
        return jsonify({"error": "InternalError", "message": str(exc)}), 500


@tickets_bp.get("/tickets/my")
def list_my_tickets():
    user_id = current_user.id if current_user.is_authenticated else None
    user_email = request.args.get("email") or (current_user.email if current_user.is_authenticated else None)

    items = support_ticket_service.list_user_tickets(user_id=user_id, user_email=user_email)
    return jsonify({"items": items})


@tickets_bp.get("/tickets/<ticket_id_or_code>")
def get_ticket_details(ticket_id_or_code: str):
    user_id = current_user.id if current_user.is_authenticated else None
    is_admin = is_admin_user(current_user)

    try:
        ticket = support_ticket_service.get_ticket_details(
            ticket_id_or_code=ticket_id_or_code,
            current_user_id=user_id,
            is_admin=is_admin,
        )
        return jsonify({"item": ticket.to_dict(include_replies=True)})
    except TicketServiceError as exc:
        return jsonify({"error": "PermissionDenied" if exc.status_code == 403 else "NotFound", "message": exc.message}), exc.status_code


@tickets_bp.post("/tickets/<ticket_id_or_code>/replies")
def add_ticket_reply(ticket_id_or_code: str):
    data = request.get_json(silent=True) or {}
    user_id = current_user.id if current_user.is_authenticated else None
    is_admin = is_admin_user(current_user)
    sender_name = current_user.username if current_user.is_authenticated else data.get("sender_name")

    try:
        reply = support_ticket_service.add_reply(
            ticket_id_or_code=ticket_id_or_code,
            user_id=user_id,
            is_admin=is_admin,
            message=data.get("message", ""),
            attachment_urls=data.get("attachment_urls"),
            sender_name=sender_name,
            new_status=data.get("new_status"),
        )
        return jsonify({"message": "Gửi phản hồi thành công", "item": reply.to_dict()}), 201
    except TicketServiceError as exc:
        return jsonify({"error": "ReplyError", "message": exc.message}), exc.status_code


# Admin endpoints
@tickets_bp.get("/admin/tickets")
@login_required
def list_admin_tickets():
    if not is_admin_user(current_user):
        return jsonify({"error": "Forbidden", "message": "Bạn không có quyền truy cập."}), 403

    status = request.args.get("status")
    category = request.args.get("category")
    priority = request.args.get("priority")
    search = request.args.get("q") or request.args.get("search")
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        page = 1
        per_page = 20

    data = support_ticket_service.list_admin_tickets(
        status=status,
        category=category,
        priority=priority,
        search=search,
        page=page,
        per_page=per_page,
    )
    return jsonify(data)


@tickets_bp.patch("/admin/tickets/<ticket_id>")
@login_required
def update_admin_ticket(ticket_id: str):
    if not is_admin_user(current_user):
        return jsonify({"error": "Forbidden", "message": "Bạn không có quyền thực hiện."}), 403

    data = request.get_json(silent=True) or {}
    try:
        ticket = support_ticket_service.update_ticket_admin(
            ticket_id=ticket_id,
            status=data.get("status"),
            priority=data.get("priority"),
            admin_notes=data.get("admin_notes"),
        )
        return jsonify({"message": "Cập nhật ticket thành công", "item": ticket.to_dict(include_replies=True)})
    except TicketServiceError as exc:
        return jsonify({"error": "UpdateFailed", "message": exc.message}), exc.status_code
