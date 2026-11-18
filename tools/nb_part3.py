"""Notebook cells, sections 7-10."""
CELLS = []
def md(t): CELLS.append(("md", t.strip("\n")))
def code(t): CELLS.append(("code", t.strip("\n")))

md(r'''## Section 7 — Evaluation metrics
For every model we compute three standard regression metrics (all in the units of the target):

| Metric | Meaning | Units | Better is |
|---|---|---|---|
| **MAE** — Mean Absolute Error | average size of the error, `mean(|actual − predicted|)` | °C | lower |
| **MSE** — Mean Squared Error | average of squared errors; punishes large misses (heat-wave misses!) | °C² | lower |
| **R²** — Coefficient of determination | share of the variation in Tmax the model explains (1 = perfect, 0 = no better than predicting the mean) | – | higher |

**Selection rule:** the best model is the ML algorithm with the **lowest validation MAE**. Only after that decision do we compute test-set scores; the test set never influences the choice. The *persistence baseline* ("tomorrow = today") is reported next to the models, so we can see whether machine learning really adds value.''')

code(r'''
ML_NAMES = list(CANDIDATES)
persistence = lambda df: df["tmax_d0"].to_numpy()

results = {}
for name, model in fitted.items():
    results[name] = {"train": regression_metrics(y_train, model.predict(X_train)),
                     "validation": regression_metrics(y_val, model.predict(X_val))}
baseline = {"validation": regression_metrics(y_val, persistence(val_df))}

# ---- MODEL SELECTION: validation MAE only -------------------------------------------------
best_name = min(ML_NAMES, key=lambda n: results[n]["validation"]["mae"])
best_model = fitted[best_name]
print(f"Selected model (lowest validation MAE): {best_name}  ({results[best_name]['validation']['mae']:.3f} °C)")

# ---- Only now evaluate on the untouched test set --------------------------------------------
for name, model in fitted.items():
    results[name]["test"] = regression_metrics(y_test, model.predict(X_test))
baseline["test"] = regression_metrics(y_test, persistence(test_df))

rows = []
for name in ML_NAMES + ["Persistence baseline"]:
    r = baseline if name.startswith("Persistence") else results[name]
    row = {"Model": name}
    if name in results: row["Train MAE"] = results[name]["train"]["mae"]
    for part in ("validation", "test"):
        for m in ("mae", "mse", "r2"):
            row[f"{part[:3].title()} {m.upper()}"] = r[part][m]
    rows.append(row)
comparison = pd.DataFrame(rows).set_index("Model")
display(comparison.round(3).style.highlight_min(subset=["Val MAE", "Val MSE", "Tes MAE", "Tes MSE"], color="#bbf7d0")
        .highlight_max(subset=["Val R2", "Tes R2"], color="#bbf7d0"))

imp_val  = 100 * (1 - results[best_name]["validation"]["mae"] / baseline["validation"]["mae"])
imp_test = 100 * (1 - results[best_name]["test"]["mae"] / baseline["test"]["mae"])
print(f"\nBest model vs persistence baseline: validation MAE {imp_val:+.1f}% , test MAE {imp_test:+.1f}% "
      f"({'better' if imp_test > 0 else 'WORSE'} than 'tomorrow = today').")
if imp_test <= 0:
    print("⚠ The ML model does not beat persistence on the test set - report this honestly.")
''')

code(r'''
# Model-wise evaluation chart
names = ML_NAMES + ["Persistence"]
def pick(part, m): return [results[n][part][m] for n in ML_NAMES] + [baseline[part][m]]
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
x = np.arange(len(names)); w = 0.38
for ax, (m, title) in zip(axes, [("mae", "MAE (°C) ↓"), ("mse", "MSE (°C²) ↓"), ("r2", "R² ↑")]):
    ax.bar(x - w / 2, pick("validation", m), w, label="Validation", color="#14b8a6")
    ax.bar(x + w / 2, pick("test", m), w, label="Test", color="#0f766e")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=15); ax.set_title(title); ax.legend()
fig.suptitle(f"Model-wise evaluation — best by validation MAE: {best_name}", fontweight="bold")
save_fig("eval_01_model_comparison")

# Actual vs predicted (test set)
fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharex=True, sharey=True)
lims = [min(y_test.min(), 15), y_test.max() + 1]
for ax, name in zip(axes, ML_NAMES):
    p = fitted[name].predict(X_test)
    ax.scatter(y_test, p, s=6, alpha=0.4, color="#0d9488"); ax.plot(lims, lims, "k--", lw=1)
    ax.set(title=f"{name}  (test MAE {results[name]['test']['mae']:.2f} °C)", xlabel="Actual next-day Tmax (°C)", ylabel="Predicted (°C)")
save_fig("eval_02_actual_vs_predicted")
''')

