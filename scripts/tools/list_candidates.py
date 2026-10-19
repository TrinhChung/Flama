#!/usr/bin/env python3
"""Write the candidate lines of an inventory task with ``git grep -n``.

Patterns live here so no shell has to escape them (PowerShell mangles quotes
passed to native commands). Output goes to
``docs/logs/old/reports/<preset>.txt`` and the line/file counts
are printed.

Usage: python scripts/tools/list_candidates.py PRESET
Presets: gt16-backend, gt16-frontend, gt17-defs, gt17-callers, gt17-kinds
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RELEASE_SERVICES = [
    "app/services/deck_release_service.py",
    "app/services/deck_install_rebase_service.py",
    "app/services/deck_working_tree_service.py",
    "app/services/deck_auto_publish_service.py",
]

PRESETS: dict[str, tuple[str, list[str]]] = {
    "gt16-backend": (
        r"\bTemplate\b|\.template\b|template_id|\.templates\b|front_html|back_html|shared_css",
        [
            "app/*.py",
            "models/*.py",
            "connect_wsgi.py",
            "study_worker.py",
            ":(exclude)app/services/worksheets/*",
            ":(exclude)app/api/v1/worksheets/*",
            ":(exclude)app/routes/worksheets*",
        ],
    ),
    "gt16-frontend": (
        r"template_id|front_html|back_html|shared_css|/templates\b|TemplateItem|CardTemplate",
        [
            "frontend/src/*.ts",
            "frontend/src/*.tsx",
            ":(exclude)*.test.ts",
            ":(exclude)*.test.tsx",
            ":(exclude)frontend/src/features/worksheets/*",
        ],
    ),
    "gt17-defs": (r"^(def|class) ", list(RELEASE_SERVICES)),
    "gt17-callers": (
        r"deck_release_service\.|deck_install_rebase_service\.|deck_working_tree_service\.|deck_auto_publish_service\.",
        [
            "app/*.py",
            "models/*.py",
            "connect_wsgi.py",
            "study_worker.py",
            *[f":(exclude){path}" for path in RELEASE_SERVICES],
        ],
    ),
    "gt17-kinds": (r"entity_kind|\"note_field\"|\"field_def\"", list(RELEASE_SERVICES)),
}


def main(preset: str) -> int:
    if preset not in PRESETS:
        print(__doc__)
        return 2
    pattern, pathspec = PRESETS[preset]
    result = subprocess.run(
        ["git", "grep", "-n", "-E", pattern, "--", *pathspec],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode not in (0, 1):
        print(result.stderr, file=sys.stderr)
        return result.returncode
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    out_dir = Path("docs/logs/old/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{preset}.txt"
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    files = {line.split(":", 1)[0] for line in lines}
    print(f"{preset}: {len(lines)} lines in {len(files)} files -> {out_path.as_posix()}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
