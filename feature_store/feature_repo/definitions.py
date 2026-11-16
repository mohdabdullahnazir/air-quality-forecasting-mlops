from datetime import timedelta

from feast import (
    Entity,
    FeatureService,
    FeatureView,
    Field,
    FileSource,
    Project,
)
from feast.types import Float64
from feast.value_type import ValueType

from src.features.export_feast import (
    FEATURE_FILE,
    FEAST_FEATURE_COLUMNS,
)


project = Project(
    name="air_quality",
    description="One-hour-ahead PM2.5 forecasting.",
)

station = Entity(
    name="station",
    join_keys=["station_id"],
    value_type=ValueType.STRING,
    description="Air-quality monitoring station identifier.",
)

hourly_source = FileSource(
    name="air_quality_hourly_source",
    path=FEATURE_FILE.as_posix(),
    timestamp_field="event_timestamp",
    description="Historical hourly features from the UCI dataset.",
)

hourly_features = FeatureView(
    name="air_quality_hourly",
    entities=[station],
    ttl=timedelta(minutes=30),
    schema=[
        Field(name=column, dtype=Float64)
        for column in FEAST_FEATURE_COLUMNS
    ],
    source=hourly_source,
    online=True,
    tags={
        "owner": "student1",
        "station": "Aotizhongxin",
        "forecast_horizon": "1_hour",
    },
)

pm25_service = FeatureService(
    name="pm25_forecasting_v1",
    features=[hourly_features],
)