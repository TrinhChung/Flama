"""Compatibility facade for flashcards sharing functionality."""
from __future__ import annotations

import logging
import sys
import time

from app.services import share as _share_pkg
from app.services.share.constants import *  # noqa: F401, F403
from app.services.share.helpers import *  # noqa: F401, F403
from app.services.share.note_types import *  # noqa: F401, F403
from app.services.share.publish import *  # noqa: F401, F403
from app.services.share.overlay import *  # noqa: F401, F403
from app.services.share.install import *  # noqa: F401, F403
from app.services.share.cutover import *  # noqa: F401, F403

# Re-export all internal helpers from share package (e.g. _stage_initial_release_if_visible, _is_mysql_deadlock)
for _attr_name in dir(_share_pkg):
    if not _attr_name.startswith("__"):
        globals()[_attr_name] = getattr(_share_pkg, _attr_name)

logger = logging.getLogger(__name__)

# Keep self-references stable while legacy call sites are migrated.
flashcards_share = sys.modules[__name__]
