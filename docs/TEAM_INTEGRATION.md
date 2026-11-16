# Shared Integration, Approval and Release Contract

This is the coordination document for all three students. Student 1's verified local foundation is available; the infrastructure/release procedures below still require implementation and evidence.

## 1. Starting facts

| Item | Verified value |
| --- | --- |
| Student 1 branch | student1/features |
| Documentation checkpoint | dc6be1f |
| Historical recovery confirmation | 7725c299b0cc2cb621967617d4126997f69eafd6 |
| Current demonstrated tests | 40 passed |
| Pinned model | models:/air-quality-pm25-aotizhongxin/1 |
| Training run | 8bb90ba8cf9c489986f5bd49813fd8fd |
| Final evaluation run | edbe53c2a1b647489feb7d5843a00dc7 |
| Validation gate run | fd24e8ed1c23472cafb64f82ebca9eec |
| Raw-data MD5 | 72a306d7a095e718c2b46ab482d5a1ac |
| Feature-data MD5 | 1904355bbc9682150d269d9060c6118a |
| Serving feature service | pm25_forecasting_v1 |
| Current decision | pending_review; deployment_approved=false |

The code/model training SHA and the later application/deployment SHA are different identifiers; preserve both.

## 2. Responsibility and integration boundaries

| Deliverable | Primary owner | Required collaboration |
| --- | --- | --- |
| Feature meaning/time/missingness and model evidence | Student 1 | Review changes with Students 2/3 |
| DVC pipeline, Airflow->KFP, CI and release orchestration | Student 2 | Student 1 module interfaces; Student 3 deployment commands |
| Flask/BentoML, containers, AWS/Kubernetes and monitoring | Student 3 | Student 1 feature/model contract; Student 2 promotion/rollback |
| Actual model approval and reproducible demo | All | Named reviewer, evidence, full-system understanding |

Student 1 has already configured shared GitHub/DagsHub/DVC/MLflow foundations; other owners should extend them rather than create disconnected replacements.

## 3. Agree on a common run/artifact interface

Before connecting tools, Students 2/3 should create a versioned schema with these fields:

- pipeline_run_id and orchestration run IDs.
- source code commit, training commit, application commit.
- raw/feature content identifiers and source cutoffs.
- feature service/schema version, station, horizon.
- training/candidate/deployed model URIs and comparison evaluation-set ID.
- absolute/relative metrics, negative/null/stale checks, coverage.
- gate result and failure reasons.
- registry version, image digest, configuration version.
- reviewer, approval time and deployment environment.
- previous approved release and rollout/rollback status.

Persist artifacts under run-specific paths. Do not send the actual model or whole dataset through Airflow XCom. KFP output artifacts/remote URIs should be explicit; small identifiers/manifests can pass as parameters.

## 4. Example release-manifest template

This is a schema example with placeholders, not a deployable approved release:

~~~json
{
  "release_schema_version": "1",
  "pipeline_run_id": "TO_BE_FILLED",
  "application_git_commit": "TO_BE_FILLED",
  "training_git_commit": "7725c299b0cc2cb621967617d4126997f69eafd6",
  "model_uri": "models:/air-quality-pm25-aotizhongxin/1",
  "source_training_run_id": "8bb90ba8cf9c489986f5bd49813fd8fd",
  "test_evaluation_run_id": "edbe53c2a1b647489feb7d5843a00dc7",
  "dataset_dvc_md5": "72a306d7a095e718c2b46ab482d5a1ac",
  "feature_source_dvc_md5": "1904355bbc9682150d269d9060c6118a",
  "feature_service": "pm25_forecasting_v1",
  "image_digest": null,
  "configuration_version": "TO_BE_FILLED",
  "serving_mode": "historical_replay",
  "quality_gate_passed": true,
  "prediction_check_passed": true,
  "approval_status": "pending_review",
  "deployment_approved": false,
  "reviewed_by": null,
  "reviewed_at": null,
  "previous_release_id": null
}
~~~

The release verifier must reject placeholders, inconsistent evidence, missing digests/review fields, unapproved branches and false deployment approval. Do not approve a template merely because quality_gate_passed is true.

## 5. Initial model review procedure

1. A real authorized reviewer inspects the validation comparison, final report, 83.61% coverage limitation, source/data/feature versions, prediction check, environment compatibility, and historical serving mode.
2. Record the review in GitHub or the agreed auditable workflow, including model name/version and reviewer identity.
3. After that actual review, an authorized operator may update the exact model version's tags to approval_status=approved_for_course_demo and deployment_approved=true, adding reviewed_by and reviewed_at. These are proposed status values; keep the implementation consistent.
4. Protect deployment credentials through GitHub environment/rules or an equivalent controlled process; mutable MLflow tags alone are not enough.
5. Refresh the registry_candidate manifest from server state after approval rather than editing the local JSON to invent approval. Re-running the existing register_candidate script reuses the exact version and reads current tags.
6. Bind the reviewed model to the built/tested image digest and deployment configuration in the release manifest.
7. Retain approval evidence with the release. If the source model or image/configuration changes materially, require the applicable checks/review again.