code(r'''
# Residual plots for the selected model (test set). residual = actual - predicted
pred_test = best_model.predict(X_test); resid_test = y_test.to_numpy() - pred_test
fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
sns.histplot(resid_test, bins=40, kde=True, color="#0d9488", ax=axes[0]); axes[0].axvline(0, color="k", ls="--")
axes[0].set(title="Residual distribution", xlabel="actual − predicted (°C)")
axes[1].scatter(pred_test, resid_test, s=6, alpha=0.4, color="#0d9488"); axes[1].axhline(0, color="k", ls="--")
axes[1].set(title="Residuals vs predicted", xlabel="predicted (°C)", ylabel="residual (°C)")
sns.boxplot(data=pd.DataFrame({"city": test_df["city"], "residual": resid_test}), x="city", y="residual", palette=palette, ax=axes[2])
axes[2].axhline(0, color="k", ls="--"); axes[2].set(title="Residuals by city", xlabel="")
fig.suptitle(f"Residual analysis — {best_name}", fontweight="bold")
save_fig("eval_03_residuals")

per_city_mae = {c: float(mean_absolute_error(g[fe.TARGET], best_model.predict(g[fe.FEATURES]))) for c, g in test_df.groupby("city")}
print("Test MAE per city (°C):", {k: round(v, 2) for k, v in per_city_mae.items()})
print("Mean residual (bias): %.3f °C | residual std: %.3f °C" % (resid_test.mean(), resid_test.std()))

# Empirical prediction interval: 5th/95th percentile of VALIDATION residuals (calibration), coverage checked on TEST
resid_val = y_val.to_numpy() - best_model.predict(X_val)
lo_off, hi_off = float(np.quantile(resid_val, 0.05)), float(np.quantile(resid_val, 0.95))
coverage = float(np.mean((y_test.to_numpy() >= pred_test + lo_off) & (y_test.to_numpy() <= pred_test + hi_off)))
prediction_interval = {"level": 0.90, "lower_offset": lo_off, "upper_offset": hi_off, "calibrated_on": "validation residuals (5th-95th percentile)",
                       "test_coverage": coverage, "method": "empirical residual quantiles; interval = prediction + offset"}
print(f"90% empirical interval: [{lo_off:+.2f}, {hi_off:+.2f}] °C around the prediction | observed coverage on test: {coverage:.1%}")
''')

code(r'''
MODEL_DESCRIPTIONS = {
    "Linear Regression": "Straight-line model on scaled features (imputer → StandardScaler → LinearRegression).",
    "SVR (RBF)": "Support Vector Regression with RBF kernel; inputs and target standardised; C, epsilon, gamma tuned with time-aware CV.",
    "Random Forest": "Ensemble of decision trees averaged; depth, leaf size, trees and max_features tuned with time-aware CV.",
}
FIGURES = []
def jsonable(o):
    if isinstance(o, dict): return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)): return o.item()
    if isinstance(o, (np.ndarray,)): return o.tolist()
    if isinstance(o, (pd.Timestamp, date)): return str(o)[:10]
    return o

hist_counts, hist_edges = np.histogram(resid_test, bins=30)
rng = np.random.default_rng(SEED)
sel = rng.choice(len(test_df), size=min(400, len(test_df)), replace=False)
metrics_doc = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "units": {"mae": "°C", "mse": "°C²", "r2": "dimensionless"},
    "selection_rule": "lowest validation MAE among the three ML algorithms; test set untouched until selection",
    "best_model": {"name": best_name, "validation": results[best_name]["validation"], "test": results[best_name]["test"]},
    "models": {n: {**results[n], **search_info[n], "description": MODEL_DESCRIPTIONS[n]} for n in ML_NAMES},
    "baseline_persistence": {**baseline, "description": "Predict tomorrow's Tmax = today's Tmax"},
    "improvement_over_persistence_pct": {"validation_mae": imp_val, "test_mae": imp_test},
    "split": split_info,
    "per_city_test_mae": per_city_mae,
    "prediction_interval": prediction_interval,
    "test_scatter": [{"actual": round(float(y_test.iloc[i]), 2), "predicted": round(float(pred_test[i]), 2), "city": test_df["city"].iloc[i]} for i in sel],
    "residual_histogram": {"bin_edges": hist_edges.round(3).tolist(), "counts": hist_counts.tolist(), "mean": float(resid_test.mean()), "std": float(resid_test.std())},
}
(MODEL_DIR / "model_metrics.json").write_text(json.dumps(jsonable(metrics_doc), indent=2, ensure_ascii=False))
print("saved:", MODEL_DIR / "model_metrics.json")
''')

