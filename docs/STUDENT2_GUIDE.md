# Student 2: MLOps and Automation Procedure

Read TEAM_INTEGRATION.md first. Student 1 provides the ML implementation; your primary task is to make it execute reproducibly through orchestration and CI/CD, with real failure blocking and auditable release decisions. All files labelled TO CREATE below are proposed work, not existing implementation.

## Phase 1 — Reproduce the baseline and start your branch

1. Review the Student 1 PR, including feature time semantics, test coverage, final metrics, and recovery evidence.
2. After it is merged, clone the shared repository and create your branch from main:

~~~powershell
git clone https://github.com/mohdabdullahnazir/air-quality-forecasting-mlops.git
Set-Location air-quality-forecasting-mlops
git switch main
git pull --ff-only
git switch -c student2/automation
~~~

If the merge is still pending, start a temporary integration branch from origin/student1/features and clearly record the dependency in your PR. Do not assume current main already contains Feast.

3. Follow README.md for Python 3.11, the pinned ML requirements, DVC authentication, data pull, and Feast apply.
4. Run the existing 40 tests and historical retrieval check. Save your own outputs.
5. Build a clean Linux/container environment and repeat the tests before claiming portability. Preserve DuckDB 1.5.6; pip check alone did not catch the previous DuckDB 2.0 integration failure.

Acceptance: a fresh checkout retrieves the two DVC artifacts, applies Feast, reproduces sample predictions, and passes the suite.

## Phase 2 — Define the automation interface before composing tools

Create a versioned pipeline configuration, for example configs/pipeline_config.yaml. Include data revision, station, horizon, evaluation protocol, MLflow experiment, output root, image identifiers, KFP endpoint/namespace, and approval policy. Keep secret values outside it.

Refactor only the necessary wrappers around existing functions:

| TO CREATE | Required behavior |
| --- | --- |
| pipelines/common/context.py | Unique pipeline_run_id and run-specific output/artifact locations |
| pipelines/common/prepare.py | Validate inputs; build/version features; apply Feast; emit data/feature manifest |
| pipelines/common/train.py | Call existing experiment logic and write a comparison manifest for this run |
| pipelines/common/evaluate.py | Gate this run; emit candidate URI, source IDs, metrics and reasons |
| pipelines/common/compare_deployed.py | Compare candidate and deployed model fairly on an approved evaluation set |
| pipelines/common/release.py | Verify review and produce a release manifest bound to exact model/image versions |

The initial scripts write fixed reports/experiments paths and the final evaluator caches its initial report. Do not run concurrent DAGs against those shared files or reuse final_evaluation as a general retraining evaluator. Keep the original final report immutable and create a separate lifecycle-demo/retraining protocol.

Return structured manifests, not only console strings. Each downstream stage must consume the producing stage's actual output. For KFP pods, transfer artifacts through the configured artifact store; a Windows D: path is not shared pod storage.

Acceptance: run two smoke workflows with different run IDs and show that outputs and source-run selections cannot overwrite or mix.

## Phase 3 — Add DVC pipeline ownership

TO CREATE: dvc.yaml, its generated dvc.lock, and stage wrapper commands.

1. Keep the raw station CSV tracked by its existing .dvc file.
2. Decide ownership of data/processed/hourly_features.parquet. It already has a standalone .dvc pointer. If a pipeline stage will own it, migrate that metadata while preserving the real file/cache; do not declare the same output twice.
3. Define preparation dependencies: raw artifact, ingestion/validation/feature code, timezone/missingness settings, feature definitions, and relevant parameters.
4. Add training/evaluation stages using the refactored wrappers and run-specific manifests. Treat hosted model URIs/run IDs as manifest content, not local files that DVC magically restores.
5. Include all imported behavioral dependencies; changing validation.py or historical.py must invalidate the appropriate stage.
6. Run dvc repro, verify its outputs, and push required artifacts before committing new pointer/lock metadata.
7. Make a harmless controlled parameter change in a development branch and show the correct dependent stages rerun.

Avoid training purely because the raw-data file modification time changed. Use explicit revisions/content hashes. A real scheduled ingestion demonstration can retrieve a versioned S3 copy or replay a documented historical batch; it must not claim new live measurements.

