from pathlib import Path
from time import perf_counter

import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
from mlflow.models import infer_signature
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from src.data.ingestion import load_station_data
from src.features.engineering import FEATURE_COLUMNS, create_features
from src.features.preprocessing import (
    create_forecast_target,
    split_by_target_time,
)
from src.models.evaluate import regression_metrics
from src.models.tracking import configure_tracking, log_lineage


PROJECT_FOLDER = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_FOLDER / "configs" / "model_params.yaml"


def prepare_training_data():
    data_file = (
        PROJECT_FOLDER
        / "data"
        / "raw"
        / "PRSA_Data_Aotizhongxin_20130301-20170228.csv"
    )

    raw = load_station_data(data_file)
    features = create_features(raw)
    forecast = create_forecast_target(features)

    train, validation, _ = split_by_target_time(forecast)

    totals = {
        "training_total_rows": len(train),
        "validation_total_rows": len(validation),
    }

    required = FEATURE_COLUMNS + ["target_pm25"]
    train = train.dropna(subset=required).copy()
    validation = validation.dropna(subset=required).copy()

    if train.empty or validation.empty:
        raise ValueError("No usable training or validation examples.")

    return train, validation, totals


def log_validation_artifacts(validation, predictions):
    results = validation[
        ["timestamp", "target_timestamp", "target_pm25"]
    ].copy()

    results["prediction"] = predictions
    results["run_id"] = mlflow.active_run().info.run_id

    mlflow.log_text(
        results.to_csv(index=False),
        "validation_predictions.csv",
    )

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(
        results["target_pm25"],
        results["prediction"],
        s=5,
        alpha=0.25,
    )

    limit = max(
        float(results["target_pm25"].max()),
        float(results["prediction"].max()),
        1.0,
    )

    ax.plot([0, limit], [0, limit], "k--")
    ax.set_xlabel("Actual PM2.5 (µg/m³)")
    ax.set_ylabel("Predicted PM2.5 (µg/m³)")
    ax.set_title("Validation: actual versus predicted")
    fig.tight_layout()

    mlflow.log_figure(fig, "validation_actual_vs_predicted.png")
    plt.close(fig)


def run_experiment(name, model, train, validation, totals):
    print(f"\nRunning {name}...", flush=True)

    x_train = train[FEATURE_COLUMNS]
    y_train = train["target_pm25"]
    x_validation = validation[FEATURE_COLUMNS]
    y_validation = validation["target_pm25"]

    with mlflow.start_run(run_name=name) as run:
        log_lineage()

        mlflow.set_tags({
            "run_type": "baseline" if model is None else "candidate",
            "approval_status": "not_reviewed",
            "dataset_citation": (
                "Chen, S. (2017). Beijing Multi-Site Air Quality. "
                "https://doi.org/10.24432/C5RK5G"
            ),
            "dataset_license": "CC-BY-4.0",
        })

        mlflow.log_param("model_type", name)
        mlflow.log_artifact(
            str(CONFIG_FILE),
            artifact_path="configuration",
        )

        model_uri = ""

        if model is None:
            training_seconds = 0.0
            train_predictions = train["PM2.5"].to_numpy()
            validation_predictions = validation["PM2.5"].to_numpy()
        else:
            mlflow.log_params(model.get_params())

            started = perf_counter()
            model.fit(x_train, y_train)
            training_seconds = perf_counter() - started

            train_predictions = model.predict(x_train)
            validation_predictions = model.predict(x_validation)

        train_metrics = regression_metrics(y_train, train_predictions)
        validation_metrics = regression_metrics(
            y_validation,
            validation_predictions,
        )

        logged_metrics = {
            **{
                f"train_{key}": value
                for key, value in train_metrics.items()
            },
            **{
                f"validation_{key}": value
                for key, value in validation_metrics.items()
            },
            "training_seconds": training_seconds,
            "training_rows": len(train),
            "validation_rows": len(validation),
            "training_coverage": len(train) / totals["training_total_rows"],
            "validation_coverage": (
                len(validation) / totals["validation_total_rows"]
            ),
        }

        mlflow.log_metrics(logged_metrics)
        log_validation_artifacts(validation, validation_predictions)

        if model is not None:
            example = x_train.head(5)
            model_info = mlflow.sklearn.log_model(
                sk_model=model,
                name="model",
                signature=infer_signature(
                    example,
                    model.predict(example),
                ),
                input_example=example,
                code_paths=[str(PROJECT_FOLDER / "src")],
            )
            model_uri = model_info.model_uri

        result = {
            "model": name,
            "run_id": run.info.run_id,
            "model_uri": model_uri,
            "validation_mae": validation_metrics["mae"],
            "validation_rmse": validation_metrics["rmse"],
            "validation_r2": validation_metrics["r2"],
            "negative_predictions": (
                validation_metrics["negative_prediction_count"]
            ),
            "training_seconds": training_seconds,
        }

    print(
        f"{name}: MAE={result['validation_mae']:.3f}, "
        f"RMSE={result['validation_rmse']:.3f}",
        flush=True,
    )

    return result


def main():
    with CONFIG_FILE.open(encoding="utf-8") as file:
        settings = yaml.safe_load(file)

    train, validation, totals = prepare_training_data()

    print("Usable training rows:", len(train))
    print("Usable validation rows:", len(validation))

    configure_tracking()

    results = [
        run_experiment(
            "persistence", None, train, validation, totals
        )
    ]

    for algorithm in ["random_forest", "xgboost"]:
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

            results.append(
                run_experiment(
                    f"{algorithm}_{number}",
                    model,
                    train,
                    validation,
                    totals,
                )
            )

    comparison = pd.DataFrame(results).sort_values("validation_mae")

    output_file = (
        PROJECT_FOLDER
        / "reports"
        / "experiments"
        / "validation_comparison.csv"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output_file, index=False)

    print("\n--- VALIDATION COMPARISON ---")
    print(
        comparison[
            [
                "model",
                "validation_mae",
                "validation_rmse",
                "validation_r2",
                "negative_predictions",
            ]
        ].to_string(index=False)
    )

    print("\nComparison saved to:", output_file)
    print("Test-period evaluation has not been performed.")


if __name__ == "__main__":
    main()