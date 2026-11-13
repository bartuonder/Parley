import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from parley.agent.llm import LiteLLMClient, LLMClient
from parley.evals.judge import CRITERIA, JudgeVerdict, judge_reply
from parley.evals.loader import EVAL_DATA_DIR
from parley.settings import PROJECT_ROOT, get_settings

LABELS_PATH = EVAL_DATA_DIR / "judge" / "labels.yaml"
REPORT_PATH = PROJECT_ROOT / "reports" / "judge_calibration.json"


class LabeledSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    ticket: str
    happened: str
    required_facts: list[str] = Field(default_factory=list)
    reply: str
    labels: dict[str, bool]
    note: str = ""

    @model_validator(mode="after")
    def labels_cover_every_criterion(self) -> "LabeledSample":
        missing = sorted(set(CRITERIA) - set(self.labels))
        if missing or set(self.labels) - set(CRITERIA):
            raise ValueError(f"{self.id}: labels must be exactly {list(CRITERIA)}")
        return self


@dataclass(frozen=True)
class Agreement:
    criterion: str
    n: int
    agree: int
    kappa: float | None
    human_pass: int
    judge_pass: int
    false_pass: int
    false_fail: int

    @property
    def rate(self) -> float:
        return self.agree / self.n if self.n else 0.0


def load_samples(path: Path = LABELS_PATH) -> list[LabeledSample]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [LabeledSample(**item) for item in raw]


def cohens_kappa(human: list[bool], judge: list[bool]) -> float | None:
    """Agreement beyond chance; undefined when both sides always give the same answer."""
    n = len(human)
    if n == 0:
        return None
    observed = sum(1 for h, j in zip(human, judge, strict=True) if h == j) / n
    h_true, j_true = sum(human) / n, sum(judge) / n
    expected = h_true * j_true + (1 - h_true) * (1 - j_true)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def measure(samples: list[LabeledSample], verdicts: list[JudgeVerdict | None]) -> list[Agreement]:
    """Per-criterion agreement between the labels and the judge, over graded samples only."""
    pairs = [(s, v) for s, v in zip(samples, verdicts, strict=True) if v is not None]
    result: list[Agreement] = []
    for name in CRITERIA:
        human = [s.labels[name] for s, _ in pairs]
        judge = [v.passes[name] for _, v in pairs]
        result.append(
            Agreement(
                criterion=name,
                n=len(pairs),
                agree=sum(1 for h, j in zip(human, judge, strict=True) if h == j),
                kappa=cohens_kappa(human, judge),
                human_pass=sum(human),
                judge_pass=sum(judge),
                false_pass=sum(1 for h, j in zip(human, judge, strict=True) if j and not h),
                false_fail=sum(1 for h, j in zip(human, judge, strict=True) if h and not j),
            )
        )
    return result


async def run_judge(
    llm: LLMClient, samples: list[LabeledSample], parallel: int = 8
) -> list[JudgeVerdict | None]:
    gate = asyncio.Semaphore(parallel)

    async def one(sample: LabeledSample) -> JudgeVerdict | None:
        async with gate:
            return await judge_reply(
                llm, sample.ticket, sample.happened, sample.required_facts, sample.reply
            )

    return list(await asyncio.gather(*(one(s) for s in samples)))


def render_calibration(agreements: list[Agreement], total: int, graded: int, model: str) -> str:
    lines = [
        f"Judge model: `{model}`. Labeled samples: {total}, graded by the judge: {graded}.",
        "",
        "| Criterion | Agreement | Cohen's kappa | Human pass | Judge pass | Judge too lenient "
        "| Judge too strict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for a in agreements:
        kappa = "n/a" if a.kappa is None else f"{a.kappa:.2f}"
        lines.append(
            f"| {a.criterion.replace('_', ' ')} | {a.agree}/{a.n} ({a.rate:.0%}) | {kappa} "
            f"| {a.human_pass} | {a.judge_pass} | {a.false_pass} | {a.false_fail} |"
        )
    overall = sum(a.agree for a in agreements) / max(1, sum(a.n for a in agreements))
    lines += ["", f"Overall agreement across criteria: {overall:.1%}."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare the judge with the labeled samples.")
    parser.add_argument("--model", help="override PARLEY_JUDGE_MODEL")
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    settings = get_settings()
    if settings.llm_api_key is None:
        raise SystemExit("PARLEY_LLM_API_KEY is not set")
    model = args.model or settings.judge_model
    samples = load_samples()
    verdicts = asyncio.run(run_judge(LiteLLMClient(model=model), samples))
    graded = sum(1 for v in verdicts if v is not None)
    agreements = measure(samples, verdicts)
    text = render_calibration(agreements, len(samples), graded, model)
    print(text)
    if graded < len(samples):
        raise SystemExit("some samples could not be graded; report not written")
    report = {
        "model": model,
        "samples": len(samples),
        "criteria": [{**a.__dict__, "agreement": a.rate} for a in agreements],
        "cost_usd": sum(v.usage.cost_usd for v in verdicts if v is not None),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.out.with_suffix(".md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
