"""Fast structural checks for Student 2 DVC pipeline ownership."""
from pathlib import Path

import yaml


def test_dvc_pipeline_has_connected_stages():
    root = Path(__file__).resolve().parents[1]
    doc = yaml.safe_load((root / "dvc.yaml").read_text(encoding="utf-8"))
    stages = doc["stages"]
    assert list(stages) == ["prepare", "verify_feast", "train", "evaluate"]
    def deps(name):
        return set(stages[name]["deps"])
    assert "reports/automation/dvc/prepared" in deps("verify_feast")
    assert "reports/automation/dvc/feast_check.json" in deps("train")
    assert "reports/automation/dvc/train_pointer.json" in deps("evaluate")


def test_dvc_output_ownership_does_not_overlap_student1_data():
    root = Path(__file__).resolve().parents[1]
    doc = yaml.safe_load((root / "dvc.yaml").read_text(encoding="utf-8"))
    paths = []
    for stage in doc["stages"].values():
        for out in stage.get("outs", []):
            paths.append(out if isinstance(out, str) else next(iter(out)))
    assert len(paths) == len(set(paths))
    assert "data/processed/hourly_features.parquet" not in paths
    assert "data/raw/PRSA_Data_Aotizhongxin_20130301-20170228.csv" not in paths
    assert all(path.startswith("reports/automation/dvc/") for path in paths)
