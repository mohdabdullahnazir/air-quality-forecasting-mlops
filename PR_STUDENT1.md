## Problem and resulting behavior

Add the data and ML foundation for one-hour-ahead Aotizhongxin PM2.5 forecasting. The workflow validates hourly measurements, creates causal features, retrieves them through Feast, tracks matched candidate experiments, blocks failing candidates, and registers the exact frozen model after final evaluation.

## Main changes

- Modular ingestion, validation, target construction, chronological splits, and 19 features.
- DVC/DagsHub raw and generated-feature versions.
- Feast definitions, DuckDB historical retrieval, SQLite materialization, and explicit online freshness checks.
- Persistence, Random Forest, and XGBoost parameter comparisons in MLflow.
- Validation gate with a demonstrated nonzero failure exit.
- Frozen final evaluation and registry version 1 with verified predictions.
- Recovery transcript, feature contract, technical report, and team handoff documentation.

## Observed validation

- Ingestion validates 35,064 hourly records with 925 missing PM2.5 values.
- 40 tests passed, including real Feast materialization and offline/online agreement.
- XGBoost 1-only gate rejects the candidate with exit code 1.
- Random Forest 1 has validation MAE 9.541573 / RMSE 19.214800.
- Final test: 7,324 of 8,760 hours scored (83.61%); MAE 10.278413 / RMSE 18.737643 versus persistence 10.459721 / 19.591246.
- Pinned registry URI: models:/air-quality-pm25-aotizhongxin/1.
- Recovery data hashes and ingestion match the training snapshot; recovered_commit.txt confirms the exact historical training commit.

## Limitations and review focus

- Complete-case coverage excludes unavailable feature/label hours.
- Historical Beijing data and replay clocks do not establish current pollution conditions.
- DuckDB 1.5.6 is the demonstrated materialization-compatible version.
- approval_status=pending_review and deployment_approved=false.
- Airflow/Kubeflow, CI/CD enforcement, Flask/BentoML, AWS, Kubernetes, monitoring, and promotion/rollback remain team integration work.
- Review feature time alignment, missingness handling, model/data lineage, secret exclusion, and the reproduction instructions.

Please record an actual teammate review and any changes requested. Do not treat this PR description as evidence that a review already happened.
