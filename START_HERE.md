# Start Here: Team Handoff

Prepared on 12 November 2026. These notes are specific to the existing air-quality project and course specification. They are implementation instructions, not evidence that Students 2/3 have already built or executed the remaining components.

## Read in this order

1. This file and [README.md](README.md).
2. [Shared integration contract](docs/TEAM_INTEGRATION.md).
3. Your own guide: [Student 2](docs/STUDENT2_GUIDE.md) or [Student 3](docs/STUDENT3_GUIDE.md).
4. [Feature contract](docs/FEATURES.md) and [Student 1 report](REPORT.md).
5. [Final demo checklist](docs/FINAL_DEMO_CHECKLIST.md).

## Verified starting point

- Student 1 documentation/code is available on student1/features, with documentation checkpoint dc6be1f.
- 40 tests passed locally, including real Feast materialization.
- Registered model URI: models:/air-quality-pm25-aotizhongxin/1.
- Final MAE 10.278413 and RMSE 18.737643 on 7,324 of 8,760 test hours.
- Historical recovery of code and both data artifacts is demonstrated.
- Model approval remains pending; deployment_approved=false.
- PR creation/review/merge has not been confirmed by execution evidence supplied to this chat.

## Language used in these guides

EXISTING means a component or command already supplied by Student 1. TO CREATE means a file or service that the responsible teammate must implement before its example command works. TEMPLATE means names such as YOUR_REGION must be replaced with the team's actual configuration.

The guides include procedures and small wiring examples; they are not a complete generated implementation of the remaining infrastructure.

## First actions together

1. Review the Student 1 PR; record reviewer comments and the merged commit.
2. Agree on the AWS account, one region, budget limit, authorized reviewer, and deployment endpoint.
3. Choose and record pinned Airflow/KFP/BentoML/Docker image versions using the linked official documentation. Keep the ML dependency snapshot and DuckDB 1.5.6 intact until an upgrade is actually tested.
4. Student 2 starts CI and orchestration while Student 3 starts model loading and Flask API work.
5. Agree on artifact paths, release-manifest fields, and API response metadata before joining the pipelines.

## Default architecture for this course

Run Airflow, standalone Kubeflow Pipelines, and the Kubernetes scaling demonstration locally. Use AWS ECR, one EC2 host running the approved container/Compose, a private S3 artifact bucket, and CloudWatch for the required cloud slice. Students can choose ECS/Fargate instead if they already have a tested setup; update deployment instructions consistently rather than mixing architectures.

Local infrastructure reduces the need to host a full orchestration platform on AWS. It does not replace the requirement for an actual working AWS-hosted prediction API.

## Evidence discipline

After each phase, save actual commands/output, commit SHA, image/model identifiers, and screenshots/run links. A YAML file alone is not a demonstrated workflow. A logged false/true flag alone is not an enforced security boundary.

The first API can provide explicitly labelled historical replay predictions using the real model and example inputs. Do not describe 2013-2017 data as live measurements. Live mode must reject these stale online features.

## Scope and estimates

Complete one verified vertical slice before adding optional tools. No Hugging Face model is needed for this tabular problem. Flask, the BentoML demonstration, Feast, Airflow, Kubeflow, AWS, Kubernetes, Prometheus/Grafana, tests, and controlled model lifecycle demonstrations remain required by the supplied specification.

Installation/network/hardware time is variable. Treat each phase's acceptance check as the stopping point; do not mark a phase complete because its configuration file exists.