Review has not been reported as completed in the supplied terminal logs.

## 6. Failure propagation

Required behavior:

~~~text
invalid data
  -> no KFP submission / no training

failed training, prediction validity or model comparison
  -> no release packaging/publishing/deployment

missing approval
  -> no access to production deployment credentials/job

readiness or smoke-test failure after update
  -> mark release failed and execute verified rollback procedure
~~~

Use nonzero process exits and failed task/job states for mandatory failures. A failure-reasons JSON is useful evidence but must be connected to a blocking dependency.

The existing quality_gate compares candidates to persistence and checks all candidates share the initial experiment's code/data context. For future deployed-model comparison, different training commits are expected. Implement compatible-contract/common-evaluation checks rather than requiring identical old/new training commits.

## 7. Secret names and configuration

Names below are proposed configuration contracts, not secret values:

| Name | Purpose / intended owner |
| --- | --- |
| MLFLOW_TRACKING_URI | Hosted DagsHub endpoint; non-secret configuration |
| MLFLOW_TRACKING_USERNAME | Authorized DagsHub user |
| MLFLOW_TRACKING_PASSWORD | Authorized token in CI/secret store |
| DVC/S3 credential configuration | Local ignored config or mounted/generated CI secret |
| MODEL_URI | Pinned registered model version |
| MODEL_LOCAL_PATH | Prepared verified model artifact path, if packaged |
| APP_MODE | historical_replay or approved live mode |
| API_TOKEN | Protected prediction API credential, or replace with an equivalent implemented auth mechanism |
| POLLUTION_THRESHOLD_UG_M3 | Versioned educational concentration threshold |
| KFP_ENDPOINT / KFP_NAMESPACE | Actual reachable, authorized KFP service |
| AWS_REGION / AWS_ROLE_ARN | AWS deployment configuration; OIDC supplies temporary credentials |
| IMAGE_URI / IMAGE_DIGEST | Exact reviewed container artifact |

Configure only names actually consumed by the implemented code. README.md explains current interactive DVC/DagsHub setup; the automation/runtime names here must be wired by Students 2/3.

Do not commit .env, .dvc/config.local, AWS keys, model-download tokens or kubeconfig. Check captured logs/screenshots before publishing. Use each teammate's own authorized credentials; do not distribute Student 1's local token.

## 8. Shared ports and storage

Agree on nonconflicting local ports, for example:

| Service | Example host port |
| --- | ---: |
| Flask API | 8000 |
| Kubernetes API demonstration port-forward | 8001 |
| Airflow UI | 8080 |
| KFP UI forwarding | 8081 |
| BentoML | 3001, if Grafana uses 3000 |
| Grafana | 3000 |
| Prometheus | 9090 |

These are proposed bindings; ensure CLI examples match the chosen service configuration. Container-to-container names and KFP service endpoints differ from host browser URLs. Localhost inside one container does not identify another container.

Generated SQLite/Feast registry state belongs in explicit local volumes and must be regenerated for container paths. For a replica demo, use read-only feature artifacts and per-pod registry state. Do not treat a shared writable SQLite file as a production multi-writer feature store.

## 9. Acceptance sequence

1. Reproduce model/data/features and the initial 40-test suite.
2. Implement and test Flask/example prediction locally.
3. Containerize; reproduce on a teammate's machine.
4. Execute Airflow->KFP with typed artifacts and MLflow IDs.
5. Prove invalid data/model rejection blocks the workflow.
6. Record review and bind a release manifest.
7. Publish/deploy exact approved image to AWS and prove a valid authenticated prediction.
8. Demonstrate local Kubernetes scaling/replacement.
9. Show Grafana/Prometheus plus CloudWatch data and actual alert evidence.
10. Execute a controlled retraining/comparison/release/rollback scenario.

Record which steps are manual and which are automatic. The deadline does not change the requirement to distinguish planned files from executed functionality.

## 10. Final team documentation

Update the root README and report with the actual cloud endpoint, tested tool/image versions, architecture/workflow diagrams, setup/configuration names, execution evidence, security controls, alert/retraining policy, rollback instructions, cost/cleanup steps, limitations and each student's contribution.

See FINAL_DEMO_CHECKLIST.md before the oral defense.
