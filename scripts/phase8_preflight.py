"""Phase 8 local read-only preflight. Does NOT approve or deploy a model."""
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = (PROJECT_ROOT / 'reports' / 'automation' / 'runs').resolve()


def inspect_manifest(path: Path) -> tuple[list[str], dict]:
    problems = []
    path = path.resolve()
    if not path.is_relative_to(RUN_ROOT) or path.name != 'evaluation_manifest.json':
        raise ValueError('Manifest must be an evaluation_manifest.json under reports/automation/runs')
    gate = json.loads(path.read_text(encoding='utf-8'))
    required = ('pipeline_run_id', 'gate_run_id', 'data_revision')
    for item in required:
        if not gate.get(item):
            problems.append(f'Missing: {item}')
    if gate.get('status') != 'eligible_for_review':
        problems.append(f"Model not eligible_for_review (status={gate.get('status')!r})")
    candidate = gate.get('selected_candidate')
    if not isinstance(candidate, dict) or not candidate.get('model_uri') or not candidate.get('run_id'):
        problems.append('No selected candidate model_uri / run_id')
    if gate.get('deployment_approved') is not False:
        problems.append('Local deployment_approved must be false (approval is server-side only)')
    return problems, gate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', help='A run-scoped evaluation_manifest.json')
    args = parser.parse_args()
    paths = [Path(args.manifest)] if args.manifest else sorted(RUN_ROOT.rglob('evaluation_manifest.json'))
    if not paths:
        print('BLOCKED: No evaluation manifests found. Complete ML evaluation first.')
        return 2
    for path in paths:
        print('\n===', path, '===')
        try:
            problems, gate = inspect_manifest(path)
        except (ValueError, OSError, json.JSONDecodeError, KeyError) as exc:
            problems = [str(exc)]
            gate = {}
        print('Pipeline run:', gate.get('pipeline_run_id', '(missing)'))
        print('Evaluation status:', gate.get('status', '(missing)'))
        print('Candidate:', (gate.get('selected_candidate') or {}).get('model_uri', '(missing)') if isinstance(gate.get('selected_candidate'), dict) else '(missing)')
        for problem in problems:
            print('BLOCKED:', problem)
        if not problems:
            print('READY FOR REVIEW ONLY (not approved, not deployed)')
    print('\nIMPORTANT: Approval must be recorded by a real reviewer and checked against hosted MLflow.')
    print('Student 3 must provide tested ECR image digest, EC2/SSM deployment and rollback commands.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