md(r'''## Section 8 — Explainable AI (XAI)
A forecast is only useful if people can ask **"why?"**. We use four complementary views:

1. **Random Forest impurity importance** — how much each feature reduced error inside the forest's trees (fast, but biased towards features with many distinct values).
2. **Permutation importance (on the test set)** — shuffle one feature at a time and measure how much the MAE gets worse. Model-agnostic and measured on unseen data.
3. **SHAP values** — game-theory-based contribution of each feature to each individual prediction, in °C.
4. **Local explanation** for single predictions — which features pushed *this* forecast up or down.

All values below are computed from the actual fitted models.''')

code(r'''
from sklearn.inspection import permutation_importance

# 8.1 Random Forest impurity importance (the RF candidate is always fitted, even if it is not the best model)
rf_model = fitted["Random Forest"].named_steps["rf"]
rf_imp = pd.Series(rf_model.feature_importances_, index=fe.FEATURES).sort_values(ascending=False)

# 8.2 Permutation importance of the SELECTED model on the test set
pi = permutation_importance(best_model, X_test, y_test, scoring="neg_mean_absolute_error",
                            n_repeats=10, random_state=SEED, n_jobs=-1)
perm = pd.DataFrame({"mean": pi.importances_mean, "std": pi.importances_std}, index=fe.FEATURES).sort_values("mean", ascending=False)

fig, axes = plt.subplots(1, 2, figsize=(15, 6))
rf_imp[::-1].plot.barh(ax=axes[0], color="#14b8a6"); axes[0].set_title("Random Forest impurity importance"); axes[0].set_xlabel("importance")
axes[1].barh(perm.index[::-1], perm["mean"][::-1], xerr=perm["std"][::-1], color="#0f766e")
axes[1].set_title(f"Permutation importance — {best_name} (test set)"); axes[1].set_xlabel("increase in MAE when shuffled (°C)")
save_fig("xai_01_feature_importance")
print("Top-5 by permutation importance:\n", perm.head(5).round(4).to_string())
''')

code(r'''
# 8.3 SHAP (global + local). Tree models use the exact TreeExplainer; others use KernelExplainer.
X_expl = X_test.sample(min(150, len(X_test)), random_state=SEED).reset_index(drop=True)
shap_values, shap_base, shap_method = None, None, None

if SHAP_OK:
    try:
        if best_name == "Random Forest":
            explainer = shap.TreeExplainer(best_model.named_steps["rf"])
            Xt = best_model[:-1].transform(X_expl)
            shap_values = np.asarray(explainer.shap_values(Xt))
            shap_base = float(np.ravel(explainer.expected_value)[0]); shap_method = "SHAP TreeExplainer (exact)"
        else:
            background = shap.kmeans(X_train, 25)
            f = lambda a: best_model.predict(pd.DataFrame(a, columns=fe.FEATURES))
            explainer = shap.KernelExplainer(f, background)
            X_expl = X_expl.iloc[:80]
            shap_values = np.asarray(explainer.shap_values(X_expl, nsamples=200, silent=True))
            shap_base = float(np.ravel(explainer.expected_value)[0]); shap_method = "SHAP KernelExplainer (approximate, 25-cluster background)"
    except Exception as exc:
        print("SHAP failed, using the built-in explainer instead:", exc); shap_values = None

if shap_values is None:      # fallback: our own permutation-Shapley (same method the API uses)
    X_expl = X_expl.iloc[:60]
    base_series = X_train.mean()
    res = [explain_core.permutation_shapley(best_model, X_expl.iloc[i], base_series, fe.FEATURES, n_permutations=30, seed=SEED) for i in range(len(X_expl))]
    shap_values = np.array([[r["contributions"][f] for f in fe.FEATURES] for r in res])
    shap_base = float(np.mean([r["base_value"] for r in res])); shap_method = "built-in permutation-sampling Shapley (30 orderings)"
print("Explanation method:", shap_method, "| rows explained:", len(X_expl), "| base value: %.2f °C" % shap_base)

mean_abs = pd.Series(np.abs(shap_values).mean(axis=0), index=fe.FEATURES).sort_values(ascending=False)
if SHAP_OK and "SHAP" in shap_method:
    plt.figure(); shap.summary_plot(shap_values, X_expl, feature_names=fe.FEATURES, show=False); plt.title("SHAP summary (beeswarm)")
    save_fig("xai_02_shap_summary")
fig, ax = plt.subplots(figsize=(8, 6)); mean_abs[::-1].plot.barh(ax=ax, color="#14b8a6")
ax.set(title="Mean |SHAP value| — average impact on predicted Tmax", xlabel="°C"); save_fig("xai_03_shap_bar")
''')

