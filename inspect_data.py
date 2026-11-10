from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

# Find the folder containing this script.
project_folder = Path(__file__).resolve().parent

# Locate our station's original CSV.
data_file = (
    project_folder
    / "data"
    / "raw"
    / "PRSA_Data_Aotizhongxin_20130301-20170228.csv"
)

# Read the CSV into a table.
df = pd.read_csv(data_file)

print("Dataset size (rows, columns):", df.shape)

print("\nColumn names:")
print(df.columns.tolist())

print("\nFirst five rows:")
print(df.head().to_string(index=False))

print("\nMissing values per column:")
print(df.isna().sum())

print("\nStation names:")
print(df["station"].unique())

# Combine the separate date columns into one timestamp.
df["timestamp"] = pd.to_datetime(
    df[["year", "month", "day", "hour"]],
    errors="coerce",
)

print("\n--- TIME CHECKS ---")

print("First timestamp:", df["timestamp"].min())
print("Last timestamp:", df["timestamp"].max())

print("Invalid timestamps:", df["timestamp"].isna().sum())

# Keep valid timestamps for the remaining checks.
valid_times = df["timestamp"].dropna()

print("Duplicate timestamps:", valid_times.duplicated().sum())
print("Already in time order:", valid_times.is_monotonic_increasing)

# Generate every hour between the first and last timestamp.
expected_hours = pd.date_range(
    start=valid_times.min(),
    end=valid_times.max(),
    freq="h",
)

# Find hours that should exist but are absent.
missing_hours = expected_hours.difference(
    pd.DatetimeIndex(valid_times)
)

print("Missing hourly timestamps:", len(missing_hours))

print("\n--- VALUE CHECKS ---")

numeric_columns = [
    "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
    "TEMP", "PRES", "DEWP", "RAIN", "WSPM",
]

# Show the smallest and largest recorded value in each column.
print("\nMinimum and maximum values:")
print(df[numeric_columns].agg(["min", "max"]).T)

# These measurements should not be negative.
non_negative_columns = [
    "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
    "RAIN", "WSPM",
]

print("\nNegative-value counts:")
print((df[non_negative_columns] < 0).sum())

print("\nZero or negative pressure readings:")
print((df["PRES"] <= 0).sum())

print("\nRecorded wind directions:")
print(sorted(df["wd"].dropna().unique()))

def longest_missing_gap(column):
    current_gap = 0
    longest_gap = 0

    for is_missing in column.isna():
        if is_missing:
            current_gap += 1
            longest_gap = max(longest_gap, current_gap)
        else:
            current_gap = 0

    return longest_gap


print("\n--- MISSING-DATA GAP CHECKS ---")

columns_to_check = numeric_columns + ["wd"]

missing_summary = pd.DataFrame({
    "missing_count": df[columns_to_check].isna().sum(),
    "missing_percent": (
        df[columns_to_check].isna().mean() * 100
    ).round(2),
    "longest_gap_hours": (
        df[columns_to_check].apply(longest_missing_gap)
    ),
})

print(missing_summary.to_string())

print("\n--- LONG PM2.5 GAPS ---")

# Mark each row where PM2.5 is missing.
pm25_missing = df["PM2.5"].isna()

# Start a new group whenever missing/non-missing status changes.
gap_groups = pm25_missing.ne(pm25_missing.shift()).cumsum()

# Summarise each consecutive block of missing readings.
missing_periods = (
    df.loc[pm25_missing]
    .groupby(gap_groups.loc[pm25_missing])
    .agg(
        start=("timestamp", "min"),
        end=("timestamp", "max"),
        missing_hours=("timestamp", "size"),
    )
)

# Display gaps lasting at least 24 hours.
long_gaps = missing_periods[
    missing_periods["missing_hours"] >= 24
]

print(long_gaps.to_string(index=False))

# Create a folder for charts.
figures_folder = project_folder / "reports" / "figures"
figures_folder.mkdir(parents=True, exist_ok=True)

# Plot the original hourly PM2.5 readings.
fig, ax = plt.subplots(figsize=(12, 4))

ax.plot(
    df["timestamp"],
    df["PM2.5"],
    linewidth=0.5,
    color="steelblue",
)

# Highlight missing periods lasting at least 24 hours.
for gap in long_gaps.itertuples(index=False):
    ax.axvspan(
        gap.start,
        gap.end + pd.Timedelta(hours=1),
        color="orange",
        alpha=0.3,
    )

ax.set_title("Aotizhongxin: hourly PM2.5 and long data gaps")
ax.set_xlabel("Date — original dataset timestamps")
ax.set_ylabel("PM2.5 concentration (µg/m³)")

fig.autofmt_xdate()
fig.tight_layout()

chart_file = figures_folder / "pm25_overview.png"
fig.savefig(chart_file, dpi=150)
plt.close(fig)

print("\nChart saved to:", chart_file)