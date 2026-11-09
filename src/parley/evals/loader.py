from pathlib import Path

import yaml
from pydantic import ValidationError

from parley.evals.schema import Scenario

DEFAULT_SCENARIO_DIR = Path(__file__).resolve().parents[3] / "data" / "eval" / "scenarios"


class ScenarioFormatError(ValueError):
    pass


def load_scenarios(directory: Path = DEFAULT_SCENARIO_DIR) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            raise ScenarioFormatError(f"{path.name}: expected a list of scenarios")
        for item in raw:
            try:
                scenarios.append(Scenario(**item))
            except (ValidationError, TypeError) as exc:
                label = item.get("id", "?") if isinstance(item, dict) else "?"
                raise ScenarioFormatError(f"{path.name} {label}: {exc}") from exc
    return scenarios
