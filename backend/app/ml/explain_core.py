"""ClimateSense AI - lightweight local explanation (shared by notebook and API).

`permutation_shapley` estimates Shapley-style attributions for ONE prediction using
only `model.predict` (no extra dependencies):

  * baseline  = training-set mean of every feature (stored in feature_schema.json)
  * sampling  = random feature orderings; features are switched from baseline to the
                real value one by one and the change in the model output is credited
                to the feature that was switched.
  * property  = contributions always sum EXACTLY to  f(x) - f(baseline).

It is model-agnostic and works for Linear Regression, SVR and Random Forest.
The notebook compares it against the `shap` library as a sanity check.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def permutation_shapley(model, x_row: pd.Series, baseline: pd.Series, features: list[str],
                        n_permutations: int = 120, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    n = len(features)
    x = x_row[features].to_numpy(dtype=float)
    b = baseline[features].to_numpy(dtype=float)

    rows = []
    orders = []
    for _ in range(n_permutations):
        order = rng.permutation(n)
        orders.append(order)
        cur = b.copy()
        rows.append(cur.copy())  # all-baseline row
        for j in order:
            cur[j] = x[j]
            rows.append(cur.copy())
    batch = pd.DataFrame(np.vstack(rows), columns=features)
    preds = np.asarray(model.predict(batch), dtype=float).reshape(n_permutations, n + 1)

    contrib = np.zeros(n)
    for p, order in enumerate(orders):
        deltas = np.diff(preds[p])
        contrib[order] += deltas
    contrib /= n_permutations

    base_value = float(preds[:, 0].mean())
    prediction = float(preds[:, -1].mean())
    return {
        "base_value": base_value,
        "prediction": prediction,
        "contributions": {f: float(c) for f, c in zip(features, contrib)},
        "method": f"permutation-sampling Shapley ({n_permutations} orderings, training-mean baseline)",
    }
