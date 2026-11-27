# Student 2: Run-specific validation and release handoff

## Intent

These are new Student 2 files. They do not overwrite `reports/experiments/quality_gate.json`, `final_test_report.json`, or registered Student 1 model versions.

- `verify_feast.py` compares Feast historical feature retrieval against Student 1's direct engineering; writes a run-specific equivalence artifact. Applying Feast alone is not proof of equivalence.
- `evaluate.py` checks actual hosted MLflow run metrics, lineage and quality policy, then writes `evaluation_manifest.json` and logs gate evidence. It never scores the final test set or approves a release.
- `compare_deployed.py` performs a separate lifecycle-holdout comparison if given explicit model versions, training cutoffs and an approved non-final-test evaluation dataset; it does **not** independently prove deployment identity.
- `release.py` fails closed unless a hosted registered model version shows an actual review, matching validation and test evidence, and an exact image digest. It only creates a handoff, not a deployment.

## Known limitations / pending work

Feast equivalence has to run locally. Current `training_manifest.json` reports `feast_status: not_applied_yet`, because its features were prepared directly; never relabel the old training run as Feast-trained. The candidate needs hosted MLflow verification. Student 3 must provide a real deployed-model reference, release approval and image digest before deployment, comparison/rollback can be claimed. DVC pipeline, Airflow, KFP and CI still require implementation and real execution.

Never put DagsHub tokens in Git, source, logs, screenshots, or chat. Revoke any exposed token and replace it securely.
