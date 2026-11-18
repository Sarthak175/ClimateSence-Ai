import { num } from "../utils/format";

/** Horizontal scale: normal → +1.5 °C → P90 → P95 zones, with the prediction marker and interval. */
export default function HeatScale({ climatology, prediction, reference }) {
  if (!climatology || !prediction) return null;
  const { seasonal_normal_c: n, p90_c: p90, p95_c: p95 } = climatology;
  const elev = n + 1.5;
  const t = prediction.predicted_tmax_c;
  const lo = Math.min(n - 4, t - 2, (prediction.interval?.lower_c ?? t) - 1);
  const hi = Math.max(p95 + 3, t + 2, (prediction.interval?.upper_c ?? t) + 1);
  const pos = (v) => `${((v - lo) / (hi - lo)) * 100}%`;
  const zones = [
    { from: lo, to: Math.min(elev, p90), color: "#2dd4bf", label: "Normal" },
    { from: Math.min(elev, p90), to: p90, color: "#facc15", label: "Elevated" },
    { from: p90, to: p95, color: "#fb923c", label: "High" },
    { from: p95, to: hi, color: "#ef4444", label: "Severe" },
  ].filter((z) => z.to > z.from);
  return (
    <div className="heatscale">
      <div className="hs-track">
        {zones.map((z) => (
          <div key={z.label} className="hs-zone" style={{ left: pos(z.from), width: `${((z.to - z.from) / (hi - lo)) * 100}%`, background: `${z.color}33`, borderColor: `${z.color}88` }}>
            <span style={{ color: z.color }}>{z.label}</span>
          </div>
        ))}
        {prediction.interval && (
          <div className="hs-interval" style={{ left: pos(prediction.interval.lower_c), width: `${((prediction.interval.upper_c - prediction.interval.lower_c) / (hi - lo)) * 100}%` }} title="empirical 90 % interval" />
        )}
        <div className="hs-marker" style={{ left: pos(t) }}><b>{num(t)}°</b></div>
        {reference != null && <div className="hs-ref" style={{ left: pos(reference) }} title="Open-Meteo NWP forecast (reference)" />}
      </div>
      <div className="hs-ticks">
        <span style={{ left: pos(n) }}>normal {num(n)}°</span>
        <span style={{ left: pos(p90) }}>P90 {num(p90)}°</span>
        <span style={{ left: pos(p95), top: 16 }}>P95 {num(p95)}°</span>
      </div>
      <p className="muted small">Bar = project-defined heat categories (not IMD warnings). White band = empirical 90 % prediction interval. Small tick = Open-Meteo's own forecast, shown for reference only.</p>
    </div>
  );
}
