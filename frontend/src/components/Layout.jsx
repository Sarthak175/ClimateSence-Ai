import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity, BrainCircuit, Cpu, FlaskConical, Globe2, LayoutDashboard, Menu, ScanSearch, SlidersHorizontal, ThermometerSun, TreePine, X,
} from "lucide-react";
import { useCity } from "../context/CityContext";
import { useApi } from "../hooks/useApi";
import { API_BASE } from "../api/client";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/live", label: "Live Monitoring", icon: Activity },
  { to: "/predictions", label: "AI Predictions", icon: BrainCircuit },
  { to: "/manual", label: "Manual Input", icon: SlidersHorizontal },
  { to: "/model-lab", label: "Model Lab", icon: FlaskConical },
  { to: "/explainability", label: "Explainable AI", icon: ScanSearch },
  { to: "/climate", label: "Climate Evidence", icon: Globe2 },
  { to: "/urban-cooling", label: "Urban Cooling", icon: TreePine },
  { to: "/prototype", label: "Prototype Lab", icon: Cpu },
];

function ApiStatus() {
  const { data, error, loading } = useApi("/health", {}, { interval: 60000 });
  let cls = "warn", text = "Connecting…";
  if (error) { cls = "bad"; text = "API offline"; }
  else if (data) {
    if (data.model?.loaded) { cls = "ok"; text = "API · model ready"; }
    else { cls = "warn"; text = "API · model missing"; }
  } else if (!loading) text = "–";
  return (
    <span className={`status-pill ${cls}`} title={data?.model?.reason || API_BASE}>
      <span className="dot" /> {text}
    </span>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { city, setCity, cities } = useCity();
  const loc = useLocation();
  const current = NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)));
  const needsCity = ["/", "/live", "/predictions", "/explainability", "/urban-cooling"].includes(current?.to);

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <span className="logo"><ThermometerSun size={20} /></span>
          <div>
            <b>ClimateSense<span className="grad"> AI</span></b>
            <small>Urban heat intelligence</small>
          </div>
          <button className="icon-btn only-mobile" onClick={() => setOpen(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        <nav>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <Icon size={17} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <p>Weather forecasts ≠ climate-change proof. Daily ML predictions describe <em>weather</em>; the Climate Evidence page shows long-term <em>climate</em> data.</p>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}

      <div className="main">
        <header className="topbar">
          <button className="icon-btn only-mobile" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
          <div className="topbar-title">{current?.label || "ClimateSense AI"}</div>
          <div className="topbar-right">
            {needsCity && (
              <label className="city-select">
                <span className="muted small">City</span>
                <select value={city} onChange={(e) => setCity(e.target.value)}>
                  {cities.map((c) => <option key={c}>{c}</option>)}
                </select>
              </label>
            )}
            <ApiStatus />
          </div>
        </header>
        <main className="content"><Outlet /></main>
        <footer className="footer">
          <span>Data: Open-Meteo · NOAA GML · NASA GISTEMP · ERA5-Land. Academic project – not an official warning service.</span>
        </footer>
      </div>
    </div>
  );
}
