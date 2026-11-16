# Code and Data Recovery

## Recorded identifiers

| Item | Recorded value |
| --- | --- |
| Training/recovery target commit | 7725c299b0cc2cb621967617d4126997f69eafd6 |
| Station CSV MD5 | 72a306d7a095e718c2b46ab482d5a1ac |
| Feature Parquet MD5 | 1904355bbc9682150d269d9060c6118a |
| Raw/feature sizes | 2,835,916 / 911,095 bytes |
| Recovery checkout used | D:\Abdullah\MLops\air-quality-recovery-demo |
| Working checkout | D:\Abdullah\MLops\MLops Project |
| Transcript | reports/reproducibility/recovery_demo.txt |
| Transcript commit | e3d80e4 |
| Observed recovery Python | 3.11.17 |
| Observed recovery DuckDB | 1.5.6 |

User-provided output confirms DVC status is up to date; both .dvc pointers contain the hashes above; recovered ingestion validates 35,064 rows and reports 925 missing PM2.5 readings.

The subsequent full transcript and reports/reproducibility/recovered_commit.txt confirmed the exact recovered HEAD. The confirmation file was committed as part of dc6be1f. To check it again:

~~~powershell
git -C "D:\Abdullah\MLops\air-quality-recovery-demo" rev-parse HEAD | Tee-Object -FilePath "D:\Abdullah\MLops\MLops Project\reports\reproducibility\recovered_commit.txt"
~~~

Confirmed full value: 7725c299b0cc2cb621967617d4126997f69eafd6. A different checkout should produce this value when repeating the same historical recovery.

## Repeat the recovery on another checkout

Use a new destination folder. The following paths are the original Windows demonstration paths; teammates should choose their own new destination.

~~~powershell
git clone --branch student1/features https://github.com/mohdabdullahnazir/air-quality-forecasting-mlops.git "D:\Abdullah\MLops\air-quality-recovery-demo"
Set-Location "D:\Abdullah\MLops\air-quality-recovery-demo"
git switch --detach 7725c299b0cc2cb621967617d4126997f69eafd6
git log -1 --oneline
~~~

The detached checkout inspects an immutable commit rather than moving the active development branch. Use an existing tested Python 3.11 environment for the demonstrated code/data recovery.

Authenticate the DVC remote using your own token and ignored .dvc/config.local. On the same trusted machine, the original exercise copied that ignored local configuration from the working checkout after checking git check-ignore .dvc/config.local. Do not copy credentials between teammates or include their contents in the transcript.

~~~powershell
python -m dvc pull -r dagshub
python -m dvc status
Get-Content "data/raw/PRSA_Data_Aotizhongxin_20130301-20170228.csv.dvc"
Get-Content "data/processed/hourly_features.parquet.dvc"
python -m src.data.ingestion
python --version
python -m pip show duckdb
~~~

DVC pull downloads the bytes referenced by the checked-out metadata and restores them to the workspace. It does not mean using whatever data happen to be newest on the remote.

## Scope of the evidence

This exercise recovers historical source code and its raw/feature data using the current tested environment. It does not demonstrate a separate clean installation of every dependency in the historical requirements file.

The current working dependency snapshot pins the materialization-compatible DuckDB 1.5.6 version. The earlier training snapshot was created before the DuckDB 2.0 materialization incompatibility was found. Preserve both historical Git records and the documented compatibility correction; do not silently rewrite the older commit.

For a stricter environment-recreation demonstration, Student 2/3 should build a clean environment/container from the current approved dependency file, run all 40 tests, pull the pinned data, reapply Feast, and verify predictions against the registry example. Capture installation/build logs and actual results.

## Model recovery

Configure DagsHub/MLflow authentication and load the pinned URI:

~~~python
import mlflow.sklearn
from src.models.tracking import configure_tracking

configure_tracking()
model = mlflow.sklearn.load_model(
    "models:/air-quality-pm25-aotizhongxin/1"
)
~~~

Use reports/models/prediction_example.json to verify inputs and expected outputs. That registry round-trip was already demonstrated by Student 1. The historical full training commit and the current loading/verification code have different Git identifiers; retain both in the audit trail.

## Official references

- [DVC pull](https://dvc.org/doc/command-reference/pull)
- [DVC checkout](https://dvc.org/doc/command-reference/checkout)
- [Git detached checkout with switch](https://git-scm.com/docs/git-switch)
- [DuckDB 1.5 timestamp semantics](https://duckdb.org/docs/1.5/sql/data_types/timestamp)
