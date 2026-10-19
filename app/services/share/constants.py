"""Shared constants for flashcards share and clone operations."""

from datetime import timezone
from models.field_types import FIELD_TYPES as _FIELD_TYPES

UTC = timezone.utc
FIELD_TYPES = set(_FIELD_TYPES)
DEFAULT_VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}
PUBLISH_STATUSES_VISIBLE = {"published", "unlisted"}
MARKET_ACTIVITY_POLICY_VERSION = 1

NOTE_TYPE_ACTIVE_DAYS_THRESHOLD = 3
NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD = 3
NOTE_TYPE_ACTIVE_NOTE_THRESHOLD = 3
DECK_ACTIVE_REVIEW_THRESHOLD = 3

SHARED_DECK_TEST_SAMPLE_LIMIT = 5
SHARED_DECK_INSTALL_MAX_RETRIES = 3
SHARED_DECK_INSTALL_DEADLOCK_MESSAGE = (
    "Hệ thống đang bận khi cài deck này. Vui lòng thử lại sau vài giây."
)

