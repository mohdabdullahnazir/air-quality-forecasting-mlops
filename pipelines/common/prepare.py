
"""Student 2: Run-specific data preparation pipeline."""

import hashlib
import json
from pathlib import Path

import yaml

from pipelines.common.context import PROJECT_ROOT, create_run_context
from src.data.ingestion import load_station_data
from src.data.validation import validate_station_data
from src.features.engineering import FEATURE_COLUMNS, create_features
from src.features.preprocessing import (
    create_forecast_target,
    split_by_target_time,
)


def file_md5(path: Path) -> str:
    """Calculate MD5 checksum to verify the dataset version."""
    digest = hashlib.md5()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def prepare_data() -> dict:
    """Validate data, engineer features, and save run-specific splits."""

    config_path = PROJECT_ROOT / "configs" / "pipeline_config.yaml"

    with config_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)

    data_config = config["data"]

    # Verify forecasting horizon.
    if data_config.get("forecast_horizon_hours") != 1:
        raise ValueError(
            "Set forecast_horizon_hours: 1 in pipeline_config.yaml"
        )

    # Locate original dataset.
    raw_path = (PROJECT_ROOT / data_config["raw_path"]).resolve()

    if not raw_path.is_relative_to(PROJECT_ROOT):
        raise ValueError("Raw dataset must be inside the project")

    if not raw_path.is_file():
        raise FileNotFoundError(
            f"Dataset is missing: {raw_path}. "
            "Restore the tracked CSV using DVC first."
        )

    # Verify dataset checksum.
    actual_md5 = file_md5(raw_path)
    expected_md5 = data_config["raw_dvc_md5"]

    if actual_md5 != expected_md5:
        raise ValueError(
            "Raw CSV does not match the configured DVC checksum. "
            "Check the dataset version."
        )

    # STEP 1: Load and validate data.
    station_data = load_station_data(raw_path)
    validate_station_data(station_data)

    if not station_data["station"].eq(data_config["station"]).all():
        raise ValueError("Station does not match configuration")

    # STEP 2: Feature engineering.
    features = create_features(station_data)

    # STEP 3: Next-hour forecasting target.
    forecast_data = create_forecast_target(features)

    # STEP 4: Chronological train/validation/test splitting.
    train, validation, test = split_by_target_time(forecast_data)

    splits = {
        "train": train,
        "validation": validation,
        "test": test,
    }

    if any(frame.empty for frame in splits.values()):
        raise ValueError("A chronological split is empty")

    # STEP 5: Create unique pipeline run context.
    context = create_run_context()
    run_dir = PROJECT_ROOT / context["output_dir"]

    outputs = {}
    split_info = {}

    # STEP 6: Save each split separately.
    for name, frame in splits.items():
        path = run_dir / f"{name}.parquet"

        frame.to_parquet(path, index=False)

        outputs[name] = path.relative_to(PROJECT_ROOT).as_posix()

        usable = frame.dropna(
            subset=FEATURE_COLUMNS + ["target_pm25"]
        )

        split_info[name] = {
            "rows": int(len(frame)),
            "usable_rows": int(len(usable)),
            "coverage": round(len(usable) / len(frame), 6),
            "first_target_timestamp": str(
                frame["target_timestamp"].min()
            ),
            "last_target_timestamp": str(
                frame["target_timestamp"].max()
            ),
        }

    # STEP 7: Generate run-specific manifest.
    manifest = {
        "pipeline_run_id": context["pipeline_run_id"],
        "source_git_commit": context["application_git_commit"],
        "raw_path": raw_path.relative_to(PROJECT_ROOT).as_posix(),
        "raw_dvc_md5": actual_md5,
        "station": data_config["station"],
        "forecast_horizon_hours": 1,
        "feature_columns": FEATURE_COLUMNS,
        "outputs": outputs,
        "splits": split_info,
        "feast_status": "not_applied_yet",
    }

    manifest_path = run_dir / "prepare_manifest.json"

    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)

    return manifest


if __name__ == "__main__":
    result = prepare_data()

    print("PREPARATION SUCCESSFUL")
    print("Pipeline Run ID:", result["pipeline_run_id"])
    print("Split outputs:", result["outputs"])
