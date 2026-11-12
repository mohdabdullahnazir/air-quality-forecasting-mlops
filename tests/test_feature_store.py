from types import SimpleNamespace

import pandas as pd

from feature_store import historical
from src.features.export_feast import FEAST_FEATURE_COLUMNS


def test_retrieval_preserves_local_times_labels_and_row_alignment(monkeypatch):
    raw = pd.DataFrame({
        "timestamp": pd.date_range("2013-03-01", periods=3, freq="h"),
        "station": ["Aotizhongxin"] * 3,
    })

    for column in [
        "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
        "TEMP", "PRES", "DEWP", "RAIN", "WSPM",
    ]:
        raw[column] = 1.0

    raw["PM2.5"] = [4.0, 8.0, 7.0]
    raw["wd"] = "N"

    class FakeStore:
        def __init__(self, repo_path):
            pass

        def get_feature_service(self, name):
            return name

        def get_historical_features(
            self, entity_df, features, full_feature_names
        ):
            # Labels and local timestamps must stay outside the query.
            assert set(entity_df.columns) == {
                "station_id", "event_timestamp"
            }
            assert entity_df["event_timestamp"].iloc[0] == pd.Timestamp(
                "2013-02-28 16:00:00", tz="UTC"
            )

            data = entity_df.copy()
            for column in FEAST_FEATURE_COLUMNS:
                data[column] = 1.0

            data["pm25_current"] = [4.0, 8.0, 7.0]

            # Simulate Feast returning rows in a different order.
            data = data.iloc[::-1].reset_index(drop=True)
            return SimpleNamespace(to_df=lambda: data)

    monkeypatch.setattr(historical, "FeatureStore", FakeStore)

    result = historical.load_forecast_from_store(raw)

    assert result["timestamp"].dt.tz is None
    assert result["target_timestamp"].dt.tz is None
    assert result["PM2.5"].tolist() == [4.0, 8.0, 7.0]

    pd.testing.assert_series_equal(result["timestamp"], raw["timestamp"])

    expected_target_times = raw["timestamp"] + pd.Timedelta(hours=1)
    pd.testing.assert_series_equal(
        result["target_timestamp"],
        expected_target_times.rename("target_timestamp"),
    )

    assert result["target_pm25"].iloc[:2].tolist() == [8.0, 7.0]
    assert pd.isna(result["target_pm25"].iloc[2])