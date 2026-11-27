"""Phase 9: train a REAL weak baseline and test rejection against the historical champion.

This is a controlled historical experiment, NOT a production model/approval.
The previous successful Phase 9 run is read-only and is never modified.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

from pipelines.common.context import PROJECT_ROOT
from scripts.phase9_lifecycle_demo import (
    CHALLENGER_END,
    CHAMPION_END,
    EVAL_END,
    MIN_COVERAGE,
    load_and_split,
)
from src.features.engineering import FEATURE_COLUMNS

ROOT = PROJECT_ROOT / "reports" / "automation" / "lifecycle_demo"


def select_baseline(explicit: str | None) -> Path:
    if explicit:
        folder = (PROJECT_ROOT / explicit).resolve()
        if not folder.is_relative_to(ROOT.resolve()):
            raise ValueError("Baseline must be within reports/automation/lifecycle_demo")
        candidates = [folder]
    else:
        candidates = sorted(ROOT.glob("phase9-*"), reverse=True)

    for folder in candidates:
        decision_path = folder / "phase9_decision.json"
        comp_path = folder / "comparison_manifest.json"
        protocol_path = folder / "protocol.json"
        if not all(p.is_file() for p in (decision_path, comp_path, protocol_path)):
            continue
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        if decision.get("candidate_gate_result") != "ELIGIBLE_FOR_HUMAN_REVIEW":
            continue
        comp = json.loads(comp_path.read_text(encoding="utf-8"))
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        if not comp.get("champion_model_uri") or not str(comp["champion_model_uri"]).startswith("models:/"):
            continue
        if not protocol.get("raw_md5"):
            continue
        return folder
    raise FileNotFoundError("No eligible original Phase 9 run with intact evidence found. Pass --baseline-dir.")


def preflight(baseline_dir: str | None):
    cfg, settings, digest, champion_df, challenger_df, evaluation, coverage = load_and_split()
    folder = select_baseline(baseline_dir)
    comparison = json.loads((folder / "comparison_manifest.json").read_text(encoding="utf-8"))
    protocol = json.loads((folder / "protocol.json").read_text(encoding="utf-8"))
    if protocol["raw_md5"] != digest:
        raise ValueError("Baseline DVC raw MD5 does not match current raw data")
    if comparison["champion_training_cutoff"] != "2013-12-31T23:59:59":
        raise ValueError("Original historical champion training cutoff does not match")
    if comparison["candidate_training_cutoff"] != "2014-02-28T23:59:59":
        raise ValueError("Original historical candidate training cutoff does not match")
    if (pd.Timestamp(protocol["training_cutoff_champion_exclusive"]) != CHAMPION_END
            or pd.Timestamp(protocol["training_cutoff_candidate_exclusive"]) != CHALLENGER_END
            or pd.Timestamp(protocol["eval_end_exclusive"]) != EVAL_END):
        raise ValueError("Baseline historical protocol differs from current project")
    if coverage < MIN_COVERAGE:
        raise ValueError("Insufficient paired coverage")
    if int(comparison["total_rows"]) != len(evaluation):
        raise ValueError("Baseline evaluation total rows differ")
    paired = evaluation.dropna(subset=FEATURE_COLUMNS + ["target_pm25"])
    if len(paired) != int(comparison["paired_rows"]):
        raise ValueError("Baseline paired evaluation rows differ")
    if challenger_df["target_timestamp"].max() >= CHALLENGER_END:
        raise ValueError("Candidate training leakage: target timestamp overlaps holdout")
    if paired["target_timestamp"].min() < CHALLENGER_END:
        raise ValueError("Evaluation target overlaps training cutoff")
    print("PHASE 9 REJECTED-CANDIDATE PREFLIGHT")
    print("Baseline directory:", folder)
    print("Original champion URI:", comparison["champion_model_uri"])
    print("Candidate fit rows:", len(challenger_df))
    print("Evaluation rows:", len(evaluation), "paired:", len(paired))
    print("Coverage:", f"{coverage:.2%}")
    print("Historical data checksum:", digest)
    print("Original successful Phase 9 run will remain unchanged.")
    return folder, comparison, protocol, digest, challenger_df, evaluation


def train_control(baseline_dir: str | None):
    folder_baseline, baseline_comparison, protocol, digest, train_data, evaluation = preflight(baseline_dir)
    from src.models.tracking import configure_tracking, log_lineage
    from pipelines.common.compare_deployed import compare
    import mlflow
    import mlflow.sklearn
    from mlflow.models import infer_signature

    # A genuine fitted, deliberately simple model used as a weak-control baseline.
    # Its real performance will decide rejection. No metric is invented or overwritten.
    fit_x = train_data[FEATURE_COLUMNS]
    fit_y = train_data["target_pm25"]
    model = DummyRegressor(strategy="mean")
    model.fit(fit_x, fit_y)
    assert np.isfinite(model.constant_).all(), "Invalid trained control model"

    run_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    experiment_id = f"phase9-rejected-control-{run_suffix}"
    output = ROOT / experiment_id
    output.mkdir(parents=True, exist_ok=False)
    evaluation_file = output / "evaluation_mar_apr_2014.parquet"
    evaluation.to_parquet(evaluation_file, index=False)

    candidate_provenance = {
        "experiment_id": experiment_id,
        "purpose": "actual_trained_underperforming_candidate_control",
        "model_class": "sklearn.dummy.DummyRegressor",
        "model_strategy": "mean",
        "note": "Intentionally simple, genuinely fitted baseline; NOT an approved release",
        "source_historical_champion_experiment": folder_baseline.name,
        "raw_md5": digest,
        "candidate_training_cutoff_exclusive": CHALLENGER_END.isoformat(),
        "evaluation_start_inclusive": CHALLENGER_END.isoformat(),
        "evaluation_end_exclusive": EVAL_END.isoformat(),
        "training_rows": len(train_data),
        "evaluation_rows": len(evaluation),
        "approval_status": "not_reviewed",
        "deployment_approved": False,
    }
    (output / "control_protocol.json").write_text(json.dumps(candidate_provenance, indent=2), encoding="utf-8")

    configure_tracking()
    with mlflow.start_run(run_name=experiment_id) as run:
        log_lineage()
        mlflow.set_tags({
            "run_type": "phase9_historical_rejection_control",
            "phase9_experiment_id": experiment_id,
            "model_role": "intentionally_weak_trained_challenger_control",
            "training_end_exclusive": CHALLENGER_END.isoformat(),
            "evaluation_window": "2014-03-01_to_2014-04-30",
            "source_raw_md5": digest,
            "approval_status": "not_reviewed",
            "deployment_approved": "false",
            "not_for_production": "true",
        })
        mlflow.log_param("model_type", "DummyRegressor")
        mlflow.log_param("strategy", "mean")
        mlflow.log_param("training_rows", len(train_data))
        example = fit_x.head(5)
        info = mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            serialization_format="skops",
            input_example=example,
            signature=infer_signature(example, model.predict(example)),
        )
        candidate_uri = info.model_uri
        if not candidate_uri:
            raise RuntimeError("MLflow did not return a candidate model URI")
        control_run_id = run.info.run_id

    comparison_path = compare(
        candidate_uri,
        baseline_comparison["champion_model_uri"],
        evaluation_file.relative_to(PROJECT_ROOT).as_posix(),
        experiment_id + "-mar-apr-2014",
        "2013-12-31T23:59:59", "2014-02-28T23:59:59",
        output.relative_to(PROJECT_ROOT).as_posix(),
    )
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    checks = {
        "candidate_improves_paired_mae": bool(comparison["candidate_improves_paired_mae"]),
        "candidate_not_worse_paired_rmse": bool(comparison["candidate_not_worse_paired_rmse"]),
        "paired_coverage_at_least_80_percent": comparison["paired_coverage"] >= MIN_COVERAGE,
        "no_negative_predictions": comparison["candidate_metrics"]["negative_prediction_count"] == 0,
    }
    passes = all(checks.values())
    reasons = [key for key, passed in checks.items() if not passed]
    decision = {
        "experiment_id": experiment_id,
        "trained_control_run_id": control_run_id,
        "control_model_uri": candidate_uri,
        "historical_champion_model_uri": baseline_comparison["champion_model_uri"],
        "comparison_manifest": comparison_path.relative_to(PROJECT_ROOT).as_posix(),
        "checks": checks,
        "gate_failure_reasons": reasons,
        "gate_result": "ELIGIBLE_FOR_HUMAN_REVIEW_NOT_DEPLOYED" if passes else "REJECTED_RETAIN_HISTORICAL_CHAMPION",
        "approval_status": "not_reviewed",
        "deployment_approved": False,
        "independently_verified_deployed_champion": False,
        "rollback_performed": False,
        "notes": "This is a real trained weak-control comparison. It is not evidence of an AWS rollback or deployed champion.",
    }
    decision_path = output / "rejection_decision.json"
    decision_path.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    with mlflow.start_run(run_id=control_run_id):
        mlflow.log_metrics({
            "paired_candidate_mae": float(comparison["candidate_metrics"]["mae"]),
            "paired_candidate_rmse": float(comparison["candidate_metrics"]["rmse"]),
            "paired_champion_mae": float(comparison["champion_metrics"]["mae"]),
            "paired_champion_rmse": float(comparison["champion_metrics"]["rmse"]),
            "paired_coverage": float(comparison["paired_coverage"]),
            "gate_passed": int(passes),
        })
        mlflow.log_artifact(str(decision_path), artifact_path="phase9_rejection_evidence")
        mlflow.log_artifact(str(comparison_path), artifact_path="phase9_rejection_evidence")

    print("\nPHASE 9 REAL TRAINED CONTROL RESULT")
    print("Champion MAE:", comparison["champion_metrics"]["mae"])
    print("Control candidate MAE:", comparison["candidate_metrics"]["mae"])
    print("Champion RMSE:", comparison["champion_metrics"]["rmse"])
    print("Control candidate RMSE:", comparison["candidate_metrics"]["rmse"])
    print("Paired coverage:", f"{comparison['paired_coverage']:.2%}")
    print("Decision:", decision["gate_result"])
    print("Failed checks:", reasons)
    print("Evidence folder:", output)
    print("Remote MLflow run:", control_run_id)
    print("No model approval, AWS deployment, or rollback was performed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Separate, genuine underperforming-candidate rejection demonstration")
    parser.add_argument("--check", action="store_true", help="Verify inputs; no training")
    parser.add_argument("--train", action="store_true", help="Fit and log a real weak control model and compare")
    parser.add_argument("--baseline-dir", default=None, help="Original eligible Phase 9 evidence path, relative to repo root")
    args = parser.parse_args()
    if args.check == args.train:
        parser.error("Choose exactly one of --check or --train")
    if args.check:
        preflight(args.baseline_dir)
        print("PREFLIGHT PASSED; no new model was trained.")
    else:
        train_control(args.baseline_dir)
