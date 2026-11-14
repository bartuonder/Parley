from pathlib import Path

import yaml
from pydantic import ValidationError

from parley.evals.schema import Scenario

EVAL_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "eval"
DEFAULT_SCENARIO_DIR = EVAL_DATA_DIR / "scenarios"
MEMORY_SCENARIO_DIR = EVAL_DATA_DIR / "memory"
HELDOUT_SCENARIO_DIR = EVAL_DATA_DIR / "heldout"
DIALOGUE_SCENARIO_DIR = EVAL_DATA_DIR / "dialogue"
REDTEAM_SCENARIO_DIR = EVAL_DATA_DIR / "redteam"

SCENARIO_SETS: dict[str, Path] = {
    "core": DEFAULT_SCENARIO_DIR,
    "heldout": HELDOUT_SCENARIO_DIR,
    "memory": MEMORY_SCENARIO_DIR,
    "dialogue": DIALOGUE_SCENARIO_DIR,
    "redteam": REDTEAM_SCENARIO_DIR,
}


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


def load_set(name: str) -> list[Scenario]:
    """Load one named scenario set; an unknown name is an error, an empty folder is not."""
    if name not in SCENARIO_SETS:
        raise KeyError(f"unknown scenario set {name!r}; choose from {sorted(SCENARIO_SETS)}")
    return load_scenarios(SCENARIO_SETS[name])
