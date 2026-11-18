import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ExternalLink, Factory, Flame, Globe2, ThermometerSun, Wind } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { Card, ErrorBox, LiveSourceBar, Loading, PageHeader, RefreshBar, SourceNote, StatCard } from "../components/ui";
import { axisProps, anim, COLORS, gridProps, tooltipProps } from "../utils/chart";
import { fmtTime, monthYear, num, signed } from "../utils/format";

const RANGES = [["All", 0], ["Last 30 y", 30], ["Last 10 y", 10]];

function SourceBlock({ s, retrieved }) {
  return (
    <div className="srcblock">
      <b>{s.name}</b>
      <span className="small muted">Source file updated: {s.source_updated || "not stated by server"} · retrieved {fmtTime(retrieved)} UTC</span>
      <span className="links">
        <a href={s.page_url} target="_blank" rel="noreferrer">Source page <ExternalLink size={11} /></a>
        <a href={s.data_url} target="_blank" rel="noreferrer">Data file <ExternalLink size={11} /></a>
      </span>
    </div>
  );
}

function GasChart({ ind, years, retrieved, color, icon }) {
  const last = ind.series[ind.series.length - 1].year;
  const data = years ? ind.series.filter((p) => p.year >= last - years) : ind.series;
  return (
    <Card title={`${ind.label} · global monthly mean`} subtitle={`Latest observation month: ${monthYear(ind.latest.date)} · unit ${ind.unit}`} icon={icon}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid {...gridProps} /><XAxis dataKey="date" {...axisProps} tickFormatter={(d) => d.slice(0, 4)} minTickGap={50} />
          <YAxis {...axisProps} width={52} domain={["dataMin - 2", "dataMax + 2"]} unit="" />
          <Tooltip {...tooltipProps} labelFormatter={monthYear} formatter={(v, n) => [`${v} ${ind.unit}`, n]} /><Legend />
          <Line type="monotone" dataKey="average" name="Monthly mean" stroke={color} dot={false} strokeWidth={1.4} {...anim} />
          <Line type="monotone" dataKey="trend" name="Deseasonalised trend" stroke="#e6edf7" dot={false} strokeWidth={2} strokeDasharray="5 3" {...anim} />
        </LineChart>
      </ResponsiveContainer>
      <SourceBlock s={ind.source} retrieved={retrieved} />
    </Card>
  );
}

