# Student 3: Serving, Deployment and Reliability Procedure

Read TEAM_INTEGRATION.md and FEATURES.md first. You own the required Flask API, additional BentoML demonstration, containers, AWS hosting, Kubernetes demonstration, monitoring and alerts. All new files below are TO CREATE; these notes do not claim those components already exist.

## Phase 1 — Reproduce the model before writing the API

1. Review the Student 1 PR. Start student3/serving from the agreed merged main commit. If it is not merged, document a temporary dependency on origin/student1/features.
2. Follow README.md for the Python environment, DVC pull and Feast registration. Confirm all 40 tests pass.
3. Read reports/models/registry_candidate.json and prediction_example.json.
4. Load models:/air-quality-pm25-aotizhongxin/1 using mlflow.sklearn.load_model after configuring DagsHub tracking. Preserve the fitted dependency versions and skops metadata.
5. Construct a DataFrame from example inputs, explicitly select FEATURE_COLUMNS, and compare predict() with expected_predictions using a numerical tolerance.
6. Record the model name/version, source training run, raw/feature hashes and exact dependency snapshot.

Keep approval_status=pending_review and deployment_approved=false until an authorized team review is actually recorded. Local development verification is permitted; production release must pass the team's enforced approval path.

Acceptance: model loading and the provided prediction examples match on your own machine.

## Phase 2 — Implement the required Flask contract

TO CREATE: src/serving/__init__.py, app.py, model_loader.py, schemas.py, feature_provider.py, and tests/test_api.py.

Use an application factory create_app(). Load the pinned model once during startup, not per request. Put validation/feature retrieval in shared functions so Flask and BentoML use the same behavior.

### Required and supporting endpoints

| Endpoint | Behavior |
| --- | --- |
| GET /health | Process liveness, simple 200 response; no credentials or lengthy network operations |
| GET /ready | 200 only when the approved/development-allowed model and required feature access are ready; otherwise 503 |
| GET /model-info | Exact registry name/version, horizon, station, serving mode, feature schema/version and approval information |
| POST /predict | Validate request, obtain correct inputs, predict, apply configured alert threshold, return versioned result |
| GET /metrics | Prometheus exposition, protected from unnecessary public access |

The first three PDF-required endpoints are /health, /model-info and /predict. /ready and /metrics support deployment/monitoring.

### Recommended initial API mode: historical replay

The existing data ends in 2017. For the first working course API, let the server retrieve historical Feast inputs for a requested station and exact hourly forecast origin. This uses the actual implemented feature store and avoids asking a caller to calculate 19 lag/calendar/weather values.

Proposed request contract, TO IMPLEMENT:

~~~json
{
  "mode": "historical_replay",
  "station_id": "Aotizhongxin",
  "forecast_origin": "2015-03-01T00:00:00+08:00"
}
~~~

The timestamp above illustrates syntax, not a promise that every requested hour has complete features. Use a known complete example for acceptance tests.

Procedure:

1. Require a JSON object, the configured mode, supported station and timezone-aware ISO timestamp on an exact hourly boundary.
2. Convert origin to UTC for Feast. Historical queries use origin t, not t+1.
3. Retrieve pm25_forecasting_v1 inputs with a one-row entity dataframe through FeatureStore.get_historical_features.
4. Reject unavailable/null/nonfinite input vectors. Restore pm25_current to PM2.5 and select FEATURE_COLUMNS exactly.
5. Predict concentration, then set target time to origin plus one hour.
6. Return mode=historical_replay explicitly. Never stamp the historical prediction as a present-day forecast.

A later live mode accepts a station and obtains the latest online features. Call feature_store.validation.validate_online_features with its default trusted real clock. It should currently reject the historical snapshot as stale. Do not let a caller supply the server's freshness reference time.

If you implement a direct-feature batch endpoint, document its separate schema/provenance limitations and validate it independently. Do not manufacture per-feature timestamps from a caller's claimed origin to make it appear fresh.

### Response contract

Include request ID, mode, station_id, forecast_origin, target_timestamp, horizon_hours=1, predicted_pm25, units=micrograms/m3, model name/version, feature version, and threshold/threshold_exceeded. For replay, describe historical event-time eligibility rather than claiming real-clock freshness.

