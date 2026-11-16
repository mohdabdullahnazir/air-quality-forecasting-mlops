import numpy as np
import pandas as pd

from src.features.engineering import FEATURE_COLUMNS
from src.features.export_feast import (
    FEAST_FEATURE_COLUMNS,
    FEAST_RENAME,
)


def validate_online_features(
    frame,
    station_id,
    now=None,
    max_age_minutes=30,
):
    """Validate one station's online features and return model-ready inputs."""
    timestamp_columns = [
        f"{column}__ts"
        for column in FEAST_FEATURE_COLUMNS
    ]

    required = (
        ["station_id"]
        + FEAST_FEATURE_COLUMNS
        + timestamp_columns
    )

    if len(frame) != 1 or not set(required).issubset(frame.columns):
        raise ValueError("Invalid online feature schema.")

    if frame["station_id"].iloc[0] != station_id:
        raise ValueError("Unexpected station identifier.")

    values = frame[FEAST_FEATURE_COLUMNS].to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise ValueError("Missing or non-finite online feature values.")

    timestamps = frame[timestamp_columns].iloc[0].to_numpy(dtype=float)

    if not np.isfinite(timestamps).all() or (timestamps <= 0).any():
        raise ValueError("Missing feature timestamps.")

    if not np.all(timestamps == timestamps[0]):
        raise ValueError("Features have inconsistent timestamps.")

    feature_time = pd.to_datetime(
        timestamps[0],
        unit="s",
        utc=True,
    )

    reference_time = (
        pd.Timestamp.now(tz="UTC")
        if now is None
        else pd.Timestamp(now)
    )

    if reference_time.tzinfo is None:
        raise ValueError("Reference time must include a timezone.")

    age_seconds = (reference_time - feature_time).total_seconds()

    if age_seconds < 0:
        raise ValueError("Feature timestamp is in the future.")

    if age_seconds > max_age_minutes * 60:
        raise ValueError("Online features are stale.")

    reverse_names = {
        feast_name: original_name
        for original_name, feast_name in FEAST_RENAME.items()
    }

    model_inputs = (
        frame[FEAST_FEATURE_COLUMNS]
        .rename(columns=reverse_names)
        .loc[:, FEATURE_COLUMNS]
        .astype("float64")
        .reset_index(drop=True)
    )

    non_negative = ["PM2.5", "RAIN", "WSPM"] + [
        column
        for column in FEATURE_COLUMNS
        if column.startswith("pm25_")
    ]

    if (model_inputs[non_negative] < 0).any().any():
        raise ValueError("Negative pollution, rainfall, or wind values.")

    if (model_inputs["PRES"] <= 0).any():
        raise ValueError("Pressure must be positive.")

    cyclic_columns = [
        column
        for column in FEATURE_COLUMNS
        if column.endswith(("_sin", "_cos"))
    ]

    if (model_inputs[cyclic_columns].abs() > 1 + 1e-9).any().any():
        raise ValueError("Invalid cyclic feature values.")

    return model_inputs, feature_time