from __future__ import annotations

from datetime import datetime
from sqlalchemy import or_, func

from models import db
from models.support_ticket import SupportTicket
from models.support_ticket_reply import SupportTicketReply


def create_ticket(ticket: SupportTicket) -> SupportTicket:
    db.session.add(ticket)
    db.session.commit()
    return ticket


def get_ticket_by_id(ticket_id: str) -> SupportTicket | None:
    return db.session.get(SupportTicket, ticket_id)


def get_ticket_by_code(ticket_code: str) -> SupportTicket | None:
    return SupportTicket.query.filter_by(ticket_code=ticket_code).first()


def list_user_tickets(user_id: int | None, user_email: str | None = None) -> list[SupportTicket]:
    query = SupportTicket.query
    if user_id is not None:
        if user_email:
            query = query.filter(
                or_(
                    SupportTicket.user_id == user_id,
                    SupportTicket.user_email == user_email,
                )
            )
        else:
            query = query.filter(SupportTicket.user_id == user_id)
    elif user_email:
        query = query.filter(SupportTicket.user_email == user_email)
    else:
        return []

    return query.order_by(SupportTicket.created_at.desc()).all()


def list_admin_tickets(
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[SupportTicket], int]:
    query = SupportTicket.query

    if status and status.strip():
        query = query.filter(SupportTicket.status == status.strip().lower())

    if category and category.strip():
        query = query.filter(SupportTicket.category == category.strip().lower())

    if priority and priority.strip():
        query = query.filter(SupportTicket.priority == priority.strip().lower())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SupportTicket.ticket_code.ilike(term),
                SupportTicket.title.ilike(term),
                SupportTicket.description.ilike(term),
                SupportTicket.user_email.ilike(term),
                SupportTicket.sender_name.ilike(term),
                SupportTicket.screen_name.ilike(term),
            )
        )

    total_count = query.count()
    tickets = (
        query.order_by(SupportTicket.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return tickets, total_count


def get_admin_stats() -> dict[str, int]:
    stats = {
        "total": 0,
        "open": 0,
        "in_progress": 0,
        "resolved": 0,
        "closed": 0,
        "rejected": 0,
    }
    counts = (
        db.session.query(SupportTicket.status, func.count(SupportTicket.id))
        .group_by(SupportTicket.status)
        .all()
    )
    total = 0
    for st, count in counts:
        st_lower = str(st).lower()
        if st_lower in stats:
            stats[st_lower] = count
        total += count
    stats["total"] = total
    return stats


def add_reply(reply: SupportTicketReply) -> SupportTicketReply:
    db.session.add(reply)
    db.session.commit()
    return reply


def save_ticket(ticket: SupportTicket) -> SupportTicket:
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    return ticket
