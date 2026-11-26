# Student 2 — Phase 3 DVC reproduction

## Existing ownership

- `data/raw/PRSA_Data_Aotizhongxin_20130301-20170228.csv` remains managed by its existing `.dvc` pointer.
- `data/processed/hourly_features.parquet` remains managed by its existing `.dvc` pointer. **Do not** add either as a `dvc.yaml` output or remove/modify its pointer.
- `reports/automation/dvc/prepared/` is **new** DVC-cached output with deterministic, stable train/validation/test Parquet paths, separate from Student 1's processed artifact.
- `reports/automation/dvc/{feast_check,train_pointer,evaluation_pointer}.json` are noncached stage outputs. They refer to run-specific evidence under the gitignored `reports/automation/runs/` folder and to hosted MLflow runs. DVC cannot rehydrate hosted MLflow runs just by checking out a local JSON pointer.

## Prerequisites (in project root, Python 3.11 venv)

```powershell
$env:PYTHONPATH = (Get-Location).Path
dvc pull -r dagshub
feast -c .\feature_store\feature_repo apply
python -m pytest tests -q
```

Never put DagsHub credentials into tracked files or screenshots; revoke the earlier exposed token.

## Initial checks and execution

```powershell
python -m py_compile pipelines/dvc_pipeline.py
dvc dag
dvc repro --dry
dvc repro
```

Stage order: `prepare -> verify_feast -> train -> evaluate`. `prepare` caches a separate stable data snapshot; `verify_feast` verifies local Feast historical agreement; `train` creates a fresh unique run directory, logs its experiments to hosted MLflow, and writes a DVC pointer; `evaluate` checks hosted MLflow evidence and records a separate immutable gate-evaluation attempt. If all candidates fail, `evaluate` raises an error and DVC stops.

Inspect:

```powershell
dvc status
Get-Content reports/automation/dvc/train_pointer.json
Get-Content reports/automation/dvc/evaluation_pointer.json
git status --short
```

`dvc.lock` is generated only by a successful/partially successful `dvc repro`, not by writing `dvc.yaml`. DVC adds generated outs to `.gitignore` as appropriate. Do not manually remove its entries. Push artifacts in DVC cache **before** committing/merging a lockfile to a shared branch:

```powershell
dvc push -r dagshub
git status --short
```

Only push/commit after validating the complete run and reviewing staged filenames. Include `dvc.yaml`, `dvc.lock`, `pipelines/dvc_pipeline.py`, `.gitignore`, and `docs/automation/PHASE3_DVC.md`; do not commit `.dvc/config.local` or `reports/automation/runs/`.

## Controlled re-execution test

Change only a *development branch* `configs/quality_policy.yaml` policy value minimally, use `dvc repro --dry` to confirm only `evaluate` has changed; then restore policy via your editor and rerun the check. On a real policy-change reproduction, the evaluation stage writes a new immutable attempt and leaves earlier evidence alone.

**Limitations**

- This pipeline requires a live Feast local registry and authorized MLflow endpoint; it is not a pure offline or fully containerized workflow yet.
- `train_pointer` and `evaluation_pointer` use `cache: false` to avoid misrepresenting external MLflow artifacts as restorable DVC objects. Deleting local `reports/automation/runs/` may require a fresh training run; preserve selected manifests separately in the shared evidence store.
- Running `dvc repro` under a different Git commit can reuse the same prepared cached data but yields a new run-specific training SHA when training is actually re-executed.
- Running against data with a new DVC revision requires updating the versioned config and tracking metadata deliberately, not silently accepting a different dataset.
- The graph gates model **validation** and marks *eligible for review*, not approved for deployment. Release comparison/approval and Airflow/KFP/AWS are other phases.
