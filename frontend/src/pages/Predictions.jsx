import { useState } from "react";
import { BrainCircuit, CalendarDays, FlaskConical, Info, Radio, Thermometer } from "lucide-react";
import ManualPredictor from "../components/ManualPredictor";
import { useCity } from "../context/CityContext";
import { useApi } from "../hooks/useApi";
import HeatScale from "../components/HeatScale";
import { Card, ErrorBox, HeatBadge, LiveSourceBar, Loading, PageHeader, QualityBanner, RefreshBar, SourceNote, StatCard } from "../components/ui";
import { num, signed } from "../utils/format";

const LABELS = {
  tmax_d0: ["Max temp, cutoff day", "°C"], tmin_d0: ["Min temp, cutoff day", "°C"], tmax_d1: ["Max temp, day −1", "°C"],
  tmax_d2: ["Max temp, day −2", "°C"], tmin_d1: ["Min temp, day −1", "°C"], rh_mean_d0: ["Mean humidity", "%"],
  precip_d0: ["Rain, cutoff day", "mm"], precip_sum3: ["Rain, last 3 days", "mm"], wind_mean_d0: ["Mean wind", "km/h"],
  solar_mj_d0: ["Solar radiation", "MJ/m²"], pressure_mean_d0: ["Mean pressure", "hPa"], cloud_mean_d0: ["Mean cloud cover", "%"],
  tmax_roll3: ["3-day mean of max", "°C"], tmax_roll7: ["7-day mean of max", "°C"], doy_sin: ["Season (sin)", ""], doy_cos: ["Season (cos)", ""],
  latitude: ["Latitude", "°"], longitude: ["Longitude", "°"],
};

