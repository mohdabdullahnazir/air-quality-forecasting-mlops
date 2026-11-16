from pathlib import Path
import subprocess

import dagshub
import mlflow
import yaml

from src.features.engineering import FEATURE_COLUMNS


PROJECT_FOLDER = Path(__file__).resolve().parents[2]

DATA_VERSION_FILE = (
    PROJECT_FOLDER
    / "data"
    / "raw"
    / "PRSA_Data_Aotizhongxin_20130301-20170228.csv.dvc"
)


def configure_tracking():
    """Connect to this project's hosted MLflow server."""
    dagshub.init(
        repo_owner="mohdabdullahnazir",
        repo_name="air-quality-forecasting-mlops",
        mlflow=True,
    )

    mlflow.set_experiment("air-quality-pm25")


def log_lineage():
    """Record code, raw data, feature data, definitions, and environment."""
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_FOLDER,
        text=True,
    ).strip()

    feature_version_file = (
        PROJECT_FOLDER
        / "data"
        / "processed"
        / "hourly_features.parquet.dvc"
    )

    with DATA_VERSION_FILE.open(encoding="utf-8") as file:
        data_version = yaml.safe_load(file)

    with feature_version_file.open(encoding="utf-8") as file:
        feature_version = yaml.safe_load(file)

    mlflow.set_tags({
        "git_commit": git_commit,
        "feature_code_commit": git_commit,
        "feature_repo_commit": git_commit,
        "dataset_dvc_md5": data_version["outs"][0]["md5"],
        "feature_source_dvc_md5": feature_version["outs"][0]["md5"],
        "feature_service": "pm25_forecasting_v1",
        "feature_store_backend": "duckdb",
        "station": "Aotizhongxin",
    })

    mlflow.log_params({
        "forecast_horizon_hours": 1,
        "feature_count": len(FEATURE_COLUMNS),
    })

    mlflow.log_dict(
        {"columns": FEATURE_COLUMNS},
        "feature_schema.json",
    )

    for version_file in [DATA_VERSION_FILE, feature_version_file]:
        mlflow.log_artifact(
            str(version_file),
            artifact_path="data_version",
        )

    feature_repo = PROJECT_FOLDER / "feature_store" / "feature_repo"

    for filename in ["definitions.py", "feature_store.yaml"]:
        mlflow.log_artifact(
            str(feature_repo / filename),
            artifact_path="feature_repo",
        )

    mlflow.log_artifact(
        str(PROJECT_FOLDER / "requirements.txt"),
        artifact_path="environment",
    )


if __name__ == "__main__":
    configure_tracking()

    with mlflow.start_run(
        run_name="tracking-connection-check"
    ) as run:
        mlflow.set_tag("run_type", "connection_check")
        log_lineage()
        run_id = run.info.run_id

    print("Tracking connection verified.")
    print("Run ID:", run_id)