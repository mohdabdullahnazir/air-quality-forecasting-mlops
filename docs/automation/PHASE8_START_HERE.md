# Phase 8 — Student 2 release automation starter (NOT a completed deployment)

## What this package does

- Adds a local read-only `scripts/phase8_preflight.py` for discovering existing evaluation manifests.
- Adds `.github/workflows/deploy.yml` with **manual** invocation, a main-branch guard, protected `production` environment, server-side MLflow registry and gate validation through existing `pipelines.common.release`, GitHub OIDC AWS credentials, and exact private-ECR digest existence check.
- Refuses to deploy when `scripts/student3_deploy.sh` does not exist; never treat a skipped or failed run as completed.

## Local start

From repo root run `python scripts/phase8_preflight.py`. Existing `pipelines/common/release.py`, `train.py`, `evaluate.py` and `compare_deployed.py` remain untouched.

## Before GitHub workflow can actually deploy

1. Merge reviewed code into `main` and confirm mandatory CI/security checks are green.
2. Set up GitHub **production** environment, with authorized reviewers, prevent self-review when supported, and restrict deployment branches. Note some private repository plans do **not** support required reviewers; use a different externally controlled approval mechanism instead, and do not enable credentials until it exists.
3. Student 1/authorized reviewer must record an actual review against the registered MLflow model version, quality/test run, dataset/feature lineage, reviewer identity and timestamps. Existing `release.py` MUST continue to fail until true.
4. Student 3 must provide a tested, pinned image already in a private ECR repository, `EC2_INSTANCE_ID`, and `scripts/student3_deploy.sh`. The script must check deployed model identity, authenticated health/model-info/predict endpoints, preserve the previous known-good release and do real rollback on failure. The workflow will fail if that script is missing.
5. Define GitHub environment variables `AWS_REGION`, `AWS_ROLE_ARN`, `ECR_REPOSITORY`, `EC2_INSTANCE_ID`, `MLFLOW_TRACKING_URI`. Define secrets `MLFLOW_TRACKING_USERNAME` and `MLFLOW_TRACKING_PASSWORD`. AWS keys should NOT be stored in GitHub. The AWS IAM OIDC trust policy must be restricted to the actual repo and environment `production`, including the correct modern `sub` format.
6. Configure least-privileged AWS IAM for only the ECR repository / selected EC2 SSM target, with deployment permissions needed by Student 3's adapter.
7. Manually dispatch **Phase 8 - Reviewed AWS deployment handoff** with a real run-scoped manifest, versioned model URI and image digest. Save actual approval/job/ECR/SSM/health/rollback screenshots and run IDs.

## Student 3 adapter contract

When called in CI, `scripts/student3_deploy.sh` receives `IMAGE_DIGEST`, `REGISTERED_MODEL_URI`, `AWS_REGION`, `ECR_REPOSITORY`, `EC2_INSTANCE_ID`, `EVALUATION_MANIFEST`, and AWS temporary credentials from OIDC. It must use AWS SSM or the team-approved mechanism to deploy the exact digest, not an unpinned `latest` tag. If model info, authenticated predict, health or readiness fails it must restore prior digest/model/config and exit nonzero. Do not log credentials.

## Important

- A successful local preflight is **not** proof of production approval.
- This starter **does not publish an image**: Student 3 supplies one that was built and tested in their CI.
- Do not use a Phase 5 smoke pipeline output as a substitute for MLflow training/evaluation evidence.
- Do not modify the immutable original final-test report for Phase 9.
