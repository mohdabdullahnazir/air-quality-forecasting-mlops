"""Verify Feast historical features against Student 1's direct feature computation.

Does NOT train a model, overwrite original reports, or alter MLflow tags.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from pipelines.common.context import PROJECT_ROOT
from feature_store.historical import load_forecast_from_store
from src.data.ingestion import load_station_data
from src.features.engineering import FEATURE_COLUMNS, create_features
from src.features.preprocessing import create_forecast_target


def verify(preparation_manifest: str) -> Path:
    path = (PROJECT_ROOT / preparation_manifest).resolve()
    run_root = (PROJECT_ROOT / "reports/automation/runs").resolve()
    if not path.is_relative_to(run_root) or path.name != "prepare_manifest.json":
        raise ValueError("Specify a run-specific prepare_manifest.json")
    prep = json.loads(path.read_text(encoding="utf-8"))
    if path.parent.name != prep["pipeline_run_id"]:
        raise ValueError("Run ID and directory mismatch")
    raw_path = (PROJECT_ROOT / prep["raw_path"]).resolve()
    if not raw_path.is_relative_to(PROJECT_ROOT):
        raise ValueError("Raw file path escapes project")
    raw_hash = hashlib.md5(raw_path.read_bytes()).hexdigest()
    if raw_hash != prep["raw_dvc_md5"]:
        raise ValueError("Raw data changed since preparation")

    raw = load_station_data(raw_path)
    direct = create_forecast_target(create_features(raw)).reset_index(drop=True)
    feast_result = load_forecast_from_store(raw).reset_index(drop=True)
    pd.testing.assert_frame_equal(
        feast_result[FEATURE_COLUMNS], direct[FEATURE_COLUMNS],
        check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-12,
    )
    for col in ("timestamp", "target_timestamp", "target_pm25"):
        pd.testing.assert_series_equal(feast_result[col], direct[col], check_dtype=False)

    result = {
        "pipeline_run_id": prep["pipeline_run_id"],
        "raw_dvc_md5": raw_hash,
        "verified_git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip(),
        "method": "feast_historical_vs_student1_direct",
        "feature_service": "pm25_forecasting_v1",
        "rows_compared": int(len(direct)),
        "feature_columns_compared": FEATURE_COLUMNS,
        "passed": True,
        "note": "Offline equivalence check; original run logged direct-prepared features.",
    }
    output = path.parent / "feast_verification.json"
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-manifest", required=True)
    args = parser.parse_args()
    output = verify(args.prepare_manifest)
    print("FEAST EQUIVALENCE VERIFIED:", output)
