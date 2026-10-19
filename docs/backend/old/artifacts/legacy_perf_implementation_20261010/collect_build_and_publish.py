"""Collect existing measurements and build manifests; never connect to a DB."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(build):
    baseline = ROOT / "docs/architecture/artifacts/legacy_perf_audit_20261010/results.json"
    spec = importlib.util.spec_from_file_location("historical_probe", baseline.parent / "probe.py")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    measured = probe.bundle(build)
    manifest = read(build / ".vite/manifest.json")
    locales = {key: row for key, row in manifest.items() if "/locales/" in key and key.endswith(".json")}
    current_js = {row["file"] for row in manifest.values() if row["file"].endswith(".js")}
    current_maps = [build / (name + ".map") for name in current_js]
    all_sources = [source for path in current_maps if path.exists() for source in read(path).get("sources", [])]
    measured.pop("largest_js", None)  # Old hashed files may remain in an external build directory.
    sources = ["frontend/src/shared/config/i18n/index.ts", "frontend/src/shared/config/i18n/resourceLoader.ts",
               "frontend/src/shared/config/i18n/loadGuard.ts", "frontend/src/main.tsx", "frontend/src/App.tsx",
               "frontend/src/features/study/session/sessionStore.ts", "frontend/src/features/study/session/sessionStorageCodec.ts"]
    report = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "build_directory": str(build), "manifest_sha256": sha(build / ".vite/manifest.json"),
        "source_capture_sha256": {name: sha(ROOT / name) for name in sources},
        "baseline_artifact_sha256": sha(baseline), "baseline_entry": read(baseline)["bundle"]["index.html"],
        "current_bundle": measured, "dynamic_locale_entries": len(locales),
        "all_locale_entries_dynamic": all(row.get("isDynamicEntry") for row in locales.values()),
        "test_resources_in_production": any("testResources" in source for source in all_sources),
        "scope": "Static transitive JS imports only, per-file gzip level 9. Boot common/shell and route dictionaries load dynamically in addition; not network transfer/LCP.",
    }
    assert len(locales) == 52 and report["all_locale_entries_dynamic"]
    assert not report["test_resources_in_production"]
    assert not measured["index.html"]["locale_json_sources"]
    (HERE / "build_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    paths = [ROOT / "output/publish_options_mysql_before_20261010.json",
             ROOT / "output/publish_options_mysql_after_20261010.json",
             ROOT / "output/publish_options_mysql_after_final_20261010.json"]
    runs = []
    for path in paths:
        source = read(path)
        keys = ("user_id", "live_decks", "owned_cards", "warm_http", "warm_service", "warm_sql_cursor",
                "sql_statements_range", "service_peak_allocations_MiB", "payload_bytes", "payload_sha256",
                "stable_payload", "modular_payload_parity")
        runs.append({"source_artifact": str(path.relative_to(ROOT)), "source_artifact_sha256": sha(path),
                     **{key: source[key] for key in ("measured_at_utc", "git_head", "source_sha256", "method", "source_unchanged_during_measurement", "passed")},
                     "mysql": {key: source["mysql"][key] for key in ("version", "buffer_pool_MiB")},
                     "users": [{key: user[key] for key in keys} for user in source["users"]]})
    first = {user["user_id"]: user for user in runs[0]["users"]}
    for run in runs[1:]:
        assert all(user["payload_sha256"] == first[user["user_id"]]["payload_sha256"] for user in run["users"])
        assert run["source_unchanged_during_measurement"] and run["passed"]
    result = {"runs": runs,
              "provenance_note": "First AFTER run omitted the new deck_publish_index.py from its source capture. Final AFTER rerun includes it and verifies all captured sources remained unchanged. Runs use the same configured local MySQL dump, without source/data writes; order/time differ and latency varies. No production SLO claim."}
    variants_path = ROOT / "output/publish_options_sql_variants_final_20261010.json"
    if variants_path.exists():
        variants = read(variants_path)
        result["sql_variants"] = {"source_artifact_sha256": sha(variants_path),
                                  **{key: variants[key] for key in ("read_only", "repetitions", "passed")},
                                  "queries": {name: {key: row[key] for key in ("samples", "median_ms", "p95_ms", "rows", "payload_parity")}
                                              for name, row in variants["queries"].items()}}
    (HERE / "publish_mysql_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"entry_raw_bytes": measured["index.html"]["static_js_raw_bytes"],
                      "entry_gzip_bytes": measured["index.html"]["static_js_gzip_bytes"],
                      "dynamic_locale_entries": len(locales), "publish_payload_parity": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    collect(parser.parse_args().build.resolve())
