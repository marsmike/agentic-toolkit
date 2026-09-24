"""The docs site must exclude the example vault's template directory."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_quartz_excludes_the_actual_template_directory():
    config = (ROOT / "docs-site/quartz.config.ts").read_text()
    patterns = json.loads(re.search(r"ignorePatterns:\s*(\[[^\]]*\])", config)[1])
    templates = list((ROOT / "vault/Templates").glob("*.md"))
    assert templates, "the example vault must supply template fixtures"
    for template in templates:
        assert template.relative_to(ROOT / "vault").parts[0] in patterns
