import { useMemo, useState } from "react";
import { Calculator, CalendarDays, CloudDownload, Eraser, FlaskConical, Play, Sigma, Thermometer } from "lucide-react";
import { api, describeError } from "../api/client";
import { useCity } from "../context/CityContext";
import { useApi } from "../hooks/useApi";
import HeatScale from "./HeatScale";
import { Card, ErrorBox, HeatBadge, Loading, SourceNote, StatCard } from "./ui";
import { num, signed } from "../utils/format";

const GROUPS = [
  { title: "Temperatures (°C)", fields: ["tmax_d0", "tmin_d0", "tmax_d1", "tmax_d2", "tmin_d1", "tmax_roll7"] },
  { title: "Atmosphere on the cutoff day", fields: ["rh_mean_d0", "cloud_mean_d0", "pressure_mean_d0", "wind_mean_d0", "solar_mj_d0"] },
  { title: "Rain (mm)", fields: ["precip_d0", "precip_sum3"] },
];
const HINTS = {
  tmax_roll7: "average of the daily maxima of the last 7 days, cutoff day included",
  precip_sum3: "rain over the last 3 days, cutoff day included (≥ today's rain)",
  solar_mj_d0: "daily total of shortwave radiation; a clear summer day is ≈ 22–30",
  tmax_d1: "the day before the cutoff day", tmax_d2: "two days before the cutoff day", tmin_d1: "the day before the cutoff day",
};

const todayLocal = () => {
  const d = new Date(Date.now() + 5.5 * 3600 * 1000); // India time
  return d.toISOString().slice(0, 10);
};

