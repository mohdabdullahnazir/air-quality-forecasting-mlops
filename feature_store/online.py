import json

import pandas as pd
from feast import FeatureStore

from feature_store.historical import PROJECT_FOLDER, REPO_PATH
from feature_store.validation import validate_online_features
from src.features.export_feast import (
    FEATURE_FILE,
    FEAST_FEATURE_COLUMNS,
    FEAST_RENAME,
)
from src.features.engineering import FEATURE_COLUMNS


def fetch_online(store, station_id):
    service = store.get_feature_service("pm25_forecasting_v1")

    return store.get_online_features(
        features=service,
        entity_rows=[{"station_id": station_id}],
        full_feature_names=False,
    ).to_df(include_event_timestamps=True)


def main():
    source = pd.read_parquet(FEATURE_FILE)

    # Choose a complete snapshot from the validation period.
    cutoff = pd.Timestamp(
        "2016-02-29 22:00:00",
        tz="Asia/Shanghai",
    ).tz_convert("UTC")

    eligible = source.loc[
        (source["event_timestamp"] <= cutoff)
        & source[FEAST_FEATURE_COLUMNS].notna().all(axis=1)
    ].sort_values("event_timestamp")

    if eligible.empty:
        raise ValueError("No complete snapshot is available.")

    snapshot = eligible.iloc[-1]
    replay_time = pd.Timestamp(snapshot["event_timestamp"])
    station_id = str(snapshot["station_id"])

    print("Mode: HISTORICAL REPLAY")
    print("Station:", station_id)
    print("Replay time:", replay_time)
    print("Materializing the selected snapshot...", flush=True)

    store = FeatureStore(repo_path=str(REPO_PATH))

    # This narrow interval contains the selected hourly snapshot.
    store.materialize(
        start_date=(
            replay_time - pd.Timedelta(minutes=1)
        ).to_pydatetime(),
        end_date=(
            replay_time + pd.Timedelta(seconds=1)
        ).to_pydatetime(),
        feature_views=["air_quality_hourly"],
    )

    online = fetch_online(store, station_id)

    inputs, feature_time = validate_online_features(
        online,
        station_id,
        now=replay_time,
    )

    # Compare online inputs against Feast's historical retrieval.
    requests = pd.DataFrame({
        "station_id": [station_id],
        "event_timestamp": [replay_time],
    })

    historical = store.get_historical_features(
        entity_df=requests,
        features=store.get_feature_service("pm25_forecasting_v1"),
        full_feature_names=False,
    ).to_df()

    reverse_names = {
        feast_name: original_name
        for original_name, feast_name in FEAST_RENAME.items()
    }

    expected = (
        historical[FEAST_FEATURE_COLUMNS]
        .rename(columns=reverse_names)
        .loc[:, FEATURE_COLUMNS]
        .astype("float64")
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        inputs,
        expected,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )

    print("Online retrieval: PASS")
    print("Offline/online feature agreement: PASS")
    print("Replay freshness check: PASS")

    scenarios = [
        (
            "Stale feature rejection",
            station_id,
            replay_time + pd.Timedelta(hours=2),
        ),
        (
            "Unknown station rejection",
            "__unknown_station__",
            replay_time,
        ),
        (
            "Historical data rejected against real clock",
            station_id,
            None,
        ),
    ]

    for label, requested_station, reference_time in scenarios:
        try:
            frame = fetch_online(store, requested_station)
            validate_online_features(
                frame,
                requested_station,
                now=reference_time,
            )
        except ValueError as error:
            print(f"{label}: PASS ({error})")
        else:
            raise AssertionError(f"{label} failed to block invalid inputs.")

    report = {
        "mode": "historical_replay",
        "station_id": station_id,
        "feature_timestamp": feature_time.isoformat(),
        "replay_time": replay_time.isoformat(),
        "model_feature_count": len(FEATURE_COLUMNS),
        "offline_online_agreement": True,
        "stale_features_rejected": True,
        "unknown_station_rejected": True,
        "real_clock_rejects_historical_data": True,
    }

    output = (
        PROJECT_FOLDER
        / "reports"
        / "feature_store"
        / "online_replay.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\nEvidence saved:", output)
    print("No test-period scoring or live pollution prediction was performed.")


if __name__ == "__main__":
    main()