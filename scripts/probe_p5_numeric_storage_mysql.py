"""Inspect FLOAT/DOUBLE round-trips without touching the configured database.

This is evidence for the NOTE precision decision, not a migration. DDL and
sample values exist only inside a generated, guarded local MySQL database.
"""

from __future__ import annotations

import json
import os
import math
from pathlib import Path
import random
import re
import secrets
import struct
import sys

from dotenv import load_dotenv
import pymysql

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.probe_phase4_shadow_schema_mysql import _connection_settings, _source_database_collation
from app.services.study_note_storage_precision import legacy_float_round_trip

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_numeric_probe_[0-9]+_[a-f0-9]{8}$")


def run_probe():
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p5_numeric_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("Numeric storage probe requires a generated local MySQL database.")
    connection = pymysql.connect(**settings)
    created = False
    report = {}
    try:
        collation = _source_database_collation(connection)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            connection.select_db(name)
            cursor.execute("CREATE TABLE scalar_sample (id INT PRIMARY KEY, narrow_value FLOAT NOT NULL, wide_value DOUBLE NOT NULL, copied_text DOUBLE NULL)")
            values = [2.35, 2.65, 1.3, 2.5, 5.0, 1 / 3, 1e-20, 1e20, 0.0, -0.0]
            values.append(struct.unpack(">f", struct.pack(">f", 2.35))[0])
            for index, value in enumerate(values):
                cursor.execute("INSERT INTO scalar_sample (id, narrow_value, wide_value) VALUES (%s, %s, %s)", (index, value, value))
            cursor.execute("UPDATE scalar_sample SET copied_text = CAST(CAST(narrow_value AS CHAR) AS DOUBLE)")
            cursor.execute("SELECT id, narrow_value, wide_value, copied_text, CAST(narrow_value AS DOUBLE) FROM scalar_sample ORDER BY id")
            before = cursor.fetchall()
            cursor.execute("ALTER TABLE scalar_sample MODIFY narrow_value DOUBLE NOT NULL")
            cursor.execute("SELECT id, narrow_value FROM scalar_sample ORDER BY id")
            after = dict(cursor.fetchall())
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            # Compare the proposed model against the actual driver, including
            # ties, exponent boundaries, subnormals and signed zero. Reinsert
            # the normalized values to verify the profile is a fixed point.
            cursor.execute("CREATE TABLE precision_sample (id INT PRIMARY KEY, raw_value FLOAT NOT NULL, normalized_value FLOAT NOT NULL)")
            rng = random.Random(20260927)
            candidates = values + [1.015625, 1.046875, -1.015625, -1.046875]
            candidates += [struct.unpack(">f", struct.pack(">I", bits))[0] for bits in (
                1, 2, 0x007fffff, 0x00800000, 0x00800001, 0x7f7fffff,
                0x80000001, 0x807fffff, 0x80800000, 0xff7fffff,
            )]
            for _ in range(4096):
                candidate = struct.unpack(">f", struct.pack(">I", rng.getrandbits(32)))[0]
                if math.isfinite(candidate):
                    candidates.append(candidate)
            cursor.executemany(
                "INSERT INTO precision_sample VALUES (%s, %s, %s)",
                [(index, value, legacy_float_round_trip(value)) for index, value in enumerate(candidates)],
            )
            cursor.execute("SELECT id, raw_value, normalized_value FROM precision_sample ORDER BY id")
            mismatches = []
            for index, observed, normalized in cursor.fetchall():
                expected = legacy_float_round_trip(candidates[index])
                if struct.pack(">d", observed) != struct.pack(">d", expected) or struct.pack(">d", normalized) != struct.pack(">d", expected):
                    mismatches.append({"input": candidates[index], "expected": expected, "observed": observed, "normalized_read": normalized})
        samples = [{
            "input": values[index], "float_read": narrow, "double_read": wide,
            "float_cast_double": cast_double, "float_widened_read": after[index],
            "text_copy_read": copied,
            "wide_preserves_input_bits": struct.pack(">d", wide) == struct.pack(">d", values[index]),
            "alter_preserves_observed_float_bits": struct.pack(">d", narrow) == struct.pack(">d", after[index]),
            "text_copy_preserves_observed_float_bits": struct.pack(">d", narrow) == struct.pack(">d", copied),
        } for index, narrow, wide, copied, cast_double in before]
        report.update({
            "schema_version": "p5-numeric-storage-observation.v1", "mysql_version": version,
            "samples": samples, "configured_database_modified": False,
            "migration_or_precision_policy_verified": False,
            "text_profile_samples": len(candidates),
            "text_profile_mismatch_count": len(mismatches),
            "text_profile_mismatches": mismatches[:10],
            "text_profile_status": "PASS" if not mismatches else "FAIL",
        })
        return report
    finally:
        try:
            if created:
                if not PROBE_NAME_PATTERN.fullmatch(name):
                    raise RuntimeError("Refusing an unsafe numeric probe cleanup target.")
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE `{name}`")
                report["probe_database_removed"] = True
        finally:
            connection.close()


if __name__ == "__main__":
    result = run_probe()
    print(json.dumps(result, sort_keys=True))
    if result["text_profile_mismatch_count"]:
        raise SystemExit(1)