References: [DVC pipelines](https://dvc.org/doc/user-guide/pipelines), [repro](https://dvc.org/doc/command-reference/repro), [DVC conflict handling](https://doc.dvc.org/user-guide/how-to/resolve-merge-conflicts).

## Phase 4 — Start Airflow separately from the ML environment

Use Linux containers/WSL for the scheduler stack. Follow the [official Docker Compose guide](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/). Choose one supported release and retain its matching Compose file and image tag.

1. TO CREATE: pipelines/airflow/docker-compose.yaml plus dags, logs, plugins, and config directories. Keep generated logs/databases out of Git.
2. Download the matching official Compose configuration into this folder; do not overwrite Student 3's application docker-compose.yml.
3. Build a custom Airflow image with only required orchestration/client dependencies. Do not install the entire ML dependency snapshot into Airflow and accept resolver conflicts.
4. If the KFP client conflicts with Airflow constraints, isolate it in a separate Python environment/task or use an authenticated REST call. The ML workload belongs in its own image.
5. Initialize and start, from that Airflow folder:

~~~text
docker compose up airflow-init
docker compose up -d
docker compose ps
~~~

6. Create the DAG in pipelines/airflow/dags/ml_orchestrator_dag.py. Use APIs appropriate to your pinned Airflow major version; current Airflow 3 examples use airflow.sdk.
7. For the initial demo, set catchup=False, max_active_runs=1, explicit timezone/schedule, retries and retry delay. Add timeouts and avoid duplicate training on retries.
8. Use an explicit historical data interval/replay mode. Re-running the unchanged archive hourly does not create new observations.

Acceptance: the UI discovers the DAG without import errors; a scheduled or manual run executes ingestion/validation and records a pipeline_run_id. Capture retry behavior from a temporary recoverable failure.

## Phase 5 — Install and execute Kubeflow Pipelines

Use standalone KFP on a local kind/Minikube cluster for the course. A full cloud Kubeflow distribution is not necessary to demonstrate the required graph.

1. Install Docker, kubectl, and your chosen local cluster tool.
2. Create a dedicated cluster/namespace and verify nodes are Ready.
3. Select an actual released KFP backend tag from [official releases](https://github.com/kubeflow/pipelines/releases); record the tag and compatible SDK version.
4. Follow the [standalone installation guide](https://www.kubeflow.org/docs/components/pipelines/operator-guides/installation/) for cluster resources and the development overlay. Templates:

~~~powershell
$kfpRelease = Read-Host "Enter the selected pinned KFP release tag"
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=$kfpRelease"
kubectl wait --for=condition=established --timeout=60s crd/applications.app.k8s.io
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/dev?ref=$kfpRelease"
kubectl get pods -n kubeflow
~~~

These are installation templates; first verify the paths against the selected release's documentation. Development manifests are for a restricted local demonstration.

5. Use a separate SDK environment; do not casually upgrade the working ML environment.
6. TO CREATE: pipelines/kubeflow/components, pipeline_definition.py, compile_pipeline.py, submit_pipeline.py, and compiled_pipeline.yaml.
7. Implement this graph with typed inputs and outputs:

~~~text
validated data revision
  -> prepare features / apply Feast
  -> chronological split
  -> train configured candidates
  -> evaluate + MLflow evidence
  -> conditional packaging/registration
  -> reviewed release handoff
~~~

8. Build/publish a pinned ML component image containing source and tested dependencies. Use KFP artifact transfer or explicit versioned remote artifacts between pods. Rebuild Feast registry paths within each relevant container; do not move a laptop SQLite/registry file blindly between pods.
9. Compile using kfp.compiler.Compiler().compile and submit through kfp.Client. A compiled YAML alone is not an executed pipeline.
10. Put packaging/build logic in an appropriate isolated builder/CI component. Do not give every training pod privileged Docker socket access.

Acceptance: an actual KFP run shows the connected graph, pod logs, output artifacts, MLflow IDs, and conditional exclusion of packaging/release when a gate fails.

References: [compile](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/compile-a-pipeline/), [run](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/run-a-pipeline/), [API authentication](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/connect-api/).

## Phase 6 — Make Airflow trigger and monitor KFP

The course specifically requires Airflow scheduling/ingestion followed by programmatic KFP execution.

1. The DAG validates data first. A failed validator must prevent submission.
2. Pass a validated revision/hash, image digest and pipeline_run_id to the compiled KFP package.
3. In the trigger task, use the SDK method after configuring actual authentication:

~~~python
run = kfp_client.create_run_from_pipeline_package(
    "pipelines/kubeflow/compiled_pipeline.yaml",
    arguments=pipeline_arguments,
)
~~~

This wiring example assumes you created the pipeline and its matching argument names.

4. Record the returned KFP run ID in XCom/a small manifest; poll/wait with a timeout until terminal status. An HTTP submission success is not ML pipeline success.
5. Mark Airflow failed when KFP fails. Do not catch an exception and return a success string.
6. Avoid duplicate KFP runs on an Airflow retry: look up the existing pipeline_run_id before resubmitting.
7. Test connectivity from the actual Airflow worker container. Its localhost is not the Windows host or the KFP service. Keep Airflow/KFP UI host ports distinct; document the actual reachable endpoint and authentication.
8. Keep local dashboard ports restricted. Never publish the development KFP endpoint openly as a shortcut.

Acceptance: one Airflow trigger yields a traceable KFP run, and an injected invalid-data/gate failure blocks downstream work.

## Phase 7 — CI and security gates

TO CREATE: .github/workflows/ci.yml, pinned CI-tool requirements, and protected checks.

On push/PR:

1. Check out the exact revision; set Python 3.11.
2. Install the tested dependencies and run pip check.
3. Run a chosen code-quality check, for example Ruff. Fix findings instead of adding blanket ignores.
4. Execute python -m pytest tests -q. The existing tests use fixtures/temporary stores and do not need production tokens.
5. Run dependency auditing and code/security scanning; preserve results and document reviewed exceptions by identifier and reason.
6. Build/test Student 3's container after its Dockerfile exists. PR builds can use a test fixture or a non-secret model artifact path; publishing the production image belongs to the trusted release job.
7. Make checks required for merging. Do not use continue-on-error for mandatory checks.

Pin action revisions to reviewed commit SHAs. Do not expose secrets through untrusted PR code or pull_request_target execution of the PR's scripts. Keep tokens out of shell traces and artifacts.

Add repository line-ending rules for Linux shell scripts, for example *.sh text eol=lf in .gitattributes. The existing Markdown LF/CRLF warnings did not fail the Student 1 commits; executable shell-script line endings need deliberate handling for containers.

Demonstrate one failing PR/workflow and a subsequent successful run. Do not rely solely on a screenshot of a green local pytest run.

References: [GitHub Actions](https://docs.github.com/en/actions), [code scanning](https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning), [pip-audit](https://github.com/pypa/pip-audit), [Ruff](https://docs.astral.sh/ruff/).

## Phase 8 — Release approval and AWS automation

Coordinate this phase with Student 3; see TEAM_INTEGRATION.md.

1. TO CREATE: a trusted release verification script, release manifest schema, deploy.yml, and deployment/rollback commands.
2. Recheck server-side MLflow gate evidence, source model, dataset/feature lineage, image digest, and reviewer identity. A PR-edited JSON file is not authoritative proof that a model passed.
3. Keep one pinned model URI, container digest, Git commit, data/feature IDs, configuration version, and review decision together.
4. Configure a protected deployment environment with an authorized reviewer. Verify your GitHub plan/repository visibility supports the rule; otherwise implement and demonstrate an equivalent controlled approval.
5. Record an actual review before changing approval_status/deployment_approved. Restrict who can use deployment credentials; mutable registry tags alone do not enforce permissions.
6. Use GitHub-to-AWS OIDC with a dedicated least-privileged role. Verify the actual subject format: GitHub changed defaults for newer repositories, including immutable repository/owner IDs where enabled. An old copied repo-name-only trust policy may not match this repository.
7. Publish the approved tested image to private ECR and deploy its exact digest through the agreed EC2/SSM deployment mechanism.
8. Wait for readiness and perform authorized health/model-info/predict smoke checks; retain deployment evidence.
9. On failure, restore the prior release's image/model/configuration and verify it. Do not merely relabel a new image latest.

References: [deployment environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [SSM Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html).

## Phase 9 — Retraining, candidate comparison and rollback evidence

The original final test period is already used. Preserve its report and the chosen model; do not tune new candidates against it and describe repeated results as an untouched test.

1. Define a separate, documented lifecycle-demo protocol and output root before fitting new demonstration models.
2. A valid historical exercise can use a champion trained on March-December 2013, a challenger trained through February 2014, and a common March-April 2014 evaluation window. Use different registered names/versions for this lifecycle demonstration. Label reused historical data as a controlled exercise.
3. Ensure neither model sees its evaluation labels in fitting. Avoid pretending the final 2015-trained model was already available in 2013.
4. Compare the candidate to the actually deployed demonstration champion on matched eligible origins and report each model's coverage plus the paired coverage.
5. Predefine error/validity/coverage/tolerance criteria and compare both absolute performance and degradation versus champion. Different training commits are normal here; require compatible feature contracts, not identical training Git SHAs.
6. Demonstrate one candidate rejected and one approved/published through the real workflow. Coordinate an actual deployment/rollback demonstration with Student 3.
7. For a drift-triggered scenario, have Student 3 emit a documented drift/quality event; Airflow ingests the event and initiates the approved protocol. Deduplicate repeated events and apply cooldowns.
8. Record champion/candidate versions, data cutoffs, evaluation set ID, decisions, reviewer, deployed digest, monitoring outcome and rollback result.

No retraining success may bypass mandatory gates because of deadline pressure. If a candidate loses, the valid outcome is to retain the champion and show that blocking behavior.

## Final Student 2 evidence

- Reviewed PRs and relevant conflict-handling evidence/procedure.
- Clean environment/container test and scan logs.
- dvc.yaml/dvc.lock plus actual reproduction and remote artifacts.
- Airflow schedule/trigger, retries, logs and KFP run ID.
- KFP compiled package, real graph execution and conditional blocking.
- CI pass/fail runs; protected release approval record.
- Candidate-versus-deployed comparison and controlled retraining.
- AWS deployment handoff and actual rollback verification with Student 3.

Store evidence under reports/automation and docs/automation, and update the team README with exact tested versions/commands. Describe anything unimplemented as remaining work.
