from pathlib import Path

import yaml
from pydantic import ValidationError

from parley.policies.models import PolicyDoc

DEFAULT_POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"
FRONTMATTER_DELIMITER = "---"


class PolicyFormatError(ValueError):
    pass


def parse_policy(text: str, source: str = "<memory>") -> PolicyDoc:
    parts = text.split(FRONTMATTER_DELIMITER, 2)
    if len(parts) != 3 or parts[0].strip():
        raise PolicyFormatError(f"{source}: missing YAML frontmatter")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise PolicyFormatError(f"{source}: invalid frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise PolicyFormatError(f"{source}: frontmatter must be a mapping")
    try:
        return PolicyDoc(**meta, body=parts[2].strip())
    except ValidationError as exc:
        raise PolicyFormatError(f"{source}: {exc}") from exc


def load_policies(directory: Path = DEFAULT_POLICY_DIR) -> list[PolicyDoc]:
    paths = sorted(directory.glob("*.md"))
    return [parse_policy(p.read_text(encoding="utf-8"), p.name) for p in paths]