code(r'''
# 8.4 Local explanations for individual predictions (same lightweight method as the live API)
base_series = X_train.mean()
order = np.argsort(pred_test)
picks = {"Hottest predicted day": order[-1], "Typical day": order[len(order) // 2], "Coolest predicted day": order[0]}
local_examples = []
for label, i in picks.items():
    res = explain_core.permutation_shapley(best_model, X_test.iloc[i], base_series, fe.FEATURES, n_permutations=150, seed=SEED)
    contrib = pd.Series(res["contributions"]).sort_values(key=np.abs, ascending=False)
    local_examples.append({"label": label, "city": test_df["city"].iloc[i], "date": str(test_df["target_date"].iloc[i].date()),
                           "actual_c": float(y_test.iloc[i]), "predicted_c": float(pred_test[i]), "base_value_c": res["base_value"],
                           "contributions": {k: float(v) for k, v in contrib.head(8).items()}})
    print(f"\n{label}: {test_df['city'].iloc[i]} → {test_df['target_date'].iloc[i].date()} | actual {y_test.iloc[i]:.1f} °C | predicted {pred_test[i]:.1f} °C | base {res['base_value']:.1f} °C")
    print(contrib.head(6).round(2).to_string())

fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
for ax, ex in zip(axes, local_examples):
    s = pd.Series(ex["contributions"])[::-1]
    ax.barh(s.index, s.values, color=["#ef4444" if v > 0 else "#3b82f6" for v in s.values])
    ax.set_title(f"{ex['label']}\n{ex['city']} {ex['date']} — pred {ex['predicted_c']:.1f} °C"); ax.set_xlabel("contribution (°C)")
save_fig("xai_04_local_explanations")

# Sanity check: does our lightweight method agree with SHAP for the same row?
if SHAP_OK and "SHAP" in shap_method:
    i0 = 0
    ours = explain_core.permutation_shapley(best_model, X_expl.iloc[i0], base_series, fe.FEATURES, n_permutations=150, seed=SEED)["contributions"]
    rho = pd.Series(ours).corr(pd.Series(dict(zip(fe.FEATURES, shap_values[i0]))), method="spearman")
    print(f"\nAgreement between the API's explainer and SHAP on one row (Spearman ρ): {rho:.2f}")
''')

md(r'''### How to read these plots (for the viva)
* **Bars to the right / red** = the feature pushed the predicted temperature *up* relative to an average day; **left / blue** = pushed it *down*.
* Expect *recent temperature* features to dominate (persistence), and humidity / cloud / radiation / season to adjust the forecast. Check the printed top-5 lists above to see what **your** run found — do not assume.
* Explanations describe the **model's behaviour**, not guaranteed physical causation.''')

md(r'''## Section 9 — Temperature anomalies and heat categories

**Temperature anomaly = Predicted temperature − historical seasonal normal.**

* The *seasonal normal* is the mean daily-maximum temperature for that calendar day in **1991–2020** (the WMO climate-normal period).
* Data product: **ERA5-Land** reanalysis through the Open-Meteo *Historical Weather API* (`models=era5_land`; ~0.1° ≈ 9–11 km grid, hourly, 1950-present, produced by ECMWF/Copernicus). One consistent product is used for the whole baseline.
* A single calendar day has only 30 values, so we pool a **±7-day window (15 days × 30 years = 450 values)** around each day-of-year. From these we get the mean (normal), standard deviation, and the **90th and 95th percentile thresholds**.
* **Product consistency:** the model's target comes from the Open-Meteo forecast archive, not ERA5-Land. We measure the average difference between both products over the overlap (2022 → today) per city and shift the normals by it, so anomalies compare like with like. The raw ERA5-Land normal and the offset are kept in the CSV.

**Heat categories are project-defined, not official IMD warnings:**
`Normal` (< normal + 1.5 °C) · `Elevated` (≥ +1.5 °C anomaly) · `High` (≥ 90th percentile) · `Severe` (≥ 95th percentile).''')

