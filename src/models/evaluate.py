import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


def regression_metrics(actual, predicted):
    """Calculate metrics after checking prediction validity."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    if actual.ndim != 1 or actual.shape != predicted.shape:
        raise ValueError("Actual values and predictions must be matching vectors.")

    if len(actual) < 2:
        raise ValueError("At least two observations are required.")

    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Actual values and predictions must be finite.")

    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
        "negative_prediction_count": int((predicted < 0).sum()),
    }