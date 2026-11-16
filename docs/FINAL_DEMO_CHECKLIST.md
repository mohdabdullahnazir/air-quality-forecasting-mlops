# Final Demonstration and Evidence Checklist

An unchecked item is still work to perform or evidence to collect. Student 1 evidence below is supplied; later system demonstrations must be real executions.

## Existing Student 1 evidence

- [x] Dataset/station scope and missingness report.
- [x] Modular validation, causal features and chronological target splits.
- [x] Raw/feature DVC pointers and DagsHub remote.
- [x] Historical Feast retrieval used in training.
- [x] Online materialization, offline/online agreement and stale/unknown rejection.
- [x] Matched baseline and four candidate experiments with MLflow lineage.
- [x] Rejected candidate exits with code 1; selected candidate passes.
- [x] Frozen final test: MAE 10.278413, RMSE 18.737643, coverage 83.61%.
- [x] Registry version 1 and prediction-loading agreement.
- [x] 40 passing local tests including real Feast integration.
- [x] Historical training commit, both data hashes, recovery ingestion and transcript.
- [x] Student 1 documentation and exact recovered HEAD committed as dc6be1f.

## Collaboration and automated quality

- [ ] PR review and merge record, including teammate identity/comments.
- [ ] Conflict-handling procedure; actual conflict/simulation evidence if required by instructor.
- [ ] Clean environment/container installation reproduces the model example.
- [ ] GitHub Actions executes code-quality, tests, security scans and container build.
- [ ] A failed test/gate visibly blocks the workflow; a corrected run passes.
- [ ] CI credentials and AWS OIDC/IAM are restricted and implemented.

## Orchestration

- [ ] Airflow runs scheduled/manual ingestion and validation.
- [ ] A real retry and task timeout/failure behavior are shown.
- [ ] Airflow programmatically submits a real KFP run and tracks terminal status.
- [ ] KFP graph components exchange actual artifacts/parameters.
- [ ] Failed data/model gate prevents the downstream release path.
- [ ] Run IDs link Airflow, KFP, MLflow, data, model and image versions.

## Serving and containers

- [ ] Flask /health, /model-info and /predict work with correct metadata.
- [ ] API validates malformed/invalid/unauthorized requests with correct codes.
- [ ] Historical mode is explicit; live mode rejects the old snapshot.
- [ ] Docker image and Compose reproduce on another machine.
- [ ] BentoML model import, health/predict behavior, build and container are demonstrated.
- [ ] Example predictions agree with the pinned registry model.
- [ ] Runtime does not contain committed secrets or unnecessary training data.

## AWS and Kubernetes

- [ ] AWS budget alert established before billable deployment.
- [ ] Private ECR/S3 and least-privileged runtime/deployment roles.
- [ ] Approved version actually deploys through CI/CD to AWS.
- [ ] Documented restricted endpoint serves a valid authenticated prediction.
- [ ] CloudWatch receives real application logs/infrastructure metrics.
- [ ] Kubernetes Deployment/Service with readiness/liveness/startup checks.
- [ ] Multiple replicas and actual Service routing evidence.
- [ ] A failed/deleted demonstration pod is replaced.

## Monitoring and model lifecycle

- [ ] Prometheus target UP and request/error/latency/feature metrics changing.
- [ ] Grafana dashboard and actual alert firing/recovery.
- [ ] Configured pollution threshold and a labelled demonstration alert.
- [ ] Drift/quality scenario produces an investigation/retraining event.
- [ ] Delayed labels join predictions by station, target time and model version.
- [ ] Candidate compared with deployed champion under a predefined protocol.
- [ ] Losing candidate retained as blocked; reviewed winner has an audit trail.
- [ ] Release manifest binds model, data, code, image, configuration and reviewer.
- [ ] Actual rollback restores the prior running release and its predictions.

## Suggested live-demo order

1. Show architecture, scope, data/model IDs and current deployment mode.
2. Run selected tests or show the recorded 40-test baseline plus new API tests.
3. Show DVC recovery and Feast consistency/freshness evidence.
4. Show MLflow experiments, frozen final report and registered version.
5. Trigger Airflow; open the linked running/completed KFP graph.
6. Show a blocked controlled bad-data/model workflow.
7. Show the reviewed release workflow and actual AWS API response.
8. Show Compose/BentoML and Kubernetes scaling/replacement evidence.
9. Generate requests/controlled drift and show Grafana/CloudWatch/alert behavior.
10. Show candidate decision, approval and actual rollback.

Prepare concise backup recordings/logs for slow installations or network problems, but label them as recorded evidence. Do not replace required actual execution evidence with fabricated screenshots.

Before submission, every team member should explain the time split, complete-case coverage, chosen model, feature freshness, gate enforcement, deployment identity, alert handling and rollback. Complete the cleanup plan and verify remaining billable resources.
