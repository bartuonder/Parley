import pytest

from parley.evals.calibration import (
    LabeledSample,
    cohens_kappa,
    measure,
    render_calibration,
)
from parley.evals.judge import CRITERIA, JudgeVerdict


def sample(sample_id: str, **overrides: bool) -> LabeledSample:
    labels = {name: overrides.get(name, True) for name in CRITERIA}
    return LabeledSample(
        id=sample_id, source="test", ticket="t", happened="h", reply="r", labels=labels
    )


def verdict(**overrides: bool) -> JudgeVerdict:
    return JudgeVerdict({name: overrides.get(name, True) for name in CRITERIA})


def test_kappa_is_agreement_beyond_chance() -> None:
    assert cohens_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert cohens_kappa([True, True, False, False], [True, False, False, False]) == 0.5
    assert cohens_kappa([True, False, True, False], [False, True, False, True]) == -1.0
    assert cohens_kappa([True, True], [True, True]) is None
    assert cohens_kappa([], []) is None


def test_agreement_is_counted_per_criterion_with_the_direction_of_errors() -> None:
    samples = [
        sample("a"),
        sample("b", no_leak=False),
        sample("c", no_false_claims=False),
        sample("d"),
    ]
    verdicts: list[JudgeVerdict | None] = [
        verdict(),
        verdict(),
        verdict(no_false_claims=False),
        verdict(no_leak=False),
    ]
    by_name = {a.criterion: a for a in measure(samples, verdicts)}
    leak = by_name["no_leak"]
    assert (leak.n, leak.agree, leak.false_pass, leak.false_fail) == (4, 2, 1, 1)
    claims = by_name["no_false_claims"]
    assert claims.agree == 4 and claims.kappa == 1.0 and claims.human_pass == 3
    assert by_name["facts_covered"].kappa is None


def test_samples_the_judge_could_not_grade_are_left_out() -> None:
    samples = [sample("a"), sample("b")]
    verdicts: list[JudgeVerdict | None] = [verdict(), None]
    agreements = measure(samples, verdicts)
    assert all(a.n == 1 for a in agreements)


def test_labels_must_cover_exactly_the_four_criteria() -> None:
    with pytest.raises(ValueError, match="labels must be exactly"):
        LabeledSample(
            id="x", source="s", ticket="t", happened="h", reply="r", labels={"no_leak": True}
        )
    with pytest.raises(ValueError, match="labels must be exactly"):
        LabeledSample(
            id="x",
            source="s",
            ticket="t",
            happened="h",
            reply="r",
            labels={**dict.fromkeys(CRITERIA, True), "extra": True},
        )


def test_the_calibration_table_names_every_criterion_and_the_overall_agreement() -> None:
    agreements = measure([sample("a"), sample("b", no_leak=False)], [verdict(), verdict()])
    text = render_calibration(agreements, total=2, graded=2, model="judge-model")
    assert "`judge-model`" in text and "Labeled samples: 2" in text
    assert "| no leak | 1/2 (50%) |" in text and "Overall agreement across criteria: 87.5%." in text
