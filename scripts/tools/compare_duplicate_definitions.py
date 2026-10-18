#!/usr/bin/env python3
"""Compare top-level functions/classes of a package with one reference module.

For every top-level definition in the package files, report whether the
reference module defines the same name with an identical AST (ignoring line
numbers), a different body, or not at all. Used to prove that a package is a
stale copy before deleting it.

Usage:
  python scripts/tools/compare_duplicate_definitions.py PACKAGE_DIR REFERENCE_MODULE
Example:
  python scripts/tools/compare_duplicate_definitions.py app/services/release app/services/deck_release_service.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def definitions(path: Path) -> dict[str, ast.AST]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def main(package_dir: Path, reference: Path) -> int:
    reference_defs = definitions(reference)
    rows: list[tuple[str, str, str]] = []
    for path in sorted(package_dir.glob("*.py")):
        for name, node in definitions(path).items():
            other = reference_defs.get(name)
            if other is None:
                status = "MISSING_IN_REFERENCE"
            elif ast.dump(node, include_attributes=False) == ast.dump(other, include_attributes=False):
                status = "IDENTICAL"
            else:
                status = "DIFFERENT"
            rows.append((path.as_posix(), name, status))
    counts: dict[str, int] = {}
    for _, _, status in rows:
        counts[status] = counts.get(status, 0) + 1
    print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    for file_name, name, status in rows:
        if status != "IDENTICAL":
            print(f"{status} {file_name}:{name}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
