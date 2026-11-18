export const COLORS = {
  teal: "#2dd4bf", green: "#34d399", blue: "#60a5fa", amber: "#fbbf24", orange: "#fb923c",
  red: "#f87171", violet: "#a78bfa", muted: "#8a9bb8", grid: "rgba(148,163,184,0.12)",
};
export const CITY_COLORS = {
  Chennai: "#2dd4bf", Delhi: "#f87171", Mumbai: "#60a5fa", Bengaluru: "#34d399", Hyderabad: "#fbbf24", Kolkata: "#a78bfa",
};
export const axisProps = { stroke: "#4b5d7a", tick: { fill: "#8a9bb8", fontSize: 11 }, tickLine: false };
export const gridProps = { stroke: COLORS.grid, strokeDasharray: "3 3" };
export const tooltipProps = {
  contentStyle: { background: "#0b1830", border: "1px solid rgba(148,163,184,0.25)", borderRadius: 10, fontSize: 12, color: "#e6edf7" },
  labelStyle: { color: "#8a9bb8" },
  itemStyle: { color: "#e6edf7" },
  cursor: { stroke: "rgba(45,212,191,0.4)", fill: "rgba(148,163,184,0.08)" },
};
export const anim = { isAnimationActive: true, animationDuration: 700, animationEasing: "ease-out" };

/** Single-line axis label that is shortened with an ellipsis (full text on hover). */
export function ShortTick({ x, y, payload, text, max = 32 }) {
  const full = String(text ?? payload?.value ?? "");
  const shown = full.length > max ? `${full.slice(0, max - 1)}…` : full;
  return (
    <text x={x} y={y} dy={3} textAnchor="end" fill="#8a9bb8" fontSize={10.5}>
      <title>{full}</title>
      {shown}
    </text>
  );
}
