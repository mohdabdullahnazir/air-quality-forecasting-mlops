from pathlib import Path

import pandas as pd

from src.data.validation import validate_station_data

def load_station_data(file_path):
    """Read a station CSV and construct its timestamps."""
    df = pd.read_csv(file_path)

    df["timestamp"] = pd.to_datetime(
        df[["year", "month", "day", "hour"]],
        errors="raise",
    )

    return df.sort_values("timestamp").reset_index(drop=True)


# Run this section when the module is executed directly.
if __name__ == "__main__":
    project_folder = Path(__file__).resolve().parents[2]

    data_file = (
        project_folder
        / "data"
        / "raw"
        / "PRSA_Data_Aotizhongxin_20130301-20170228.csv"
    )

    station_data = load_station_data(data_file)
    
    validate_station_data(station_data)
    print("Validation passed.")

    print("Loaded shape:", station_data.shape)
    print("Missing PM2.5 readings:", station_data["PM2.5"].isna().sum())
    print(station_data[["timestamp", "PM2.5", "station"]].head())