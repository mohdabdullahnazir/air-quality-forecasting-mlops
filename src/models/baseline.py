from pathlib import Path

from src.data.ingestion import load_station_data
from src.features.preprocessing import (
    create_forecast_target,
    split_by_target_time,
)


def evaluate_persistence(df):
    """Predict next-hour PM2.5 using the current measured value."""
    scored = df[["PM2.5", "target_pm25"]].dropna()

    if scored.empty:
        raise ValueError("No complete input-target pairs are available.")

    predictions = scored["PM2.5"]
    actual_values = scored["target_pm25"]

    errors = predictions - actual_values

    return {
        "total_rows": len(df),
        "scored_rows": len(scored),
        "mae": float(errors.abs().mean()),
        "rmse": float((errors.pow(2).mean()) ** 0.5),
    }


if __name__ == "__main__":
    project_folder = Path(__file__).resolve().parents[2]

    data_file = (
        project_folder
        / "data"
        / "raw"
        / "PRSA_Data_Aotizhongxin_20130301-20170228.csv"
    )

    station_data = load_station_data(data_file)
    forecast_data = create_forecast_target(station_data)

    _, validation_data, _ = split_by_target_time(forecast_data)

    metrics = evaluate_persistence(validation_data)

    print("--- VALIDATION: PERSISTENCE BASELINE ---")
    print("Total rows:", metrics["total_rows"])
    print("Scored rows:", metrics["scored_rows"])
    print("Rows not scored:", metrics["total_rows"] - metrics["scored_rows"])
    print(f"MAE: {metrics['mae']:.2f} µg/m³")
    print(f"RMSE: {metrics['rmse']:.2f} µg/m³")