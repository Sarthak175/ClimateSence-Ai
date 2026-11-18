import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from "recharts";
import { Cloud, Droplets, Gauge, Sun, Thermometer, Wind, CloudRain } from "lucide-react";
import { useCity } from "../context/CityContext";
import { useApi } from "../hooks/useApi";
import { Card, ErrorBox, LiveSourceBar, Loading, PageHeader, RefreshBar, SourceNote, StatCard } from "../components/ui";
import { axisProps, anim, CITY_COLORS, COLORS, gridProps, tooltipProps } from "../utils/chart";
import { fmtTime, hourLabel, num, shortDate } from "../utils/format";

const POLL = 5 * 60 * 1000;

export default function LiveMonitoring() {
  const { city } = useCity();
  const live = useApi("/live", { city }, { interval: POLL });
  const cmp = useApi("/compare", {}, { interval: POLL });
  const L = live.data;
  const hourly = L?.hourly.map((h) => ({ ...h, label: `${h.time.slice(8, 10)} ${hourLabel(h.time)}`, short: hourLabel(h.time) })) || [];
  const nowIdx = hourly.findIndex((h) => h.is_forecast);
  const nowLabel = nowIdx > 0 ? hourly[nowIdx - 1].label : null;
  const daily = L?.daily.map((d) => ({ ...d, label: shortDate(d.date) })) || [];
  const past = daily.filter((d) => !d.is_forecast);
  const todayLabel = daily.find((d) => d.is_today)?.label;

  const cities = cmp.data?.cities || [];
  const cmpBars = cities.map((c) => ({ city: c.city, temp: c.current.temperature_c, apparent: c.current.apparent_c }));
  const days = cities[0]?.daily.map((d) => d.date) || [];
  const cmpLines = days.map((dt, i) => Object.fromEntries([["label", shortDate(dt)], ...cities.map((c) => [c.city, c.daily[i]?.tmax_c])]));

  return (
    <>
      <PageHeader title={`${city} · Live monitoring`} subtitle="Current conditions and trends from the Open-Meteo Forecast API. Auto-refreshes every 5 minutes.">
        <RefreshBar updatedAt={live.updatedAt} onRefresh={() => { live.refresh(); cmp.refresh(); }} loading={live.loading} note="Auto-refresh 5 min ·" />
      </PageHeader>

      <LiveSourceBar updatedAt={live.updatedAt} attemptedAt={live.attemptedAt} intervalMs={POLL} error={live.error} stale={live.data?.cache?.stale}
        loading={live.loading} onRefresh={() => { live.refresh(); cmp.refresh(); }}
        sources={[{ label: `Live weather request (${city})`, url: live.data?.source?.request_url || "https://api.open-meteo.com/v1/forecast" }, { label: "Open-Meteo Forecast API docs", url: "https://open-meteo.com/en/docs" }]} />
      {live.error && !L && <ErrorBox error={live.error} onRetry={live.refresh} />}

      <Card title="Current conditions" subtitle={L ? `API timestamp ${fmtTime(L.timestamps.api_current_time_local)} (${L.timestamps.timezone}) · fetched ${fmtTime(L.timestamps.fetched_at_utc)} UTC` : ""} icon={Thermometer}>
        {!L ? <Loading /> : (
          <div className="grid stats tight">
            <StatCard label="Temperature" icon={Thermometer} value={num(L.current.temperature_c)} unit="°C" sub={`Feels like ${num(L.current.apparent_c)}°C`} />
            <StatCard label="Humidity" icon={Droplets} accent="blue" value={num(L.current.humidity_pct, 0)} unit="%" />
            <StatCard label="Wind" icon={Wind} value={num(L.current.wind_kmh)} unit="km/h" />
            <StatCard label="Pressure" icon={Gauge} accent="amber" value={num(L.current.pressure_hpa, 0)} unit="hPa" sub="surface" />
            <StatCard label="Cloud cover" icon={Cloud} accent="blue" value={num(L.current.cloud_pct, 0)} unit="%" />
            <StatCard label="Solar radiation" icon={Sun} accent="amber" value={num(L.current.solar_wm2, 0)} unit="W/m²" sub="shortwave" />
            <StatCard label="Precipitation" icon={CloudRain} accent="blue" value={num(L.current.precipitation_mm)} unit="mm" sub="current interval" />
          </div>
        )}
        <SourceNote href="https://open-meteo.com/en/docs" label="Open-Meteo docs">{L?.note}</SourceNote>
        {L?.cache?.stale && <p className="warn-text small">Upstream temporarily unavailable – showing the last successful response ({Math.round(L.cache.age_s / 60)} min old).</p>}
      </Card>

      <div className="grid two">
        <Card title="Hourly temperature" subtitle="Past 24 h + next 48 h" icon={Thermometer}>
          {!L ? <Loading /> : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={hourly}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={48} /><YAxis {...axisProps} unit="°" width={42} domain={["dataMin - 1", "dataMax + 1"]} />
                <Tooltip {...tooltipProps} />
                {nowLabel && <ReferenceLine x={nowLabel} stroke={COLORS.amber} strokeDasharray="4 3" />}
                <Line type="monotone" dataKey="temp_c" name="Temperature °C" stroke={COLORS.teal} dot={false} strokeWidth={2} {...anim} />
                <Line type="monotone" dataKey="apparent_c" name="Feels like °C" stroke={COLORS.orange} dot={false} strokeDasharray="4 3" {...anim} />
                <Legend />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Humidity trend" subtitle="Relative humidity, hourly" icon={Droplets}>
          {!L ? <Loading /> : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={hourly}>
                <defs><linearGradient id="gH" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS.blue} stopOpacity={0.5} /><stop offset="100%" stopColor={COLORS.blue} stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={48} /><YAxis {...axisProps} unit="%" width={42} domain={[0, 100]} />
                <Tooltip {...tooltipProps} />
                {nowLabel && <ReferenceLine x={nowLabel} stroke={COLORS.amber} strokeDasharray="4 3" />}
                <Area type="monotone" dataKey="humidity_pct" name="Humidity %" stroke={COLORS.blue} fill="url(#gH)" strokeWidth={2} {...anim} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <div className="grid two">
        <Card title="Hourly rainfall" subtitle="Precipitation (mm per hour)" icon={CloudRain}>
          {!L ? <Loading /> : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={hourly}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={48} /><YAxis {...axisProps} width={46} tickFormatter={(v) => `${+Number(v).toFixed(2)}`} />
                <Tooltip {...tooltipProps} />
                <Bar dataKey="precip_mm" name="Rain mm" fill={COLORS.blue} radius={[3, 3, 0, 0]} {...anim} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Wind & solar" subtitle="Hourly wind speed (km/h) and shortwave radiation (W/m²)" icon={Wind}>
          {!L ? <Loading /> : (
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={hourly}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} minTickGap={48} />
                <YAxis yAxisId="l" {...axisProps} width={38} /><YAxis yAxisId="r" orientation="right" {...axisProps} width={42} />
                <Tooltip {...tooltipProps} /><Legend />
                <Area yAxisId="r" type="monotone" dataKey="solar_wm2" name="Solar W/m²" stroke={COLORS.amber} fill={`${COLORS.amber}22`} {...anim} />
                <Line yAxisId="l" type="monotone" dataKey="wind_kmh" name="Wind km/h" stroke={COLORS.green} dot={false} strokeWidth={2} {...anim} />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <div className="grid two">
        <Card title="Seven-day temperature outlook" subtitle="Daily max / min (past 7 days + next 7 days)" icon={Thermometer}>
          {!L ? <Loading /> : (
            <ResponsiveContainer width="100%" height={270}>
              <LineChart data={daily}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} /><YAxis {...axisProps} unit="°" width={42} domain={["dataMin - 2", "dataMax + 2"]} />
                <Tooltip {...tooltipProps} /><Legend />
                {todayLabel && <ReferenceLine x={todayLabel} stroke={COLORS.amber} strokeDasharray="4 3" label={{ value: "today", fill: COLORS.amber, fontSize: 11 }} />}
                <Line type="monotone" dataKey="tmax_c" name="Max °C" stroke={COLORS.red} strokeWidth={2} {...anim} />
                <Line type="monotone" dataKey="tmin_c" name="Min °C" stroke={COLORS.blue} strokeWidth={2} {...anim} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Temperature history" subtitle="Last 7 days of daily max/min (model-derived analysis)" icon={Thermometer}>
          {!L ? <Loading /> : (
            <ResponsiveContainer width="100%" height={270}>
              <BarChart data={past}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} /><YAxis {...axisProps} unit="°" width={42} />
                <Tooltip {...tooltipProps} /><Legend />
                <Bar dataKey="tmax_c" name="Max °C" fill={COLORS.red} radius={[4, 4, 0, 0]} {...anim} />
                <Bar dataKey="tmin_c" name="Min °C" fill={COLORS.blue} radius={[4, 4, 0, 0]} {...anim} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <Card title="Daily rainfall (7 days back, 7 days ahead)" icon={CloudRain}>
        {!L ? <Loading /> : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={daily}>
              <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} /><YAxis {...axisProps} width={46} tickFormatter={(v) => `${+Number(v).toFixed(2)}`} />
              <Tooltip {...tooltipProps} />
              <Bar dataKey="precip_mm" name="Rain mm" radius={[4, 4, 0, 0]} {...anim}>
                {daily.map((d) => <Cell key={d.date} fill={d.is_forecast ? `${COLORS.blue}99` : COLORS.blue} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
        <p className="muted small">Lighter bars are forecasts.</p>
      </Card>

      <h2 className="section-title">City comparison</h2>
      {cmp.error && !cmp.data && <ErrorBox error={cmp.error} onRetry={cmp.refresh} compact />}
      <div className="grid two">
        <Card title="Current temperature by city" icon={Thermometer}>
          {!cmp.data ? <Loading /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={cmpBars}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="city" {...axisProps} /><YAxis {...axisProps} unit="°" width={42} />
                <Tooltip {...tooltipProps} /><Legend />
                <Bar dataKey="temp" name="Temperature °C" radius={[4, 4, 0, 0]} {...anim}>{cmpBars.map((c) => <Cell key={c.city} fill={CITY_COLORS[c.city]} />)}</Bar>
                <Bar dataKey="apparent" name="Feels like °C" fill="#475569" radius={[4, 4, 0, 0]} {...anim} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Daily maximum, all cities" subtitle="3 days back to 6 days ahead" icon={Thermometer}>
          {!cmp.data ? <Loading /> : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={cmpLines}>
                <CartesianGrid {...gridProps} /><XAxis dataKey="label" {...axisProps} /><YAxis {...axisProps} unit="°" width={42} domain={["dataMin - 1", "dataMax + 1"]} />
                <Tooltip {...tooltipProps} /><Legend />
                {Object.keys(CITY_COLORS).map((c) => <Line key={c} type="monotone" dataKey={c} stroke={CITY_COLORS[c]} dot={false} strokeWidth={c === city ? 3 : 1.5} {...anim} />)}
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </>
  );
}
