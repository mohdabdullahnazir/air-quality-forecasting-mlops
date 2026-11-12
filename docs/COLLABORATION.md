# Collaboration and Conflict Handling

## Branch and PR procedure

Student 1 work is on student1/features. Earlier work also used student1/data-versioning. Do not assume either branch has been merged into main without checking GitHub.

1. Push the tested Student 1 branch.
2. Open a PR from student1/features into main. The compare page is:
   https://github.com/mohdabdullahnazir/air-quality-forecasting-mlops/compare/main...student1%2Ffeatures?expand=1
3. Use PR_STUDENT1.md as the description.
4. Have another team member review the code, feature/time contract, model evidence, and recovery evidence.
5. Record reviewer comments and address changes through normal commits.
6. Merge after required checks/review. Students 2/3 then start their branches from the agreed merged commit.

If an earlier data-versioning PR remains open and its changes are included in the final PR, coordinate whether to merge it first or close it as superseded. Do not duplicate or drop dataset metadata accidentally.

PR review and cloud deployment approval are separate decisions. A code review does not automatically set deployment_approved=true.

## Source/configuration conflicts

This is a documented procedure, not a claim that an actual merge conflict was already demonstrated.

1. Commit or safely preserve current work before beginning a merge.
2. Inspect Git's reported conflicting files.
3. Read both versions and decide the intended combined behavior.
4. Edit the files to remove conflict markers and implement that behavior.
5. Run relevant tests; run the full suite before merging shared validation/feature changes.
6. Stage resolved files, complete the merge commit, and document the resolution in the PR.

For feature changes, verify time alignment, null behavior, column order, and offline/online agreement. A syntactically merged feature function can still change what a fitted model means.

## Conflicts in add-generated .dvc files

A .dvc pointer describes the checksum, size, and path of actual data. Do not average, concatenate, or invent checksum values.

Choose one consistent data version after reviewing its source, schema, generation code, and intended use. Keep the pointer fields for that version together. Then:

~~~powershell
python -m dvc pull -r dagshub
python -m dvc status
python -m src.data.ingestion
python -m pytest tests -q
~~~

If both raw datasets must be combined, recover both versions into separate working locations, define a deterministic merge policy for station/time duplicates and conflicting readings, validate the resulting data, and run dvc add on the merged output. Push its cache before sharing the new Git pointer. Regenerate dependent features and create a new model evaluation record; the old model remains tied to its original versions.

The current raw station dataset is a fixed historical source. A claimed new ingestion version must have a documented reason; do not modify it merely to create version-history screenshots.

## Future pipeline metadata

Student 2 will add dvc.yaml and dvc.lock. Reconcile stage commands, dependencies, and parameters first; regenerate the lock through an actual successful reproduction rather than hand-editing checksums.

The existing feature Parquet currently has standalone .dvc ownership. When moving that output into a DVC pipeline stage, arrange one owner for the output. Preserve the actual artifact and cache while migrating metadata; do not leave duplicate DVC output definitions.

## Evidence to retain

- PR URL, source/base commit, reviewer, and actual review comments.
- Test/CI output for the merged revision.
- If a conflict occurs: affected files, chosen behavior/data version, and verification output.
- If a conflict is simulated: explicitly label it as a controlled exercise.

The course requires a documented conflict-handling procedure. Confirm with the instructor whether an executed conflict exercise is additionally required; do not fabricate one.

## Reference

[Official DVC merge-conflict guidance](https://doc.dvc.org/user-guide/how-to/resolve-merge-conflicts)
