import pandas as pd


def validate_station_data(df):
    """Check the minimum structure and hourly timeline."""
    required_columns = [
        "timestamp", "station",
        "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
        "TEMP", "PRES", "DEWP", "RAIN", "wd", "WSPM",
    ]

    if df.empty:
        raise ValueError("The dataset is empty.")

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(f"Required columns are missing: {missing_columns}")

    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        raise ValueError("The timestamp column must contain datetimes.")

    if df["timestamp"].isna().any():
        raise ValueError("The dataset contains missing timestamps.")

    if df["station"].isna().any() or df["station"].nunique() != 1:
        raise ValueError("The dataset must contain exactly one station.")

    if df["timestamp"].duplicated().any():
        raise ValueError("The dataset contains duplicate timestamps.")

    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError("The dataset is not in chronological order.")

    time_steps = df["timestamp"].diff().dropna()

    if not time_steps.eq(pd.Timedelta(hours=1)).all():
        raise ValueError("The timeline must have exactly one row per hour.")