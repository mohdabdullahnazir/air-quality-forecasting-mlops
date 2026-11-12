import pandas as pd
import pytest

from feature_store.validation import validate_online_features
from src.features.engineering import FEATURE_COLUMNS
from src.features.export_feast import FEAST_FEATURE_COLUMNS


STATION = "Aotizhongxin"
EVENT_TIME = pd.Timestamp("2016-02-29 14:00:00", tz="UTC")


def make_online_frame():
    data = {"station_id": [STATION]}

    for column in FEAST_FEATURE_COLUMNS:
        data[column] = [0.0]
        data[f"{column}__ts"] = [int(EVENT_TIME.timestamp())]

    data["pm25_current"] = [25.0]
    data["PRES"] = [1013.0]

    return pd.DataFrame(data)


def test_accepts_fresh_features_in_model_column_order():
    inputs, feature_time = validate_online_features(
        make_online_frame(),
        STATION,
        now=EVENT_TIME,
    )

    assert inputs.columns.tolist() == FEATURE_COLUMNS
    assert inputs["PM2.5"].iloc[0] == 25.0
    assert feature_time == EVENT_TIME


@pytest.mark.parametrize(
    "scenario",
    [
        "null",
        "infinite",
        "negative",
        "stale",
        "future",
        "mixed_timestamps",
        "missing_column",
        "wrong_station",
    ],
)
def test_rejects_invalid_online_features(scenario):
    frame = make_online_frame()
    reference_time = EVENT_TIME

    if scenario == "null":
        frame.loc[0, "TEMP"] = float("nan")
    elif scenario == "infinite":
        frame.loc[0, "TEMP"] = float("inf")
    elif scenario == "negative":
        frame.loc[0, "pm25_current"] = -1.0
    elif scenario == "stale":
        reference_time += pd.Timedelta(hours=2)
    elif scenario == "future":
        reference_time -= pd.Timedelta(minutes=1)
    elif scenario == "mixed_timestamps":
        frame.loc[0, "TEMP__ts"] -= 3600
    elif scenario == "missing_column":
        frame = frame.drop(columns="TEMP")
    elif scenario == "wrong_station":
        frame.loc[0, "station_id"] = "another_station"

    with pytest.raises(ValueError):
        validate_online_features(
            frame,
            STATION,
            now=reference_time,
        )