"""Build browser inputs with the canonical candidate compiler; no database access."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.template_authoring_service import preview_candidate


def main():
    recipe = json.loads((ROOT / 'app/services/mcp/recipes/quiz.json').read_text(encoding='utf-8'))
    fixtures = {}
    for count in (1, 2, 3):
        candidate = dict(recipe)
        candidate['sample_values'] = dict(recipe['sample_values'],
            options=['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon'][:count + 2],
            correct_answers=[str(n) for n in range(1, count + 1)])
        fixtures[f'quiz-{count}'] = preview_candidate(**candidate)
    empty = dict(recipe, sample_values=dict(recipe['sample_values'], explanation=''))
    fixtures['no-explanation'] = preview_candidate(**empty)
    failing = dict(recipe, front_html='<p>Broken</p><script>throw new Error("fixture runtime failure")</script>')
    fixtures['runtime-error'] = preview_candidate(**failing)
    unsafe = dict(recipe, front_html='<p>{{question}}</p><script>window.__outerEscape = true;</script>')
    fixtures['boundary'] = preview_candidate(**unsafe)
    invalid = dict(recipe, front_html='{{#each options}}{{.}}{{/each}}')
    fixtures['invalid'] = preview_candidate(**invalid)
    path = ROOT / 'output/template-browser/fixtures.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixtures, ensure_ascii=False), encoding='utf-8')
    print(f'Built {len(fixtures)} browser fixtures: {path}')


if __name__ == '__main__':
    main()
