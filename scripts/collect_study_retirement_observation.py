"""Combine a retained journal export with an operator-reviewed coverage record.

This does not infer coverage from silence. The coverage file must specify
the actual UTC interval, covered entrypoints, gaps, and ``continuous``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.study_retirement_telemetry_service import (  # noqa: E402
    ENTRYPOINTS, OBSERVATION_SCHEMA, retirement_usage_evidence, _utc,
)


def collect_observation(journal_path: Path, coverage_path: Path) -> dict:
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    if not isinstance(coverage.get("continuous"), bool) or not isinstance(coverage.get("gaps"), list):
        raise ValueError("Coverage must explicitly state continuous and gaps")
    result = {**coverage, "schema_version": OBSERVATION_SCHEMA, "events": []}
    digest = hashlib.sha256()
    with journal_path.open("rb") as source:
        for raw in source:
            digest.update(raw)
            if not raw.strip():
                continue
            row = json.loads(raw)
            message = str(row.get("MESSAGE", ""))
            marker = "STUDY_RETIREMENT "
            if marker in message:
                result["events"].append(json.loads(message.split(marker, 1)[1]))
    result["journal_sha256"] = digest.hexdigest()
    result["coverage_sha256"] = hashlib.sha256(coverage_path.read_bytes()).hexdigest()
    end = _utc(result["end_utc"])
    for gate in ENTRYPOINTS:
        retirement_usage_evidence(result, gate=gate, since=_utc(result["start_utc"]), now=end)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect_observation(args.journal, args.coverage)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
