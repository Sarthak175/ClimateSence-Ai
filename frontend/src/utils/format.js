export const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? "–" : Number(v).toFixed(d));
export const signed = (v, d = 1) => (v === null || v === undefined ? "–" : `${v > 0 ? "+" : ""}${Number(v).toFixed(d)}`);

export function fmtTime(iso) {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}
export const fmtClock = (d) => (d ? d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "–");
export const shortDate = (s) => {
  if (!s) return "";
  const d = new Date(s.length <= 10 ? `${s}T00:00:00` : s);
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" });
};
export const hourLabel = (s) => (s ? s.slice(11, 16) : "");
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const monthYear = (s) => {
  if (!s) return "–";
  const [y, m] = s.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
};
