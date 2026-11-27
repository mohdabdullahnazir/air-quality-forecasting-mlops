"""Run-specific validation quality gate using hosted MLflow evidence.

No original reports or final test set are modified or evaluated.
"""
import argparse
import json
import math

import yaml

from pipelines.common.context import PROJECT_ROOT
from src.models.quality_gate import assess_candidate

RUN_ROOT = (PROJECT_ROOT / "reports/automation/runs").resolve()


def load_pair(training_file: str):
    path = (PROJECT_ROOT / training_file).resolve()
    if not path.is_relative_to(RUN_ROOT) or path.name != "training_manifest.json":
        raise ValueError("Specify a run-specific training_manifest.json")
    training = json.loads(path.read_text(encoding="utf-8"))
    if path.parent.name != training["pipeline_run_id"]:
        raise ValueError("Training run ID mismatch")
    prepare_path = (PROJECT_ROOT / training["preparation_manifest"]).resolve()
    if prepare_path != path.parent / "prepare_manifest.json":
        raise ValueError("Preparation manifest is not from the same run")
    preparation = json.loads(prepare_path.read_text(encoding="utf-8"))
    if preparation["pipeline_run_id"] != training["pipeline_run_id"]:
        raise ValueError("Preparation/training run ID mismatch")
    if not training.get("runs"):
        raise ValueError("Training manifest has no MLflow runs")
    return path, training, preparation


def check_remote_runs(training, preparation, client):
    """Trust remote MLflow metrics and lineage, not local CSV claims."""
    validated = []
    origin_tags = None
    required_tags = (
        "dataset_dvc_md5", "feature_source_dvc_md5", "feature_code_commit",
        "feature_service", "station", "pipeline_run_id", "preparation_git_commit",
    )
    for item in training["runs"]:
        remote = client.get_run(item["run_id"])
        if remote.info.status != "FINISHED":
            raise RuntimeError(f"MLflow run did not finish: {item['run_id']}")
        tags = remote.data.tags
        missing = [key for key in required_tags if not tags.get(key)]
        if missing:
            raise ValueError(f"Missing MLflow lineage tags: {missing}")
        if tags["pipeline_run_id"] != training["pipeline_run_id"]:
            raise ValueError("Remote run belongs to another pipeline_run_id")
        if tags["dataset_dvc_md5"] != preparation["raw_dvc_md5"]:
            raise ValueError("MLflow raw dataset version mismatch")
        if tags["preparation_git_commit"] != preparation["source_git_commit"]:
            raise ValueError("MLflow preparation commit mismatch")
        if tags["feature_service"] != "pm25_forecasting_v1":
            raise ValueError("MLflow feature service mismatch")
        if tags["station"] != preparation["station"]:
            raise ValueError("MLflow station mismatch")
        scope = tuple(tags[k] for k in required_tags if k not in (
            "pipeline_run_id", "preparation_git_commit",
        ))
        if origin_tags is None:
            origin_tags = scope
        elif scope != origin_tags:
            raise ValueError("Candidate and persistence have differing lineage")

        m = remote.data.metrics
        required_metrics = (
            "validation_mae", "validation_rmse", "validation_coverage",
            "validation_negative_prediction_count", "validation_rows",
        )
        for key in required_metrics:
            if key not in m or not math.isfinite(m[key]):
                raise ValueError(f"Remote run has missing/invalid {key}")
        if int(m["validation_rows"]) != preparation["splits"]["validation"]["usable_rows"]:
            raise ValueError("Remote validation rows differ from preparation")
        expected_cov = preparation["splits"]["validation"]["coverage"]
        if not math.isclose(m["validation_coverage"], expected_cov, abs_tol=1e-5):
            raise ValueError("Remote validation coverage differs")
        for metric_name, field in (
            ("validation_mae", "validation_mae"),
            ("validation_rmse", "validation_rmse"),
            ("validation_negative_prediction_count", "negative_predictions"),
        ):
            if not math.isclose(float(m[metric_name]), float(item[field]), abs_tol=1e-5):
                raise ValueError(f"Remote and local {metric_name} disagree")
        validated.append({
            "model": item["model"], "run_id": item["run_id"],
            "model_uri": item["model_uri"],
            "training_git_commit": tags.get("git_commit"),
            "metrics": {
                "mae": m["validation_mae"],
                "rmse": m["validation_rmse"],
                "negative_predictions": m["validation_negative_prediction_count"],
                "coverage": m["validation_coverage"],
            },
        })
    return validated


