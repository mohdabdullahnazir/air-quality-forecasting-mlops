import pandas as pd


def validate_station_data(df):
    """Validate station schema, hourly timeline, and measurement values."""
    required_columns = [
        "timestamp", "station",
        "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
        "TEMP", "PRES", "DEWP", "RAIN", "wd", "WSPM",
    ]

    if df.empty:
        raise ValueError("The dataset is empty.")

    missing_columns = [
        column
        for column in required_columns
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

    numeric_columns = [
        "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
        "TEMP", "PRES", "DEWP", "RAIN", "WSPM",
    ]

    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise ValueError(f"{column} must contain numeric measurements.")

        if df[column].isin([float("inf"), float("-inf")]).any():
            raise ValueError(f"{column} contains infinite measurements.")

    non_negative_columns = [
        "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
        "RAIN", "WSPM",
    ]

    if (df[non_negative_columns] < 0).any().any():
        raise ValueError("Pollution, rainfall, and wind cannot be negative.")

    if (df["PRES"] <= 0).any():
        raise ValueError("Pressure must be positive.")

    valid_directions = {
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW",
    }

    if not df["wd"].dropna().isin(valid_directions).all():
        raise ValueError("Invalid wind direction.")

    if not df["station"].eq("Aotizhongxin").all():
        raise ValueError("Unexpected station for the Aotizhongxin pipeline.")