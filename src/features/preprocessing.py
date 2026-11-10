from pathlib import Path

import pandas as pd

from src.data.ingestion import load_station_data
from src.data.validation import validate_station_data


def create_forecast_target(df):
    """Attach the observed PM2.5 value for the following hour."""
    validate_station_data(df)

    result = df.copy()

    result["target_timestamp"] = (
        result["timestamp"] + pd.Timedelta(hours=1)
    )

    result["target_pm25"] = result["PM2.5"].shift(-1)

    return result

def split_by_target_time(df):
    """Separate forecasting examples into chronological periods."""
    validation_start = pd.Timestamp("2015-03-01")
    test_start = pd.Timestamp("2016-03-01")

    # Exclude forecasts beyond the recorded dataset period.
    last_recorded_time = df["timestamp"].max()

    eligible = df.loc[
        df["target_timestamp"] <= last_recorded_time
    ].copy()

    target_times = eligible["target_timestamp"]

    train = eligible.loc[
        target_times < validation_start
    ].copy()

    validation = eligible.loc[
        (target_times >= validation_start)
        & (target_times < test_start)
    ].copy()

    test = eligible.loc[
        target_times >= test_start
    ].copy()

    return train, validation, test

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

    preview_columns = [
        "timestamp",
        "PM2.5",
        "target_timestamp",
        "target_pm25",
    ]

    print(forecast_data[preview_columns].head().to_string(index=False))

    print(
        "\nRows without an observed next-hour target:",
        forecast_data["target_pm25"].isna().sum(),
    )
    
    train_data, validation_data, test_data = split_by_target_time(
        forecast_data
    )

    print("\n--- CHRONOLOGICAL SPLITS ---")

    for name, split in [
        ("Training", train_data),
        ("Validation", validation_data),
        ("Test", test_data),
    ]:
        print(f"\n{name}")
        print("Rows:", len(split))
        print("First target time:", split["target_timestamp"].min())
        print("Last target time:", split["target_timestamp"].max())
        print("Observed targets:", split["target_pm25"].notna().sum())