def make_decisions(validated, policy):
    baseline_rows = [r for r in validated if r["model"] == "persistence"]
    if len(baseline_rows) != 1:
        raise ValueError("Exactly one persistence baseline required")
    baseline = baseline_rows[0]
    decisions = []
    for row in validated:
        if row["model"] == "persistence":
            continue
        reasons = assess_candidate(row["metrics"], baseline["metrics"], policy)
        if not row["model_uri"]:
            reasons.append("Missing candidate model URI")
        decisions.append({**row, "passed": not reasons, "reasons": reasons})
    if not decisions:
        raise ValueError("No candidates found")
    passing = [r for r in decisions if r["passed"]]
    selected = min(passing, key=lambda r: r["metrics"]["mae"]) if passing else None
    return baseline, decisions, selected


def evaluate(training_file: str) -> dict:
    path, training, preparation = load_pair(training_file)
    output = path.parent / "evaluation_manifest.json"
    if output.exists():
        raise FileExistsError("Run already evaluated; never overwrite evaluation evidence")

    from mlflow.tracking import MlflowClient
    import mlflow
    from src.models.tracking import configure_tracking

    configure_tracking()
    client = MlflowClient()
    verified = check_remote_runs(training, preparation, client)
    with (PROJECT_ROOT / "configs/quality_policy.yaml").open(encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    baseline, decisions, selected = make_decisions(verified, policy)

    feast_record = path.parent / "feast_verification.json"
    feast_verified = False
    if feast_record.exists():
        v = json.loads(feast_record.read_text(encoding="utf-8"))
        feast_verified = (v.get("passed") is True
                          and v.get("pipeline_run_id") == training["pipeline_run_id"]
                          and v.get("raw_dvc_md5") == preparation["raw_dvc_md5"])
    # A validation gate is not final-test approval or a deployment authorization.
    status = ("eligible_for_review" if selected and feast_verified
              else "blocked_pending_feast_verification" if selected
              else "blocked_quality_gate")
    report = {
        "pipeline_run_id": training["pipeline_run_id"],
        "basis": "validation_only_no_final_test_rescoring",
        "data_revision": preparation["raw_dvc_md5"],
        "feature_service": "pm25_forecasting_v1",
        "mlflow_verified": True,
        "feast_direct_equivalence_verified": feast_verified,
        "policy": policy, "baseline": baseline,
        "decisions": decisions, "selected_candidate": selected,
        "status": status,
        "approval_status": "pending_review" if status == "eligible_for_review" else "blocked",
        "deployment_approved": False,
    }
    # Log evidence to hosted MLflow first; local success is not authoritative by itself.
    with mlflow.start_run(run_name=f"automation-validation-gate-{training['pipeline_run_id']}") as run:
        mlflow.set_tags({
            "run_type": "automation_validation_gate",
            "pipeline_run_id": training["pipeline_run_id"],
            "quality_gate_passed": str(status == "eligible_for_review").lower(),
            "approval_status": report["approval_status"],
            "deployment_approved": "false",
        })
        report["gate_run_id"] = run.info.run_id
        mlflow.log_dict(report, "evaluation_manifest.json")
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-manifest", required=True)
    args = parser.parse_args()
    result = evaluate(args.training_manifest)
    print("Evaluation status:", result["status"])
    for d in result["decisions"]:
        print(d["model"], "PASS" if d["passed"] else "FAIL", "; ".join(d["reasons"]))
    if result["status"] != "eligible_for_review":
        raise SystemExit(1)
    print("VALIDATION GATE ELIGIBLE FOR REVIEW - NOT DEPLOYMENT APPROVAL")