export default function ClimateEvidence() {
  const { data, error, loading, updatedAt, refresh } = useApi("/climate-indicators", {}, { interval: 6 * 3600 * 1000 });
  const [range, setRange] = useState(0);
  const [trange, setTrange] = useState(0);
  const I = data?.indicators || {};
  const g = I.gistemp;
  const gm = g ? (trange ? g.monthly.filter((p) => p.year >= g.latest_month.year - trange) : g.monthly) : [];
  const ga = g ? (trange ? g.annual.filter((p) => p.year >= g.latest_month.year - trange) : g.annual) : [];
  const gseries = g ? gm.map((p) => ({ ...p })) : [];

  return (
    <>
      <PageHeader title="Global climate evidence" subtitle="Official long-term datasets: NOAA greenhouse-gas concentrations and NASA global temperature anomalies.">
        <RefreshBar updatedAt={updatedAt} onRefresh={refresh} loading={loading} note="" />
      </PageHeader>

      <LiveSourceBar updatedAt={updatedAt} attemptedAt={null} intervalMs={6 * 3600 * 1000} error={error} loading={loading} onRefresh={refresh}
        sources={Object.values(I).map((x) => ({ label: x.source?.name?.split(" (")[0] || x.label, url: x.source?.data_url })).filter((x) => x.url)} />

      <div className="notice"><Globe2 size={16} /> <span>These are <b>monthly</b> products published with a delay of weeks. They are fetched live from the official servers and cached for a few hours - they are <b>not</b> minute-by-minute measurements.</span></div>

      {error && !data && <ErrorBox error={error} onRetry={refresh} />}
      {loading && !data && !error && <Loading label="Downloading NOAA and NASA data (up to ~20 s)…" />}
      {data && Object.keys(data.errors).length > 0 && Object.entries(data.errors).map(([k, e]) => <p key={k} className="warn-text small">{k.toUpperCase()}: {e}</p>)}

      {data && (
        <>
          <div className="grid stats">
            {["co2", "ch4", "n2o"].filter((k) => I[k]).map((k, i) => (
              <StatCard key={k} label={I[k].label} icon={[Factory, Flame, Wind][i]} accent={["teal", "amber", "blue"][i]} value={num(I[k].latest.average, k === "co2" ? 2 : 1)} unit={I[k].unit}
                sub={`${monthYear(I[k].latest.date)}${I[k].latest.year_over_year_change != null ? ` · ${signed(I[k].latest.year_over_year_change, 2)} vs a year earlier` : ""}`} />
            ))}
            {g && <StatCard label="Global temperature anomaly" icon={ThermometerSun} accent="red" value={signed(g.latest_month.anomaly, 2)} unit="°C" sub={`${monthYear(g.latest_month.date)} · vs 1951–1980`} />}
          </div>

          <div className="range-row">
            <span className="muted small">Greenhouse-gas range:</span>
            {RANGES.map(([l, v]) => <button key={l} className={`chip ${range === v ? "on" : ""}`} onClick={() => setRange(v)}>{l}</button>)}
          </div>
          <div className="grid two">
            {I.co2 && <GasChart ind={I.co2} years={range} retrieved={data.retrieved_at_utc} color={COLORS.teal} icon={Factory} />}
            {I.ch4 && <GasChart ind={I.ch4} years={range} retrieved={data.retrieved_at_utc} color={COLORS.amber} icon={Flame} />}
          </div>
          {I.n2o && <div className="grid two"><GasChart ind={I.n2o} years={range} retrieved={data.retrieved_at_utc} color={COLORS.blue} icon={Wind} />
            <Card title="How to read these" icon={Globe2}>
              <p className="small">CO₂, CH₄ and N₂O are long-lived greenhouse gases. NOAA reports global averages of marine-surface measurements. The dashed line removes the seasonal cycle so the long-term rise is visible.</p>
              <p className="small">Rising concentrations are one line of evidence for human-driven climate change. This page shows the <i>data</i>; the daily temperature model on the other pages is a short-range <i>weather</i> forecast and does not test greenhouse-gas causation.</p>
            </Card></div>}

          {g && (
            <>
              <div className="range-row">
                <span className="muted small">Temperature range:</span>
                {[["1880 →", 0], ["Last 50 y", 50], ["Last 20 y", 20]].map(([l, v]) => <button key={l} className={`chip ${trange === v ? "on" : ""}`} onClick={() => setTrange(v)}>{l}</button>)}
              </div>
              <div className="grid two">
                <Card title="NASA GISTEMP · monthly anomaly" subtitle={`Latest month ${monthYear(g.latest_month.date)} · °C relative to 1951–1980`} icon={ThermometerSun}>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={gseries}>
                      <CartesianGrid {...gridProps} /><XAxis dataKey="date" {...axisProps} tickFormatter={(d) => d.slice(0, 4)} minTickGap={50} />
                      <YAxis {...axisProps} width={44} unit="°" /><ReferenceLine y={0} stroke="#8a9bb8" />
                      <Tooltip {...tooltipProps} labelFormatter={monthYear} formatter={(v) => [`${v} °C`, "anomaly"]} />
                      <Line type="monotone" dataKey="anomaly" stroke={COLORS.red} dot={false} strokeWidth={1.2} isAnimationActive animationDuration={900} />
                    </LineChart>
                  </ResponsiveContainer>
                  <SourceBlock s={g.source} retrieved={data.retrieved_at_utc} />
                </Card>
                <Card title="Annual mean anomaly" subtitle="Calendar-year average (J–D). The current year is a year-to-date mean." icon={ThermometerSun}>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={ga}>
                      <CartesianGrid {...gridProps} /><XAxis dataKey="year" {...axisProps} minTickGap={40} /><YAxis {...axisProps} width={44} unit="°" /><ReferenceLine y={0} stroke="#8a9bb8" />
                      <Tooltip {...tooltipProps} formatter={(v, n, p) => [`${v} °C${p.payload.complete ? "" : ` (year to date, ${p.payload.months_available} months)`}`, "anomaly"]} />
                      <Line type="monotone" dataKey="anomaly" stroke={COLORS.orange} strokeWidth={2} {...anim}
                        dot={(p) => (p.payload.complete ? null : <circle key={p.key} cx={p.cx} cy={p.cy} r={5} fill="none" stroke={COLORS.amber} strokeWidth={2} />)} />
                    </LineChart>
                  </ResponsiveContainer>
                  <SourceNote>{g.note}</SourceNote>
                </Card>
              </div>
            </>
          )}
          <p className="muted small">Attribution: NOAA Global Monitoring Laboratory (gml.noaa.gov) · NASA Goddard Institute for Space Studies, GISTEMP v4 (data.giss.nasa.gov/gistemp). Please cite the original providers when reusing the data.</p>
        </>
      )}
    </>
  );
}
