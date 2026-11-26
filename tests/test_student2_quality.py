"""Offline tests: validate quality-gate behavior without a hosted MLflow token."""
from pipelines.common.evaluate import make_decisions

POLICY = {"max_mae": 12.0, "max_rmse": 25.0,
          "min_validation_coverage": 0.80}


def row(name, mae, rmse, negatives=0, coverage=0.809768, uri="models:/m-example"):
    return {"model": name, "run_id": "example", "model_uri": uri,
            "training_git_commit": "example", "metrics": {
                "mae": mae, "rmse": rmse, "negative_predictions": negatives,
                "coverage": coverage}}


def test_rf_candidate_eligible():
    rows = [row("persistence", 9.7246, 19.7896, uri=""),
            row("random_forest_1", 9.5416, 19.2148)]
    baseline, decisions, selected = make_decisions(rows, POLICY)
    assert selected["model"] == "random_forest_1"
    assert decisions[0]["passed"] is True


def test_negative_predictions_block():
    rows = [row("persistence", 9.7246, 19.7896, uri=""),
            row("xgboost_1", 9.8, 20.3, negatives=6)]
    _, decisions, selected = make_decisions(rows, POLICY)
    assert selected is None
    assert decisions[0]["passed"] is False
    assert any("Negative" in reason for reason in decisions[0]["reasons"])


def test_missing_candidate_uri_blocks():
    rows = [row("persistence", 9.7246, 19.7896, uri=""),
            row("candidate", 9.0, 19.0, uri="")]
    _, decisions, selected = make_decisions(rows, POLICY)
    assert selected is None
    assert "Missing candidate model URI" in decisions[0]["reasons"]


def test_coverage_below_policy_blocks():
    rows = [row("persistence", 9.7246, 19.7896, uri=""),
            row("candidate", 9.0, 19.0, coverage=0.79)]
    _, decisions, selected = make_decisions(rows, POLICY)
    assert selected is None
    assert any("coverage" in reason.lower() for reason in decisions[0]["reasons"])


def test_missing_persistence_fails_closed():
    import pytest
    with pytest.raises(ValueError, match="persistence"):
        make_decisions([row("candidate", 9.0, 19.0)], POLICY)