code(r'''
NORMAL_START, NORMAL_END, WINDOW_HALF, ERA_MODEL = date(1991, 1, 1), date(2020, 12, 31), 7, "era5_land"
APPLY_PRODUCT_OFFSET = True

def fetch_era_daily(city, start, end):
    c = fe.CITIES[city]; parts, meta = [], {}
    cur = start
    while cur <= end:
        stop = min(date(cur.year + 9, 12, 31), end)
        js = get_json(ERA5_URL, dict(latitude=c["lat"], longitude=c["lon"], start_date=cur.isoformat(), end_date=stop.isoformat(),
                                     daily="temperature_2m_max", models=ERA_MODEL, timezone=fe.TIMEZONE))
        unit = (js.get("daily_units") or {}).get("temperature_2m_max")
        if unit != "°C": raise ApiError(f"ERA unit problem: {unit}")
        parts.append(pd.DataFrame({"date": pd.to_datetime(js["daily"]["time"]), "era_tmax": js["daily"]["temperature_2m_max"]}))
        meta = {"grid_latitude": js.get("latitude"), "grid_longitude": js.get("longitude"), "elevation_m": js.get("elevation")}
        cur = stop + timedelta(days=1); time.sleep(1.0)
    return pd.concat(parts, ignore_index=True), meta

def climatology(era_df, half=WINDOW_HALF):
    s = era_df.dropna(subset=["era_tmax"]).copy(); s["doy"] = fe.day_of_year_365(s["date"])
    by_doy = {d: g["era_tmax"].to_numpy() for d, g in s.groupby("doy")}
    out = []
    for d in range(1, 366):
        idx = [((d - 1 + k) % 365) + 1 for k in range(-half, half + 1)]
        v = np.concatenate([by_doy[i] for i in idx if i in by_doy])
        out.append({"doy": d, "normal_tmax": v.mean(), "std_tmax": v.std(ddof=1), "p90_tmax": np.percentile(v, 90),
                    "p95_tmax": np.percentile(v, 95), "n_samples": len(v)})
    return pd.DataFrame(out)

normal_frames, era_meta, offsets = [], {}, {}
overlap_end = min(TRAIN_END, date.today() - timedelta(days=8))     # ERA5 lags ~5 days
for city in fe.CITIES:
    era_base, meta = fetch_era_daily(city, NORMAL_START, NORMAL_END)
    clim = climatology(era_base); clim.insert(0, "city", city)
    era_recent, _ = fetch_era_daily(city, TRAIN_START, overlap_end)
    both = daily[daily["city"] == city][["date", "tmax"]].merge(era_recent, on="date").dropna()
    diff = both["tmax"] - both["era_tmax"]
    offsets[city] = {"mean_offset_c": float(diff.mean()), "rmsd_c": float(np.sqrt((diff ** 2).mean())), "n_days": int(len(both)),
                     "monthly_offset_c": diff.groupby(both["date"].dt.month).mean().round(2).to_dict()}
    era_meta[city] = {**meta, "baseline_days": int(era_base["era_tmax"].notna().sum())}
    clim["normal_tmax_era5land_raw"] = clim["normal_tmax"]
    clim["product_offset_c"] = offsets[city]["mean_offset_c"] if APPLY_PRODUCT_OFFSET else 0.0
    for col in ("normal_tmax", "p90_tmax", "p95_tmax"): clim[col] = clim[col] + clim["product_offset_c"]
    normal_frames.append(clim)
    print(f"{city:<10} baseline days {era_meta[city]['baseline_days']:,} | product offset (forecast archive − ERA5-Land) "
          f"{offsets[city]['mean_offset_c']:+.2f} °C (RMSD {offsets[city]['rmsd_c']:.2f}, n={offsets[city]['n_days']})")

normals = pd.concat(normal_frames, ignore_index=True)
assert normals.groupby("city").size().eq(365).all() and normals[["normal_tmax", "p90_tmax", "p95_tmax"]].notna().all().all()
normals.round(3).to_csv(MODEL_DIR / "city_climate_normals.csv", index=False)
display(normals[normals["doy"].isin([15, 105, 135, 195, 300])].round(1))
''')

