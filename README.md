# Air Quality Forecasting and Pollution Alert System

Predict the following hour's PM2.5 concentration at the Aotizhongxin station in Beijing. The verified Student 1 implementation covers data validation, causal features, Feast retrieval, training, experiment tracking, evaluation gates, model registration, and code/data recovery.

**Status, 12 November 2026:** the Student 1 ML workflow works locally; 40 tests pass. Model version 1 passed validation and final-test gates and its registry loading check. Deployment approval is pending. Cloud serving, orchestration, CI/CD, monitoring, and pollution alerts still require team implementation and execution evidence.

## Project links

- [GitHub repository](https://github.com/mohdabdullahnazir/air-quality-forecasting-mlops)
- [DagsHub repository](https://dagshub.com/mohdabdullahnazir/air-quality-forecasting-mlops)
- [Hosted MLflow interface](https://dagshub.com/mohdabdullahnazir/air-quality-forecasting-mlops.mlflow/)
- [Dataset and attribution](https://archive.ics.uci.edu/dataset/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata)

## Reproducible model and data identifiers

| Item | Identifier |
| --- | --- |
| Registered model | air-quality-pm25-aotizhongxin |
| Registered version | 1 |
| Pinned serving URI | models:/air-quality-pm25-aotizhongxin/1 |
| Source logged-model URI | models:/m-6b15549cc70d409c92ea7850b7577a71 |
| Training run | 8bb90ba8cf9c489986f5bd49813fd8fd |
| Training commit | 7725c299b0cc2cb621967617d4126997f69eafd6 |
| Final test run | edbe53c2a1b647489feb7d5843a00dc7 |
| Raw CSV MD5 | 72a306d7a095e718c2b46ab482d5a1ac |
| Feature Parquet MD5 | 1904355bbc9682150d269d9060c6118a |
| Feast feature service | pm25_forecasting_v1 |

Registration identifies a model; the current registry tags explicitly retain approval_status=pending_review and deployment_approved=false.

## Local setup

Run commands from the repository root. Until the Student 1 PR is merged, use its branch:

~~~powershell
git clone --branch student1/features https://github.com/mohdabdullahnazir/air-quality-forecasting-mlops.git
Set-Location air-quality-forecasting-mlops
conda create --name air-quality-mlops python=3.11 pip
conda activate air-quality-mlops
python -m pip install -r requirements.txt
python -m pip check
~~~

Run each command after the previous one succeeds. The observed working environment is Windows/PowerShell with Python 3.11.17, Feast 0.67.0, and DuckDB 1.5.6. The repository's requirements.txt is the exact dependency snapshot. Linux/container installation remains a team validation task; do not describe it as already verified.

DuckDB must remain in the tested 1.5 series until the team validates an upgrade. DuckDB 2.0 caused a real nanosecond timezone cast failure during Feast materialization even though dependency resolution succeeded.

### Authenticate DVC locally

The committed DVC remote configuration uses the DagsHub S3-compatible endpoint. Each collaborator needs their own authorized DagsHub token; configure it without adding it to Git:

~~~powershell
$dagshubSecret = Read-Host -Prompt "Enter your DagsHub token privately" -AsSecureString
$dagshubToken = [System.Net.NetworkCredential]::new("", $dagshubSecret).Password
python -m dvc remote modify --local dagshub access_key_id $dagshubToken
python -m dvc remote modify --local dagshub secret_access_key $dagshubToken
Remove-Variable dagshubToken, dagshubSecret
python -m dvc pull -r dagshub
python -m dvc status
~~~

Both credentials use the token for this DagsHub S3-compatible storage. The token belongs in ignored .dvc/config.local. Do not place the token in the Read-Host prompt text. For unattended jobs, Student 2 must supply secrets through the CI/orchestrator secret mechanism.

### Validate and prepare Feast

~~~powershell
python -m src.data.ingestion
python -m feature_store.setup_store
python -m feature_store.historical
python -m pytest tests -q
~~~

Expected results: ingestion validates 35,064 rows; historical retrieval retains 35,064 rows and 30,043 complete feature vectors; usable training and validation counts are 15,461 and 7,113. The verified suite has 40 passing tests.

DVC pull restores the recorded feature artifact. Regenerate it only when deliberately preparing a new version:

~~~powershell
python -m src.features.export_feast
python -m dvc add data/processed/hourly_features.parquet
python -m dvc push -r dagshub
~~~

Commit source/configuration/dependency changes and the new .dvc metadata before logging training experiments. Reapply Feast definitions after relocating the repository because the FileSource path is derived from that local checkout.

## Run the ML workflow

The following commands exist now:

| Command | Purpose and important behavior |
| --- | --- |
| python -m src.data.ingestion | Load raw measurements and enforce schema, time, station, and value checks |
| python -m feature_store.setup_store | Register the local Feast definitions |
| python -m feature_store.historical | Verify historical features, timestamps, labels, and row counts |
| python -m src.models.train | Run the matched persistence baseline and four configured candidates; replaces the local validation comparison CSV |
| python -m src.models.quality_gate | Evaluate that comparison using recorded MLflow metrics and the committed policy |
| python -m src.models.quality_gate --candidate xgboost_1 | Demonstrated rejected candidate, exit code 1 |
| python -m feature_store.online | Materialize a validation-period historical snapshot and verify online/offline agreement, freshness, and missing-station rejection |
| python -m src.models.final_evaluation | Evaluate the frozen candidate on the reserved test period; reuse the existing report on later calls |
| python -m src.models.register_candidate | Register/reuse the exact tested artifact and verify predictions against saved validation predictions |

The tracking helper connects to DagsHub using dagshub.init and sets the MLflow experiment to air-quality-pm25. Interactive authentication may open the DagsHub login flow. Automated credentials must be configured by Student 2.

The final evaluation is already complete. Do not delete its saved report to tune repeatedly against the test period. A future retraining workflow must use a new evaluation protocol and its own output locations.

## Model selection and final results

Random Forest 1 uses 150 trees, max_depth=12, min_samples_leaf=3, random_state=42. It had the lowest validation MAE among the tested candidates.

| Model | Validation MAE | Validation RMSE | Outcome |
| --- | ---: | ---: | --- |
| Random Forest 1 | 9.541573 | 19.214800 | Selected |
| Random Forest 2 | 9.572705 | 19.215204 | Passed; slightly worse MAE, 250 trees |
| XGBoost 1 | 9.800157 | 20.313252 | Failed relative error checks; six negative predictions |
| XGBoost 2 | 9.693698 | 21.218986 | Failed relative RMSE check |
| Persistence | 9.724589 | 19.789574 | Matched-row reference |

| Final test metric | Selected Random Forest | Matched persistence |
| --- | ---: | ---: |
| MAE, micrograms/m3 | 10.278413 | 10.459721 |
| RMSE, micrograms/m3 | 18.737643 | 19.591246 |
| R2 | 0.953074 | 0.948701 |

Final evaluation scored 7,324 of 8,760 test hours: 83.61% coverage. These are errors on eligible complete examples, not a claim about every hour. R2 is not classification accuracy.

## Data and forecasting rules

Use one station from the UCI Beijing Multi-Site dataset. The original station file covers 1 March 2013 through 28 February 2017 with 35,064 hourly rows. It contains 925 missing PM2.5 measurements, including a 343-hour gap.

Keep hourly rows while building lag and rolling features. Do not backward-fill, interpolate from the future, or invent missing targets. The initial model uses complete-case feature vectors and observed next-hour targets. At origin t, only measurements at or before t may become inputs.

Original timestamps are treated as Beijing local time, an explicit project assumption. Feast event timestamps are converted to UTC. Original local forecast and target timestamps stay outside the Feast query and are attached back by station/time keys.

The historical dataset does not contain verified publication/arrival times. The replay assumes recorded hourly measurements are available at their timestamp; real deployment must account for ingestion delays.

## Architecture and remaining ownership

Verified Student 1 path:

~~~text
Raw CSV + DVC metadata
    -> ingestion and validation
    -> causal feature engineering
    -> DVC-versioned Parquet
    -> Feast historical retrieval
    -> chronological train/validation split
    -> persistence + Random Forest/XGBoost experiments
    -> MLflow + validation gate
    -> frozen final evaluation
    -> model registry version 1, pending review

Parquet -> Feast materialization -> SQLite online lookup
        -> schema/null/value/timestamp/freshness checks
~~~

Student 2 must integrate scheduling, DVC pipeline ownership, Airflow triggering Kubeflow, CI quality gates, retraining comparisons, and promotion/rollback automation. Student 3 must implement Flask plus a BentoML demonstration, containers, AWS, Kubernetes, monitoring, and configurable pollution alerts. These shared integrations are not yet demonstrated by the Student 1 terminal logs.

## Documentation and evidence

- [Student 1 report and contribution](REPORT.md)
- [Feature catalogue and serving contract](docs/FEATURES.md)
- [Code/data recovery procedure and evidence](docs/REPRODUCIBILITY.md)
- [Collaboration and DVC merge-conflict procedure](docs/COLLABORATION.md)
- [Student 1 handoff checklist](docs/STUDENT1_HANDOFF.md)
- [Student 2 procedure guide](docs/STUDENT2_GUIDE.md)
- [Student 3 procedure guide](docs/STUDENT3_GUIDE.md)
- [Shared integration and release contract](docs/TEAM_INTEGRATION.md)
- [Final demonstration checklist](docs/FINAL_DEMO_CHECKLIST.md)
- Local evidence: reports/experiments, reports/feature_store, reports/models, and reports/reproducibility.

## Attribution

Chen, S. (2017). Beijing Multi-Site Air Quality [Dataset]. UCI Machine Learning Repository. [DOI: 10.24432/C5RK5G](https://doi.org/10.24432/C5RK5G). Dataset license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

This repository's software license must be chosen by the team; the dataset's license does not automatically license the project code.
