from pathlib import Path

from feast import FeatureStore

from feature_store.feature_repo.definitions import (
    hourly_features,
    hourly_source,
    pm25_service,
    project,
    station,
)
from src.features.export_feast import FEATURE_FILE


PROJECT_FOLDER = Path(__file__).resolve().parents[1]
REPO_PATH = PROJECT_FOLDER / "feature_store" / "feature_repo"


def main():
    if not FEATURE_FILE.exists():
        raise FileNotFoundError(
            "Export features first: python -m src.features.export_feast"
        )

    (REPO_PATH / "data").mkdir(parents=True, exist_ok=True)

    store = FeatureStore(repo_path=str(REPO_PATH))
    store.apply([
        project,
        station,
        hourly_source,
        hourly_features,
        pm25_service,
    ])

    registered = store.get_feature_view("air_quality_hourly")

    print("Feast registration completed.")
    print("Feature view:", registered.name)
    print("Registered model features:", len(registered.features))
    print("Entity join key:", station.join_key)
    print("Feature service:", pm25_service.name)


if __name__ == "__main__":
    main()
    