export default function ManualPredictor() {
  const { city } = useCity();
  const schema = useApi("/predict/manual/schema", {}, { interval: 0 });
  const [vals, setVals] = useState({});
  const [date, setDate] = useState(todayLocal());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [res, setRes] = useState(null);
  const [note, setNote] = useState("");

  const fields = useMemo(() => Object.fromEntries((schema.data?.fields || []).map((f) => [f.name, f])), [schema.data]);
  const set = (k, v) => setVals((p) => ({ ...p, [k]: v }));
  const filled = (schema.data?.fields || []).filter((f) => vals[f.name] !== undefined && vals[f.name] !== "").length;
  const total = schema.data?.fields?.length || 13;

  async function fillLive() {
    setBusy(true); setErr(null); setNote("");
    try {
      const r = await api.get("/predict", { params: { city } });
      const fu = r.data.features_used;
      const next = {};
      (schema.data?.fields || []).forEach((f) => { next[f.name] = String(Math.round(fu[f.name] * 100) / 100); });
      setVals(next); setDate(r.data.prediction.cutoff_date);
      setNote(`Filled with today's real Open-Meteo values for ${city} (fetched ${r.data.timestamps.fetched_at_utc}). Edit any field and press Predict.`);
    } catch (e) { setErr(describeError(e)); } finally { setBusy(false); }
  }
  function fillTypical() {
    const next = {};
    (schema.data?.fields || []).forEach((f) => { if (f.train_median != null) next[f.name] = String(Math.round(f.train_median * 10) / 10); });
    setVals(next); setNote("Filled with the MEDIAN of the training data (a neutral starting point, not a real observation). Change the values you care about.");
  }
  function clearAll() { setVals({}); setRes(null); setErr(null); setNote(""); }

  async function submit(e) {
    e.preventDefault();
    setErr(null); setRes(null);
    const body = { city, cutoff_date: date };
    for (const f of schema.data.fields) {
      const raw = vals[f.name];
      if (raw === undefined || raw === "" || Number.isNaN(Number(raw))) {
        setErr({ code: "invalid_input", message: `Please enter a number for “${f.label}”. Nothing is guessed on your behalf.` });
        return;
      }
      body[f.name] = Number(raw);
    }
    setBusy(true);
    try { setRes((await api.post("/predict/manual", body)).data); }
    catch (e2) { setErr(describeError(e2)); }
    finally { setBusy(false); }
  }

  const E = res?.explanation;
  return (
    <>
      <Card title={`Try your own values · ${city}`} subtitle="Type the weather of a cutoff day; the trained model predicts the NEXT day's maximum temperature" icon={FlaskConical}>
        {schema.loading && !schema.data && <Loading label="Loading input fields…" height={80} />}
        {schema.error && !schema.data && <ErrorBox error={schema.error} onRetry={schema.refresh} compact />}
        {schema.data && (
          <form onSubmit={submit} className="mform">
            <div className="mform-top">
              <label className="mfield">
                <span><CalendarDays size={13} /> Cutoff day (the day your values are from)</span>
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
                <small>The forecast is for the next day. City = {city} (change it in the top bar).</small>
              </label>
              <div className="mform-actions">
                <button type="button" className="btn ghost sm" onClick={fillLive} disabled={busy}><CloudDownload size={14} /> Fill with live values</button>
                <button type="button" className="btn ghost sm" onClick={fillTypical} disabled={busy}><Calculator size={14} /> Fill training medians</button>
                <button type="button" className="btn ghost sm" onClick={clearAll} disabled={busy}><Eraser size={14} /> Clear</button>
              </div>
            </div>
            {note && <p className="small muted mnote">{note}</p>}

            {GROUPS.map((g) => (
              <fieldset key={g.title} className="mgroup">
                <legend>{g.title}</legend>
                <div className="mgrid">
                  {g.fields.map((k) => {
                    const f = fields[k]; if (!f) return null;
                    return (
                      <label key={k} className="mfield">
                        <span>{f.label} <em>{f.unit}</em></span>
                        <input type="number" step="any" inputMode="decimal" value={vals[k] ?? ""} onChange={(e) => set(k, e.target.value)}
                          placeholder={f.train_median != null ? `typical ${num(f.train_median, 1)}` : ""} min={f.min} max={f.max} required />
                        <small>{HINTS[k] ? `${HINTS[k]} · ` : ""}training range {num(f.train_min, 0)}…{num(f.train_max, 0)}</small>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ))}
            <p className="small muted">Computed for you from these values and the city/date: 3-day mean of max temperature, season terms (day of year) and the city's latitude/longitude — exactly as during training.</p>
            <div className="mform-submit">
              <button type="submit" className="btn" disabled={busy}><Play size={15} /> {busy ? "Running model…" : "Predict next-day maximum"}</button>
              <span className="small muted">{filled}/{total} fields filled</span>
            </div>
          </form>
        )}
      </Card>

      {err && <ErrorBox error={err} compact />}

      {res && (
        <>
          <div className="grid stats">
            <StatCard label="Predicted maximum" icon={Thermometer} accent="green" value={num(res.prediction.predicted_tmax_c)} unit="°C"
              sub={res.prediction.interval ? `90 % range ${num(res.prediction.interval.lower_c)}–${num(res.prediction.interval.upper_c)}°C` : "no interval available"} />
            <StatCard label="For the day" icon={CalendarDays} accent="blue" value={res.prediction.prediction_date} sub={`from your cutoff day ${res.prediction.cutoff_date}`} />
            <StatCard label="Seasonal normal" icon={Thermometer} accent="amber" value={num(res.climatology.seasonal_normal_c)} unit="°C" sub="1991–2020 climate" />
            <StatCard label="Anomaly" accent="orange" value={signed(res.climatology.anomaly_c)} unit="°C" sub="prediction − normal" />
            <StatCard label="Heat-risk category" accent="red" value={<HeatBadge risk={res.heat_risk} />} sub="project-defined, not IMD" />
            <StatCard label="Model" icon={Sigma} accent="teal" value={<span className="small-val">{res.model.name}</span>} sub="same model as the live page" />
          </div>

          <Card title="Where does your result sit?" subtitle="Against the city's climate for the target day" icon={Thermometer}>
            <HeatScale climatology={res.climatology} prediction={res.prediction} />
            <SourceNote>{res.heat_risk.disclaimer}</SourceNote>
            {res.warnings.length > 0 && <ul className="warnlist">{res.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
          </Card>

          {E && (
            <Card title="Why this number?" subtitle={`${E.method}. Contributions are in °C versus an average training day (${num(E.base_value_c)} °C).`} icon={Sigma}>
              <div className="contrib">
                {E.all.slice(0, 10).map((i) => {
                  const max = Math.max(...E.all.map((x) => Math.abs(x.contribution_c)), 0.01);
                  const w = (Math.abs(i.contribution_c) / max) * 50;
                  return (
                    <div key={i.feature} className="contrib-row">
                      <span className="contrib-label" title={i.label}>{i.label}</span>
                      <div className="contrib-track">
                        <div className={`contrib-bar ${i.contribution_c >= 0 ? "up" : "down"}`} style={i.contribution_c >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }} />
                      </div>
                      <b className={i.contribution_c >= 0 ? "pos" : "neg"}>{signed(i.contribution_c, 2)} °C</b>
                      <small>{num(i.value, Math.abs(i.value) < 5 ? 3 : 1)} {i.unit}</small>
                    </div>
                  );
                })}
              </div>
              <p className="small muted">{E.reading_guide}</p>
            </Card>
          )}
          <p className="small muted">{res.disclaimer}</p>
        </>
      )}
    </>
  );
}
