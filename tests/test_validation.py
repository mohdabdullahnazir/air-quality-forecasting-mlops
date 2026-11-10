import pandas as pd
import pytest

from src.data.validation import validate_station_data


@pytest.fixture
def sample_data():
    """Create three example hourly records for testing."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=3, freq="h"),
        "station": ["Aotizhongxin"] * 3,
        "PM2.5": [10.0, 11.0, 12.0],
        "PM10": [20.0, 21.0, 22.0],
        "SO2": [5.0] * 3,
        "NO2": [10.0] * 3,
        "CO": [300.0] * 3,
        "O3": [40.0] * 3,
        "TEMP": [15.0] * 3,
        "PRES": [1013.0] * 3,
        "DEWP": [5.0] * 3,
        "RAIN": [0.0] * 3,
        "wd": ["N"] * 3,
        "WSPM": [2.0] * 3,
    })


def test_accepts_missing_measurement(sample_data):
    sample_data.loc[1, "PM2.5"] = float("nan")

    validate_station_data(sample_data)


def test_rejects_missing_column(sample_data):
    invalid_data = sample_data.drop(columns=["PM2.5"])

    with pytest.raises(ValueError, match="Required columns"):
        validate_station_data(invalid_data)


def test_rejects_duplicate_timestamp(sample_data):
    invalid_data = pd.concat(
        [sample_data, sample_data.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="duplicate timestamps"):
        validate_station_data(invalid_data)


def test_rejects_missing_hour(sample_data):
    invalid_data = sample_data.drop(index=1)

    with pytest.raises(ValueError, match="exactly one row per hour"):
        validate_station_data(invalid_data)