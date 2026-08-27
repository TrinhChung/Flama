"""Shared constants for flashcards share and clone operations."""

from datetime import timezone
from decimal import Decimal

UTC = timezone.utc
FIELD_TYPES = ("text", "markdown", "image", "diagram", "audio")
DEFAULT_VISIBLE_PUBLISH_STATUSES = ("published", "unlisted")
PUBLISH_STATUSES_VISIBLE = DEFAULT_VISIBLE_PUBLISH_STATUSES
MARKET_ACTIVITY_POLICY_VERSION = "2026-03-24"

NOTE_TYPE_ACTIVE_DAYS_THRESHOLD = 30
NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD = 5
NOTE_TYPE_ACTIVE_NOTE_THRESHOLD = 1
DECK_ACTIVE_REVIEW_THRESHOLD = 5

SHARED_DECK_INSTALL_MAX_RETRIES = 3
SHARED_DECK_INSTALL_DEADLOCK_MESSAGE = "Transaction was deadlocked. Retrying install..."
