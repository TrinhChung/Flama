"""Content-independent publication and three-way inheritance policy.

Adapters retain entity persistence, immutable snapshot formats and transaction
ownership. Both deck and template services execute these policies.
"""

from dataclasses import dataclass
import json
import re


@dataclass(frozen=True)
class PublishRequest:
    version_label: str
    idempotency_key: str
    expected_head_id: str | None
    expected_revision: object
    change_note: str | None
    mode: str = "manual"


def publish(adapter, request):
    """Replay, fence, plan and persist under the adapter's publisher lock."""
    existing = adapter.find_replay(request.idempotency_key)
    if existing is not None:
        if not adapter.matches_replay(existing, request):
            adapter.fail("IDEMPOTENCY_KEY_REUSED", "Idempotency-Key was already used for another release request.", field="Idempotency-Key")
        return existing, True
    if request.expected_head_id != adapter.head_id:
        adapter.fail("RELEASE_HEAD_STALE", "The published release changed. Refresh the preview and retry.", field="expected_current_release_id")
    if request.expected_revision is not None and request.expected_revision != adapter.revision:
        adapter.fail("WORKING_REVISION_STALE", "The owner working revision changed. Refresh the preview and retry.", field="expected_working_revision")
    if adapter.label_exists(request.version_label):
        adapter.fail("VERSION_ALREADY_EXISTS", "version_label already exists for this publication.", field="version_label")
    plan = adapter.plan()
    if adapter.head_id is not None and not adapter.has_changes(plan):
        adapter.fail("NO_RELEASE_CHANGES", "There are no unpublished source changes.")
    return adapter.persist(plan, request), False


def same(left, right):
    return json.dumps(left, sort_keys=True, ensure_ascii=True, separators=(",", ":")) == json.dumps(right, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def has_conflict(base, upstream, local):
    return not (same(local, upstream) or same(local, base) or same(upstream, base))


def merge_unit(base, upstream, local, *, resolution=None, manual_value=None):
    """Return (action, value); CLEAR means the upstream value needs no overlay."""
    if same(local, upstream) or same(local, base):
        return "clear", upstream
    if same(upstream, base):
        return "keep", local
    if resolution == "keep_upstream":
        return "clear", upstream
    if resolution == "keep_mine":
        return "keep", local
    if resolution == "manual":
        return ("clear" if same(manual_value, upstream) else "set"), manual_value
    return "conflict", None


def next_auto_version(current_label):
    if not current_label or not str(current_label).strip():
        return "1.0.0"
    label = str(current_label).strip()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", label)
    if match:
        major, minor, patch = map(int, match.groups())
        return f"{major}.{minor}.{patch + 1}"
    match = re.match(r"^v?(\d+)$", label, re.IGNORECASE)
    return f"v{int(match.group(1)) + 1}" if match else f"{label}.1"


def should_auto_publish(*, enabled, eligible, revision, published_revision):
    return bool(enabled and eligible and (published_revision is None or revision > published_revision))
