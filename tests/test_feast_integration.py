from datetime import timedelta

import pandas as pd
import pytest
import yaml
from feast import Entity, FeatureStore, FeatureView, Field, FileSource, Project
from feast.types import Float64
from feast.value_type import ValueType

from feature_store.validation import validate_online_features
from src.features.engineering import FEATURE_COLUMNS
from src.features.export_feast import (
    FEAST_FEATURE_COLUMNS,
    FEAST_RENAME,
)


EVENT_TIME = pd.Timestamp("2020-01-01 00:00:00", tz="UTC")
STATION = "Aotizhongxin"


@pytest.fixture
def local_store(tmp_path):
    configuration = {
        "project": "air_quality_tests",
        "provider": "local",
        "registry": str(tmp_path / "registry.db"),
        "offline_store": {"type": "duckdb"},
        "online_store": {
            "type": "sqlite",
            "path": str(tmp_path / "online.db"),
        },
        "entity_key_serialization_version": 3,
    }

    (tmp_path / "feature_store.yaml").write_text(
        yaml.safe_dump(configuration),
        encoding="utf-8",
    )

    data = pd.DataFrame({
        "station_id": [STATION, STATION],
        "event_timestamp": pd.date_range(
            EVENT_TIME, periods=2, freq="h"
        ).as_unit("ns"),
    })

    for column in FEAST_FEATURE_COLUMNS:
        data[column] = 1.0

    data["PRES"] = 1013.0
    data["pm25_current"] = [25.0, 999.0]

    source_path = tmp_path / "features.parquet"
    data.to_parquet(source_path, index=False)

    entity = Entity(
        name="station",
        join_keys=["station_id"],
        value_type=ValueType.STRING,
    )
    source = FileSource(
        name="test_source",
        path=source_path.as_posix(),
        timestamp_field="event_timestamp",
    )
    view = FeatureView(
        name="test_hourly",
        entities=[entity],
        ttl=timedelta(minutes=30),
        schema=[
            Field(name=column, dtype=Float64)
            for column in FEAST_FEATURE_COLUMNS
        ],
        source=source,
        online=True,
    )

    store = FeatureStore(repo_path=str(tmp_path))
    store.apply([
        Project(name="air_quality_tests"),
        entity,
        source,
        view,
    ])

    references = [
        f"test_hourly:{column}"
        for column in FEAST_FEATURE_COLUMNS
    ]

    yield store, references

    # Only the temporary test store is removed.
    store.teardown()


def test_real_materialization_and_online_offline_agreement(local_store):
    store, references = local_store

    store.materialize(
        start_date=(EVENT_TIME - pd.Timedelta(minutes=1)).to_pydatetime(),
        end_date=(EVENT_TIME + pd.Timedelta(seconds=1)).to_pydatetime(),
        feature_views=["test_hourly"],
    )

    online = store.get_online_features(
        features=references,
        entity_rows=[{"station_id": STATION}],
    ).to_df(include_event_timestamps=True)

    actual, feature_time = validate_online_features(
        online, STATION, now=EVENT_TIME
    )

    historical = store.get_historical_features(
        entity_df=pd.DataFrame({
            "station_id": [STATION],
            "event_timestamp": [EVENT_TIME],
        }),
        features=references,
    ).to_df()

    reverse_names = {
        value: key for key, value in FEAST_RENAME.items()
    }
    expected = (
        historical[FEAST_FEATURE_COLUMNS]
        .rename(columns=reverse_names)
        .loc[:, FEATURE_COLUMNS]
        .astype("float64")
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(actual, expected)

    assert actual["PM2.5"].iloc[0] == 25.0
    assert feature_time == EVENT_TIME


def test_historical_lookup_rejects_future_and_expired_features(local_store):
    store, references = local_store

    result = store.get_historical_features(
        entity_df=pd.DataFrame({
            "station_id": [STATION, STATION],
            "event_timestamp": [
                EVENT_TIME - pd.Timedelta(minutes=1),
                EVENT_TIME + pd.Timedelta(minutes=31),
            ],
        }),
        features=references,
    ).to_df()

    assert len(result) == 2
    assert result[FEAST_FEATURE_COLUMNS].isna().all().all()