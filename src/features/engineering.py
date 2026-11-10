from pathlib import Path

import numpy as np

from src.data.ingestion import load_station_data
from src.data.validation import validate_station_data
from src.features.preprocessing import (
    create_forecast_target,
    split_by_target_time,
)
from src.models.baseline import evaluate_persistence


FEATURE_COLUMNS = [
    "PM2.5", "TEMP", "PRES", "DEWP", "RAIN", "WSPM",
    "pm25_lag_1h", "pm25_lag_3h",
    "pm25_lag_6h", "pm25_lag_24h",
    "pm25_mean_3h", "pm25_mean_6h", "pm25_mean_24h",
    "hour_sin", "hour_cos",
    "weekday_sin", "weekday_cos",
    "month_sin", "month_cos",
]


def create_features(df):
    """Create features using current and earlier readings only."""
    validate_station_data(df)
    result = df.copy()

    for hours in [1, 3, 6, 24]:
        result[f"pm25_lag_{hours}h"] = result["PM2.5"].shift(hours)

    for hours in [3, 6, 24]:
        result[f"pm25_mean_{hours}h"] = (
            result["PM2.5"]
            .rolling(window=hours, min_periods=hours)
            .mean()
        )

    hour = result["timestamp"].dt.hour
    weekday = result["timestamp"].dt.day_of_week
    month = result["timestamp"].dt.month - 1

    result["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    result["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    result["weekday_sin"] = np.sin(2 * np.pi * weekday / 7)
    result["weekday_cos"] = np.cos(2 * np.pi * weekday / 7)

    result["month_sin"] = np.sin(2 * np.pi * month / 12)
    result["month_cos"] = np.cos(2 * np.pi * month / 12)

    return result


if __name__ == "__main__":
    project_folder = Path(__file__).resolve().parents[2]

    data_file = (
        project_folder
        / "data"
        / "raw"
        / "PRSA_Data_Aotizhongxin_20130301-20170228.csv"
    )

    station_data = load_station_data(data_file)
    feature_data = create_features(station_data)
    forecast_data = create_forecast_target(feature_data)

    _, validation_data, _ = split_by_target_time(forecast_data)

    usable_validation = validation_data.dropna(
        subset=FEATURE_COLUMNS + ["target_pm25"]
    )

    baseline = evaluate_persistence(usable_validation)

    print("Feature count:", len(FEATURE_COLUMNS))
    print("Validation rows:", len(validation_data))
    print("Usable validation rows:", len(usable_validation))

    coverage = len(usable_validation) / len(validation_data) * 100
    print(f"Validation coverage: {coverage:.2f}%")

    print(f"Matched persistence MAE: {baseline['mae']:.2f}")
    print(f"Matched persistence RMSE: {baseline['rmse']:.2f}")