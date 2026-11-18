import { Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { Award, FlaskConical, Layers, Target } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { Card, ErrorBox, Loading, PageHeader, QualityBanner, SourceNote, StatCard } from "../components/ui";
import { axisProps, anim, CITY_COLORS, COLORS, gridProps, tooltipProps } from "../utils/chart";
import { num } from "../utils/format";

const ORDER = ["Linear Regression", "SVR (RBF)", "Random Forest"];

function MetricBlock({ title, m, tone }) {
  return (
    <div className={`mblock ${tone}`}>
      <div className="mblock-title">{title}</div>
      <div className="mrow"><span>MAE</span><b>{num(m.mae, 3)} <small>°C</small></b></div>
      <div className="mrow"><span>MSE</span><b>{num(m.mse, 3)} <small>°C²</small></b></div>
      <div className="mrow"><span>R²</span><b>{num(m.r2, 3)}</b></div>
    </div>
  );
}

function ModelCard({ name, info, best, baseline }) {
  return (
    <div className={`modelcard ${best ? "best" : ""}`}>
      <div className="modelcard-head">
        <h3>{name}</h3>
        {best && <span className="badge ok-badge"><Award size={12} /> Selected</span>}
        {baseline && <span className="badge muted-badge">Baseline</span>}
      </div>
      <p className="muted small">{info.description}</p>
      <div className="mblocks">
        <MetricBlock title="Validation (model selection)" m={info.validation} tone="val" />
        <MetricBlock title="Test (final, untouched)" m={info.test} tone="test" />
      </div>
      {info.cv_mae_mean != null && <p className="small">Time-aware CV MAE (train only): <b>{num(info.cv_mae_mean, 3)} ± {num(info.cv_mae_std, 3)} °C</b> · {info.n_candidates} settings × {info.n_cv_folds} folds</p>}
      {info.best_params && Object.keys(info.best_params).length > 0 && (
        <p className="small muted">Best params: {Object.entries(info.best_params).map(([k, v]) => `${k.split("__").pop()}=${v}`).join(", ")}</p>
      )}
    </div>
  );
}

export default function ModelLab() {
  const metrics = useApi("/metrics");
  const models = useApi("/models");
  const M = metrics.data;
  if (metrics.error) return <><PageHeader title="Model Lab" /><ErrorBox error={metrics.error} onRetry={metrics.refresh} /></>;
  if (!M) return <><PageHeader title="Model Lab" /><Loading /></>;

  const base = M.baseline_persistence;
  const chartData = (metric) => [
    ...ORDER.map((n) => ({ name: n.replace(" (RBF)", ""), Validation: M.models[n]?.validation[metric], Test: M.models[n]?.test[metric] })),
    { name: "Persistence", Validation: base.validation[metric], Test: base.test[metric] },
  ];
  const hist = M.residual_histogram;
  const histData = hist.counts.map((c, i) => ({ x: ((hist.bin_edges[i] + hist.bin_edges[i + 1]) / 2).toFixed(2), count: c }));
  const cityData = Object.entries(M.per_city_test_mae).map(([city, mae]) => ({ city, mae }));
  const sc = M.test_scatter || [];
  const lo = Math.floor(Math.min(...sc.map((s) => Math.min(s.actual, s.predicted))));
  const hi = Math.ceil(Math.max(...sc.map((s) => Math.max(s.actual, s.predicted))));
  const D = models.data?.dataset;

  return (
    <>
      <PageHeader title="Model Lab" subtitle="Real MAE, MSE and R² produced by the Colab notebook. Nothing on this page is hard-coded." />
      <QualityBanner />

      <div className="grid stats">
        <StatCard label="Selected model" icon={Award} accent="green" value={<span className="small-val">{M.best_model.name}</span>} sub={M.selection_rule} />
        <StatCard label="Test MAE" icon={Target} accent="teal" value={num(M.best_model.test.mae, 2)} unit="°C" sub={`R² ${num(M.best_model.test.r2, 3)} · MSE ${num(M.best_model.test.mse, 2)}`} />
        <StatCard label="vs persistence (test MAE)" icon={Layers} accent={M.improvement_over_persistence_pct.test_mae > 0 ? "green" : "red"}
          value={`${M.improvement_over_persistence_pct.test_mae > 0 ? "+" : ""}${num(M.improvement_over_persistence_pct.test_mae, 1)}`} unit="%"
          sub={M.improvement_over_persistence_pct.test_mae > 0 ? "lower error than 'tomorrow = today'" : "NOT better than 'tomorrow = today'"} />
        <StatCard label="Generated" icon={FlaskConical} accent="blue" value={<span className="small-val">{M.generated_at_utc?.slice(0, 10)}</span>} sub={D ? `${D.model_rows?.toLocaleString()} rows · ${D.period}` : ""} />
      </div>

      <h2 className="section-title">Model comparison</h2>
      <div className="grid three">
        {ORDER.filter((n) => M.models[n]).map((n) => <ModelCard key={n} name={n} info={M.models[n]} best={M.best_model.name === n} />)}
      </div>
      <div className="grid one"><ModelCard name="Persistence baseline" info={{ ...base, description: base.description }} baseline /></div>

      <div className="grid three">
        {[["mae", "MAE (°C) – lower is better"], ["mse", "MSE (°C²) – lower is better"], ["r2", "R² – higher is better"]].map(([k, t]) => (
          <Card key={k} title={t} icon={FlaskConical}>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData(k)}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="name" {...axisProps} interval={0} tick={{ fill: "#8a9bb8", fontSize: 10 }} /><YAxis {...axisProps} width={40} />
                <Tooltip {...tooltipProps} formatter={(v) => num(v, 3)} /><Legend />
                <Bar dataKey="Validation" fill={COLORS.teal} radius={[4, 4, 0, 0]} {...anim} />
                <Bar dataKey="Test" fill="#0f766e" radius={[4, 4, 0, 0]} {...anim} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        ))}
      </div>

      <div className="grid two">
        <Card title={`Actual vs predicted · ${M.best_model.name}`} subtitle={`Test set sample (${sc.length} points) · dashed line = perfect prediction`} icon={Target}>
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart>
              <CartesianGrid {...gridProps} />
              <XAxis type="number" dataKey="actual" name="Actual" unit="°C" domain={[lo, hi]} {...axisProps} /><YAxis type="number" dataKey="predicted" name="Predicted" unit="°C" domain={[lo, hi]} {...axisProps} width={46} />
              <ZAxis range={[14, 14]} />
              <Tooltip {...tooltipProps} cursor={{ strokeDasharray: "3 3" }} />
              <ReferenceLine segment={[{ x: lo, y: lo }, { x: hi, y: hi }]} stroke="#e6edf7" strokeDasharray="5 4" />
              <Scatter data={sc} fill={COLORS.teal} fillOpacity={0.55} {...anim} />
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Residual distribution (test)" subtitle={`actual − predicted · mean ${num(hist.mean, 2)} °C, std ${num(hist.std, 2)} °C`} icon={Layers}>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={histData}>
              <CartesianGrid {...gridProps} /><XAxis dataKey="x" {...axisProps} minTickGap={40} /><YAxis {...axisProps} width={38} />
              <Tooltip {...tooltipProps} /><ReferenceLine x={histData.reduce((a, b) => (Math.abs(b.x) < Math.abs(a.x) ? b : a)).x} stroke={COLORS.amber} />
              <Bar dataKey="count" name="days" fill={COLORS.teal} {...anim} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid two">
        <Card title="Test MAE by city" subtitle={M.best_model.name} icon={Target}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={cityData}>
              <CartesianGrid {...gridProps} /><XAxis dataKey="city" {...axisProps} /><YAxis {...axisProps} width={38} unit="°" />
              <Tooltip {...tooltipProps} formatter={(v) => `${num(v, 2)} °C`} />
              <Bar dataKey="mae" name="MAE" radius={[4, 4, 0, 0]} {...anim}>{cityData.map((c) => <Cell key={c.city} fill={CITY_COLORS[c.city]} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Data split & heat-event detection" icon={Layers}>
          <table className="kv"><tbody>
            {["train", "validation", "test"].map((k) => (
              <tr key={k}><td>{k}</td><td className="small">{M.split[k].start} → {M.split[k].end} · {M.split[k].n_rows.toLocaleString()} rows ({M.split[k].share_pct}%)</td></tr>
            ))}
            {M.heat_event_detection && <>
              <tr><td>Heat-event rule</td><td className="small">{M.heat_event_detection.definition}</td></tr>
              <tr><td>Precision / Recall / F1</td><td><b>{num(M.heat_event_detection.precision, 2)} / {num(M.heat_event_detection.recall, 2)} / {num(M.heat_event_detection.f1, 2)}</b> <span className="muted small">({M.heat_event_detection.n_actual_events} events in {M.heat_event_detection.n_test_days} test days)</span></td></tr>
            </>}
          </tbody></table>
          <SourceNote>Chronological split by unique date with a 1-day gap; hyper-parameters tuned only with time-aware cross-validation on the training period. The test set is touched after model selection.</SourceNote>
        </Card>
      </div>

      {models.data?.training?.search && (
        <Card title="Training details" icon={FlaskConical}>
          <p className="small">Dataset: {models.data.dataset.source} · retrieved {models.data.dataset.retrieval_date_utc?.slice(0, 10)} · cities: {Object.keys(models.data.dataset.cities).join(", ")}</p>
          <p className="small muted">{models.data.dataset.nature_of_values}. Climate normals: {models.data.climate_normals?.product}.</p>
          {models.data.warnings?.map((w) => <p key={w} className="warn-text small">{w}</p>)}
        </Card>
      )}
    </>
  );
}
