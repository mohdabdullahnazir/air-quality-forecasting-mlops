from pathlib import Path

from src.data.ingestion import load_station_data
from src.features.engineering import FEATURE_COLUMNS, create_features


PROJECT_FOLDER = Path(__file__).resolve().parents[2]

FEATURE_FILE = (
    PROJECT_FOLDER / "data" / "processed" / "hourly_features.parquet"
)

# Use a simple feature name inside Feast.
FEAST_RENAME = {"PM2.5": "pm25_current"}

FEAST_FEATURE_COLUMNS = [
    FEAST_RENAME.get(column, column)
    for column in FEATURE_COLUMNS
]


def prepare_feast_features(raw):
    """Build historical features without adding future targets."""
    features = create_features(raw)

    result = features[FEATURE_COLUMNS].rename(
        columns=FEAST_RENAME
    ).astype("float64")

    result.insert(
        0,
        "station_id",
        features["station"].astype(str),
    )

    # Project assumption: original timestamps represent Beijing local time.
    event_time = (
        features["timestamp"]
        .dt.tz_localize("Asia/Shanghai")
        .dt.tz_convert("UTC")
        .dt.as_unit("ns")
    )
    result.insert(1, "event_timestamp", event_time)

    if result[["station_id", "event_timestamp"]].isna().any().any():
        raise ValueError("Entity keys and timestamps cannot be missing.")

    if result.duplicated(["station_id", "event_timestamp"]).any():
        raise ValueError("Duplicate station/timestamp pairs.")

    return result


def main():
    raw_file = (
        PROJECT_FOLDER
        / "data"
        / "raw"
        / "PRSA_Data_Aotizhongxin_20130301-20170228.csv"
    )

    raw = load_station_data(raw_file)
    features = prepare_feast_features(raw)

    FEATURE_FILE.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(FEATURE_FILE, index=False)

    print("Saved:", FEATURE_FILE)
    print("Rows:", len(features))
    print("Model features:", len(FEAST_FEATURE_COLUMNS))
    print("Columns including entity and timestamp:", len(features.columns))
    print(
        "Rows with complete model features:",
        features[FEAST_FEATURE_COLUMNS].notna().all(axis=1).sum(),
    )
    print("\nPreview:")
    print(
        features[
            ["station_id", "event_timestamp", "pm25_current"]
        ].head().to_string(index=False)
    )


if __name__ == "__main__":
    main()