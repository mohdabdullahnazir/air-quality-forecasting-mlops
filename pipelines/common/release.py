"""Verify server-side review evidence before creating a release handoff.

This does not deploy or approve any model. It rejects local self-approval,
missing test-gate evidence, unapproved registry tags and incomplete image IDs.
"""
import argparse
import json
import re

from pipelines.common.context import PROJECT_ROOT

ROOT = (PROJECT_ROOT / "reports/automation/runs").resolve()


def verify_handoff(evaluation_manifest, registered_model_uri, image_digest):
    path = (PROJECT_ROOT / evaluation_manifest).resolve()
    if not path.is_relative_to(ROOT) or path.name != "evaluation_manifest.json":
        raise ValueError("Expected a run-scoped evaluation_manifest.json")
    gate = json.loads(path.read_text(encoding="utf-8"))
    candidate = gate.get("selected_candidate")
    if gate.get("status") != "eligible_for_review" or not candidate:
        raise ValueError("Validation gate has not passed")
    if gate.get("deployment_approved") is not False:
        raise ValueError("Locally forged approval state")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
        raise ValueError("Use the actual reviewed sha256 image digest")
    match = re.fullmatch(r"models:/([^/]+)/([1-9][0-9]*)", registered_model_uri)
    if not match:
        raise ValueError("Require a pinned REGISTERED model version URI")

    from mlflow.tracking import MlflowClient
    from src.models.tracking import configure_tracking
    configure_tracking()
    client = MlflowClient()
    gate_run = client.get_run(gate["gate_run_id"])
    if (gate_run.info.status != "FINISHED"
            or gate_run.data.tags.get("run_type") != "automation_validation_gate"
            or gate_run.data.tags.get("pipeline_run_id") != gate["pipeline_run_id"]
            or gate_run.data.tags.get("quality_gate_passed") != "true"):
        raise PermissionError("Hosted quality-gate evidence not authoritative")
    name, version = match.groups()
    registered = client.get_model_version(name, version)
    tags = registered.tags
    required = {
        "approval_status": "approved_for_course_demo",
        "deployment_approved": "true",
        "prediction_check": "passed",
        "validation_gate_passed": "true",
        "test_gate_passed": "true",
        "source_model_uri": candidate["model_uri"],
        "source_training_run": candidate["run_id"],
        "dataset_dvc_md5": gate["data_revision"],
    }
    for k, expected in required.items():
        if tags.get(k) != expected:
            raise PermissionError(f"Server-side model version tag missing or mismatched: {k}")
    if not tags.get("reviewed_by") or not tags.get("reviewed_at"):
        raise PermissionError("No real recorded reviewer identity/time")
    source_eval_id = tags.get("test_evaluation_run")
    if not source_eval_id:
        raise PermissionError("No hosted final test evidence")
    tested = client.get_run(source_eval_id)
    if (tested.info.status != "FINISHED"
            or tested.data.tags.get("test_gate_passed") != "true"
            or tested.data.tags.get("source_training_run") != candidate["run_id"]
            or tested.data.tags.get("source_model_uri") != candidate["model_uri"]):
        raise PermissionError("Hosted final test evidence does not match candidate")
    result = {
        "pipeline_run_id": gate["pipeline_run_id"],
        "validation_gate_run_id": gate["gate_run_id"],
        "test_evaluation_run_id": source_eval_id,
        "model_uri": registered_model_uri,
        "source_training_run_id": candidate["run_id"],
        "source_model_uri": candidate["model_uri"],
        "raw_dvc_md5": gate["data_revision"],
        "image_digest": image_digest,
        "reviewed_by": tags["reviewed_by"],
        "reviewed_at": tags["reviewed_at"],
        "hosted_registry_tags_report_approval": True,
        "protected_ci_approval_independently_verified": False,
        "image_digest_existence_verified": False,
        "deployment_executed": False,
        "status": "handoff_pending_protected_ci_review_not_deployed",
    }
    output = path.parent / "release_handoff.json"
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--evaluation-manifest", required=True)
    p.add_argument("--registered-model-uri", required=True)
    p.add_argument("--image-digest", required=True)
    a = p.parse_args()
    print("Verified handoff:", verify_handoff(a.evaluation_manifest,
                                               a.registered_model_uri,
                                               a.image_digest))
    print("Deployment has NOT been executed by this command")
