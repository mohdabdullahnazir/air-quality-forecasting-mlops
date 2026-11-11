# Student 1 Technical Report

Prepared from observed execution results through 12 November 2026. This document distinguishes completed Student 1 work from remaining team requirements.

## 1. Problem and scope

Forecast PM2.5 one hour ahead at Aotizhongxin, Beijing. The intended complete product combines forecasts with configurable pollution-threshold alerts and operational monitoring. The implemented ML component uses historical measurements; live data collection and alerts are not yet demonstrated.

The initial scope is one station, one pollutant, and a one-hour horizon. The model is not validated for other cities, present-day conditions, or health decisions.

## 2. Data and quality assessment

The project uses the [UCI Beijing Multi-Site Air Quality dataset](https://archive.ics.uci.edu/dataset/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata), with attribution in README.md.

| Check | Observed result |
| --- | --- |
| Raw shape | 35,064 rows, 18 original columns |
| Loaded shape after timestamp construction | 35,064 rows, 19 columns |
| Original station period | 2013-03-01 00:00 through 2017-02-28 23:00 |
| Station | Aotizhongxin |
| Invalid or duplicate timestamps | None observed |
| Missing hourly rows | None observed |
| Missing PM2.5 values | 925, approximately 2.64% |
| Longest consecutive PM2.5 gap | 343 hours |
| Maximum observed PM2.5 | 898 micrograms/m3 |

Observed long PM2.5 gaps:

| Start | End | Missing hours |
| --- | --- | ---: |
| 2014-04-26 17:00 | 2014-04-29 08:00 | 64 |
| 2014-12-17 10:00 | 2014-12-31 16:00 | 343 |
| 2015-08-02 17:00 | 2015-08-03 16:00 | 24 |
| 2016-04-09 14:00 | 2016-04-10 17:00 | 28 |
| 2016-07-25 17:00 | 2016-07-26 17:00 | 25 |

The validator enforces required columns; datetime timestamps; one expected station; chronological, nonduplicated hourly rows; numeric measurement columns without infinities; nonnegative pollutants/rain/wind; positive pressure; and valid compass directions. Negative temperature and dew point are accepted. Missing measurements are allowed so the hourly timeline remains intact.

Large pollution readings were retained rather than clipped solely because they were extreme. Missing labels were never imputed. Complete-case selection occurs after lag/rolling construction.

## 3. Target and chronological split

At origin t, the target is the observed PM2.5 value at t+1 hour. The last row has no recorded following-hour target. Together with missing next-hour measurements, 926 rows have unavailable targets.

Splitting uses target time, not random shuffling:

| Split | Target-time interval | Total rows | Observed targets | Complete features and observed target |
| --- | --- | ---: | ---: | ---: |
| Training | Before 2015-03-01 | 17,519 | 16,989 | 15,461 |
| Validation | 2015-03-01 through 2016-02-29 | 8,784 | 8,568 | 7,113 |
| Test | 2016-03-01 through 2017-02-28 | 8,760 | 8,581 | 7,324 |

Feature histories may cross a split boundary when those observations would already be available at the forecast origin. Future values and targets are not used as inputs.

Validation coverage is 80.98%; test coverage is 83.61%. Excluded hours may be systematically different, so complete-case performance does not quantify performance during long sensor outages.

## 4. Features and Feast

The model consumes 19 features: current PM2.5; five weather measurements; four PM2.5 lags; three rolling means; and six cyclical calendar encodings. See docs/FEATURES.md for order, formulas, mapping, and time semantics.

Feast 0.67.0 defines a station entity, FileSource, FeatureView, and versioned feature service. The offline artifact is Parquet, queried through DuckDB. The development online store is SQLite. Source data is tracked with DVC and definitions with Git.

Historical retrieval was verified against direct feature engineering across all 35,064 rows, including null locations. It yielded 30,043 complete feature vectors before filtering missing targets.

The online demonstration materialized the snapshot at 2016-02-29 14:00 UTC. Online inputs matched historical retrieval. Tests rejected stale features, unknown stations, and use of this historical snapshot against the real clock. The demonstration is a controlled historical replay.

The 30-minute FeatureView TTL controls historical lookup. SQLite does not enforce retrieval-time expiry, so feature_store.validation explicitly checks the returned feature timestamps.

## 5. Experiments and selection

The matched persistence baseline predicts next-hour PM2.5 using current PM2.5. All candidate comparisons use the same 7,113 eligible validation rows.

| Configuration | Main settings | MAE | RMSE | Negative predictions |
| --- | --- | ---: | ---: | ---: |
| Persistence | Current value | 9.724589 | 19.789574 | 0 |
| Random Forest 1 | 150 trees, depth 12, leaf minimum 3 | 9.541573 | 19.214800 | 0 |
| Random Forest 2 | 250 trees, depth 18, leaf minimum 5 | 9.572705 | 19.215204 | 0 |
| XGBoost 1 | 400 trees, depth 3, rate 0.05, squared-error objective | 9.800157 | 20.313252 | 6 |
| XGBoost 2 | 400 trees, depth 3, rate 0.05, absolute-error objective | 9.693698 | 21.218986 | 0 |

Random Forest 1 had the lowest validation MAE, marginally lower RMSE than Random Forest 2, and fewer trees. Both XGBoost configurations failed at least one mandatory comparison check. This selection is based on the tested configurations; no claim is made that one algorithm always wins.

Runs log hyperparameters, duration, training/validation metrics, coverage, predictions, plots, dependency snapshot, feature schema/definitions, Git commit, and both raw/feature DVC identifiers.

## 6. Evaluation policy and test result

Policy established after exploratory validation and frozen before final-test evaluation:

- MAE no greater than 12 micrograms/m3.
- RMSE no greater than 25 micrograms/m3.
- Strict MAE improvement over matched persistence.
- RMSE no worse than matched persistence.
- Zero negative predictions.
- At least 80% coverage. The configuration key is named min_validation_coverage; the frozen evaluator applies that same minimum to test coverage.

These are engineering acceptance criteria for the course demonstration, not health-advisory thresholds. They were not specified numerically by the course PDF.

An XGBoost 1-only gate execution failed with exit code 1. The full validation gate selected Random Forest 1. Source-code/data lineage and validation row counts are checked before candidate comparison.

The selected saved estimator was evaluated without refitting on the final period:

| Metric | Random Forest 1 | Matched persistence |
| --- | ---: | ---: |
| MAE | 10.278412957357128 | 10.45972146368105 |
| RMSE | 18.73764304246239 | 19.591245578867944 |
| R2 | 0.9530736318784214 | 0.9487007379370034 |
| Negative predictions | 0 | 0 |

7,324 of 8,760 hours were scored. Both absolute and relative gates passed. MAE improved by approximately 1.7%, and RMSE by approximately 4.4%. Gains are modest; confidence intervals and statistical significance were not estimated.

The final evaluator freezes candidate/policy information and reuses the local report on subsequent calls. This helps avoid accidental repeated test scoring; it is not a tamper-proof holdout service.

## 7. Model management

- Registered model: air-quality-pm25-aotizhongxin, version 1.
- URI: models:/air-quality-pm25-aotizhongxin/1.
- Source model: models:/m-6b15549cc70d409c92ea7850b7577a71.
- Source training run: 8bb90ba8cf9c489986f5bd49813fd8fd.
- Source training commit: 7725c299b0cc2cb621967617d4126997f69eafd6.
- Final evaluation run: edbe53c2a1b647489feb7d5843a00dc7.
- Latest demonstrated validation gate run: fd24e8ed1c23472cafb64f82ebca9eec.

Registered-model predictions matched the training run's saved validation predictions. The registry tags retain approval_status=pending_review and deployment_approved=false. A registry version is available for integration; a deployment review and enforcement mechanism still require team work.

Random Forest artifacts use skops serialization with the specific trusted tree type recorded during logging. XGBoost artifacts use native UBJ. Load the team's own pinned artifacts using compatible dependencies; do not broadly disable model-loading protections.

## 8. Reproducibility and evidence

| Artifact | MD5 | Recorded size |
| --- | --- | ---: |
| Station CSV | 72a306d7a095e718c2b46ab482d5a1ac | 2,835,916 bytes |
| Feature Parquet | 1904355bbc9682150d269d9060c6118a | 911,095 bytes |

The separate recovery checkout was configured to restore the training commit. User-provided output confirms DVC data are up to date, both pointers match the identifiers above, and recovered ingestion validates 35,064 rows with 925 missing PM2.5 values.

The recovery log is committed as e3d80e4 in reports/reproducibility/recovery_demo.txt. Record the exact recovered HEAD separately as described in docs/REPRODUCIBILITY.md; the last shared output excerpt did not include its commit line.

The recovery exercise used the current tested environment, Python 3.11.17 and DuckDB 1.5.6. It demonstrates code/data recovery rather than an isolated recreation of every old package version.

## 9. Testing and resolved integration issues

Latest observed result: 40 tests passed, three dependency deprecation warnings, in 26.40 seconds.

Tests cover timeline/schema rules, measurement values, causal features, target/split correctness, serialization round trips, quality-gate regressions, local-time/label preservation, online schema/value/freshness checks, real Feast materialization, offline/online agreement, and future/expired historical lookup.

Key resolved issues:

| Issue | Resolution |
| --- | --- |
| Tkinter thread crash during plotting | Explicit FigureCanvasAgg / noninteractive plotting |
| AWS dependency mismatch | Compatible boto3 and botocore versions recorded in requirements |
| Feast query changed timestamp timezone handling | Keep original labels/local times outside query and merge retrieved features by station/UTC time |
| Large default file-reader join risk | Use Feast DuckDB offline reader for Parquet |
| DuckDB 2.0 materialization cast failure | Tested DuckDB 1.5.6 pin; real integration test now covers materialization |

No claim is made that these tests have already run in GitHub Actions; Student 2 must add that execution evidence.

## 10. Risks, ethics, and limitations

| Risk | Evidence or implication | Mitigation / owner |
| --- | --- | --- |
| Historical/geographic mismatch | One Beijing station, 2013-2017, not present-day other-city measurements | Label scope; obtain approved fresh data and revalidate before live use; shared |
| Missingness and outage bias | Long gaps and only 83.61% final test coverage | Report coverage; reject incomplete/stale inputs; monitor availability; Student 1/3 |
| Late or delayed observations | Arrival timestamps are unavailable in the source | Treat immediate availability as an assumption; add actual arrival metadata in ingestion; Student 2 |
| Distribution change | Weather, emissions, seasonality and sensors can change | Monitor inputs and delayed errors; scheduled/conditional retraining; shared |
| Secret exposure | Remote storage/tracking and AWS need credentials | Ignored local config, CI secrets/IAM, token rotation when exposed; shared |
| Alert misinterpretation | A one-hour concentration prediction is not an official AQI or health assessment | Explicit demo threshold/units; retain historical labels and limitations; Student 3 |

Missing records can disproportionately remove severe events or outages. This representativeness risk remains even with strong aggregate R2. No demographic fairness claim can be assessed from the available station-level data.

## 11. Individual contribution and remaining team work

Student 1, GitHub account mohdabdullahnazir, completed dataset selection, exploration, modular ingestion/validation, causal features, target/split logic, baselines and parameter search, DVC/DagsHub data versioning, Feast offline/online demonstrations, MLflow tracking, evaluation gates, final holdout evaluation, registry loading verification, and recovery evidence. The documentation pack records this work and its limitations.

Student 2 owns primary implementation of DVC pipeline integration, Airflow scheduling and Kubeflow triggering, reusable orchestration components, CI checks/security scanning, gate enforcement, and automation evidence.

Student 3 owns primary implementation of Flask, BentoML demonstration, serving validation, containers/Compose, AWS, Kubernetes, Prometheus/Grafana, CloudWatch, prediction/pollution alerts, and operational evidence.

Review, integration, model approval, retraining comparisons, and rollback require collaboration. These are responsibilities, not isolated knowledge areas.

### Remaining acceptance evidence

- Actual PR review and merge records.
- GitHub Actions execution showing passing and blocked workflows.
- Airflow triggering a demonstrated Kubeflow run with retries and conditional execution.
- Required Flask API and BentoML demonstration, with integration/API tests.
- Docker/Compose, AWS hosting, Kubernetes scaling/restart proof.
- Monitoring dashboard, alert, drift/retraining scenario, controlled promotion and rollback.
- Implemented access controls, secret handling, and security scans.
- Final team architecture/report and oral-defense evidence.

The Student 1 logs do not establish completion of these team deliverables.
