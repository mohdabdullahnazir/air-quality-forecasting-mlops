import hashlib
import json
from pathlib import Path

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from feature_store.historical import (
    RAW_FILE,
    load_forecast_from_store,
)
from src.features.engineering import FEATURE_COLUMNS
from src.features.export_feast import FEATURE_FILE
from src.features.preprocessing import split_by_target_time
from src.models.evaluate import regression_metrics
from src.models.quality_gate import assess_candidate
from src.models.tracking import configure_tracking, log_lineage


PROJECT_FOLDER = Path(__file__).resolve().parents[2]
REPORT_FOLDER = PROJECT_FOLDER / "reports" / "experiments"

GATE_FILE = REPORT_FOLDER / "quality_gate.json"
FROZEN_FILE = REPORT_FOLDER / "frozen_candidate.json"
REPORT_FILE = REPORT_FOLDER / "final_test_report.json"


def print_report(report):
    candidate = report["test_metrics"]
    baseline = report["persistence_metrics"]

    print("\n--- FINAL TEST EVALUATION ---")
    print("Selected model:", report["model"])
    print("Total test rows:", report["total_rows"])
    print("Scored test rows:", report["scored_rows"])
    print(f"Test coverage: {report['coverage']:.2%}")

    print(
        f"Random Forest: MAE={candidate['mae']:.3f}, "
        f"RMSE={candidate['rmse']:.3f}, "
        f"R²={candidate['r2']:.4f}"
    )
    print(
        f"Persistence:   MAE={baseline['mae']:.3f}, "
        f"RMSE={baseline['rmse']:.3f}, "
        f"R²={baseline['r2']:.4f}"
    )

    status = "PASS" if report["test_gate_passed"] else "FAIL"
    print("Test quality gate:", status)

    for reason in report["failure_reasons"]:
        print(" -", reason)

    print("Deployment approved:", report["deployment_approved"])
    print("Report:", REPORT_FILE)


def main():
    # Reuse the recorded result instead of casually repeating test scoring.
    if REPORT_FILE.exists():
        report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        print("Using the previously saved final test report.")
        print_report(report)
        return 0 if report["test_gate_passed"] else 1

    gate = json.loads(GATE_FILE.read_text(encoding="utf-8"))
    selected = gate.get("selected_candidate")

    if (
        gate.get("status") != "eligible_for_review"
        or not selected
        or not selected.get("passed")
    ):
        raise ValueError("No validation-approved candidate is available.")

    if selected["model"] != "random_forest_1":
        raise ValueError("This evaluation is fixed to Random Forest 1.")

    configure_tracking()
    source_run = MlflowClient().get_run(selected["run_id"])

    if source_run.info.status != "FINISHED":
        raise ValueError("The selected training run did not finish.")

    # Check the actual files match the versions used for training.
    file_versions = [
        (RAW_FILE, "dataset_dvc_md5"),
        (FEATURE_FILE, "feature_source_dvc_md5"),
    ]

    for path, tag in file_versions:
        digest = hashlib.md5(path.read_bytes()).hexdigest()

        if digest != source_run.data.tags.get(tag):
            raise ValueError(
                f"{path.name} differs from the selected training version."
            )

    frozen = {
        "selected_candidate": selected,
        "validation_gate_run_id": gate["gate_run_id"],
        "policy": gate["policy"],
        "dataset_dvc_md5": source_run.data.tags["dataset_dvc_md5"],
        "feature_source_dvc_md5": (
            source_run.data.tags["feature_source_dvc_md5"]
        ),
    }

    if FROZEN_FILE.exists():
        previous = json.loads(FROZEN_FILE.read_text(encoding="utf-8"))

        if previous != frozen:
            raise ValueError(
                "The candidate or policy differs from the frozen selection."
            )
    else:
        FROZEN_FILE.write_text(
            json.dumps(frozen, indent=2),
            encoding="utf-8",
        )

    print("Frozen candidate:", selected["model"])
    print("Loading the saved model...", flush=True)

    model = mlflow.sklearn.load_model(selected["model_uri"])

    if list(model.feature_names_in_) != FEATURE_COLUMNS:
        raise ValueError("Saved model feature names or order differ.")

    forecast = load_forecast_from_store()
    _, _, test = split_by_target_time(forecast)

    usable = test.dropna(
        subset=FEATURE_COLUMNS + ["target_pm25"]
    ).copy()

    if len(usable) < 2:
        raise ValueError("Insufficient complete test observations.")

    coverage = len(usable) / len(test)

    with mlflow.start_run(run_name="final-test-random-forest-1") as run:
        log_lineage()

        # Evaluate the exact saved estimator, without fitting it again.
        predictions = model.predict(usable[FEATURE_COLUMNS])
        persistence = usable["PM2.5"].to_numpy()
        actual = usable["target_pm25"].to_numpy()

        test_metrics = regression_metrics(actual, predictions)
        baseline_metrics = regression_metrics(actual, persistence)

        gate_metrics = {
            "mae": test_metrics["mae"],
            "rmse": test_metrics["rmse"],
            "negative_predictions": (
                test_metrics["negative_prediction_count"]
            ),
            "coverage": coverage,
        }

        reasons = assess_candidate(
            gate_metrics,
            baseline_metrics,
            frozen["policy"],
        )

        report = {
            "model": selected["model"],
            "model_uri": selected["model_uri"],
            "source_run_id": selected["run_id"],
            "training_git_commit": selected["training_git_commit"],
            "evaluation_run_id": run.info.run_id,
            "validation_gate_run_id": gate["gate_run_id"],
            "first_target_time": test["target_timestamp"].min().isoformat(),
            "last_target_time": test["target_timestamp"].max().isoformat(),
            "total_rows": len(test),
            "scored_rows": len(usable),
            "coverage": coverage,
            "test_metrics": test_metrics,
            "persistence_metrics": baseline_metrics,
            "policy": frozen["policy"],
            "test_gate_passed": not reasons,
            "failure_reasons": reasons,
            "approval_status": "pending_review" if not reasons else "blocked",
            "deployment_approved": False,
        }

        mlflow.set_tags({
            "run_type": "final_test_evaluation",
            "source_training_run": selected["run_id"],
            "source_model_uri": selected["model_uri"],
            "source_training_commit": selected["training_git_commit"],
            "test_gate_passed": str(not reasons).lower(),
            "approval_status": report["approval_status"],
        })

        mlflow.log_metrics({
            **{
                f"test_{key}": value
                for key, value in test_metrics.items()
            },
            **{
                f"test_persistence_{key}": value
                for key, value in baseline_metrics.items()
            },
            "test_total_rows": len(test),
            "test_scored_rows": len(usable),
            "test_coverage": coverage,
        })

        results = usable[
            ["timestamp", "target_timestamp", "target_pm25"]
        ].copy()
        results["prediction"] = predictions
        results["persistence_prediction"] = persistence

        mlflow.log_text(
            results.to_csv(index=False),
            "test_predictions.csv",
        )
        mlflow.log_dict(report, "final_test_report.json")
        mlflow.log_artifact(str(FROZEN_FILE))

    REPORT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print_report(report)
    return 0 if report["test_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())