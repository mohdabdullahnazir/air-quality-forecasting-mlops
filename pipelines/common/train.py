
"""Student 2: Train models using run-specific prepared data."""

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from pipelines.common.context import PROJECT_ROOT
from src.features.engineering import FEATURE_COLUMNS
from src.models.tracking import configure_tracking
from src.models.train import run_experiment


RUNS_ROOT = (
    PROJECT_ROOT / "reports" / "automation" / "runs"
).resolve()

REQUIRED_COLUMNS = FEATURE_COLUMNS + ["target_pm25"]


def load_inputs(manifest_name):
    """Load artifacts from an existing preparation run."""

    manifest_path = (PROJECT_ROOT / manifest_name).resolve()

    if (
        not manifest_path.is_relative_to(RUNS_ROOT)
        or manifest_path.name != "prepare_manifest.json"
    ):
        raise ValueError(
            "Select a valid preparation manifest."
        )

    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    run_dir = manifest_path.parent
    run_id = manifest["pipeline_run_id"]

    if run_dir.name != run_id:
        raise ValueError("Pipeline run ID mismatch.")

    splits = {}
    totals = {}

    for name in ("train", "validation"):
        data_path = (
            PROJECT_ROOT / manifest["outputs"][name]
        ).resolve()

        if (
            data_path.parent != run_dir
            or data_path.name != f"{name}.parquet"
        ):
            raise ValueError(
                f"Unexpected {name} artifact location."
            )

        frame = pd.read_parquet(data_path)

        required = REQUIRED_COLUMNS + ["target_timestamp"]

        if not set(required).issubset(frame.columns):
            raise ValueError(
                f"Missing required columns in {name} data."
            )

        total_key = (
            "training_total_rows"
            if name == "train"
            else "validation_total_rows"
        )

        totals[total_key] = int(len(frame))

        if len(frame) != manifest["splits"][name]["rows"]:
            raise ValueError(
                f"{name} row count does not match manifest."
            )

        frame = frame.dropna(
            subset=REQUIRED_COLUMNS
        ).copy()

        if frame.empty:
            raise ValueError(
                f"No usable examples in {name} data."
            )

        splits[name] = frame

    if (
        splits["train"]["target_timestamp"].max()
        >= splits["validation"]["target_timestamp"].min()
    ):
        raise ValueError(
            "Training and validation periods overlap."
        )

    return (
        manifest,
        run_dir,
        splits["train"],
        splits["validation"],
        totals,
    )


def train_from_manifest(manifest_name, dry_run=False):
    """Execute Student 1's model experiments safely."""

    manifest, run_dir, train, validation, totals = (
        load_inputs(manifest_name)
    )

    config_path = (
        PROJECT_ROOT / "configs" / "model_params.yaml"
    )

    with config_path.open(encoding="utf-8") as file:
        settings = yaml.safe_load(file)

    for algorithm in ("random_forest", "xgboost"):
        if (
            not isinstance(settings.get(algorithm), list)
            or not settings[algorithm]
        ):
            raise ValueError(
                f"Missing model configurations: {algorithm}"
            )

    print("Pipeline Run ID:", manifest["pipeline_run_id"])
    print("Training rows:", len(train))
    print("Validation rows:", len(validation))
    print(
        "Feast status:",
        manifest.get("feast_status", "unknown"),
    )

    if dry_run:
        print("DRY RUN PASSED")
        print("No models were trained.")
        return

    comparison_path = run_dir / "training_comparison.csv"
    manifest_path = run_dir / "training_manifest.json"

    if comparison_path.exists() or manifest_path.exists():
        raise FileExistsError(
            "Training results already exist for this run."
        )

    # Connect to Student 1's MLflow tracking setup.
    configure_tracking()
    client = MlflowClient()

    results = []

    def record_result(name, model):
        result = run_experiment(
            name,
            model,
            train,
            validation,
            totals,
        )

        tags = {
            "pipeline_run_id": manifest["pipeline_run_id"],
            "preparation_git_commit": (
                manifest["source_git_commit"]
            ),
            "raw_dvc_md5": manifest["raw_dvc_md5"],
            "feast_status": manifest.get(
                "feast_status", "unknown"
            ),
            "evaluation_split": "validation_only",
        }

        for key, value in tags.items():
            client.set_tag(
                result["run_id"], key, str(value)
            )

        results.append(result)

    # Persistence baseline.
    record_result("persistence", None)

    # Model configurations from Student 1.
    for algorithm in ("random_forest", "xgboost"):
        for number, parameters in enumerate(
            settings[algorithm], start=1
        ):
            if algorithm == "random_forest":
                model = RandomForestRegressor(
                    random_state=42,
                    n_jobs=4,
                    **parameters,
                )
            else:
                model = XGBRegressor(
                    random_state=42,
                    n_jobs=4,
                    tree_method="hist",
                    **parameters,
                )

            record_result(
                f"{algorithm}_{number}",
                model,
            )

    comparison = pd.DataFrame(results).sort_values(
        "validation_mae"
    )

    with comparison_path.open(
        "x", encoding="utf-8", newline=""
    ) as file:
        comparison.to_csv(file, index=False)

    training_manifest = {
        "pipeline_run_id": manifest["pipeline_run_id"],
        "preparation_manifest": manifest_name,
        "feast_status": manifest.get(
            "feast_status", "unknown"
        ),
        "comparison_path": (
            comparison_path.relative_to(
                PROJECT_ROOT
            ).as_posix()
        ),
        "runs": results,
        "selected_by_validation_mae": (
            comparison.iloc[0]["model"]
        ),
        "approval_status": "not_reviewed",
        "deployment_approved": False,
    }

    with manifest_path.open(
        "x", encoding="utf-8"
    ) as file:
        json.dump(
            training_manifest,
            file,
            indent=2,
            default=lambda value: (
                value.item()
                if hasattr(value, "item")
                else str(value)
            ),
        )

    print("TRAINING COMPLETE")
    print("Results saved in:", run_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--prepare-manifest",
        required=True,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    train_from_manifest(
        args.prepare_manifest,
        args.dry_run,
    )
