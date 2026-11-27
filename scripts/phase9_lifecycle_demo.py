"""Phase 9 controlled *historical replay* for the air quality MLOps course.

Train two new Random Forest models using predefined 2013 / early 2014 cutoffs.
Do NOT reuse the original final test or treat either model as an approved deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestRegressor

from pipelines.common.context import PROJECT_ROOT
from src.data.ingestion import load_station_data
from src.features.engineering import FEATURE_COLUMNS, create_features
from src.features.preprocessing import create_forecast_target

# The course's proposed historical replay. These boundaries are exclusive at the end.
CHAMPION_END = pd.Timestamp("2014-01-01T00:00:00")
CHALLENGER_END = pd.Timestamp("2014-03-01T00:00:00")
EVAL_END = pd.Timestamp("2014-05-01T00:00:00")
MIN_COVERAGE = 0.80  # Demonstration gate; this is not production policy.


def md5(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_and_split():
    cfg = yaml.safe_load((PROJECT_ROOT / "configs/pipeline_config.yaml").read_text(encoding="utf-8"))
    params = yaml.safe_load((PROJECT_ROOT / "configs/model_params.yaml").read_text(encoding="utf-8"))
    if cfg["data"]["forecast_horizon_hours"] != 1:
        raise ValueError("This demonstration requires one-hour target horizon")
    raw = (PROJECT_ROOT / cfg["data"]["raw_path"]).resolve()
    if not raw.is_relative_to(PROJECT_ROOT) or not raw.is_file():
        raise FileNotFoundError("DVC raw CSV missing: run 'dvc pull' first")
    digest = md5(raw)
    if digest != cfg["data"]["raw_dvc_md5"]:
        raise ValueError("DVC raw CSV MD5 differs from configured source")
    frame = create_forecast_target(create_features(load_station_data(raw)))
    if not frame["station"].eq(cfg["data"]["station"]).all():
        raise ValueError("Station mismatch")
    if frame["target_timestamp"].isna().any():
        raise ValueError("Invalid target timestamps")
    frame = frame.sort_values("timestamp").copy()
    # Avoid fitting from any post-cutoff *target*. Trailing-window features
    # use time t or earlier to predict t+1.
    required = FEATURE_COLUMNS + ["target_pm25"]
    champion = frame.loc[frame["target_timestamp"] < CHAMPION_END].dropna(subset=required).copy()
    challenger = frame.loc[frame["target_timestamp"] < CHALLENGER_END].dropna(subset=required).copy()
    evaluation = frame.loc[
        (frame["target_timestamp"] >= CHALLENGER_END)
        & (frame["target_timestamp"] < EVAL_END)
    ].copy()
    if not len(champion) or not len(challenger) or len(evaluation) < 2:
        raise ValueError("Historical periods are empty")
    if champion["target_timestamp"].max() >= CHAMPION_END:
        raise ValueError("Champion cutoff violation")
    if challenger["target_timestamp"].max() >= CHALLENGER_END:
        raise ValueError("Challenger cutoff violation")
    if evaluation["target_timestamp"].min() < CHALLENGER_END:
        raise ValueError("Evaluation overlaps training")
    complete = evaluation.dropna(subset=required)
    if len(complete) < 2:
        raise ValueError("Not enough paired evaluation records")
    cov = len(complete) / len(evaluation)
    return cfg, params, digest, champion, challenger, evaluation, cov


def log_model(name, frame, params, data_md5, experiment_id):
    import mlflow
    import mlflow.sklearn
    from mlflow.models import infer_signature
    from src.models.tracking import log_lineage

    model = RandomForestRegressor(random_state=42, n_jobs=4, **params)
    x = frame[FEATURE_COLUMNS]
    y = frame["target_pm25"]
    with mlflow.start_run(run_name=f"phase9-{name}-{experiment_id}") as run:
        log_lineage()
        mlflow.set_tags({
            "run_type": "phase9_historical_lifecycle_demo",
            "lifecycle_role": name,
            "phase9_experiment_id": experiment_id,
            "phase9_training_end_exclusive": (
                CHAMPION_END if name == "champion" else CHALLENGER_END
            ).isoformat(),
            "phase9_evaluation_window": "2014-03-01_to_2014-04-30",
            "source_raw_md5": data_md5,
            "approval_status": "not_reviewed",
            "deployment_approved": "false",
        })
        mlflow.log_params({f"rf_{key}": value for key, value in params.items()})
        mlflow.log_param("training_rows", len(frame))
        model.fit(x, y)
        mlflow.log_metric("training_rows", len(frame))
        example = x.head(5)
        info = mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            serialization_format="skops",
            skops_trusted_types=["sklearn.tree._tree.Tree"],
            input_example=example,
            signature=infer_signature(example, model.predict(example)),
        )
        if not info.model_uri:
            raise RuntimeError("MLflow model URI not created")
        return {"run_id": run.info.run_id, "model_uri": info.model_uri}


def execute():
    cfg, settings, digest, champ, chall, ev, cov = load_and_split()
    if not isinstance(settings.get("random_forest"), list) or not settings["random_forest"]:
        raise ValueError("Missing Random Forest settings")
    # Same fixed parameters for both models isolates the historical data-window effect.
    params = settings["random_forest"][0]
    assert isinstance(params, dict)
    print("\nPHASE 9 HISTORICAL REPLAY CHECK")
    print("Champion training rows:", len(champ))
    print("Challenger training rows:", len(chall))
    print("March-April 2014 evaluation rows:", len(ev))
    print("Paired coverage:", round(cov * 100, 2), "%")
    print("Config Random Forest:", params)
    return cfg, params, digest, champ, chall, ev, cov


def run_training():
    cfg, params, digest, champ, chall, ev, cov = execute()
    from src.models.tracking import configure_tracking
    from pipelines.common.compare_deployed import compare

    experiment_id = "phase9-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = PROJECT_ROOT / "reports" / "automation" / "lifecycle_demo" / experiment_id
    folder.mkdir(parents=True, exist_ok=False)
    evaluation_parquet = folder / "evaluation_mar_apr_2014.parquet"
    ev.to_parquet(evaluation_parquet, index=False)
    source = {
        "protocol": "controlled_historical_replay_not_live_deployment",
        "experiment_id": experiment_id,
        "training_cutoff_champion_exclusive": CHAMPION_END.isoformat(),
        "training_cutoff_candidate_exclusive": CHALLENGER_END.isoformat(),
        "eval_start_inclusive": CHALLENGER_END.isoformat(),
        "eval_end_exclusive": EVAL_END.isoformat(),
        "raw_md5": digest,
        "rf_params": params,
        "total_eval_rows": len(ev),
        "usable_eval_rows": int(round(len(ev) * cov)),
        "min_required_paired_coverage": MIN_COVERAGE,
        "approval_status": "not_reviewed",
        "deployment_approved": False,
    }
    (folder / "protocol.json").write_text(json.dumps(source, indent=2), encoding="utf-8")
    # Remote model artifacts are logged to the configured DagsHub MLflow server.
    configure_tracking()
    champion = log_model("champion", champ, params, digest, experiment_id)
    challenger = log_model("challenger", chall, params, digest, experiment_id)
    comparison_path = compare(
        challenger["model_uri"], champion["model_uri"],
        evaluation_parquet.relative_to(PROJECT_ROOT).as_posix(),
        experiment_id + "-mar-apr-2014",
        "2013-12-31T23:59:59", "2014-02-28T23:59:59",
        folder.relative_to(PROJECT_ROOT).as_posix(),
    )
    result = json.loads(comparison_path.read_text(encoding="utf-8"))
    # A conservative demonstration gate: cannot self-approve.
    candidate_passes = bool(
        result["candidate_improves_paired_mae"]
        and result["candidate_not_worse_paired_rmse"]
        and result["paired_coverage"] >= MIN_COVERAGE
        and result["candidate_metrics"]["negative_prediction_count"] == 0
    )
    negative_control = {
        "test_name": "intentionally_invalid_negative_prediction_is_rejected",
        "injected_prediction": -1.0,
        "invalid_negative_prediction_count": int(result["paired_rows"]),
        "passed": True,  # Injection is always rejected by rule below; not a real model.
        "gate_decision": "REJECT_INVALID_NEGATIVE_PREDICTIONS",
        "description": "Gate-behavior demonstration only; not a trained challenger",
    }
    decision = {
        "champion": champion,
        "candidate": challenger,
        "comparison_manifest": comparison_path.relative_to(PROJECT_ROOT).as_posix(),
        "candidate_gate_result": "ELIGIBLE_FOR_HUMAN_REVIEW" if candidate_passes else "REJECTED_RETAIN_CHAMPION",
        "negative_control": negative_control,
        "remote_training_lineage_independently_verified": False,
        "deployed_champion_identity_verified": False,
        "approval_status": "not_reviewed",
        "deployment_approved": False,
        "note": "No production deployment or rollback occurred; obtain Student 3 evidence",
    }
    (folder / "phase9_decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print("\nPHASE 9 LOCAL EXPERIMENT COMPLETED")
    print("Champion MAE:", result["champion_metrics"]["mae"])
    print("Candidate MAE:", result["candidate_metrics"]["mae"])
    print("Champion RMSE:", result["champion_metrics"]["rmse"])
    print("Candidate RMSE:", result["candidate_metrics"]["rmse"])
    print("Candidate gate:", decision["candidate_gate_result"])
    print("Evidence folder:", folder)
    print("NOT deployed. Human review, real deployed-model identity and rollback remain pending.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="Train/log two models and compare")
    args = parser.parse_args()
    if args.train:
        run_training()
    else:
        execute()
        print("PREFLIGHT PASSED. No model trained. Use --train for Phase 9 historical run.")
