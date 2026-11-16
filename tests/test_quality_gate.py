import pytest

from src.models.quality_gate import assess_candidate


POLICY = {
    "max_mae": 12.0,
    "max_rmse": 25.0,
    "min_validation_coverage": 0.80,
}

BASELINE = {"mae": 9.725, "rmse": 19.790}

GOOD = {
    "mae": 9.542,
    "rmse": 19.215,
    "negative_predictions": 0,
    "coverage": 0.81,
}


def test_accepts_candidate_that_meets_policy():
    assert assess_candidate(GOOD, BASELINE, POLICY) == []


@pytest.mark.parametrize(
    "change",
    [
        {"mae": 10.0},
        {"rmse": 20.0},
        {"negative_predictions": 1},
        {"coverage": 0.70},
        {"mae": float("nan")},
        {"rmse": float("inf")},
    ],
)
def test_rejects_failed_quality_check(change):
    candidate = {**GOOD, **change}
    assert assess_candidate(candidate, BASELINE, POLICY)


def test_rejects_absolute_error_limit_even_if_baseline_is_worse():
    candidate = {**GOOD, "mae": 13.0}
    weak_baseline = {"mae": 15.0, "rmse": 30.0}

    reasons = assess_candidate(candidate, weak_baseline, POLICY)

    assert "MAE exceeds the maximum." in reasons