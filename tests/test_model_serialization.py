import numpy as np
import skops.io
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor


def test_random_forest_serialization():
    x = np.arange(12, dtype=float).reshape(-1, 1)
    y = x[:, 0] + 1

    model = RandomForestRegressor(
        n_estimators=3,
        random_state=42,
    ).fit(x, y)

    restored = skops.io.loads(
        skops.io.dumps(model),
        trusted=["sklearn.tree._tree.Tree"],
    )

    np.testing.assert_allclose(
        model.predict(x),
        restored.predict(x),
    )


def test_xgboost_native_serialization(tmp_path):
    x = np.arange(12, dtype=float).reshape(-1, 1)
    y = x[:, 0] + 1

    model = XGBRegressor(
        n_estimators=3,
        max_depth=2,
        n_jobs=1,
        random_state=42,
    ).fit(x, y)

    model_file = tmp_path / "model.ubj"
    model.save_model(model_file)

    restored = XGBRegressor()
    restored.load_model(model_file)

    np.testing.assert_allclose(
        model.predict(x),
        restored.predict(x),
        rtol=1e-6,
    )