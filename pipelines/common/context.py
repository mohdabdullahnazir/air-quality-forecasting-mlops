
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def create_run_context():
    config_path = PROJECT_ROOT / "configs" / "pipeline_config.yaml"

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("Invalid pipeline configuration")

    output_root = config["pipeline"]["output_root"]
    if not isinstance(output_root, str) or not output_root.strip():
        raise ValueError("Invalid output_root")

    base_dir = (PROJECT_ROOT / output_root).resolve()

    if not base_dir.is_relative_to(PROJECT_ROOT):
        raise ValueError("Output directory must remain inside project")

    timestamp = datetime.now(timezone.utc)
    run_id = (
        f"run-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}"
        f"-{uuid4().hex[:8]}"
    )

    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    git_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()

    context = {
        "pipeline_run_id": run_id,
        "created_at_utc": timestamp.isoformat(),
        "application_git_commit": git_sha,
        "station": config["data"]["station"],
        "raw_dvc_md5": config["data"]["raw_dvc_md5"],
        "feature_dvc_md5": config["data"]["feature_dvc_md5"],
        "forecast_horizon_hours": config["data"]["forecast_horizon_hours"],
        "output_dir": run_dir.relative_to(PROJECT_ROOT).as_posix(),
        "approval_status": "pending_review",
        "deployment_approved": False,
    }

    manifest_path = run_dir / "run_context.json"

    with manifest_path.open("x", encoding="utf-8") as file:
        json.dump(context, file, indent=2)

    return context


if __name__ == "__main__":
    result = create_run_context()
    print("Pipeline Run ID:", result["pipeline_run_id"])
    print("Output Folder:", result["output_dir"])
    print("Run context created successfully")
