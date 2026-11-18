import axios from "axios";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export const api = axios.create({ baseURL: `${API_BASE}/api`, timeout: 60000 });

/** Convert any axios error into { code, message, status } for display. */
export function describeError(e) {
  const d = e?.response?.data?.detail;
  if (e?.response && d && typeof d === "object") {
    return { code: d.error || `http_${e.response.status}`, message: d.message || JSON.stringify(d), status: e.response.status, source: d.source };
  }
  if (e?.response) {
    return { code: `http_${e.response.status}`, message: typeof d === "string" ? d : e.message, status: e.response.status };
  }
  return {
    code: "network",
    message: `Cannot reach the ClimateSense API (${API_BASE}). If the backend runs on Render's free plan it may need 30-60 seconds to wake up - try again shortly.`,
    status: 0,
  };
}
