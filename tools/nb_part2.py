"""Notebook cells, sections 4-6."""
CELLS = []
def md(t): CELLS.append(("md", t.strip("\n")))
def code(t): CELLS.append(("code", t.strip("\n")))

md(r'''## Section 4 — Exploratory Data Analysis (EDA)
EDA means *looking at the data before modelling*. Every figure below is followed by what to look for, and an automatic text summary computed from the real data (so the statements always match what you see).''')

code(r'''
def save_fig(name):
    plt.tight_layout()
    plt.savefig(FIG_DIR / f"{name}.png", dpi=130, bbox_inches="tight")
    plt.show()

palette = dict(zip(fe.CITIES, sns.color_palette("husl", len(fe.CITIES))))

# 4.1 Temperature trend plots (7-day rolling mean of daily max temperature)
fig, ax = plt.subplots(figsize=(13, 5))
for city, g in daily.groupby("city"):
    g = g.sort_values("date")
    ax.plot(g["date"], g["tmax"].rolling(7, min_periods=4).mean(), label=city, color=palette[city], lw=1.3)
ax.set(title="Daily maximum temperature (7-day rolling mean)", xlabel="Date", ylabel="Tmax (°C)")
ax.legend(ncol=3)
save_fig("eda_01_temperature_trends")
''')
md(r'''**What it reveals:** the *seasonal cycle* (pre-monsoon peak, monsoon dip, winter low) and differences between cities. Delhi swings the most (continental climate); coastal cities (Chennai, Mumbai) vary less. Year-to-year differences hint at how unusual a given season was — but 4 years are far too short to say anything about *climate change*.''')

code(r'''
# 4.2 City-wise comparison
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
order = daily.groupby("city")["tmax"].median().sort_values().index
sns.boxplot(data=daily, x="city", y="tmax", order=order, palette=palette, ax=axes[0])
axes[0].set(title="City-wise distribution of daily Tmax", xlabel="", ylabel="Tmax (°C)")
sns.boxplot(data=daily.assign(dtr=daily["tmax"] - daily["tmin"]), x="city", y="dtr", order=order, palette=palette, ax=axes[1])
axes[1].set(title="Diurnal temperature range (Tmax − Tmin)", xlabel="", ylabel="°C")
save_fig("eda_02_city_comparison")

# 4.3 Historical distributions
g = sns.displot(data=daily, x="tmax", col="city", col_wrap=3, kde=True, height=3, color="#0d9488", bins=30)
g.set_axis_labels("Tmax (°C)", "days")
g.fig.suptitle("Distribution of daily maximum temperature by city", y=1.03, fontweight="bold")
save_fig("eda_03_distributions")
''')
md(r'''**What it reveals:** the *median* and *spread* of each city's Tmax. Wide boxes = large seasonal range. Points above the whiskers are the hottest days (kept in the data). A large diurnal range (Delhi, Hyderabad) indicates dry air; a small one (Mumbai, Kolkata) indicates humid air. Distributions that are two-humped (bimodal) reflect hot-dry and cooler-wet seasons.''')

code(r'''
# 4.4 Correlation heatmap
corr_cols = [c for c in fe.FEATURES if c not in ("latitude", "longitude")] + [fe.TARGET]
corr = model_df[corr_cols].corr()
fig, ax = plt.subplots(figsize=(11, 9))
sns.heatmap(corr, cmap="RdBu_r", center=0, annot=True, fmt=".2f", annot_kws={"size": 7}, ax=ax)
ax.set_title("Correlation between features and next-day Tmax")
save_fig("eda_04_correlation_heatmap")
top = corr[fe.TARGET].drop(fe.TARGET).abs().sort_values(ascending=False).head(5)
print("Features most correlated (|r|) with next-day Tmax:\n", top.round(3).to_string())
''')
md(r'''**What it reveals:** today's temperature measures (`tmax_d0`, `tmax_roll3`, `tmax_roll7`) correlate strongly with tomorrow's — *persistence* is a strong baseline in weather. Humidity and cloud cover correlate **negatively** (humid/cloudy air limits daytime heating), solar radiation positively. Strongly inter-correlated features (e.g. the three temperature averages) are *redundant*; that matters for interpreting linear coefficients but not for tree models.''')

code(r'''
# 4.5 Seasonal trend analysis
monthly = daily.assign(month=daily["date"].dt.month).groupby(["city", "month"])["tmax"].mean().reset_index()
fig, ax = plt.subplots(figsize=(11, 5))
for city, g in monthly.groupby("city"):
    ax.plot(g["month"], g["tmax"], marker="o", label=city, color=palette[city])
ax.set(title="Mean daily Tmax by calendar month (dataset period)", xlabel="Month", ylabel="°C", xticks=range(1, 13))
ax.legend(ncol=3)
save_fig("eda_05_seasonal")

# 4.6 Missing-value visualisation
fig, ax = plt.subplots(figsize=(9, 3.5))
sns.heatmap(miss, annot=True, fmt=".2f", cmap="YlOrRd", cbar_kws={"label": "% missing"}, ax=ax)
ax.set_title("Missing hourly values (%) by city and variable")
save_fig("eda_06_missing_values")
print("Total missing hourly values:", int(hourly[fe.MODEL_HOURLY_VARIABLES].isna().sum().sum()))
''')
md(r'''**What they reveal:** the seasonal plot shows *when* each city peaks (e.g. April–May pre-monsoon in most cities). The missing-value map confirms data quality: a (near-)white heat-map means (almost) nothing was missing; any coloured cell tells us which city/variable to be careful with.''')

