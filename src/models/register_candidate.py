import json
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient

from src.features.engineering import FEATURE_COLUMNS
from src.models.tracking import configure_tracking
from src.models.train import prepare_training_data


PROJECT_FOLDER = Path(__file__).resolve().parents[2]
REPORT_FOLDER = PROJECT_FOLDER / "reports" / "experiments"
OUTPUT_FOLDER = PROJECT_FOLDER / "reports" / "models"

MODEL_NAME = "air-quality-pm25-aotizhongxin"


def main():
    report = json.loads(
        (REPORT_FOLDER / "final_test_report.json").read_text(
            encoding="utf-8"
        )
    )
    frozen = json.loads(
        (REPORT_FOLDER / "frozen_candidate.json").read_text(
            encoding="utf-8"
        )
    )

    selected = frozen["selected_candidate"]

    if not report["test_gate_passed"] or not selected["passed"]:
        raise ValueError("Both validation and test gates must pass.")

    if (
        report["model_uri"] != selected["model_uri"]
        or report["source_run_id"] != selected["run_id"]
    ):
        raise ValueError("The tested model differs from the frozen candidate.")

    configure_tracking()
    client = MlflowClient()

    evaluation = client.get_run(report["evaluation_run_id"])

    if (
        evaluation.info.status != "FINISHED"
        or evaluation.data.tags.get("test_gate_passed") != "true"
        or evaluation.data.tags.get("source_model_uri")
        != report["model_uri"]
        or evaluation.data.tags.get("source_training_run")
        != report["source_run_id"]
    ):
        raise ValueError("Hosted evaluation evidence does not match.")

    tags = {
        "approval_status": "pending_review",
        "deployment_approved": "false",
        "prediction_check": "pending",
        "validation_gate_passed": "true",
        "test_gate_passed": "true",
        "source_model_uri": report["model_uri"],
        "source_training_run": report["source_run_id"],
        "training_git_commit": report["training_git_commit"],
        "test_evaluation_run": report["evaluation_run_id"],
        "dataset_dvc_md5": frozen["dataset_dvc_md5"],
        "feature_source_dvc_md5": frozen["feature_source_dvc_md5"],
        "feature_service": "pm25_forecasting_v1",
        "usage": "historical_course_demo",
    }

    # Reuse an existing registration of this exact source model.
    existing = [
        version
        for version in client.search_model_versions(
            f"name = '{MODEL_NAME}'"
        )
        if version.tags.get("source_model_uri") == report["model_uri"]
    ]

    if existing:
        version = max(existing, key=lambda item: int(item.version))
        print("Reusing registered version:", version.version)
    else:
        version = mlflow.register_model(
            model_uri=report["model_uri"],
            name=MODEL_NAME,
            tags=tags,
        )

    registered_uri = f"models:/{MODEL_NAME}/{version.version}"

    print("Loading registered model:", registered_uri, flush=True)
    model = mlflow.sklearn.load_model(registered_uri)

    if list(model.feature_names_in_) != FEATURE_COLUMNS:
        raise ValueError("Registered model feature schema differs.")

    # Use validation examples for loading verification, not new test scoring.
    _, validation, _ = prepare_training_data()
    sample = validation.head(5).copy()
    inputs = sample[FEATURE_COLUMNS]

    predictions = model.predict(inputs)

    saved_predictions_file = mlflow.artifacts.download_artifacts(
        run_id=report["source_run_id"],
        artifact_path="validation_predictions.csv",
    )
    expected = pd.read_csv(saved_predictions_file).head(5)

    pd.testing.assert_series_equal(
        sample["timestamp"].reset_index(drop=True),
        pd.to_datetime(expected["timestamp"]).reset_index(drop=True),
        check_names=False,
        check_dtype=False,
    )

    np.testing.assert_allclose(
        predictions,
        expected["prediction"].to_numpy(),
        rtol=1e-10,
        atol=1e-10,
    )

    client.set_model_version_tag(
        MODEL_NAME,
        version.version,
        "prediction_check",
        "passed",
    )

    current = client.get_model_version(MODEL_NAME, version.version)

    manifest = {
        "model_name": MODEL_NAME,
        "model_version": str(version.version),
        "registered_model_uri": registered_uri,
        "source_model_uri": report["model_uri"],
        "source_training_run_id": report["source_run_id"],
        "test_evaluation_run_id": report["evaluation_run_id"],
        "training_git_commit": report["training_git_commit"],
        "dataset_dvc_md5": frozen["dataset_dvc_md5"],
        "feature_source_dvc_md5": frozen["feature_source_dvc_md5"],
        "feature_service": "pm25_forecasting_v1",
        "feature_columns": FEATURE_COLUMNS,
        "prediction_check_passed": True,
        "approval_status": current.tags.get(
            "approval_status", "pending_review"
        ),
        "deployment_approved": (
            current.tags.get("deployment_approved") == "true"
        ),
    }

    example = {
        "mode": "historical_validation_example",
        "registered_model_uri": registered_uri,
        "forecast_origins": [
            value.isoformat() for value in sample["timestamp"]
        ],
        "inputs": inputs.to_dict(orient="records"),
        "expected_predictions": predictions.tolist(),
    }

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    for filename, content in [
        ("registry_candidate.json", manifest),
        ("prediction_example.json", example),
    ]:
        path = OUTPUT_FOLDER / filename
        path.write_text(
            json.dumps(content, indent=2),
            encoding="utf-8",
        )
        client.log_artifact(
            report["evaluation_run_id"],
            str(path),
            artifact_path="registry",
        )

    print("\n--- REGISTERED CANDIDATE ---")
    print("Model name:", MODEL_NAME)
    print("Version:", version.version)
    print("Registered URI:", registered_uri)
    print("Prediction agreement with training artifact: PASS")
    print("Approval status:", manifest["approval_status"])
    print("Deployment approved:", manifest["deployment_approved"])
    print("Handoff files:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()