export default function Predictions() {
  const { city } = useCity();
  const pred = useApi("/predict", { city }, { interval: 5 * 60 * 1000 });
  const all = useApi("/predict/all", {}, { interval: 5 * 60 * 1000 });
  const P = pred.data;
  const [mode, setMode] = useState("live");

  return (
    <>
      <div className="seg" role="tablist" aria-label="Prediction mode">
        <button role="tab" aria-selected={mode === "live"} className={mode === "live" ? "on" : ""} onClick={() => setMode("live")}><Radio size={14} /> Live prediction</button>
        <button role="tab" aria-selected={mode === "manual"} className={mode === "manual" ? "on" : ""} onClick={() => setMode("manual")}><FlaskConical size={14} /> Manual entry (what-if)</button>
      </div>
      {mode === "manual" ? (
        <>
          <PageHeader title={`${city} · Manual prediction`} subtitle="Enter your own weather values and the same trained model returns the next-day maximum temperature, with its uncertainty and explanation." />
          <ManualPredictor />
        </>
      ) : (<>
      <PageHeader title={`${city} · AI prediction`} subtitle="Next-day maximum temperature from the trained ML model, using live Open-Meteo inputs - no model, no prediction.">
        <RefreshBar updatedAt={pred.updatedAt} onRefresh={() => { pred.refresh(); all.refresh(); }} loading={pred.loading} note="" />
      </PageHeader>

      <LiveSourceBar updatedAt={pred.updatedAt} attemptedAt={pred.attemptedAt} intervalMs={5 * 60 * 1000} error={pred.error}
        loading={pred.loading} onRefresh={() => { pred.refresh(); all.refresh(); }}
        sources={[{ label: "Open-Meteo Forecast API (model inputs)", url: "https://api.open-meteo.com/v1/forecast" }, { label: "Open-Meteo Forecast API docs", url: "https://open-meteo.com/en/docs" }]} />
      {P && <QualityBanner />}

      {pred.error && !P && <ErrorBox error={pred.error} onRetry={pred.refresh} />}
      {pred.loading && !P && !pred.error && <Loading label="Computing features and running the model…" />}

      {P && (
        <>
          <div className="grid stats">
            <StatCard label="Predicted maximum" icon={BrainCircuit} accent="green" value={num(P.prediction.predicted_tmax_c)} unit="°C"
              sub={P.prediction.interval ? `90 % range ${num(P.prediction.interval.lower_c)}–${num(P.prediction.interval.upper_c)}°C` : "no interval available"} />
            <StatCard label="Prediction date" icon={CalendarDays} accent="blue" value={P.prediction.prediction_date} sub={`cutoff day ${P.prediction.cutoff_date}`} />
            <StatCard label="Seasonal normal" icon={Thermometer} accent="amber" value={num(P.climatology.seasonal_normal_c)} unit="°C"
              sub={`${P.climatology.baseline_period} · ±${Math.floor((P.climatology.window_days || 15) / 2)}-day window`} />
            <StatCard label="Temperature anomaly" accent="orange" value={signed(P.climatology.anomaly_c)} unit="°C" sub="prediction − normal" />
            <StatCard label="Heat-risk category" accent="red" value={<HeatBadge risk={P.heat_risk} />} sub="project-defined, not IMD" />
            <StatCard label="Model" icon={BrainCircuit} accent="teal" value={<span className="small-val">{P.model.name}</span>} sub={`selected by ${P.model.selected_by}`} />
          </div>

          <Card title="Where does the prediction sit?" subtitle="Compared with the city's 1991–2020 climate for the target day" icon={Thermometer}>
            <HeatScale climatology={P.climatology} prediction={P.prediction} reference={P.reference_nwp_forecast_tmax_c} />
            <div className="legend-row">
              {[["Normal", "#2dd4bf", "below normal + 1.5 °C"], ["Elevated", "#facc15", "anomaly ≥ +1.5 °C"], ["High", "#fb923c", "≥ 90th percentile"], ["Severe", "#ef4444", "≥ 95th percentile"]].map(([l, c, d]) => (
                <span key={l}><span className="dot" style={{ background: c }} /> <b>{l}</b> <span className="muted small">{d}</span></span>
              ))}
            </div>
            <SourceNote>{P.heat_risk.disclaimer}</SourceNote>
          </Card>

          <div className="grid two">
            <Card title="Reference & uncertainty" icon={Info}>
              <table className="kv">
                <tbody>
                  <tr><td>ML model prediction</td><td><b>{num(P.prediction.predicted_tmax_c)} °C</b></td></tr>
                  <tr><td>Open-Meteo forecast (reference, not an input)</td><td>{P.reference_nwp_forecast_tmax_c != null ? `${num(P.reference_nwp_forecast_tmax_c)} °C` : "–"}</td></tr>
                  <tr><td>90 % interval</td><td>{P.prediction.interval ? `${num(P.prediction.interval.lower_c)} – ${num(P.prediction.interval.upper_c)} °C` : "–"}</td></tr>
                  <tr><td>Interval method</td><td className="small">{P.prediction.interval ? `Empirical residual quantiles (${P.prediction.interval.calibrated_on}); observed test coverage ${P.prediction.interval.test_coverage != null ? `${(P.prediction.interval.test_coverage * 100).toFixed(0)} %` : "n/a"}` : "–"}</td></tr>
                  <tr><td>90th / 95th percentile</td><td>{num(P.climatology.p90_c)} / {num(P.climatology.p95_c)} °C</td></tr>
                  <tr><td>Normal product</td><td className="small">{P.climatology.product || "ERA5-Land"}</td></tr>
                  <tr><td>Trained on</td><td className="small">{P.model.trained_on || "–"}</td></tr>
                  <tr><td>Data fetched (UTC)</td><td className="small">{P.timestamps.fetched_at_utc}</td></tr>
                </tbody>
              </table>
              {P.warnings.length > 0 && <ul className="warnlist">{P.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
            </Card>
            <Card title="Inputs the model actually used" subtitle="Computed live with the same code as in training" icon={BrainCircuit}>
              <div className="feat-grid">
                {Object.entries(P.features_used).map(([k, v]) => (
                  <div key={k} className="feat"><span className="muted small">{LABELS[k]?.[0] || k}</span><b>{num(v, Math.abs(v) < 5 ? 3 : 1)} <small>{LABELS[k]?.[1]}</small></b></div>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}

      <Card title="All cities" subtitle="Same model, same method, every supported city" icon={Thermometer}>
        {all.error && !all.data && <ErrorBox error={all.error} onRetry={all.refresh} compact />}
        {!all.data && !all.error && <Loading />}
        {all.data && (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>City</th><th>Date</th><th>Predicted max</th><th>Normal</th><th>Anomaly</th><th>Category</th><th>Open-Meteo ref.</th></tr></thead>
              <tbody>
                {all.data.cities.map((c) => (
                  <tr key={c.city} className={c.city === city ? "hl" : ""}>
                    <td><b>{c.city}</b></td><td>{c.prediction.prediction_date}</td><td>{num(c.prediction.predicted_tmax_c)}°C</td>
                    <td>{num(c.climatology.seasonal_normal_c)}°C</td><td>{signed(c.climatology.anomaly_c)}°C</td>
                    <td><HeatBadge risk={c.heat_risk} /></td><td>{c.reference_nwp_forecast_tmax_c != null ? `${num(c.reference_nwp_forecast_tmax_c)}°C` : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {Object.entries(all.data.errors || {}).map(([c, e]) => <p key={c} className="warn-text small">{c}: {e}</p>)}
          </div>
        )}
      </Card>

      <Card title="Weather forecast vs climate change" icon={Info}>
        <p className="small">This page shows a <b>weather</b> forecast for one day. A single hot day, or a model score, says nothing about greenhouse-gas causation. Long-term <b>climate</b> evidence (CO₂, CH₄, N₂O, global temperature anomalies) is on the <i>Climate Evidence</i> page.</p>
      </Card>
    </>)}
    </>
  );
}
