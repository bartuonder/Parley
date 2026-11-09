from pathlib import Path

from parley.evals.loader import DEFAULT_SCENARIO_DIR, load_scenarios
from parley.policies.loader import DEFAULT_POLICY_DIR, load_policies
from parley.policies.validate import filename_problems, validate_corpus


def check_static_data(
    policy_dir: Path = DEFAULT_POLICY_DIR, scenario_dir: Path = DEFAULT_SCENARIO_DIR
) -> dict[str, int]:
    """Validate policy and scenario files; raise ValueError listing every problem."""
    docs = load_policies(policy_dir)
    names = [p.name for p in policy_dir.glob("*.md")]
    problems = validate_corpus(docs) + filename_problems(docs, names)

    scenarios = load_scenarios(scenario_dir)
    ids = [s.id for s in scenarios]
    problems += [
        f"scenario {i}: duplicated id" for i in sorted({i for i in ids if ids.count(i) > 1})
    ]
    if problems:
        raise ValueError("static data is inconsistent:\n" + "\n".join(problems))
    return {
        "policy_files": len(docs),
        "policy_docs": len({d.doc_id for d in docs}),
        "scenarios": len(scenarios),
    }
