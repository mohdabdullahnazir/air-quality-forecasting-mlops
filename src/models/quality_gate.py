import argparse
import json
import math
from pathlib import Path

import pandas as pd
import yaml


PROJECT_FOLDER = Path(__file__).resolve().parents[2]


def assess_candidate(candidate, baseline, policy):
    """Return the reasons a candidate fails validation checks."""
    reasons = []

    required = ["mae", "rmse", "negative_predictions", "coverage"]

    if any(
        key not in candidate or not math.isfinite(candidate[key])
        for key in required
    ):
        return ["Candidate has missing or non-finite metrics."]

    if any(
        key not in baseline or not math.isfinite(baseline[key])
        for key in ["mae", "rmse"]
    ):
        return ["Baseline has missing or non-finite error metrics."]

    if candidate["mae"] < 0 or candidate["rmse"] < 0:
        reasons.append("Error metrics cannot be negative.")

    if candidate["mae"] > policy["max_mae"]:
        reasons.append("MAE exceeds the maximum.")

    if candidate["rmse"] > policy["max_rmse"]:
        reasons.append("RMSE exceeds the maximum.")

    if candidate["mae"] >= baseline["mae"]:
        reasons.append("MAE does not improve on persistence.")

    if candidate["rmse"] > baseline["rmse"]:
        reasons.append("RMSE is worse than persistence.")

    if candidate["negative_predictions"] != 0:
        reasons.append("Negative pollution predictions were produced.")

    if not policy["min_validation_coverage"] <= candidate["coverage"] <= 1:
        reasons.append("Validation coverage is unacceptable.")

    return reasons


def main():
    # Imported here so unit tests do not need a tracking connection.
    import mlflow
    from mlflow.tracking import MlflowClient

    from src.models.tracking import configure_tracking, log_lineage

    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default=None)
    args = parser.parse_args()

    folder = PROJECT_FOLDER / "reports" / "experiments"
    folder.mkdir(parents=True, exist_ok=True)
    output_file = folder / "quality_gate.json"

    # Clear any earlier successful decision before checking new inputs.
    report = {
        "status": "blocked",
        "deployment_approved": False,
        "selected_candidate": None,
        "decisions": [],
    }
    output_file.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    policy_file = PROJECT_FOLDER / "configs" / "quality_policy.yaml"
    with policy_file.open(encoding="utf-8") as file:
        policy = yaml.safe_load(file)

    comparison = pd.read_csv(
        folder / "validation_comparison.csv",
        keep_default_na=False,
    )

    baseline_rows = comparison.loc[comparison["model"] == "persistence"]
    if len(baseline_rows) != 1:
        raise ValueError("Exactly one persistence baseline is required.")

    configure_tracking()
    client = MlflowClient()

    def fetch_metrics(row):
        run = client.get_run(row["run_id"])

        if run.info.status != "FINISHED":
            raise ValueError(f"{row['model']} did not finish successfully.")

        # Read recorded metrics from MLflow.
        metrics = run.data.metrics
        values = {
            "mae": metrics["validation_mae"],
            "rmse": metrics["validation_rmse"],
            "negative_predictions": (
                metrics["validation_negative_prediction_count"]
            ),
            "coverage": metrics["validation_coverage"],
        }
        return run, values

    baseline_row = baseline_rows.iloc[0]
    baseline_run, baseline_metrics = fetch_metrics(baseline_row)

    version_tags = ["dataset_dvc_md5", "feature_code_commit"]
    for tag in version_tags:
        if not baseline_run.data.tags.get(tag):
            raise ValueError(f"Baseline is missing lineage tag: {tag}")

    candidates = comparison.loc[comparison["model"] != "persistence"]

    if args.candidate:
        candidates = candidates.loc[
            candidates["model"] == args.candidate
        ]

    if candidates.empty:
        raise ValueError("No matching candidate was found.")

    for _, row in candidates.iterrows():
        run, metrics = fetch_metrics(row)
        reasons = assess_candidate(metrics, baseline_metrics, policy)

        for tag in version_tags:
            if run.data.tags.get(tag) != baseline_run.data.tags[tag]:
                reasons.append(f"Baseline and candidate differ: {tag}")

        if (
            run.data.metrics["validation_rows"]
            != baseline_run.data.metrics["validation_rows"]
        ):
            reasons.append("Validation row counts differ.")

        if not row["model_uri"]:
            reasons.append("Candidate has no saved model URI.")

        decision = {
            "model": row["model"],
            "run_id": row["run_id"],
            "model_uri": row["model_uri"],
            "training_git_commit": run.data.tags.get("git_commit"),
            "metrics": metrics,
            "passed": not reasons,
            "reasons": reasons,
        }
        report["decisions"].append(decision)

        status = "PASS" if decision["passed"] else "FAIL"
        print(f"{row['model']}: {status}")
        for reason in reasons:
            print(f"  - {reason}")

    passing = [
        decision
        for decision in report["decisions"]
        if decision["passed"]
    ]

    if passing:
        report["selected_candidate"] = min(
            passing,
            key=lambda decision: decision["metrics"]["mae"],
        )
        report["status"] = "eligible_for_review"

    report["baseline_run_id"] = baseline_row["run_id"]
    report["dataset_dvc_md5"] = baseline_run.data.tags["dataset_dvc_md5"]
    report["policy"] = policy

    with mlflow.start_run(run_name="validation-quality-gate") as gate_run:
        log_lineage()
        mlflow.set_tags({
            "run_type": "quality_gate",
            "quality_gate_passed": str(bool(passing)).lower(),
            "approval_status": "pending_review",
        })
        report["gate_run_id"] = gate_run.info.run_id
        mlflow.log_dict(report, "quality_gate.json")
        mlflow.log_artifact(str(policy_file), artifact_path="configuration")

    output_file.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    if not passing:
        print("\nBLOCKED: no candidate passed the quality gate.")
        return 1

    selected = report["selected_candidate"]["model"]
    print(f"\nSelected candidate: {selected}")
    print("Quality gate passed. Deployment approval is still pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())