from pathlib import Path

import pandas as pd
from feast import FeatureStore

from src.data.ingestion import load_station_data
from src.features.engineering import FEATURE_COLUMNS, create_features
from src.features.export_feast import FEAST_RENAME
from src.features.preprocessing import (
    create_forecast_target,
    split_by_target_time,
)


PROJECT_FOLDER = Path(__file__).resolve().parents[1]
REPO_PATH = PROJECT_FOLDER / "feature_store" / "feature_repo"

RAW_FILE = (
    PROJECT_FOLDER
    / "data"
    / "raw"
    / "PRSA_Data_Aotizhongxin_20130301-20170228.csv"
)


def load_forecast_from_store(raw=None):
    """Retrieve features while keeping original times and labels outside Feast."""
    if raw is None:
        raw = load_station_data(RAW_FILE)

    forecast = create_forecast_target(raw)

    # Keep original timestamps and future labels outside the Feast query.
    metadata = forecast[
        ["timestamp", "target_timestamp", "target_pm25", "station"]
    ].copy()

    metadata["station_id"] = metadata["station"].astype(str)

    metadata["event_timestamp"] = (
        metadata["timestamp"]
        .dt.tz_localize("Asia/Shanghai")
        .dt.tz_convert("UTC")
        .dt.as_unit("ns")
    )

    keys = ["station_id", "event_timestamp"]

    # Feast receives only the entity and forecast-origin time.
    requests = metadata[keys].copy()

    store = FeatureStore(repo_path=str(REPO_PATH))
    service = store.get_feature_service("pm25_forecasting_v1")

    features = store.get_historical_features(
        entity_df=requests,
        features=service,
        full_feature_names=False,
    ).to_df()

    reverse_names = {
        feast_name: original_name
        for original_name, feast_name in FEAST_RENAME.items()
    }
    features = features.rename(columns=reverse_names)

    features["event_timestamp"] = (
        pd.to_datetime(features["event_timestamp"], utc=True)
        .dt.as_unit("ns")
    )

    if len(features) != len(metadata):
        raise ValueError("Historical retrieval changed the number of rows.")

    # Match by station and time rather than relying on returned row order.
    result = metadata.merge(
        features[keys + FEATURE_COLUMNS],
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    if not result["_merge"].eq("both").all():
        raise ValueError("Some requested station/timestamp keys were not returned.")

    result = (
        result.drop(columns="_merge")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    result[FEATURE_COLUMNS] = result[FEATURE_COLUMNS].astype("float64")

    # Check timestamps, their data types, and labels remain unchanged.
    for column in ["timestamp", "target_timestamp", "target_pm25"]:
        pd.testing.assert_series_equal(
            result[column],
            forecast[column].reset_index(drop=True),
        )

    return result


def main():
    raw = load_station_data(RAW_FILE)

    print("Retrieving historical features through Feast...", flush=True)
    retrieved = load_forecast_from_store(raw)

    # Compare against the existing feature engineering implementation.
    direct = create_features(raw).reset_index(drop=True)

    pd.testing.assert_frame_equal(
        retrieved[FEATURE_COLUMNS],
        direct[FEATURE_COLUMNS],
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )

    print("Feature values and missing-value positions match.")
    print("Forecast timestamps and target values match.")
    print("Retrieved rows:", len(retrieved))

    complete = retrieved[FEATURE_COLUMNS].notna().all(axis=1)
    print("Rows with complete features:", int(complete.sum()))

    train, validation, _ = split_by_target_time(retrieved)
    required = FEATURE_COLUMNS + ["target_pm25"]

    usable_train = train.dropna(subset=required)
    usable_validation = validation.dropna(subset=required)

    print("Usable training rows:", len(usable_train))
    print("Usable validation rows:", len(usable_validation))

    print("\nPreview:")
    print(
        retrieved[
            [
                "timestamp",
                "PM2.5",
                "pm25_lag_1h",
                "target_timestamp",
                "target_pm25",
            ]
        ].head().to_string(index=False)
    )

    print("\nHistorical retrieval checks passed.")
    print("No model training or test-period scoring was performed.")


if __name__ == "__main__":
    main()