code(r'''
# Visualise the normals + percentile thresholds, and the seasonal product offset
fig, axes = plt.subplots(2, 3, figsize=(16, 7), sharex=True)
for ax, (city, g) in zip(axes.ravel(), normals.groupby("city")):
    ax.fill_between(g["doy"], g["normal_tmax"], g["p95_tmax"], color="#fecaca", alpha=0.6, label="normal → 95th pct")
    ax.plot(g["doy"], g["normal_tmax"], color="#0f766e", label="1991–2020 normal"); ax.plot(g["doy"], g["p90_tmax"], "--", color="#f59e0b", label="90th pct")
    ax.plot(g["doy"], g["p95_tmax"], "--", color="#ef4444", label="95th pct"); ax.set_title(city)
axes[0, 0].legend(fontsize=7); fig.suptitle("City climate normals of daily Tmax (ERA5-Land, window ±7 days)", fontweight="bold")
save_fig("climate_01_normals")

fig, ax = plt.subplots(figsize=(9, 4))
for city in fe.CITIES:
    m = pd.Series(offsets[city]["monthly_offset_c"]); ax.plot(m.index, m.values, marker="o", label=city, color=palette[city])
ax.axhline(0, color="k", lw=0.8); ax.set(title="Product offset by month: forecast-archive Tmax − ERA5-Land Tmax (2022→)", xlabel="month", ylabel="°C"); ax.legend(ncol=3)
save_fig("climate_02_product_offset")
''')

code(r'''
# Anomalies and categories for the TEST period using the selected model
te = test_df[["city", "date", "target_date", fe.TARGET]].copy(); te["predicted"] = pred_test
te["doy"] = fe.day_of_year_365(te["target_date"])
te = te.merge(normals[["city", "doy", "normal_tmax", "p90_tmax", "p95_tmax"]], on=["city", "doy"], how="left")
te["anomaly_pred"] = te["predicted"] - te["normal_tmax"]; te["anomaly_actual"] = te[fe.TARGET] - te["normal_tmax"]
te["cat_pred"] = [fe.classify_heat(p, n, a, b)["label"] for p, n, a, b in zip(te["predicted"], te["normal_tmax"], te["p90_tmax"], te["p95_tmax"])]
te["cat_actual"] = [fe.classify_heat(p, n, a, b)["label"] for p, n, a, b in zip(te[fe.TARGET], te["normal_tmax"], te["p90_tmax"], te["p95_tmax"])]

print("Predicted heat categories on the test set:"); display(pd.crosstab(te["city"], te["cat_pred"]))
print("Confusion matrix (rows = category from ACTUAL Tmax, columns = category from PREDICTED Tmax):")
display(pd.crosstab(te["cat_actual"], te["cat_pred"]))

from sklearn.metrics import precision_score, recall_score, f1_score
ev_true, ev_pred = (te[fe.TARGET] >= te["p90_tmax"]), (te["predicted"] >= te["p90_tmax"])
heat_event = {"definition": "event = Tmax >= city/day 90th percentile of the 1991-2020 climatology",
              "n_actual_events": int(ev_true.sum()), "n_test_days": int(len(te)),
              "precision": float(precision_score(ev_true, ev_pred, zero_division=0)),
              "recall": float(recall_score(ev_true, ev_pred, zero_division=0)),
              "f1": float(f1_score(ev_true, ev_pred, zero_division=0))}
print("\nHeat-event detection on test set:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in heat_event.items()})
print("Mean anomaly (predicted): %+.2f °C | MAE of anomaly = MAE of temperature: %.2f °C" % (te["anomaly_pred"].mean(), (te["anomaly_pred"] - te["anomaly_actual"]).abs().mean()))

city_show = "Delhi"; g = te[te["city"] == city_show].sort_values("target_date")
fig, ax = plt.subplots(figsize=(13, 4.8))
ax.plot(g["target_date"], g[fe.TARGET], color="#64748b", lw=1, label="actual (model-derived)"); ax.plot(g["target_date"], g["predicted"], color="#0d9488", lw=1.4, label="predicted")
ax.plot(g["target_date"], g["normal_tmax"], color="#0f766e", ls=":", label="1991–2020 normal"); ax.plot(g["target_date"], g["p90_tmax"], "--", color="#f59e0b", label="90th pct"); ax.plot(g["target_date"], g["p95_tmax"], "--", color="#ef4444", label="95th pct")
ax.set(title=f"{city_show}: predicted vs actual Tmax against climatology (test period)", ylabel="°C"); ax.legend(ncol=5, fontsize=8)
save_fig("climate_03_anomaly_example")
''')

