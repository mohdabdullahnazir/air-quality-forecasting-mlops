"""Compare candidate and champion fairly on a NEW lifecycle demonstration holdout.

No original final-test period is used, and a local comparison is not proof of
what is actually deployed. Student 3 must supply independently checked deployment
identity and health evidence before a release decision.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from pipelines.common.context import PROJECT_ROOT
from src.features.engineering import FEATURE_COLUMNS
from src.models.evaluate import regression_metrics


def compare(candidate_uri, champion_uri, data_file, eval_id,
            champion_cutoff, candidate_cutoff, output_dir):
    if not eval_id.strip() or not candidate_uri or not champion_uri:
        raise ValueError("Candidate, champion and evaluation set identity required")
    file_path = (PROJECT_ROOT / data_file).resolve()
    if not file_path.is_relative_to(PROJECT_ROOT):
        raise ValueError("Evaluation path must remain inside project")
    # The original final test was already used and is immutable.
    if file_path.name in {"test.parquet", "final_test_report.json"}:
        raise ValueError("Original final test cannot be reused for candidate comparison")
    df = pd.read_parquet(file_path)
    cols = FEATURE_COLUMNS + ["target_pm25", "target_timestamp"]
    if not set(cols).issubset(df.columns):
        raise ValueError("Missing columns for a paired evaluation")
    df["target_timestamp"] = pd.to_datetime(df["target_timestamp"])
    if df["target_timestamp"].isna().any():
        raise ValueError("Invalid evaluation timestamps")
    earliest = df["target_timestamp"].min()
    latest = df["target_timestamp"].max()
    if latest >= pd.Timestamp("2016-03-01"):
        raise ValueError("Do not use the original final-test period")
    for cutoff in (champion_cutoff, candidate_cutoff):
        if earliest <= pd.Timestamp(cutoff):
            raise ValueError("Evaluation must start AFTER both training cutoffs")
    eligible = df.dropna(subset=FEATURE_COLUMNS + ["target_pm25"]).copy()
    if len(eligible) < 2:
        raise ValueError("Not enough shared complete feature rows")
    x = eligible[FEATURE_COLUMNS]
    y = eligible["target_pm25"].to_numpy()

    import mlflow.pyfunc
    from src.models.tracking import configure_tracking
    configure_tracking()
    champion = mlflow.pyfunc.load_model(champion_uri)
    candidate = mlflow.pyfunc.load_model(candidate_uri)
    pred_champion = np.asarray(champion.predict(x), dtype=float).reshape(-1)
    pred_candidate = np.asarray(candidate.predict(x), dtype=float).reshape(-1)
    if pred_champion.shape != y.shape or pred_candidate.shape != y.shape:
        raise ValueError("Prediction lengths do not match target lengths")
    if not np.isfinite(pred_champion).all() or not np.isfinite(pred_candidate).all():
        raise ValueError("Non-finite predictions")
    champ_metrics = regression_metrics(y, pred_champion)
    cand_metrics = regression_metrics(y, pred_candidate)
    cov = len(eligible) / len(df)
    result = {
        "evaluation_set_id": eval_id,
        "evaluation_file": file_path.relative_to(PROJECT_ROOT).as_posix(),
        "first_target_time": earliest.isoformat(),
        "last_target_time": latest.isoformat(),
        "champion_training_cutoff": champion_cutoff,
        "candidate_training_cutoff": candidate_cutoff,
        "champion_model_uri": champion_uri,
        "candidate_model_uri": candidate_uri,
        "total_rows": len(df), "paired_rows": len(eligible),
        "paired_coverage": cov,
        "champion_metrics": champ_metrics,
        "candidate_metrics": cand_metrics,
        "candidate_improves_paired_mae": cand_metrics["mae"] < champ_metrics["mae"],
        "candidate_not_worse_paired_rmse": cand_metrics["rmse"] <= champ_metrics["rmse"],
        "training_cutoffs_verified_against_remote_lineage": False,
        "deployment_identity_independently_verified": False,
        "deployment_approved": False,
        "status": "local_lifecycle_comparison_only_pending_deployment_verification",
    }
    outdir = (PROJECT_ROOT / output_dir).resolve()
    if not outdir.is_relative_to(PROJECT_ROOT / "reports/automation"):
        raise ValueError("Output must be inside reports/automation")
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / "comparison_manifest.json"
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--candidate-uri", required=True)
    p.add_argument("--champion-uri", required=True)
    p.add_argument("--evaluation-parquet", required=True)
    p.add_argument("--evaluation-id", required=True)
    p.add_argument("--champion-training-cutoff", required=True)
    p.add_argument("--candidate-training-cutoff", required=True)
    p.add_argument("--output-dir", required=True)
    a = p.parse_args()
    result = compare(a.candidate_uri, a.champion_uri, a.evaluation_parquet,
                     a.evaluation_id, a.champion_training_cutoff,
                     a.candidate_training_cutoff, a.output_dir)
    print("Comparison saved:", result)
    print("NOT an approved release: independent deployed-model verification is pending")
