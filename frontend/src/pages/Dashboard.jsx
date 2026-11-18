import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BrainCircuit, CloudRain, Droplets, Flame, Gauge, RefreshCw, Thermometer, TrendingUp, Wind } from "lucide-react";
import { useCity } from "../context/CityContext";
import { useApi } from "../hooks/useApi";
import { Card, ErrorBox, HeatBadge, LiveSourceBar, Loading, PageHeader, QualityBanner, SourceNote, StatCard } from "../components/ui";
import { axisProps, anim, COLORS, gridProps, tooltipProps } from "../utils/chart";
import { fmtTime, fmtClock, hourLabel, num, signed } from "../utils/format";

const POLL = 5 * 60 * 1000;

export default function Dashboard() {
  const { city } = useCity();
  const live = useApi("/live", { city }, { interval: POLL });
  const pred = useApi("/predict", { city }, { interval: POLL });
  const refreshAll = () => { live.refresh(); pred.refresh(); };
  const L = live.data, P = pred.data;
  const nowIdx = L?.hourly?.findIndex((h) => h.is_forecast);
  const nowLabel = nowIdx > 0 ? hourLabel(L.hourly[nowIdx - 1].time) : null;

  return (
    <>
      <PageHeader title={`${city} · Heat dashboard`} subtitle="Live conditions, tomorrow's ML forecast and how it compares with the 1991–2020 climate.">
        <div className="stamp">
          <span className="muted small">
            {L ? <>API time <b>{fmtTime(L.timestamps.api_current_time_local)}</b> · fetched {fmtClock(live.updatedAt)}{L.cache?.stale && <span className="warn-text"> · stale (upstream down)</span>}</> : "Waiting for data…"}
          </span>
          <button className="btn" onClick={refreshAll} disabled={live.loading || pred.loading}>
            <RefreshCw size={14} className={live.loading || pred.loading ? "spin" : ""} /> Refresh
          </button>
        </div>
      </PageHeader>

      <LiveSourceBar updatedAt={live.updatedAt} attemptedAt={live.attemptedAt} intervalMs={POLL} error={live.error} stale={L?.cache?.stale}
        loading={live.loading} onRefresh={refreshAll}
        sources={[{ label: `Live weather request (${city})`, url: L?.source?.request_url || "https://api.open-meteo.com/v1/forecast" }, { label: "Open-Meteo Forecast API docs", url: "https://open-meteo.com/en/docs" }]} />
      {P && <QualityBanner compact />}

      {live.error && !L && <ErrorBox error={live.error} onRetry={live.refresh} />}

      <div className="grid stats">
        <StatCard label="Current temperature" icon={Thermometer} accent="teal"
          value={L ? num(L.current.temperature_c) : "…"} unit="°C"
          sub={L ? `Feels like ${num(L.current.apparent_c)}°C · model-derived` : ""} />
        <StatCard label="Today's max / min" icon={TrendingUp} accent="amber"
          value={L?.today ? `${num(L.today.tmax_c)}° / ${num(L.today.tmin_c)}°` : "…"}
          sub="Open-Meteo daily forecast for today" />
        <StatCard label="Tomorrow's predicted max" icon={BrainCircuit} accent="green"
          value={P ? num(P.prediction.predicted_tmax_c) : pred.error ? "n/a" : "…"} unit={P ? "°C" : ""}
          sub={P ? (P.prediction.interval ? `90 % range ${num(P.prediction.interval.lower_c)}–${num(P.prediction.interval.upper_c)}°C · ${P.model.name}` : P.model.name) : pred.error ? "ML model not available" : ""} />
        <StatCard label="Temperature anomaly" icon={Flame} accent="orange"
          value={P ? signed(P.climatology.anomaly_c) : pred.error ? "n/a" : "…"} unit={P ? "°C" : ""}
          sub={P ? `vs 1991–2020 normal ${num(P.climatology.seasonal_normal_c)}°C` : ""} />
        <StatCard label="Heat-risk category" icon={Gauge} accent="red" value={P ? <HeatBadge risk={P.heat_risk} /> : pred.error ? "n/a" : "…"}
          sub="Project-defined · not an IMD warning" />
        <StatCard label="Humidity" icon={Droplets} accent="blue" value={L ? num(L.current.humidity_pct, 0) : "…"} unit="%" sub="Relative humidity, 2 m" />
        <StatCard label="Wind speed" icon={Wind} accent="teal" value={L ? num(L.current.wind_kmh) : "…"} unit="km/h" sub="10 m above ground" />
        <StatCard label="Rainfall" icon={CloudRain} accent="blue" value={L?.today ? num(L.today.precip_mm) : "…"} unit="mm"
          sub={L ? `today's total · now ${num(L.current.precipitation_mm)} mm` : ""} />
      </div>

      {pred.error && <ErrorBox error={pred.error} onRetry={pred.refresh} compact />}

      <Card title="Temperature: last 24 h and next 48 h" subtitle="Hourly 2 m air temperature and apparent temperature (Open-Meteo)" icon={Thermometer}>
        {!L ? <Loading /> : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={L.hourly.map((h) => ({ ...h, label: hourLabel(h.time) }))}>
              <defs>
                <linearGradient id="gT" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS.teal} stopOpacity={0.5} /><stop offset="100%" stopColor={COLORS.teal} stopOpacity={0} /></linearGradient>
              </defs>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="label" {...axisProps} minTickGap={48} />
              <YAxis {...axisProps} unit="°" domain={["dataMin - 2", "dataMax + 2"]} width={44} />
              <Tooltip {...tooltipProps} formatter={(v, n) => [`${v}°C`, n]} />
              {nowLabel && <ReferenceLine x={nowLabel} stroke={COLORS.amber} strokeDasharray="4 3" label={{ value: "now", fill: COLORS.amber, fontSize: 11 }} />}
              <Area type="monotone" dataKey="temp_c" name="Temperature" stroke={COLORS.teal} fill="url(#gT)" strokeWidth={2} {...anim} />
              <Area type="monotone" dataKey="apparent_c" name="Feels like" stroke={COLORS.orange} fill="none" strokeWidth={1.5} strokeDasharray="4 3" {...anim} />
            </AreaChart>
          </ResponsiveContainer>
        )}
        <SourceNote href="https://open-meteo.com/en/docs" label="Open-Meteo">{L?.note || "Open-Meteo values are model-derived, not direct station observations."}</SourceNote>
      </Card>

      {P && (
        <Card title="How to read the forecast" icon={BrainCircuit}>
          <p className="small">
            The machine-learning model ({P.model.name}) forecasts <b>{P.prediction.prediction_date}</b> using weather up to <b>{P.prediction.cutoff_date}</b>.
            Open-Meteo's own forecast for that day is {num(P.reference_nwp_forecast_tmax_c)}°C (shown for comparison only – it is not a model input).
          </p>
          {P.warnings.length > 0 && <ul className="warnlist">{P.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
          <p className="muted small">{P.disclaimer}</p>
        </Card>
      )}
    </>
  );
}