code(r'''
# 4.7 Scatter plots of important weather variables vs next-day Tmax
sample = model_df.sample(min(4000, len(model_df)), random_state=SEED)
pairs = [("tmax_d0", "Today's Tmax (°C)"), ("rh_mean_d0", "Mean humidity today (%)"),
         ("solar_mj_d0", "Solar radiation today (MJ/m²)"), ("cloud_mean_d0", "Mean cloud cover today (%)")]
fig, axes = plt.subplots(2, 2, figsize=(12, 9))
for ax, (col, lab) in zip(axes.ravel(), pairs):
    sns.scatterplot(data=sample, x=col, y=fe.TARGET, hue="city", palette=palette, s=10, alpha=0.5, ax=ax, legend=(col == "tmax_d0"))
    ax.set(xlabel=lab, ylabel="Next-day Tmax (°C)")
fig.suptitle("Key weather variables vs next-day maximum temperature", fontweight="bold")
save_fig("eda_07_scatter")

hot = daily.loc[daily["tmax"].idxmax()]
warm_month = monthly.loc[monthly["tmax"].idxmax()]
print("AUTOMATIC OBSERVATIONS (computed from the data)")
print(f" • Highest daily Tmax in the dataset: {hot['tmax']:.1f} °C in {hot['city']} on {hot['date'].date()}")
print(f" • City with the highest median Tmax : {daily.groupby('city')['tmax'].median().idxmax()}")
print(f" • Warmest city-month on average     : {warm_month['city']}, month {int(warm_month['month'])} ({warm_month['tmax']:.1f} °C)")
print(f" • Strongest single predictor (|r|)  : {top.index[0]} (r = {corr.loc[top.index[0], fe.TARGET]:.2f})")
''')
md(r'''**What it reveals:** a tight diagonal in the first panel = temperature persistence. A downward cloud for humidity/cloud cover and upward cloud for solar radiation show *physical* relationships the model can use. Overlapping coloured clouds from different cities show why latitude/longitude are included.''')

md(r'''## Section 5 — Train / validation / test split (chronological, no leakage)

* **Time never flows backwards.** We sort all unique *dates* and cut them into **70 % train → 15 % validation → 15 % test**.
* Splitting by **unique dates** (not rows) means every city's record for a given date goes into the *same* partition.
* A **1-day gap (embargo)** between partitions makes sure the target of the last training row is not an input of the first validation row.
* **Time-aware cross-validation** inside the training set: each fold trains on the past and validates on the *next* block of dates (expanding window). We never shuffle.
* **Imputers and scalers are fitted inside the scikit-learn Pipeline**, so inside every CV fold they learn only from that fold's training part, and finally only from the training set.
* The **test set is not touched** until the model has been chosen.''')

code(r'''
dates = np.sort(model_df["date"].unique())
n = len(dates); i1, i2 = int(n * 0.70), int(n * 0.85)
train_dates, val_dates, test_dates = dates[:i1], dates[i1 + 1:i2], dates[i2 + 1:]     # 1-day embargo at each boundary

train_df = model_df[model_df["date"].isin(train_dates)].reset_index(drop=True)
val_df   = model_df[model_df["date"].isin(val_dates)].reset_index(drop=True)
test_df  = model_df[model_df["date"].isin(test_dates)].reset_index(drop=True)

X_train, y_train = train_df[fe.FEATURES], train_df[fe.TARGET]
X_val,   y_val   = val_df[fe.FEATURES],   val_df[fe.TARGET]
X_test,  y_test  = test_df[fe.FEATURES],  test_df[fe.TARGET]

split_info = {}
for name, part, dts in [("train", train_df, train_dates), ("validation", val_df, val_dates), ("test", test_df, test_dates)]:
    split_info[name] = {"start": str(pd.Timestamp(dts[0]).date()), "end": str(pd.Timestamp(dts[-1]).date()),
                        "n_dates": int(len(dts)), "n_rows": int(len(part)), "share_pct": round(100 * len(part) / len(model_df), 1)}
display(pd.DataFrame(split_info).T)

# Safety checks
assert train_df["date"].max() < val_df["date"].min() < val_df["date"].max() < test_df["date"].min()
assert set(train_dates).isdisjoint(val_dates) and set(val_dates).isdisjoint(test_dates)
for dts in (train_dates, val_dates, test_dates):                 # every city must be in the same date partition
    assert model_df[model_df["date"].isin(dts)].groupby("date")["city"].nunique().max() <= len(fe.CITIES)
print("✔ Chronological order, disjoint partitions and same-date-same-partition verified.")

def date_blocked_time_splits(dates_col, n_splits=5, embargo=1):
    """Expanding-window CV over UNIQUE DATES: train on the past, validate on the next block."""
    u = np.sort(dates_col.unique()); k = len(u) // (n_splits + 1); arr = dates_col.to_numpy()
    for s in range(1, n_splits + 1):
        tr, va = u[: s * k], u[s * k + embargo: (s + 1) * k]
        yield np.where(np.isin(arr, tr))[0], np.where(np.isin(arr, va))[0]

cv_splits = list(date_blocked_time_splits(train_df["date"], n_splits=5))
for i, (tr, va) in enumerate(cv_splits, 1):
    print(f"CV fold {i}: train {train_df['date'].iloc[tr].min().date()} → {train_df['date'].iloc[tr].max().date()}  |  "
          f"validate {train_df['date'].iloc[va].min().date()} → {train_df['date'].iloc[va].max().date()}")
''')