md(r'''## Section 10 — Model export
Everything the website needs is written to `climatesense_output/backend/models/`:

| File | Purpose |
|---|---|
| `best_model.joblib` | the fitted scikit-learn Pipeline selected by validation MAE |
| `model_metrics.json` | actual MAE / MSE / R² (train, validation, test), baseline, interval, per-city scores |
| `feature_importance.json` | RF importance, permutation importance, SHAP summary data, local examples |
| `feature_schema.json` | feature names/order/units, training statistics and baseline, feature-module version |
| `training_metadata.json` | data source, periods, hyper-parameters, environment, limitations |
| `city_climate_normals.csv` | 1991–2020 city normals and p90/p95 thresholds by day-of-year |''')

code(r'''
# Feature importance + explanation JSON
shap_rows = [{"x": {f: round(float(X_expl.iloc[i][f]), 3) for f in fe.FEATURES},
              "shap": {f: round(float(shap_values[i][j]), 4) for j, f in enumerate(fe.FEATURES)}} for i in range(len(X_expl))]
importance_doc = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "best_model": best_name,
    "units": "°C",
    "rf_impurity": {"description": "Random Forest impurity-based importance (sums to 1)", "values": rf_imp.round(5).to_dict()},
    "permutation": {"description": f"Increase in MAE (°C) on the TEST set when a feature is shuffled; model = {best_name}; 10 repeats",
                    "mean": perm["mean"].round(5).to_dict(), "std": perm["std"].round(5).to_dict()},
    "shap": {"method": shap_method, "base_value_c": shap_base, "n_rows": len(X_expl), "mean_abs": mean_abs.round(5).to_dict(), "rows": shap_rows},
    "local_examples": local_examples,
    "feature_labels": {f: {"label": fe.FEATURE_INFO[f][0], "unit": fe.FEATURE_INFO[f][1]} for f in fe.FEATURES},
}
(MODEL_DIR / "feature_importance.json").write_text(json.dumps(jsonable(importance_doc), indent=1, ensure_ascii=False))

# Feature schema (the contract between training and the live API)
stats = {f: {"min": float(X_train[f].min()), "max": float(X_train[f].max()), "mean": float(X_train[f].mean()),
             "median": float(X_train[f].median()), "std": float(X_train[f].std())} for f in fe.FEATURES}
schema_doc = {
    "features": fe.FEATURES, "target": fe.TARGET, "details": fe.feature_schema_entries(),
    "feature_module_version": fe.FEATURE_MODULE_VERSION, "feature_module_sha256": FE_SHA256,
    "hourly_variables": fe.MODEL_HOURLY_VARIABLES, "expected_units": fe.EXPECTED_UNITS,
    "cutoff_definition": "Features use data of days <= D (local calendar days); target = max 2 m temperature of day D+1.",
    "training_cities": list(fe.CITIES), "feature_stats": stats, "baseline": {f: stats[f]["mean"] for f in fe.FEATURES},
}
(MODEL_DIR / "feature_schema.json").write_text(json.dumps(jsonable(schema_doc), indent=2, ensure_ascii=False))

# Heat-event results added to the metrics file
metrics_doc["heat_event_detection"] = heat_event
metrics_doc["heat_categories"] = {"levels": fe.HEAT_LEVELS, "disclaimer": fe.HEAT_DISCLAIMER}
metrics_doc["figures"] = sorted(p.name for p in FIG_DIR.glob("*.png"))
(MODEL_DIR / "model_metrics.json").write_text(json.dumps(jsonable(metrics_doc), indent=2, ensure_ascii=False))

# Training metadata
training_doc = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "dataset": {**{k: dataset_meta[k] for k in ["source", "source_url", "retrieval_date_utc", "observation_period", "cities", "units",
                                                "hourly_records", "daily_records", "model_rows", "nature_of_values"]},
                "period": dataset_meta["observation_period"]},
    "training": {"seed": SEED, "cv": f"{len(cv_splits)}-fold expanding-window by unique date, 1-day embargo", "scoring": "neg_mean_absolute_error",
                 "search": search_info, "split": split_info, "selected_model": best_name},
    "climate_normals": {"baseline_period": "1991-2020", "product": "ERA5-Land via Open-Meteo Historical Weather API (models=era5_land)",
                        "variable": "temperature_2m_max (daily)", "window_days": 2 * WINDOW_HALF + 1, "percentiles": [90, 95],
                        "product_offset_applied": APPLY_PRODUCT_OFFSET, "product_offsets": offsets, "grid": era_meta,
                        "resolution": "approx. 0.1° (≈9-11 km)", "documentation": "https://open-meteo.com/en/docs/historical-weather-api"},
    "environment": {"python": platform.python_version(), "scikit_learn": sklearn.__version__, "pandas": pd.__version__, "numpy": np.__version__,
                    "shap": shap.__version__ if SHAP_OK else None, "platform": platform.platform()},
    "limitations": [
        "Training data are archived weather-model values (not station observations); the target is model-derived.",
        "About four years of data: enough to learn the seasonal cycle, not to represent rare extremes or climate trends.",
        "Latitude/longitude identify only six cities; the model is not validated for other locations.",
        "Heat categories are project-defined and are not IMD warnings.",
        "The daily regression model forecasts weather; it does not prove greenhouse-gas causation.",
    ],
}
(MODEL_DIR / "training_metadata.json").write_text(json.dumps(jsonable(training_doc), indent=2, ensure_ascii=False))

joblib.dump(best_model, MODEL_DIR / "best_model.joblib", compress=3)
(MODEL_DIR / "RUNTIME_VERSIONS.txt").write_text(f"scikit-learn=={sklearn.__version__}\npandas=={pd.__version__}\nnumpy=={np.__version__}\n")
for p in sorted(MODEL_DIR.iterdir()):
    if p.is_file(): print(f"{p.name:<28}{p.stat().st_size / 1024:>10.1f} KB")
''')

