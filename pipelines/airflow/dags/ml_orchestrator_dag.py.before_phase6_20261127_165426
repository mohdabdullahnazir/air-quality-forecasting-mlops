"""Phase 4 only: verify a frozen historical dataset in Airflow.

This DAG deliberately DOES NOT submit a Kubeflow pipeline or approve deployment.
Phase 6 must add KFP submission, polling, and downstream failure propagation.
"""

import csv
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.sdk import dag, get_current_context, task

# Provided read-only to the worker via docker-compose.override.yaml.
RAW_DATA = Path(
    "/opt/mlops/data/raw/PRSA_Data_Aotizhongxin_20130301-20170228.csv"
)
EXPECTED_MD5 = "72a306d7a095e718c2b46ab482d5a1ac"
STATION = "Aotizhongxin"


@dag(
    dag_id="ml_orchestrator_dag",
    description="Phase 4: validate versioned historical replay, record trace ID (KFP not connected)",
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["student2", "historical-replay", "phase4"],
)
def ml_orchestrator_dag():
    @task(execution_timeout=timedelta(minutes=5))
    def validate_input_revision() -> dict:
        """Fail early if the mounted DVC dataset is absent, modified, or malformed."""
        if not RAW_DATA.is_file():
            raise FileNotFoundError(
                f"Missing {RAW_DATA}; mount the repo read-only and run dvc pull first"
            )
        digest = hashlib.md5(usedforsecurity=False)
        with RAW_DATA.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        actual = digest.hexdigest()
        if actual != EXPECTED_MD5:
            raise ValueError(f"Unexpected raw-data revision: {actual}")

        with RAW_DATA.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {"year", "month", "day", "hour", "PM2.5", "station"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError("Required raw-data columns missing")
            first = next(reader, None)
            if first is None or first.get("station") != STATION:
                raise ValueError("Unexpected station or empty raw dataset")
        return {"station": STATION, "raw_dvc_md5": actual, "mode": "historical_replay"}

    @task(execution_timeout=timedelta(minutes=2))
    def record_replay_run_id(validated: dict) -> dict:
        """Retry-safe ID derived from the Airflow DAG run ID; no duplicate model training."""
        context = get_current_context()
        airflow_run_id = context["dag_run"].run_id
        stable_id = hashlib.sha256(airflow_run_id.encode()).hexdigest()[:20]
        trace = {
            "pipeline_run_id": f"airflow-{stable_id}",
            "airflow_run_id": airflow_run_id,
            "data_revision": validated["raw_dvc_md5"],
            "mode": validated["mode"],
            "status": "validated_only_kfp_not_connected",
        }
        print(f"Phase 4 validated replay: {trace}")
        return trace

    record_replay_run_id(validate_input_revision())


ml_orchestrator_dag()
