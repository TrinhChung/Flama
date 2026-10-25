"""Usage quota configuration: one policy per quota kind plus per-user overrides.

Counters live in Redis (see ``app.services.quota_service``); these tables only
hold what an admin configures, so they are written rarely and read through a
short in-process cache.
"""

from datetime import datetime

from models import db


QUOTA_KINDS = ("api", "mcp", "media")
QUOTA_PERIODS = ("day", "month", "year")
UNLIMITED = -1


class QuotaPolicy(db.Model):
    """Platform-wide rule for one quota kind (API, MCP or media upload)."""

    __tablename__ = "quota_policies"
    __table_args__ = (
        db.CheckConstraint("period IN ('day', 'month', 'year')", name="ck_quota_policies_period"),
    )

    quota_kind = db.Column(db.String(16), primary_key=True)
    # False = monitor only: usage is counted, nobody is blocked.
    enforce = db.Column(db.Boolean, nullable=False, default=False)
    period = db.Column(db.String(8), nullable=False, default="day")
    # Role code -> limit per period (requests, or MB for media); -1 or a
    # missing role means unlimited. Read only through the service cache.
    role_limits = db.Column(db.JSON, nullable=False, default=dict)
    # No foreign key on purpose: it would add an index for an audit-only field.
    updated_by_user_id = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserQuotaOverride(db.Model):
    """Admin-granted limit for one user and quota kind, optionally until a date."""

    __tablename__ = "user_quota_overrides"
    __table_args__ = (
        db.CheckConstraint(
            "period IS NULL OR period IN ('day', 'month', 'year')",
            name="ck_user_quota_overrides_period",
        ),
        db.CheckConstraint("limit_value >= -1", name="ck_user_quota_overrides_limit"),
    )

    # The composite primary key also covers the user_id foreign key, so InnoDB
    # needs no secondary index.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    quota_kind = db.Column(db.String(16), primary_key=True)
    limit_value = db.Column(db.BigInteger, nullable=False)
    # NULL follows the policy period.
    period = db.Column(db.String(8), nullable=True)
    # NULL never expires; afterwards the role default applies again.
    expires_at = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.String(255), nullable=True)
    updated_by_user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
