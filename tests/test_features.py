import numpy as np
import pandas as pd
import pytest

from src.features.engineering import FEATURE_COLUMNS, create_features
from src.features.preprocessing import (
    create_forecast_target,
    split_by_target_time,
)


@pytest.fixture
def hourly_data():
    """Create 72 known hourly records spanning a split boundary."""
    df = pd.DataFrame({
        "timestamp": pd.date_range(
            "2015-02-28", periods=72, freq="h"
        ),
        "station": ["Aotizhongxin"] * 72,
        "PM2.5": np.arange(1, 73, dtype=float),
    })

    fixed_values = {
        "PM10": 20.0,
        "SO2": 5.0,
        "NO2": 10.0,
        "CO": 300.0,
        "O3": 40.0,
        "TEMP": 15.0,
        "PRES": 1013.0,
        "DEWP": 5.0,
        "RAIN": 0.0,
        "wd": "N",
        "WSPM": 2.0,
    }

    for column, value in fixed_values.items():
        df[column] = value

    return df


def test_lags_and_rolling_mean(hourly_data):
    features = create_features(hourly_data)

    # At row 24, current PM2.5 is 25.
    assert features.loc[24, "pm25_lag_1h"] == 24.0
    assert features.loc[24, "pm25_lag_24h"] == 1.0

    # Current and previous two values are 25, 24, and 23.
    assert features.loc[24, "pm25_mean_3h"] == pytest.approx(24.0)

    assert pd.isna(features.loc[0, "pm25_lag_1h"])


def test_future_readings_do_not_change_past_features(hourly_data):
    before = create_features(hourly_data)

    changed = hourly_data.copy()
    changed.loc[31:, "PM2.5"] = 9999.0
    after = create_features(changed)

    pd.testing.assert_series_equal(
        before.loc[30, FEATURE_COLUMNS],
        after.loc[30, FEATURE_COLUMNS],
    )


def test_missing_history_is_not_filled(hourly_data):
    hourly_data.loc[10, "PM2.5"] = np.nan
    features = create_features(hourly_data)

    assert len(features) == len(hourly_data)
    assert pd.isna(features.loc[11, "pm25_lag_1h"])
    assert pd.isna(features.loc[12, "pm25_mean_3h"])

    forecast = create_forecast_target(features)
    assert pd.isna(forecast.loc[9, "target_pm25"])


def test_target_alignment(hourly_data):
    forecast = create_forecast_target(hourly_data)

    assert forecast.loc[0, "target_pm25"] == 2.0
    assert forecast.loc[0, "target_timestamp"] == pd.Timestamp(
        "2015-02-28 01:00:00"
    )
    assert pd.isna(forecast.iloc[-1]["target_pm25"])
    assert "target_pm25" not in FEATURE_COLUMNS
    assert "target_timestamp" not in FEATURE_COLUMNS


def test_split_boundaries_use_target_time(hourly_data):
    forecast = create_forecast_target(hourly_data)
    train, validation, _ = split_by_target_time(forecast)

    assert train["target_timestamp"].max() == pd.Timestamp(
        "2015-02-28 23:00:00"
    )
    assert validation["target_timestamp"].min() == pd.Timestamp(
        "2015-03-01 00:00:00"
    )

    later_data = hourly_data.copy()
    later_data["timestamp"] = pd.date_range(
        "2016-02-29", periods=72, freq="h"
    )

    later_forecast = create_forecast_target(later_data)
    _, validation, test = split_by_target_time(later_forecast)

    assert validation["target_timestamp"].max() < (
        test["target_timestamp"].min()
    )
    assert test["target_timestamp"].min() == pd.Timestamp(
        "2016-03-01 00:00:00"
    )