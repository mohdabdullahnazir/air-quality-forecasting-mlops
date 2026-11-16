# Student 1 Handoff and Completion Checklist

Prepared for Students 2 and 3 from actual Student 1 execution evidence.

## Available implementation

| File/module | Contract |
| --- | --- |
| src.data.ingestion.load_station_data(path) | Read station CSV, construct timestamp, sort chronologically |
| src.data.validation.validate_station_data(frame) | Enforce station/schema/timeline/value rules; allow missing measurements |
| src.features.engineering.create_features(frame) | Create the 19 causal inputs on the preserved hourly grid |
| src.features.preprocessing.create_forecast_target(frame) | Attach observed next-hour label and target time |
| src.features.preprocessing.split_by_target_time(frame) | Fixed initial train/validation/test target-time split |
| src.features.export_feast | Export all hourly feature rows to Parquet |
| feature_store.setup_store | Register local entity/source/view/service |
| feature_store.historical.load_forecast_from_store() | Retrieve inputs via Feast; retain local times/labels outside its query |
| feature_store.online | Controlled historical materialization/retrieval demonstration |
| feature_store.validation.validate_online_features | Validate feature schema, station, values, timestamp consistency and age; return model-ready input frame plus feature timestamp |
| src.models.train | Persistence + four parameter configurations; common eligible rows |
| src.models.quality_gate.assess_candidate | Pure gate function; returns failure reasons |
| src.models.quality_gate CLI | Hosted-metric comparison, lineage checks, report, nonzero exit when no candidate passes |
| src.models.final_evaluation | Frozen initial test evaluation, already completed |
| src.models.register_candidate | Register/reuse exact tested source model; verify saved validation predictions |

Ingestion's sort step precedes validation. The validator itself requires chronological input. Targets and lag calculations assume one validated station with one row per hour.

## Concrete handoff artifacts

- reports/experiments/validation_comparison.csv: the most recent local candidate comparison.
- reports/experiments/quality_gate.json: selected candidate, policy, decisions, gate run identifiers.
- reports/experiments/frozen_candidate.json: initial candidate/policy frozen before test scoring.
- reports/experiments/final_test_report.json: final observed metrics and deployment=false.
- reports/feature_store/online_replay.json: actual replay checks.
- reports/models/registry_candidate.json: exact registered version and lineage.
- reports/models/prediction_example.json: five validation examples and expected predictions.
- reports/reproducibility/recovery_demo.txt: recovery transcript.
- reports/reproducibility/recovered_commit.txt: confirmed recovered HEAD, committed in dc6be1f.

Some experiment output files may still need explicit Git staging. MLflow also contains predictions, plots, source/version metadata, environment snapshot, and registry handoff artifacts.

## Fixed identifiers for initial integration

- Registry URI: models:/air-quality-pm25-aotizhongxin/1.
- Feature service: pm25_forecasting_v1.
- Raw MD5: 72a306d7a095e718c2b46ab482d5a1ac.
- Feature MD5: 1904355bbc9682150d269d9060c6118a.
- Training SHA: 7725c299b0cc2cb621967617d4126997f69eafd6.
- Test run: edbe53c2a1b647489feb7d5843a00dc7.
- Status: pending_review, deployment_approved=false.
- Python: 3.11.17; Feast: 0.67.0; DuckDB: 1.5.6.

## Student 2 integration priorities

1. Review/merge the Student 1 PR and use the shared tested commit.
2. Install/pin a clean Linux/container environment and run the 40 tests.
3. Configure DVC and MLflow secrets through CI/orchestrator mechanisms.
4. Add a DVC pipeline without duplicate ownership of the feature artifact.
5. Have scheduled Airflow ingestion/validation trigger a real Kubeflow Pipeline through its API/SDK.
6. Containerize the ML graph with explicit inputs/outputs and gate failure propagation.
7. Add push/PR CI, code quality checks, security scanning, and evidence of blocked execution.
8. Isolate each future retraining run's outputs. The current comparison, frozen-selection, and final-report locations are designed for the initial course experiment and can otherwise collide.
9. Refactor the fixed initial split/evaluator for a separately defined future retraining protocol. Do not repeatedly optimize against the original final test.
10. Compare a future candidate and the currently deployed pinned model on the same approved evaluation set, using predefined criteria. The current gate compares to persistence; deployed-model comparison remains work.
11. Implement a reviewed promotion decision, approved artifact handoff to deployment, and rollback metadata with Student 3.

## Student 3 integration priorities

1. Load pinned model version 1 and match the provided prediction example.
2. Implement Flask GET /health, GET /model-info, POST /predict, plus API/integration tests.
3. Implement the additional BentoML packaging/serving demonstration required by the course.
4. Use the exact 19-feature order/mapping and the feature/freshness contract in FEATURES.md.
5. Keep historical replay mode explicit. Current SQLite features are historical and should fail a real-clock live request.
6. Package runtime dependencies, model loading, and feature access in Docker; demonstrate Compose on another machine.
7. Coordinate explicit review/promotion enforcement with Student 2. A true/false local JSON field alone is not an access-control mechanism.
8. Deploy to AWS with budgets, restricted IAM/network access, ECR, a running hosted API, and CloudWatch evidence.
9. Demonstrate Kubernetes Service/Deployment, health probes, multiple replicas, and replacement of a failed pod.
10. Implement Prometheus/Grafana metrics and alerts, a configurable pollution threshold, input drift, delayed-label performance monitoring, and a retraining signal.
11. Demonstrate a controlled retraining/deployment/rollback scenario jointly with Student 2.

## Student 1 completion checklist

- [x] Station selection and missingness assessment.
- [x] Modular ingestion and enforceable measurement/time validation.
- [x] Leakage-aware target/split/feature logic.
- [x] Raw and generated-feature DVC versions pushed to DagsHub.
- [x] Feast definitions, actual historical training retrieval, online materialization/retrieval, freshness handling.
- [x] Matched baseline, Random Forest/XGBoost parameter comparison, tracked runs.
- [x] Executed validation gate success and failure.
- [x] Frozen final evaluation with paired persistence and reported coverage.
- [x] Registered model version and prediction-loading verification.
- [x] 40 passing tests including actual Feast integration.
- [x] Recovery data checks and ingestion evidence committed as e3d80e4.
- [x] Explicit recovered HEAD captured and checked against the training SHA.
- [x] Documentation copied into the repository, committed, and pushed as dc6be1f; teammate review remains open.
- [ ] Actual PR review/merge evidence recorded.
- [ ] Integration questions and role ownership acknowledged by the team.

These open items need real actions; they must not be marked complete solely because this checklist exists. Remaining team infrastructure is not part of the completed local Student 1 implementation.