code(r'''
# Verify the export: reload from disk, predict, and check that outputs match the in-memory model.
reloaded = joblib.load(MODEL_DIR / "best_model.joblib")
assert np.allclose(reloaded.predict(X_test.head(50)), best_model.predict(X_test.head(50)))
assert json.loads((MODEL_DIR / "feature_schema.json").read_text())["features"] == fe.FEATURES
print("✔ Exported model reproduces the in-memory predictions; feature schema matches feature_engineering.FEATURES")
print(f"\nFINAL SUMMARY — selected model: {best_name}")
print(f"  validation MAE {results[best_name]['validation']['mae']:.3f} °C | MSE {results[best_name]['validation']['mse']:.3f} | R² {results[best_name]['validation']['r2']:.3f}")
print(f"  test       MAE {results[best_name]['test']['mae']:.3f} °C | MSE {results[best_name]['test']['mse']:.3f} | R² {results[best_name]['test']['r2']:.3f}")
print(f"  persistence baseline test MAE {baseline['test']['mae']:.3f} °C")
print(f"\nPin this in backend/requirements.txt:  scikit-learn=={sklearn.__version__}")
''')

md(r'''### Download the artifacts
The next cell zips `backend/models/` (model, JSON files, normals, figures) and `data/` (raw CSV, metadata). In Colab it starts the download automatically. Unzip the archive in the **project root** so the files land in `backend/models/` and `data/`.''')
code(r'''
zip_path = Path("climatesense_artifacts.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for p in ROOT.rglob("*"):
        if p.is_file():
            zf.write(p, p.relative_to(ROOT))
print(f"Created {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB) with {len(zf.namelist())} files")
try:
    from google.colab import files
    files.download(str(zip_path))
except ImportError:
    print("Not running in Colab - find the zip next to the notebook.")
''')

md(r'''## Reproducibility notes & limitations
* **Seeds:** `SEED = 42` is used for NumPy, Python, the Random Forest, permutation importance and sampling.
* **Data drift:** the API archive is extended every day, so a re-run later will include more recent dates and give slightly different numbers. The retrieval date and observation period are stored in `dataset_metadata.json`.
* **What the numbers mean:** MAE is the typical error in °C. Always compare with the persistence baseline above.
* **Limitations:** model-derived data, short history (≈4 years), six cities, project-defined heat categories, and a weather-scale model that cannot attribute temperature change to greenhouse gases.''')
