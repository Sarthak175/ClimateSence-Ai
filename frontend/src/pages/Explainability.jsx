import { ShortTick } from "../utils/chart";
import { Bar, BarChart, CartesianGrid, Cell, ErrorBar, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { ArrowDownRight, ArrowUpRight, ScanSearch } from "lucide-react";
import { useCity } from "../context/CityContext";
import { useApi } from "../hooks/useApi";
import { Card, ErrorBox, Loading, PageHeader, SourceNote } from "../components/ui";
import { axisProps, anim, COLORS, gridProps, tooltipProps } from "../utils/chart";
import { num, signed } from "../utils/format";

const topN = (obj, n = 12) => Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, n);

function Swarm({ shap, labels }) {
  const feats = topN(shap.mean_abs, 10).map(([f]) => f);
  const rows = shap.rows;
  const rng = (i) => ((Math.sin(i * 12.9898) * 43758.5453) % 1 + 1) % 1; // deterministic jitter
  const ext = {};
  feats.forEach((f) => { const v = rows.map((r) => r.x[f]); ext[f] = [Math.min(...v), Math.max(...v)]; });
  const buckets = { low: [], mid: [], high: [] };
  feats.forEach((f, fi) => rows.forEach((r, i) => {
    const [a, b] = ext[f]; const t = b === a ? 0.5 : (r.x[f] - a) / (b - a);
    buckets[t < 0.33 ? "low" : t < 0.66 ? "mid" : "high"].push({ x: r.shap[f], y: feats.length - 1 - fi + (rng(i + fi * 997) - 0.5) * 0.6, raw: r.x[f], f });
  }));
  const ticks = feats.map((_, i) => feats.length - 1 - i);
  const nameAt = (v) => labels[feats[feats.length - 1 - Math.round(v)]]?.label || "";
  return (
    <ResponsiveContainer width="100%" height={Math.max(300, feats.length * 38)}>
      <ScatterChart margin={{ left: 190, right: 12 }}>
        <CartesianGrid {...gridProps} />
        <XAxis type="number" dataKey="x" name="SHAP" unit="°C" {...axisProps} />
        <YAxis type="number" dataKey="y" domain={[-0.6, feats.length - 0.4]} ticks={ticks} {...axisProps} tick={(p) => <ShortTick {...p} text={nameAt(p.payload.value)} />} width={190} interval={0} />
        <ZAxis range={[18, 18]} />
        <ReferenceLine x={0} stroke="#8a9bb8" />
        <Tooltip {...tooltipProps} cursor={false} formatter={(v, n, p) => (n === "SHAP" ? [`${num(v, 2)} °C`, p.payload.f] : [v, n])} />
        <Scatter name="low" data={buckets.low} fill="#60a5fa" fillOpacity={0.75} {...anim} />
        <Scatter name="mid" data={buckets.mid} fill="#a78bfa" fillOpacity={0.6} {...anim} />
        <Scatter name="high" data={buckets.high} fill="#f87171" fillOpacity={0.75} {...anim} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export default function Explainability() {
  const { city } = useCity();
  const ex = useApi("/explain", { city });
  const G = ex.data?.global, Lc = ex.data?.local;
  const labels = G?.feature_labels || {};
  const name = (f) => labels[f]?.label || f;

  const rf = G ? topN(G.rf_impurity.values).map(([f, v]) => ({ f, label: name(f), v })) : [];
  const perm = G ? Object.entries(G.permutation.mean).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([f, v]) => ({ f, label: name(f), v, err: G.permutation.std[f] })) : [];
  const shapBar = G ? topN(G.shap.mean_abs).map(([f, v]) => ({ f, label: name(f), v })) : [];
  const local = Lc ? [...Lc.all].slice(0, 12).reverse() : [];

  return (
    <>
      <PageHeader title="Explainable AI" subtitle="Which weather variables drive the forecast - computed from the real trained model." />
      {ex.error && !ex.data && <ErrorBox error={ex.error} onRetry={ex.refresh} />}
      {ex.loading && !ex.data && !ex.error && <Loading label="Loading explanations…" />}

      {G && (
        <>
          <div className="grid two">
            <Card title="Random Forest feature importance" subtitle="Impurity-based, from training (sums to 1)" icon={ScanSearch}>
              <ResponsiveContainer width="100%" height={380}>
                <BarChart data={rf} layout="vertical" margin={{ left: 120 }}>
                  <CartesianGrid {...gridProps} horizontal={false} /><XAxis type="number" {...axisProps} /><YAxis type="category" dataKey="label" {...axisProps} tick={<ShortTick />} width={190} interval={0} />
                  <Tooltip {...tooltipProps} formatter={(v) => num(v, 4)} /><Bar dataKey="v" name="importance" fill={COLORS.teal} radius={[0, 4, 4, 0]} {...anim} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title={`Permutation importance · ${G.best_model}`} subtitle="Increase in MAE (°C) on the TEST set when a feature is shuffled" icon={ScanSearch}>
              <ResponsiveContainer width="100%" height={380}>
                <BarChart data={perm} layout="vertical" margin={{ left: 120 }}>
                  <CartesianGrid {...gridProps} horizontal={false} /><XAxis type="number" {...axisProps} /><YAxis type="category" dataKey="label" {...axisProps} tick={<ShortTick />} width={190} interval={0} />
                  <Tooltip {...tooltipProps} formatter={(v) => `${num(v, 3)} °C`} />
                  <Bar dataKey="v" name="MAE increase" fill="#0f766e" radius={[0, 4, 4, 0]} {...anim}><ErrorBar dataKey="err" width={4} stroke="#e6edf7" /></Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <div className="grid two">
            <Card title="SHAP · mean absolute impact" subtitle={G.shap.method} icon={ScanSearch}>
              <ResponsiveContainer width="100%" height={380}>
                <BarChart data={shapBar} layout="vertical" margin={{ left: 120 }}>
                  <CartesianGrid {...gridProps} horizontal={false} /><XAxis type="number" unit="°C" {...axisProps} /><YAxis type="category" dataKey="label" {...axisProps} tick={<ShortTick />} width={190} interval={0} />
                  <Tooltip {...tooltipProps} formatter={(v) => `${num(v, 3)} °C`} /><Bar dataKey="v" fill={COLORS.green} radius={[0, 4, 4, 0]} {...anim} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="SHAP summary (beeswarm)" subtitle={`${G.shap.n_rows} test days · each dot is one day`} icon={ScanSearch}>
              <Swarm shap={G.shap} labels={labels} />
              <div className="legend-row"><span><span className="dot" style={{ background: "#60a5fa" }} /> low feature value</span><span><span className="dot" style={{ background: "#a78bfa" }} /> mid</span><span><span className="dot" style={{ background: "#f87171" }} /> high</span></div>
              <p className="muted small">Dots to the right raised the predicted temperature, dots to the left lowered it (°C relative to an average day).</p>
            </Card>
          </div>
        </>
      )}

      {Lc && (
        <>
          <h2 className="section-title">Why this forecast? · {city} → {Lc.prediction_date}</h2>
          <div className="grid two">
            <Card title="Individual prediction explanation" subtitle={`${Lc.model} · base ${num(Lc.base_value_c)} °C → predicted ${num(Lc.predicted_tmax_c)} °C`} icon={ScanSearch}>
              <ResponsiveContainer width="100%" height={420}>
                <BarChart data={local} layout="vertical" margin={{ left: 130 }}>
                  <CartesianGrid {...gridProps} horizontal={false} /><XAxis type="number" unit="°C" {...axisProps} /><YAxis type="category" dataKey="label" {...axisProps} tick={<ShortTick />} width={190} interval={0} />
                  <ReferenceLine x={0} stroke="#8a9bb8" />
                  <Tooltip {...tooltipProps} formatter={(v, n, p) => [`${signed(v, 2)} °C (value ${p.payload.value} ${p.payload.unit})`, "contribution"]} />
                  <Bar dataKey="contribution_c" radius={[0, 4, 4, 0]} {...anim}>{local.map((d) => <Cell key={d.feature} fill={d.contribution_c >= 0 ? COLORS.red : COLORS.blue} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
              <SourceNote>{Lc.method}. {Lc.reading_guide}</SourceNote>
            </Card>
            <div className="stack">
              <Card title="Factors increasing the predicted temperature" icon={ArrowUpRight}>
                <ul className="factors up">{Lc.increasing.slice(0, 6).map((i) => <li key={i.feature}><span>{i.label}</span><b>{signed(i.contribution_c, 2)} °C</b><small>value {i.value} {i.unit} (avg {i.baseline_value})</small></li>)}{Lc.increasing.length === 0 && <li>None</li>}</ul>
              </Card>
              <Card title="Factors decreasing the predicted temperature" icon={ArrowDownRight}>
                <ul className="factors down">{Lc.decreasing.slice(0, 6).map((i) => <li key={i.feature}><span>{i.label}</span><b>{signed(i.contribution_c, 2)} °C</b><small>value {i.value} {i.unit} (avg {i.baseline_value})</small></li>)}{Lc.decreasing.length === 0 && <li>None</li>}</ul>
              </Card>
            </div>
          </div>
        </>
      )}

      {G?.local_examples?.length > 0 && (
        <Card title="Notebook examples (test-set days)" subtitle="Local explanations saved during training" icon={ScanSearch}>
          <div className="grid three">
            {G.local_examples.map((e) => (
              <div key={e.label} className="example">
                <b>{e.label}</b><span className="muted small">{e.city} · {e.date}</span>
                <span className="small">actual {num(e.actual_c)}°C · predicted {num(e.predicted_c)}°C</span>
                <ul className="mini">{Object.entries(e.contributions).slice(0, 5).map(([f, v]) => <li key={f}><span>{name(f)}</span><b className={v >= 0 ? "pos" : "neg"}>{signed(v, 2)}</b></li>)}</ul>
              </div>
            ))}
          </div>
        </Card>
      )}
      <p className="muted small">Explanations show how the <i>model</i> uses its inputs; they are not proof of physical causation.</p>
    </>
  );
}
