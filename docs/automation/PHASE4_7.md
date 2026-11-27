# Student 2: Phase 4 Airflow bootstrap + Phase 7 CI

## Scope and honest status

- Airflow 3.4.0 official Docker Compose is downloaded by `setup_airflow.ps1` and pinned via `.env`. Do not overwrite Student 3's root Docker Compose file. The local Airflow stack is a **course development demo**, not a production installation.
- `ml_orchestrator_dag.py` initially validates the DVC raw CSV by MD5 and expected schema, and provides a stable `pipeline_run_id` in XCom. This is **historical replay** and is NOT current air-quality ingestion. Phase 6's actual KFP submission/polling is **not implemented** by this DAG.
- `.github/workflows/ci.yml` runs Python 3.11 tests, pip consistency, basic critical Ruff checks, `pip-audit`, and Bandit scans without secrets. A failed mandatory check must be fixed, not ignored. Once the PR passes, configure required GitHub branch-protection checks in repository settings.
- Linux/container portability test with DuckDB 1.5.6, controlled retry, actual KFP run, candidate/champion comparison, AWS approvals/deployment and rollback still need separate evidence.

## Windows 10/11 + Docker Desktop prerequisites

Confirm `docker version`, `docker compose version` and WSL2/Linux containers. Allocate sufficient Docker RAM (Airflow Compose stack typically needs **at least 4 GB**, more comfortable with 8 GB). DVC CSV must already be in project `data/raw/`. Use `dvc status` before starting.

From project root PowerShell (with Docker Desktop running):

```powershell
powershell -ExecutionPolicy Bypass -File .\pipelines\airflow\setup_airflow.ps1
Set-Location .\pipelines\airflow
docker compose up airflow-init
docker compose up -d
docker compose ps
```

Do not claim success until the API server/scheduler/worker/DAG processor are healthy, the UI at `http://localhost:8080` discovers `ml_orchestrator_dag`, and a manual run is successful. User/password in the official sample are intended for local demonstration only; do not expose this service publicly. After checking, return to repository root with `Set-Location ..\..`.

**Important:** The Compose override only mounts a read-only repository path into the worker. If your selected official Compose uses a different task executor or volume paths, review its worker service and adapt the override, then run `docker compose config`. A failure to see `/opt/mlops/...csv` is a mount issue, not a reason to skip validation.

## CI workflow

In project root:

```powershell
python -m py_compile pipelines/airflow/dags/ml_orchestrator_dag.py
Get-Content .github/workflows/ci.yml
# after reviewing modifications
git status --short
```

Push the CI workflow to `student2/automation`, open a PR to `main` and inspect **Actions**. The CI workflow on Linux could fail on dependency resolution, Ruff/Bandit or existing vulnerabilities; report/fix actual failures instead of using `continue-on-error`. For required status checks, a repository admin must configure branch protection. PR code gets no DagsHub/AWS secrets. A separate Docker build job is needed after Student 3 provides a tested Dockerfile.

## Security

Revoke previously exposed DagsHub tokens. Never stage `.dvc/config.local`, `.env`, generated Airflow config/logs, dataset files, or AWS credentials. Do not claim that a successful Airflow DAG is KFP integration or approved deployment.
