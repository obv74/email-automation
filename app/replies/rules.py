"""Load stock-reply rules from YAML."""

from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings


def load_rules() -> dict[str, Any]:
    settings = get_settings()
    path = Path(settings.rules_file)
    if not path.exists():
        return {"default_template": "default", "templates": {}}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def pick_template_name(job_summary: str, rules: dict[str, Any]) -> str:
    for rule in rules.get("rules", []):
        keyword = rule.get("if_contains", "").lower()
        if keyword and keyword in job_summary.lower():
            return rule.get("template", rules.get("default_template", "default"))
    return rules.get("default_template", "default")