Use consistent error codes:

| Status | Example |
| --- | --- |
| 200 | Valid prediction |
| 400 | Malformed JSON, missing/extra-invalid fields, invalid time/station |
| 401/403 | Missing/invalid authentication or insufficient access |
| 413 | Request too large |
| 422 | Requested historical hour has unavailable/invalid features |
| 503 | Model/feature service unavailable or live data stale |

Do not return a traceback or convert all errors into HTTP 200. Liveness should remain distinct from model readiness.

### API tests

Test a real example prediction; exact metadata; malformed JSON; unsupported station; missing/invalid/future time as applicable; unavailable historical hour; stale live features; nonfinite/negative values in any direct-input route; oversized input; unauthorized access; model unavailable; and concurrent prediction stability. Verify that secrets and full request payloads are not dumped to logs.

The saved prediction_example.json contains model inputs, not this HTTP wrapper. After implementing the proposed replay contract, a Windows smoke request can be:

~~~powershell
$example = Get-Content "reports/models/prediction_example.json" -Raw | ConvertFrom-Json
$body = @{
    mode = "historical_replay"
    station_id = "Aotizhongxin"
    forecast_origin = $example.forecast_origins[0] + "+08:00"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/predict" -ContentType "application/json" -Body $body
~~~

The saved origins are naive Beijing-local timestamps; append the documented offset once. Match the result to expected_predictions[0] and add the required auth header once authentication is enabled.

Reference: [Flask testing](https://flask.palletsprojects.com/en/stable/testing/).

## Phase 3 — Package and run Flask in Docker/Compose

TO CREATE: docker/Dockerfile.api, runtime dependency file, .dockerignore, docker-compose.yml, and scripts/smoke_api.py.

1. Start from a pinned Python 3.11 Linux base and confirm its CPU architecture matches the deployment host.
2. Install the compatible inference/feature dependencies. Start with the tested snapshot for compatibility; reduce to a smaller runtime set only after model/example/API tests still pass.
3. Include the serving modules, feature definitions/helpers and exact model artifact. The saved model's code_paths contains src; feature_store is additional application code and must be included where needed.
4. Download the approved pinned artifact in a trusted CI step using secrets, then stage it for packaging. Do not put DagsHub credentials in Docker ARG/ENV layers or copy .dvc/config.local into the image.
5. Preserve the complete MLflow model directory, including MLmodel and skops metadata. Pin the build to the artifact/version and record a digest.
6. Keep raw training data, Git history, caches and unrelated artifacts out of the image. The historical feature Parquet is necessary for replay retrieval; restore it separately as a verified read-only data mount.
7. Reapply Feast definitions in the container/init process at its actual /app path. Give each container a writable generated-registry directory; do not use a laptop registry whose source path points to D:.
8. Run as a non-root user. Provide writable paths only for required state/logs.
9. Use Gunicorn in Linux/WSL/container, not the Flask development server on AWS. After creating the application factory, a possible command is:

~~~text
gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60 --access-logfile - src.serving.app:create_app()
~~~

Quote the factory argument as required by your shell. One process simplifies the initial metrics demonstration; if you add multiple processes, configure Prometheus client multiprocess collection correctly.

10. Compose should define api plus prometheus/grafana, with initialization/feature mounts where needed. Define readiness health checks and persistent monitoring volumes. Keep dashboards on loopback/private networking.

After these files exist:

~~~text
docker build -f docker/Dockerfile.api -t air-quality-api:dev .
docker compose up -d --build
docker compose ps
docker compose logs --tail 100 api
~~~

Acceptance: API tests and example predictions pass in the container; another teammate can reproduce them. Capture the image ID/digest and configuration, not just a successful build log.

References: [Flask/Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/), [Compose](https://docs.docker.com/compose/), [Prometheus multiprocess mode](https://prometheus.github.io/client_python/multiprocess/).

## Phase 4 — Demonstrate BentoML in addition to Flask

The supplied addendum requires a BentoML demonstration. It does not replace the required Flask API.

1. Use an isolated dependency file/environment so installing BentoML cannot silently alter the working ML dependencies.
2. TO CREATE: src/serving/bentoml_service.py and versioned Bento packaging/configuration.
3. Import the exact model into the Bento model store. In a controlled authenticated preparation script:

~~~python
import bentoml.mlflow
from src.models.tracking import configure_tracking

configure_tracking()
saved = bentoml.mlflow.import_model(
    name="air_quality_pm25",
    model_uri="models:/air-quality-pm25-aotizhongxin/1",
)
print(saved.tag)
~~~

4. Record the returned Bento model tag. Load that exact tag rather than latest.
5. Define a class-based service using @bentoml.service and @bentoml.api. Reuse the Flask path's feature provider, input rules and prediction/metadata formatting.
6. Implement readiness that checks successful loading. BentoML provides /livez and /readyz health endpoints.
7. After creating the class AirQualityService, run:

~~~text
bentoml serve src.serving.bentoml_service:AirQualityService
~~~

8. Verify health and the same example prediction. Configure packaging to include the model and needed feature access but exclude secrets/raw datasets.
9. Build, list and containerize the actual returned Bento tag:

~~~text
bentoml build
bentoml list
bentoml containerize YOUR_BENTO_TAG
~~~

Set the project service/import path in the pinned BentoML version's build configuration or dedicated packaging directory. Test the resulting container and retain its tag/digest and output.

References: [MLflow import/load](https://docs.bentoml.com/en/latest/reference/bentoml/frameworks/mlflow.html), [service definitions](https://docs.bentoml.com/en/latest/build-with-bentoml/services.html), [packaging](https://docs.bentoml.com/en/latest/get-started/packaging-for-deployment.html), [health endpoints](https://docs.bentoml.com/en/latest/build-with-bentoml/observability/monitoring-and-data-collection.html).

## Phase 5 — AWS-hosted vertical slice

Default course route: private ECR image repository, one EC2 Linux host with Docker/Compose, private S3 artifacts, and CloudWatch. Keep Airflow/KFP/local Kubernetes off AWS unless the team deliberately chooses otherwise. AWS resources incur charges; check current regional pricing before creating them.

### Before resource creation

1. Confirm authorized account access, region, resource names and a written spending limit.
2. Create a budget alert first. A notification is not an automatic spending cap.
3. Define distinct IAM roles for CI publishing/deployment and EC2 runtime. Require IMDSv2 on the host and avoid permanent AWS keys in containers.
4. Choose network restrictions and authentication. Prefer HTTPS; restrict any temporary demonstration endpoint to agreed client IPs and never send reusable bearer secrets over plain public HTTP.
5. Keep SSH restricted or use Systems Manager. Prometheus/Grafana/Airflow/KFP must not become public unauthenticated services.

### ECR and S3 preparation

Create a private ECR repository and record its URI. TEMPLATE PowerShell commands, after authenticated AWS CLI setup:

~~~powershell
$awsRegion = Read-Host "Enter the selected AWS region"
$awsAccount = Read-Host "Enter the AWS account ID"
$imageTag = Read-Host "Enter the reviewed immutable image tag"
$registry = "$awsAccount.dkr.ecr.$awsRegion.amazonaws.com"
aws sts get-caller-identity
aws ecr create-repository --repository-name air-quality-api --region $awsRegion
aws ecr get-login-password --region $awsRegion | docker login --username AWS --password-stdin $registry
docker tag air-quality-api:dev "$registry/air-quality-api:$imageTag"
docker push "$registry/air-quality-api:$imageTag"
~~~

Creating an existing repository may return an already-exists error; verify and reuse the intended repository rather than creating duplicates. Capture the pushed digest. Student 2 will automate this publishing step after gates/review.

Create a private S3 bucket/prefix with public access blocked and encryption enabled. Store artifacts under content/version-specific keys, including the 911,095-byte feature Parquet and release manifests. Record SHA/MD5 and object/version IDs; S3 versioning, if enabled, preserves full additional object versions and has storage costs.

EC2 needs only the required serving feature artifact, model image, release/config files and logs. DagsHub already stores the training data; copying the entire repository cache to AWS is unnecessary.

### EC2 setup and deployment

1. Launch a supported Linux instance with enough memory for the measured model/API workload. Pin its architecture to the image. Avoid assuming the tiniest shape can run all development stacks.
2. Attach the runtime instance profile: restricted ECR pull, required S3 prefix read, and appropriate CloudWatch/SSM permissions. The runtime role does not need broad model-training or account-administration permissions.
3. Install Docker Engine and the Compose plugin using official OS-specific instructions; verify docker version and docker compose version.
4. Stage the immutable release manifest and fetch the pinned feature artifact from private S3 into a read-only application data directory. Verify its checksum before serving.
5. Use the exact ECR image digest and approved model URI. Initialize Feast registry paths for the container's location and mounts.
6. Run Compose with server-side mode, authentication, request-size limit, model metadata, and log configuration.
7. Configure reverse proxy/TLS and security-group rules for the intended clients. Confirm that a request cannot bypass the reverse proxy on an exposed backend port.
8. Smoke-test /health, /ready, /model-info and a known valid historical prediction through the AWS endpoint; test unauthorized and malformed requests too.
9. Record region, instance/resource identifiers, image digest, model version, endpoint, response and access-control evidence.
10. Hand deployment commands to Student 2 for a least-privileged SSM/CI workflow. A manual first launch is preparation; actual CI/CD execution still needs demonstration.

References: [AWS budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-create.html), [ECR push](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html), [S3 versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html), [Docker on Ubuntu](https://docs.docker.com/engine/install/ubuntu/), [Compose plugin](https://docs.docker.com/compose/install/linux/), [SSM Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html).

### Private demonstration access without a public API port

If the team does not have a TLS/domain setup, an IAM-authorized Session Manager port-forward can access an API running on EC2 while keeping its inbound port closed. Configure the managed-node agent, instance role, client Session Manager plugin and narrowly scoped session permissions first. Publish the host API on loopback; forward remote port 8000 to local port 18000 using AWS-StartPortForwardingSession, then call localhost:18000 through that encrypted session.

Record the real EC2 target, access prerequisites and successful remote prediction so an instructor can reproduce it. This is private AWS-hosted access, not a public HTTPS endpoint. Use a correctly configured restricted HTTPS route if public access is required by the instructor.

Reference: [Session Manager port-forward document and IAM](https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-specify-session-document.html).

## Phase 6 — Kubernetes scaling and replacement demonstration

Use local kind/Minikube. AWS EKS is not necessary for this course requirement.

1. TO CREATE: k8s/namespace.yaml, api-deployment.yaml, api-service.yaml and required configuration/volume/init definitions.
2. Use the exact tested image; set resource requests/limits, non-root execution, startup/readiness/liveness probes, and a Service.
3. For replay, mount a verified feature artifact read-only and give each pod its own generated Feast registry/state directory. A single-node demonstration may use node-local read-only feature storage; document that it is not a production distributed storage design.
4. Keep pods stateless with respect to requests. Do not have multiple replicas write the same SQLite online store concurrently. A production online feature store/storage choice needs separate design.
5. After creating the manifests:

~~~text
kind create cluster --name air-quality-api
kind load docker-image air-quality-api:dev --name air-quality-api
kubectl apply -f k8s/
kubectl rollout status deployment/air-quality-api -n air-quality
kubectl scale deployment/air-quality-api --replicas=3 -n air-quality
kubectl get pods -n air-quality -o wide
kubectl port-forward service/air-quality-api 8001:8000 -n air-quality
~~~

These names must match your manifests. Use a non-latest tag with the appropriate imagePullPolicy for locally loaded images. Check the current kubectl context before changing workloads.

6. Send repeated requests through the Service and record pod identities in structured logs/debug metadata to demonstrate distribution. A port-forward alone is not proof of load balancing; observe requests through the Service from inside the cluster if needed.
7. Remove one named demonstration pod and show the Deployment creates a replacement while readiness protects routing. Restrict this action to the dedicated demo namespace.
8. HPA is optional beyond the required replica scaling. If demonstrated, install a metrics source and set CPU requests; do not claim automatic scaling from a manual kubectl scale.

References: [kind quickstart](https://kind.sigs.k8s.io/docs/user/quick-start/), [probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/), [HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/).

## Phase 7 — Monitoring, pollution alerts and drift

TO CREATE: monitoring/prometheus.yml, Grafana datasource/dashboard/alert provisioning, application metrics/logging, drift and delayed-label evaluation modules.

1. Expose request counts, error counts, request/prediction latency, ready/model-loaded status, feature failures, feature age, and model version. Keep labels bounded; request IDs and timestamps belong in logs, not metric labels.
2. Configure Prometheus scraping. Verify the target is UP and queries change after actual requests.
3. Import/provision Grafana panels for traffic, error ratio, latency, feature age/null failures, predicted concentration distribution, alert counts, and model version.
4. Configure an actual Grafana alert/contact point. A course example policy might use readiness down for one minute, or a 5xx ratio above 5% for two minutes with a minimum traffic condition. These are proposed demo thresholds and must be versioned before testing.
5. Produce a controlled condition, capture the alert firing, restore the service and capture recovery. Do not call a dashboard screenshot alone an alert demonstration.
6. Implement a separate pollution threshold rule using configurable concentration units and target time. Use a test threshold below a known example's prediction to demonstrate an alert, then restore the committed setting. Label it as an educational concentration threshold, not an official AQI/health rule.
7. Build a drift reference from training-only features; record its data/model version. Monitor feature distributions and missingness, accounting for seasonality and sample size.
8. Simulate a documented input shift to show drift detection. Drift is a signal to investigate/retrain, not permission to auto-promote a model.
9. When delayed labels arrive, join them by station and target time to stored model-versioned predictions and report error plus coverage. Do not compare labels with mismatched forecast horizons.
10. Emit a deduplicated, authenticated retraining event to Student 2's workflow. Retain run links and the resulting candidate decision.

For Gunicorn multiple processes, follow the Prometheus client's multiprocess guidance; ordinary in-memory counters do not automatically combine across workers.

### CloudWatch

On AWS, send structured JSON application logs to CloudWatch through an appropriate agent/logging driver and record CPU/host health. The Docker awslogs driver can use the instance role. Precreate log groups, choose retention, and restrict write permissions. Add a useful CloudWatch alarm and prove actual log ingestion; local Grafana does not replace required AWS logging.

References: [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/), [Prometheus Python multiprocess mode](https://prometheus.github.io/client_python/multiprocess/), [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/), [Docker CloudWatch logging](https://docs.docker.com/engine/logging/drivers/awslogs/), [CloudWatch agent](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Install-CloudWatch-Agent.html).

## Phase 8 — Approval, release, rollback and cleanup

1. Coordinate the exact approval/release contract with Student 2. Registry tags, reviewer identity, code/data/model identifiers and image digest must agree.
2. Keep the previous approved image digest, model version and config before updating the service.
3. Execute the reviewed update through CI/CD; verify readiness, metadata, example prediction and monitoring.
4. Demonstrate rollback by deploying the previous complete release and proving /model-info and predictions match it. Do not claim that editing an alias without restarting a cached model updated the running service.
5. Preserve the initial frozen test result. Use Student 2's separate lifecycle-demo protocol for controlled retraining/promotion evidence.
6. Save API/container/cloud/Kubernetes/alert/rollback evidence under reports/deployment and reports/monitoring.
7. After the demonstration, inventory and stop/delete only the dedicated project resources under the agreed retention plan: EC2 workloads/instances, disks/snapshots, public IP allocations, optional load balancers, ECR images, S3 object versions and logs. Verify billing/resource state rather than assuming stopping one process ends all charges.

## Troubleshooting checkpoints

| Symptom | First check |
| --- | --- |
| Wrong predictions | Pinned model URI, exact feature order, timezone, runtime package versions |
| D: path missing inside container | Regenerate Feast registry/source paths for the container and mount the artifact |
| Historical feature request rejected | Exact origin hour, supported station, complete feature availability, UTC conversion |
| Live request rejected as stale | Expected with the archive; provide fresh validated ingestion before live use |
| Gunicorn fails on Windows | Run in Linux container/WSL; use Flask development CLI only for local development |
| K8s ImagePullBackOff | Correct kind cluster image load, tag/pull policy, or authenticated registry |
| Metrics look inconsistent with multiple workers | Prometheus multiprocess configuration |
| CloudWatch logs absent | Runtime role, region, log-group/stream settings, outbound connectivity |

The required outcome is a tested, versioned, AWS-accessible API with implemented controls and actual operational evidence, plus the separate BentoML and local Kubernetes demonstrations.
