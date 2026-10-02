"""Rare compatibility usage, retained in the service journal across workers.

Logs contain fixed labels only. Operators must attest continuous journal
coverage; an empty/missing log is never evidence of zero usage.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging

SCHEMA_VERSION = "study-retirement-usage.v1"
OBSERVATION_SCHEMA = "study-retirement-observation.v1"
ENTRYPOINTS = {
    "old_session_wire_versions": frozenset({"session.issue", "session.restore", "session.commit", "worker.batch"}),
    "positional_anki_ordinals": frozenset({"anki.ordinal"}),
}
logger = logging.getLogger(__name__)


def record_legacy_usage(entrypoint: str, *, wire: str | None = None) -> None:
    if entrypoint not in set().union(*ENTRYPOINTS.values()):
        raise ValueError("Unknown retirement telemetry entrypoint")
    if wire is not None and wire == "study-session.v4":
        return
    # Do not copy an arbitrary client version into labels or log payloads.
    version = wire if wire in {"study-session.v2", "study-session.v3"} else "unknown"
    logger.warning("STUDY_RETIREMENT %s", json.dumps({
        "schema_version": SCHEMA_VERSION, "entrypoint": entrypoint, "wire": version,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    }, sort_keys=True))


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Observation timestamps must explicitly be UTC")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def retirement_usage_evidence(observation: dict | None, *, gate: str, since: datetime, now: datetime) -> dict:
    expected = ENTRYPOINTS[gate]
    result = {"status": "unknown", "blocking_reasons": ["MISSING_CONTINUOUS_TELEMETRY"],
              "window_start_utc": since.isoformat() + "Z", "window_end_utc": now.isoformat() + "Z",
              "required_entrypoints": sorted(expected), "counts": {}, "last_use_utc": None}
    if observation is None:
        return result
    if observation.get("schema_version") != OBSERVATION_SCHEMA:
        raise ValueError("Unsupported retirement observation schema")
    if (not isinstance(observation.get("continuous"), bool)
            or not isinstance(observation.get("gaps"), list)
            or not isinstance(observation.get("covered_entrypoints"), list)
            or not isinstance(observation.get("events"), list)):
        raise ValueError("Observation must explicitly include coverage, gaps and events")
    start, end = _utc(observation["start_utc"]), _utc(observation["end_utc"])
    if end < start or end > now:
        raise ValueError("Invalid retirement observation interval")
    counts, last = {}, None
    for event in observation.get("events", []):
        if event.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported retirement usage event")
        when = _utc(event["observed_at_utc"])
        if not start <= when <= end:
            raise ValueError("Usage event falls outside its retained observation interval")
        entrypoint = event.get("entrypoint")
        if entrypoint not in set().union(*ENTRYPOINTS.values()):
            raise ValueError("Unknown retirement usage label")
        if entrypoint in expected and since <= when <= now:
            counts[entrypoint] = counts.get(entrypoint, 0) + 1
            last = max(last, when) if last else when
    covered = set(observation.get("covered_entrypoints", []))
    complete = (observation.get("continuous") is True and not observation.get("gaps")
                and start <= since and end == now and expected <= covered)
    result.update(counts=counts, last_use_utc=last.isoformat() + "Z" if last else None,
                  coverage_complete=complete, covered_entrypoints=sorted(covered))
    if counts:
        result.update(status="waiting", blocking_reasons=["LEGACY_RUNTIME_USAGE"])
    elif complete:
        result.update(status="ready", blocking_reasons=[])
    return result
