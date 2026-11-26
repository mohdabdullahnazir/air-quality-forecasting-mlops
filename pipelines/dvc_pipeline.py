"""Student 2 DVC stage bridge.

Owns only reports/automation/dvc/* and new reports/automation/runs/<run_id>/*.
Never rewrites Student 1's raw/processed .dvc outputs or final-test report.

The stable DVC preparation output is cached. MLflow jobs and run-specific
manifests are external side effects: their stable pointers are not cached.
"""

import argparse
import hashlib
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DVC_ROOT = ROOT / "reports" / "automation" / "dvc"
PREPARED_DIR = DVC_ROOT / "prepared"
RUNS_ROOT = (ROOT / "reports" / "automation" / "runs").resolve()


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _md5(path: Path) -> str:
    md5 = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required stage artifact: {path}")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _config() -> dict:
    import yaml
    cfg = yaml.safe_load((ROOT / "configs/pipeline_config.yaml").read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("Invalid pipeline_config.yaml")
    if cfg["data"].get("forecast_horizon_hours") != 1:
        raise ValueError("Student 1's forecasting contract requires horizon=1 hour")
    return cfg


def _raw_file(cfg: dict) -> Path:
    path = (ROOT / cfg["data"]["raw_path"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise FileNotFoundError(f"Expected versioned raw CSV inside project: {path}")
    expected = cfg["data"]["raw_dvc_md5"]
    actual = _md5(path)
    if expected != actual:
        raise ValueError(f"Raw DVC MD5 mismatch: expected {expected}, actual {actual}")
    return path


def prepare() -> None:
    from src.data.ingestion import load_station_data
    from src.data.validation import validate_station_data
    from src.features.engineering import FEATURE_COLUMNS, create_features
    from src.features.preprocessing import create_forecast_target, split_by_target_time

    cfg = _config()
    raw_file = _raw_file(cfg)
    data = load_station_data(raw_file)
    validate_station_data(data)
    if not data["station"].eq(cfg["data"]["station"]).all():
        raise ValueError("Unexpected air quality station")
    forecast = create_forecast_target(create_features(data))
    train, validation, test = split_by_target_time(forecast)
    splits = {"train": train, "validation": validation, "test": test}
    if any(x.empty for x in splits.values()):
        raise ValueError("One of the chronological splits is empty")

    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": 1,
        "raw_path": _relative(raw_file),
        "raw_dvc_md5": cfg["data"]["raw_dvc_md5"],
        "feature_source_dvc_md5": cfg["data"]["feature_dvc_md5"],
        "station": cfg["data"]["station"],
        "forecast_horizon_hours": 1,
        "feature_service": cfg["features"]["service"],
        "feature_columns": FEATURE_COLUMNS,
        "splits": {},
    }
    for name, frame in splits.items():
        destination = PREPARED_DIR / f"{name}.parquet"
        frame.to_parquet(destination, index=False)
        usable = frame.dropna(subset=FEATURE_COLUMNS + ["target_pm25"])
        summary["splits"][name] = {
            "rows": len(frame),
            "usable_rows": len(usable),
            "coverage": round(len(usable) / len(frame), 6),
            "first_target_timestamp": str(frame["target_timestamp"].min()),
            "last_target_timestamp": str(frame["target_timestamp"].max()),
            "path": _relative(destination),
        }
    _write_json(PREPARED_DIR / "prepared.json", summary)
    print("DVC PREPARE COMPLETE:", summary["splits"])


def verify_feast() -> None:
    import pandas as pd
    from feature_store.historical import load_forecast_from_store
    from src.data.ingestion import load_station_data
    from src.features.engineering import FEATURE_COLUMNS, create_features
    from src.features.preprocessing import create_forecast_target

    prepared = _read_json(PREPARED_DIR / "prepared.json")
    cfg = _config()
    raw = _raw_file(cfg)
    if prepared["raw_dvc_md5"] != cfg["data"]["raw_dvc_md5"]:
        raise ValueError("Prepared data hash not linked to current DVC source")

    source = load_station_data(raw)
    direct = create_forecast_target(create_features(source)).reset_index(drop=True)
    fetched = load_forecast_from_store(source).reset_index(drop=True)
    pd.testing.assert_frame_equal(
        fetched[FEATURE_COLUMNS], direct[FEATURE_COLUMNS],
        check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-12,
    )
    for field in ("timestamp", "target_timestamp", "target_pm25"):
        pd.testing.assert_series_equal(fetched[field], direct[field], check_dtype=False)
    if len(fetched) != sum(s["rows"] for s in prepared["splits"].values()) + 1:
        # The terminal hour cannot be part of any target-time split.
        raise ValueError("Feast row count inconsistent with prepared data")
    report = {
        "schema_version": 1,
        "passed": True,
        "verified_against": _relative(PREPARED_DIR / "prepared.json"),
        "prepared_sha256": _digest(PREPARED_DIR / "prepared.json"),
        "raw_dvc_md5": prepared["raw_dvc_md5"],
        "feature_source_dvc_md5": prepared["feature_source_dvc_md5"],
        "feature_service": prepared["feature_service"],
        "rows_compared": len(direct),
        "mode": "direct_feature_equivalence_check_not_training_from_feast",
    }
    _write_json(DVC_ROOT / "feast_check.json", report)
    print("FEAST FEATURE EQUIVALENCE VERIFIED, rows:", len(direct))


def train() -> None:
    from pipelines.common.context import create_run_context
    from pipelines.common.train import train_from_manifest
    from pipelines.common.verify_feast import verify

    meta = _read_json(PREPARED_DIR / "prepared.json")
    feast = _read_json(DVC_ROOT / "feast_check.json")
    if not feast.get("passed") or feast.get("prepared_sha256") != _digest(PREPARED_DIR / "prepared.json"):
        raise ValueError("Feast verification missing/stale: training blocked")
    _raw_file(_config())  # Revalidate actual raw data before any training.
    if feast["raw_dvc_md5"] != meta["raw_dvc_md5"]:
        raise ValueError("Feast/raw MD5 mismatch")

    context = create_run_context()
    run_dir = (ROOT / context["output_dir"]).resolve()
    if not run_dir.is_relative_to(RUNS_ROOT):
        raise ValueError("Run must live below reports/automation/runs")
    run_id = context["pipeline_run_id"]
    outputs = {}
    for key in ("train", "validation", "test"):
        source = PREPARED_DIR / f"{key}.parquet"
        destination = run_dir / f"{key}.parquet"
        shutil.copyfile(source, destination)
        outputs[key] = _relative(destination)
    prep_manifest = {
        "pipeline_run_id": run_id,
        "source_git_commit": context["application_git_commit"],
        "raw_path": meta["raw_path"],
        "raw_dvc_md5": meta["raw_dvc_md5"],
        "station": meta["station"],
        "forecast_horizon_hours": meta["forecast_horizon_hours"],
        "feature_columns": meta["feature_columns"],
        "outputs": outputs,
        "splits": {
            key: {k: v for k, v in values.items() if k != "path"}
            for key, values in meta["splits"].items()
        },
        "feast_status": "direct_features_verified_against_feast_not_trained_from_feast",
    }
    manifest_file = run_dir / "prepare_manifest.json"
    _write_json(manifest_file, prep_manifest)
    # This does a real second Feast equivalence check tied to this unique run ID.
    verify(_relative(manifest_file))
    train_from_manifest(_relative(manifest_file))
    trained_file = run_dir / "training_manifest.json"
    trained = _read_json(trained_file)
    if trained["pipeline_run_id"] != run_id:
        raise ValueError("Training output has wrong run ID")
    pointer = {
        "pipeline_run_id": run_id,
        "preparation_manifest": _relative(manifest_file),
        "training_manifest": _relative(trained_file),
        "training_manifest_sha256": _digest(trained_file),
        "raw_dvc_md5": meta["raw_dvc_md5"],
        "feast_check_sha256": _digest(DVC_ROOT / "feast_check.json"),
        "external_mlflow_artifacts": True,
    }
    _write_json(DVC_ROOT / "train_pointer.json", pointer)
    print("DVC TRAIN COMPLETE. Run ID:", run_id)


def evaluate() -> None:
    import mlflow
    import yaml
    from mlflow.tracking import MlflowClient
    from pipelines.common.evaluate import check_remote_runs, load_pair, make_decisions
    from src.models.tracking import configure_tracking

    pointer = _read_json(DVC_ROOT / "train_pointer.json")
    stored = ROOT / pointer["training_manifest"]
    if not stored.resolve().is_relative_to(RUNS_ROOT):
        raise ValueError("Training manifest path outside run root")
    if _digest(stored) != pointer["training_manifest_sha256"]:
        raise ValueError("Training manifest changed since upstream stage")
    _, training, preparation = load_pair(pointer["training_manifest"])
    if training["pipeline_run_id"] != pointer["pipeline_run_id"]:
        raise ValueError("DVC training pointer ID mismatch")
    feast = _read_json(stored.parent / "feast_verification.json")
    if not feast.get("passed") or feast.get("pipeline_run_id") != training["pipeline_run_id"]:
        raise ValueError("Run-specific Feast proof missing or invalid")
    cfg = _config()
    policy = yaml.safe_load((ROOT / "configs/quality_policy.yaml").read_text(encoding="utf-8"))
    configure_tracking()
    records = check_remote_runs(training, preparation, MlflowClient())
    baseline, decisions, selected = make_decisions(records, policy)
    status = "eligible_for_review" if selected else "blocked_quality_gate"
    report = {
        "schema_version": 1,
        "pipeline_run_id": training["pipeline_run_id"],
        "basis": "validation_only_no_final_test_rescoring",
        "data_revision": preparation["raw_dvc_md5"],
        "feature_service": cfg["features"]["service"],
        "mlflow_verified": True,
        "feast_direct_equivalence_verified": True,
        "quality_policy_sha256": _digest(ROOT / "configs/quality_policy.yaml"),
        "baseline": baseline,
        "decisions": decisions,
        "selected_candidate": selected,
        "status": status,
        "approval_status": "pending_review" if selected else "blocked",
        "deployment_approved": False,
    }
    with mlflow.start_run(run_name=f"dvc-gate-{training['pipeline_run_id']}") as run:
        mlflow.set_tags({
            "run_type": "dvc_validation_gate",
            "pipeline_run_id": training["pipeline_run_id"],
            "quality_gate_passed": str(bool(selected)).lower(),
            "deployment_approved": "false",
        })
        report["gate_run_id"] = run.info.run_id
        mlflow.log_dict(report, "evaluation_manifest.json")
    # Never overwrite earlier evaluation evidence; a policy-only rerun gets a new review attempt.
    dest = stored.parent / "evaluation_attempts" / report["gate_run_id"] / "evaluation_manifest.json"
    _write_json(dest, report)
    state = {
        "pipeline_run_id": training["pipeline_run_id"],
        "evaluation_manifest": _relative(dest),
        "evaluation_sha256": _digest(dest),
        "status": status,
        "gate_run_id": report["gate_run_id"],
        "deployment_approved": False,
        "external_mlflow_artifacts": True,
    }
    _write_json(DVC_ROOT / "evaluation_pointer.json", state)
    print("DVC EVALUATION:", status, "gate run", report["gate_run_id"])
    if not selected:
        raise RuntimeError("Mandatory quality gate rejected all candidates; no deployment")


def main():
    parser = argparse.ArgumentParser(description="Student 2 DVC stage bridge")
    parser.add_argument("stage", choices=("prepare", "verify-feast", "train", "evaluate"))
    stage = parser.parse_args().stage
    {"prepare": prepare, "verify-feast": verify_feast, "train": train, "evaluate": evaluate}[stage]()


if __name__ == "__main__":
    main()
