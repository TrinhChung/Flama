from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Any

from werkzeug.utils import secure_filename
from flask import current_app

from app.repositories import support_ticket_repository
from models.support_ticket import SupportTicket
from models.support_ticket_reply import SupportTicketReply

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


class TicketServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def generate_ticket_code() -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    random_hex = uuid.uuid4().hex[:6].upper()
    return f"TK-{date_str}-{random_hex}"


def save_ticket_attachment(
    file_storage: Any,
    upload_root: Path,
) -> str:
    """Validate and persist an uploaded image attachment. Returns the relative filename."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise TicketServiceError("Tập tin tải lên không hợp lệ.", 400)

    orig_filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(orig_filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise TicketServiceError("Chỉ chấp nhận tập tin ảnh (PNG, JPG, WEBP, GIF).", 400)

    # Check file size
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_ATTACHMENT_BYTES:
        raise TicketServiceError("Dung lượng tập tin vượt quá 10MB.", 400)

    unique_filename = f"ticket_{uuid.uuid4().hex[:12]}{ext}"
    target_dir = upload_root / "ticket_attachments"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / unique_filename

    file_storage.save(str(target_path))
    return f"/api/tickets/attachments/{unique_filename}"


def resolve_attachment_file_path(filename: str, upload_root: Path) -> Path:
    safe_name = os.path.basename(filename)
    file_path = (upload_root / "ticket_attachments" / safe_name).resolve()
    base_dir = (upload_root / "ticket_attachments").resolve()
    if not str(file_path).startswith(str(base_dir)):
        raise TicketServiceError("Đường dẫn không hợp lệ.", 400)
    return file_path


def create_ticket(
    user_id: int | None,
    user_email: str | None,
    sender_name: str | None,
    category: str,
    title: str,
    description: str,
    reproduce_steps: str | None = None,
    screen_url: str | None = None,
    screen_name: str | None = None,
    attachment_urls: list[str] | None = None,
) -> SupportTicket:
    title_clean = (title or "").strip()
    desc_clean = (description or "").strip()
    if not title_clean:
        raise TicketServiceError("Vui lòng nhập tiêu đề báo cáo lỗi.", 400)
    if not desc_clean:
        raise TicketServiceError("Vui lòng nhập nội dung mô tả chi tiết.", 400)

    valid_categories = {"bug", "feature", "ui", "other"}
    cat_clean = (category or "bug").strip().lower()
    if cat_clean not in valid_categories:
        cat_clean = "bug"

    ticket_code = generate_ticket_code()
    # Retry if code collision occurs
    while support_ticket_repository.get_ticket_by_code(ticket_code):
        ticket_code = generate_ticket_code()

    ticket = SupportTicket(
        ticket_code=ticket_code,
        user_id=user_id,
        user_email=(user_email or "").strip() or None,
        sender_name=(sender_name or "").strip() or None,
        category=cat_clean,
        title=title_clean,
        description=desc_clean,
        reproduce_steps=(reproduce_steps or "").strip() or None,
        screen_url=(screen_url or "").strip() or None,
        screen_name=(screen_name or "").strip() or None,
        status="open",
        priority="medium",
    )
    if attachment_urls:
        ticket.attachment_urls = [u.strip() for u in attachment_urls if u.strip()]

    return support_ticket_repository.create_ticket(ticket)


def get_ticket_details(
    ticket_id_or_code: str,
    current_user_id: int | None = None,
    is_admin: bool = False,
) -> SupportTicket:
    ticket = support_ticket_repository.get_ticket_by_code(ticket_id_or_code)
    if not ticket:
        ticket = support_ticket_repository.get_ticket_by_id(ticket_id_or_code)

    if not ticket:
        raise TicketServiceError("Không tìm thấy ticket yêu cầu.", 404)

    # Permission check: Admin or Ticket owner
    if not is_admin:
        if current_user_id is None or ticket.user_id != current_user_id:
            raise TicketServiceError("Bạn không có quyền xem ticket này.", 403)

    return ticket


def list_user_tickets(user_id: int | None, user_email: str | None = None) -> list[dict]:
    tickets = support_ticket_repository.list_user_tickets(user_id=user_id, user_email=user_email)
    return [t.to_dict(include_replies=False) for t in tickets]


def list_admin_tickets(
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    tickets, total_count = support_ticket_repository.list_admin_tickets(
        status=status,
        category=category,
        priority=priority,
        search=search,
        page=page,
        per_page=per_page,
    )
    stats = support_ticket_repository.get_admin_stats()
    return {
        "items": [t.to_dict(include_replies=False) for t in tickets],
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "stats": stats,
    }


def update_ticket_admin(
    ticket_id: str,
    status: str | None = None,
    priority: str | None = None,
    admin_notes: str | None = None,
) -> SupportTicket:
    ticket = support_ticket_repository.get_ticket_by_id(ticket_id)
    if not ticket:
        raise TicketServiceError("Không tìm thấy ticket.", 404)

    if status and status.strip():
        valid_statuses = {"open", "in_progress", "resolved", "closed", "rejected"}
        st_clean = status.strip().lower()
        if st_clean in valid_statuses:
            ticket.status = st_clean
            if st_clean in {"resolved", "closed"} and not ticket.resolved_at:
                ticket.resolved_at = datetime.utcnow()
            elif st_clean in {"open", "in_progress"}:
                ticket.resolved_at = None

    if priority and priority.strip():
        valid_priorities = {"low", "medium", "high", "urgent"}
        pr_clean = priority.strip().lower()
        if pr_clean in valid_priorities:
            ticket.priority = pr_clean

    if admin_notes is not None:
        ticket.admin_notes = admin_notes.strip()

    return support_ticket_repository.save_ticket(ticket)


def add_reply(
    ticket_id_or_code: str,
    user_id: int | None,
    is_admin: bool,
    message: str,
    attachment_urls: list[str] | None = None,
    sender_name: str | None = None,
    new_status: str | None = None,
) -> SupportTicketReply:
    ticket = support_ticket_repository.get_ticket_by_code(ticket_id_or_code)
    if not ticket:
        ticket = support_ticket_repository.get_ticket_by_id(ticket_id_or_code)

    if not ticket:
        raise TicketServiceError("Không tìm thấy ticket.", 404)

    if not is_admin:
        if user_id is None or ticket.user_id != user_id:
            raise TicketServiceError("Bạn không có quyền gửi phản hồi cho ticket này.", 403)

    msg_clean = (message or "").strip()
    if not msg_clean:
        raise TicketServiceError("Vui lòng nhập nội dung phản hồi.", 400)

    reply = SupportTicketReply(
        ticket_id=ticket.id,
        user_id=user_id,
        is_admin_reply=is_admin,
        sender_name=(sender_name or "").strip() or None,
        message=msg_clean,
    )
    if attachment_urls:
        reply.attachment_urls = [u.strip() for u in attachment_urls if u.strip()]

    created_reply = support_ticket_repository.add_reply(reply)

    # Auto update ticket status
    if is_admin:
        if new_status and new_status.strip().lower() in {"open", "in_progress", "resolved", "closed", "rejected"}:
            ticket.status = new_status.strip().lower()
            if ticket.status in {"resolved", "closed"} and not ticket.resolved_at:
                ticket.resolved_at = datetime.utcnow()
        elif ticket.status == "open":
            ticket.status = "in_progress"
    else:
        # If user replies on a resolved/closed ticket, optionally re-open to in_progress
        if ticket.status in {"resolved", "closed"}:
            ticket.status = "in_progress"
            ticket.resolved_at = None

    support_ticket_repository.save_ticket(ticket)
    return created_reply
