"""
ML Experiment extension (spec section 6F, "run ML models when appropriate").

Only triggers when there's a plausible regression target (the numeric
column the question is about) and at least 2 other numeric predictors —
running ML on 3 columns of synthetic data isn't meaningful, so this
agent says so explicitly rather than fabricating a model that looks
more rigorous than the data supports.
"""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from core.state import InvestigationState, Evidence
from tools import dataset_tools


MIN_ROWS_FOR_ML = 50


def run(state: InvestigationState, target_col: str) -> None:
    for path in state.datasets:
        try:
            df = dataset_tools.load(path)
        except Exception:
            continue
        if target_col not in df.columns:
            continue

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        predictors = [c for c in numeric_cols if c != target_col]
        data = df[predictors + [target_col]].dropna()

        if len(data) < MIN_ROWS_FOR_ML or len(predictors) < 2:
            state.emit("MLExperimentAgent",
                        f"Skipping ML experiment for '{target_col}': need >= {MIN_ROWS_FOR_ML} rows "
                        f"and >= 2 numeric predictors, have {len(data)} rows / {len(predictors)} predictors")
            continue

        X_train, X_test, y_train, y_test = train_test_split(
            data[predictors], data[target_col], test_size=0.25, random_state=42
        )
        model = RandomForestRegressor(n_estimators=200, random_state=42)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        r2 = r2_score(y_test, preds)
        mae = mean_absolute_error(y_test, preds)
        importances = dict(sorted(
            zip(predictors, model.feature_importances_.tolist()),
            key=lambda kv: kv[1], reverse=True,
        ))

        state.add_evidence(Evidence(
            kind="experiment",
            description=f"RandomForest regression predicting {target_col} from {predictors}",
            source=path,
            payload={
                "model": "RandomForestRegressor(n_estimators=200)",
                "n_train": len(X_train), "n_test": len(X_test),
                "r2_test": round(float(r2), 3), "mae_test": round(float(mae), 3),
                "feature_importances": {k: round(v, 3) for k, v in importances.items()},
            },
            strength=max(0.0, min(r2, 0.9)),
        ))
        state.emit("MLExperimentAgent",
                    f"Trained model for {target_col}: test R²={r2:.3f}, MAE={mae:.2f}, "
                    f"top predictor={next(iter(importances))}")