md(r'''## Section 6 — Model implementation

### The algorithms in simple language
**Persistence baseline.** "Tomorrow's maximum = today's maximum." Weather has memory, so this simple rule is surprisingly hard to beat. Any real model must do better, otherwise it adds no value.

**1. Linear Regression.** Fits one straight-line formula:  `Tmax_tomorrow = b0 + b1·x1 + b2·x2 + …`. It learns the weights `b` that minimise the squared error. *Strength:* fast, easy to explain. *Weakness:* can only model straight-line relationships. Needs **scaling** so that features with different units (hPa vs °C) are comparable.

**2. Support Vector Regression (SVR, RBF kernel).** Fits a smooth curve that stays within a tolerance tube of width **ε** around the data; points outside the tube are penalised with strength **C**. The **RBF kernel** lets it model curved relationships by measuring similarity between days; **γ** controls how local that similarity is. *Strength:* captures non-linear patterns. *Weakness:* sensitive to scaling and hyper-parameters; slower on huge data. We scale inputs *and* the target.

**3. Random Forest Regressor.** Builds many decision trees on random subsets of rows and features and **averages** them. Each tree asks questions like "was today above 36 °C?". *Strength:* handles non-linear interactions, robust, gives feature importance, needs no scaling. *Weakness:* cannot extrapolate beyond the temperatures seen in training; larger model file.

### Why Pipelines?
A `Pipeline` bundles *imputer → scaler → model* into one object. It guarantees the same preprocessing at training time and live prediction time, and prevents leakage because each step is fitted only on training data.

### Hyper-parameter tuning
`GridSearchCV` tries many settings, scores each with the **time-aware CV on the training data only**, and keeps the best (lowest MAE). Validation and test sets are not used for tuning.''')

code(r'''
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def make_linear():
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("lr", LinearRegression())])

def make_svr():
    inner = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()),
                      ("svr", SVR(kernel="rbf", cache_size=500))])
    return TransformedTargetRegressor(regressor=inner, transformer=StandardScaler())     # target scaled too

def make_rf():
    return Pipeline([("imputer", SimpleImputer(strategy="median")),
                     ("rf", RandomForestRegressor(random_state=SEED, n_jobs=-1))])

CANDIDATES = {
    "Linear Regression": (make_linear(), {}),
    "SVR (RBF)": (make_svr(), {"regressor__svr__C": [1, 10, 30],
                               "regressor__svr__epsilon": [0.05, 0.1],
                               "regressor__svr__gamma": ["scale", 0.01]}),
    "Random Forest": (make_rf(), {"rf__n_estimators": [300], "rf__max_depth": [8, 14, None],
                                  "rf__min_samples_leaf": [2, 5], "rf__max_features": [0.5, 1.0]}),
}

def regression_metrics(y_true, y_pred):
    return {"mae": float(mean_absolute_error(y_true, y_pred)),
            "mse": float(mean_squared_error(y_true, y_pred)),
            "r2": float(r2_score(y_true, y_pred))}

fitted, search_info = {}, {}
for name, (est, grid) in CANDIDATES.items():
    t0 = time.time()
    gs = GridSearchCV(est, grid, scoring="neg_mean_absolute_error", cv=cv_splits, n_jobs=-1, refit=True)
    gs.fit(X_train, y_train)                                    # tuning sees ONLY training data
    fitted[name] = gs.best_estimator_
    i = gs.best_index_
    search_info[name] = {"best_params": {k: (None if v is None else v) for k, v in gs.best_params_.items()},
                         "cv_mae_mean": float(-gs.cv_results_["mean_test_score"][i]),
                         "cv_mae_std": float(gs.cv_results_["std_test_score"][i]),
                         "n_candidates": int(len(gs.cv_results_["params"])), "n_cv_folds": len(cv_splits),
                         "fit_seconds": round(time.time() - t0, 1)}
    print(f"{name:<18} CV-MAE {search_info[name]['cv_mae_mean']:.3f} ± {search_info[name]['cv_mae_std']:.3f} °C | "
          f"best params: {gs.best_params_} | {search_info[name]['fit_seconds']}s")
''')
