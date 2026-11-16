# Feature Catalogue and Prediction Contract

Owner: Student 1, GitHub mohdabdullahnazir. Model: one-hour-ahead Aotizhongxin PM2.5 regression. This contract documents the implemented transformations and the interface required by serving.

## Entity and time semantics

- Entity: station, with join key station_id.
- Supported station in this implementation: Aotizhongxin.
- Forecast origin: timestamp t in the original Beijing local clock.
- Forecast target time: t plus one hour.
- Feast event_timestamp: t localized to Asia/Shanghai and converted to UTC.
- Timezone interpretation is a project assumption; raw files have no explicit timezone/arrival field.
- Query historical features at t, never at the target time.
- Future labels and original local timestamps remain outside the Feast query.
- Observations at t are assumed available when the forecast is made. A live ingestion system must account for real publication delays.

## Exact model feature order

All 19 model inputs are floating-point numeric values.

| Position | Model name | Feast name | Meaning / units |
| ---: | --- | --- | --- |
| 1 | PM2.5 | pm25_current | Current measured concentration, micrograms/m3 |
| 2 | TEMP | TEMP | Current temperature, degrees Celsius |
| 3 | PRES | PRES | Current pressure, hPa |
| 4 | DEWP | DEWP | Current dew-point temperature, degrees Celsius |
| 5 | RAIN | RAIN | Recorded precipitation, mm |
| 6 | WSPM | WSPM | Wind speed, m/s |
| 7 | pm25_lag_1h | pm25_lag_1h | PM2.5 at t-1 hour |
| 8 | pm25_lag_3h | pm25_lag_3h | PM2.5 at t-3 hours |
| 9 | pm25_lag_6h | pm25_lag_6h | PM2.5 at t-6 hours |
| 10 | pm25_lag_24h | pm25_lag_24h | PM2.5 at t-24 hours |
| 11 | pm25_mean_3h | pm25_mean_3h | Mean over t-2 through t |
| 12 | pm25_mean_6h | pm25_mean_6h | Mean over t-5 through t |
| 13 | pm25_mean_24h | pm25_mean_24h | Mean over t-23 through t |
| 14 | hour_sin | hour_sin | sin(2*pi*local_hour/24) |
| 15 | hour_cos | hour_cos | cos(2*pi*local_hour/24) |
| 16 | weekday_sin | weekday_sin | sin(2*pi*weekday/7), Monday=0 |
| 17 | weekday_cos | weekday_cos | cos(2*pi*weekday/7), Monday=0 |
| 18 | month_sin | month_sin | sin(2*pi*(month-1)/12) |
| 19 | month_cos | month_cos | cos(2*pi*(month-1)/12) |

The current recorded pollution/weather values are predictors. The next-hour observation target_pm25 is a label, never an input. Other raw pollutants, wind direction, row number, and station name are not among the fitted estimator's 19 input columns.

## Transformation and missing-data rules

Preserve the hourly grid before applying shifts. Lag k uses shift(k) on the validated chronological series. A rolling mean of width k requires all k observations and includes the current row. Do not drop missing rows before calculating lags, because that would change the meaning of an hour.

No backward fill, future interpolation, or target imputation is used. Feature export retains missing values; model training/evaluation uses rows with all 19 features and an observed following-hour target. Serving rejects incomplete feature vectors.

## Feast definitions

| Object | Value |
| --- | --- |
| Repository configuration | feature_store/feature_repo/feature_store.yaml |
| Definitions | feature_store/feature_repo/definitions.py |
| Feature source | data/processed/hourly_features.parquet |
| Feature view | air_quality_hourly |
| Feature service | pm25_forecasting_v1 |
| Offline query engine | DuckDB 1.5.6, reading Parquet |
| Development online store | SQLite |
| Historical lookup TTL | 30 minutes relative to each requested origin |
| Feature Git version for model 1 | 7725c299b0cc2cb621967617d4126997f69eafd6 |
| Feature-data DVC MD5 | 1904355bbc9682150d269d9060c6118a |

The local registry and SQLite files are generated state and ignored by Git. Regenerate them after pulling data and reapplying definitions on another checkout. The feature source's absolute path is derived from the checkout location; do not copy an old registry unchanged to another machine.

## Freshness and serving validation

The SQLite backend does not automatically expire retrieved values. Use feature_store.validation.validate_online_features:

1. Require one station row and the complete expected feature/timestamp schema.
2. Verify the returned station equals the requested station.
3. Reject null, nonnumeric, or nonfinite feature values.
4. Require positive, consistent per-feature event timestamps.
5. Reject future features and ages over 30 minutes.
6. Restore the PM2.5 model-column name and exact model input order.
7. Reject negative pollution/lag/rolling/rain/wind values, nonpositive pressure, and cyclic values outside [-1,1] within numeric tolerance.

The helper's default reference time is the actual current UTC time. Its explicit now argument supports controlled testing/replay. A production endpoint must not let arbitrary requests select a trusted server clock to bypass stale-data checks.

The online replay uses source time 2016-02-29 14:00 UTC, equivalent to 22:00 Beijing time. It proves retrieval/freshness behavior under a replay clock and separately proves that this source is stale against the actual clock. It does not establish present-day freshness.

## Model and API handoff

Pinned URI: models:/air-quality-pm25-aotizhongxin/1.

Use reports/models/registry_candidate.json for lineage/status and reports/models/prediction_example.json for five real validation examples and their expected predictions. These JSON files are available in Git and attached under registry in the final evaluation MLflow run.

A model-input example is not automatically a Flask request contract. Student 3 must define and test the HTTP wrapper. Two proposed serving modes should remain explicit:

- Station lookup: the server fetches Feast values and validates event time/freshness using its trusted clock.
- Historical replay or batch example: accepts/derives a documented historical feature vector, labels the response as historical, and reports its origin/target time.

If a direct-feature endpoint is allowed, validate all names, order/types, finiteness, value bounds, station, and provenance. Nineteen plausible numbers alone do not prove that lag features were calculated correctly. Prefer server-side retrieval/transformation where feasible.

For each response include model name/version, station, forecast origin, target time, horizon_hours=1, predicted_pm25, concentration units, serving mode, and feature freshness metadata.

The existing estimator is trained from historical data. The team may serve a clearly labelled historical demonstration while building a fresh-data path. Do not present historical predictions as current pollution alerts.

## Alert contract to implement

Use a versioned configurable concentration threshold and emit threshold_exceeded when the predicted concentration crosses it. Record the threshold, units, model version, and forecast target time in the alert event.

The model does not predict AQI or an official risk class. Any real health-standard/AQI mapping requires a separately sourced, correctly averaged and documented rule. A course demonstration threshold should be labelled as such.

## Official references

- [Feast quickstart](https://docs.feast.dev/getting-started/quickstart)
- [Point-in-time retrieval and TTL](https://docs.feast.dev/getting-started/concepts/point-in-time-joins)
- [SQLite backend and its TTL limitations](https://docs.feast.dev/reference/online-stores/sqlite)
- [DuckDB offline store](https://docs.feast.dev/reference/offline-stores/duckdb)
- [MLflow model registry](https://mlflow.org/docs/latest/model-registry)
