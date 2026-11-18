import { useEffect, useState } from "react";
import { Building2, ExternalLink, Leaf, Sun, TreePine, Umbrella, Warehouse } from "lucide-react";
import { useCity } from "../context/CityContext";
import { useApi } from "../hooks/useApi";
import { Card, HeatBadge, PageHeader, SourceNote } from "../components/ui";

const STRATEGIES = [
  { icon: Warehouse, title: "Cool roofs", what: "Roofs coated or built with high solar-reflectance, high thermal-emittance materials (white / reflective paints, tiles, membranes).",
    why: "Reflect more sunlight, so the roof surface and the rooms below stay cooler and less heat is released into the street air. Most useful on flat, sun-exposed roofs of homes, schools, warehouses and markets.",
    note: "Keep reflectivity by cleaning; avoid glare toward neighbouring buildings." },
  { icon: Leaf, title: "Green roofs", what: "Roofs with a waterproofed, root-safe growing layer and vegetation.",
    why: "Plants shade the surface and cool the air through evapotranspiration; soil adds insulation and absorbs rain. Works best where structure, water and maintenance are available.",
    note: "Needs structural check, drainage and irrigation planning; lighter 'extensive' systems suit retrofit." },
  { icon: TreePine, title: "Tree cover", what: "Street trees, avenues and urban forests, with species chosen for shade and local climate.",
    why: "Canopies block direct sun on pavements and walls and cool the air through transpiration. Shaded pedestrian routes and bus stops directly lower heat exposure.",
    note: "Plant native, drought-tolerant species and give roots enough soil volume." },
  { icon: Leaf, title: "Urban vegetation & water", what: "Parks, green corridors, vertical greenery, bioswales, lakes and fountains.",
    why: "Connected green and blue spaces create cooler 'refuge' areas and improve airflow; permeable ground reduces runoff and surface heating.",
    note: "Prefer many small, well-distributed green spaces near dense, low-income neighbourhoods." },
  { icon: Umbrella, title: "Shade structures", what: "Shade sails, pergolas, covered walkways, shaded waiting areas and market canopies.",
    why: "The fastest, cheapest way to cut radiant heat for people at bus stops, markets and playgrounds, and a good bridge until trees mature.",
    note: "Use light-coloured, ventilated materials so the structure itself does not trap heat." },
  { icon: Building2, title: "Sustainable urban development", what: "Compact, mixed-use planning; ventilation corridors; cool pavements; reflective walls; energy-efficient buildings and public transport.",
    why: "Reduces waste heat (air-conditioning exhaust, vehicles), keeps breezes flowing through the city and makes new neighbourhoods heat-resilient by design.",
    note: "Build heat criteria into building codes and master plans, and review them regularly." },
];

const TIERS = {
  Normal: { color: "#2dd4bf", now: ["Maintain tree-watering and shade-structure maintenance.", "Use this season to plan and fund cool-roof, tree-planting and shade projects before the next hot spell.", "Keep drinking water points, cool rooms and heat-health information ready."],
    plan: ["Map the city's hottest neighbourhoods (dense buildings, little vegetation).", "Adopt cool-roof and green-space standards for new buildings."] },
  Elevated: { color: "#facc15", now: ["Share a heat-awareness message: drink water, avoid strenuous outdoor work at midday.", "Open shaded rest spots and keep public water points working.", "Check on older adults, outdoor workers and people living in top-floor / tin-roof homes."],
    plan: ["Prioritise shade structures at bus stops, markets and schools.", "Start quick-win cool-roof coating on public buildings."] },
  High: { color: "#fb923c", now: ["Shift outdoor work, deliveries and sports away from the hottest hours.", "Open cooling centres / shaded halls and extend hours; put up temporary shade.", "Water-sprinkle shaded roads and busy junctions; keep hospitals alerted."],
    plan: ["Fast-track cool roofs for schools, clinics and informal-settlement homes.", "Plant shade trees along high-footfall streets and around bus stops."] },
  Severe: { color: "#ef4444", now: ["Treat as an emergency: limit outdoor work to early morning / evening, close open-air events.", "Activate heat-action-plan cooling centres, ambulance readiness and hydration stations.", "Contact vulnerable people directly; keep power supply for fans / coolers a priority."],
    plan: ["Review the heat-action plan after the event and fix the gaps.", "Scale up cool roofs, green corridors and shade as permanent infrastructure."] },
};

export default function UrbanCooling() {
  const { city } = useCity();
  const pred = useApi("/predict", { city }, { interval: 10 * 60 * 1000 });
  const live = pred.data?.heat_risk?.label;
  const [tier, setTier] = useState("Normal");
  const [manual, setManual] = useState(false);
  useEffect(() => { if (live && !manual) setTier(live); }, [live, manual]);
  const T = TIERS[tier];

  return (
    <>
      <PageHeader title="Urban heat-island reduction" subtitle="Cities are hotter than their surroundings because of heat-absorbing surfaces, little vegetation and waste heat. These measures reduce heat exposure." />

      <Card title={`Recommended actions · ${city}`} subtitle={live ? `Based on today's project-defined heat category: ${live}` : "Model forecast unavailable - choose a level to see guidance"} icon={Sun}
        right={pred.data && <HeatBadge risk={pred.data.heat_risk} />}>
        <div className="range-row">
          {Object.keys(TIERS).map((t) => (
            <button key={t} className={`chip ${tier === t ? "on" : ""}`} style={tier === t ? { borderColor: TIERS[t].color, color: TIERS[t].color } : {}} onClick={() => { setTier(t); setManual(true); }}>{t}</button>
          ))}
          {manual && live && <button className="chip" onClick={() => setManual(false)}>Use live category ({live})</button>}
        </div>
        <div className="grid two">
          <div className="tier" style={{ borderColor: `${T.color}66` }}><h4 style={{ color: T.color }}>Immediate actions</h4><ul>{T.now.map((x) => <li key={x}>{x}</li>)}</ul></div>
          <div className="tier"><h4>Planning &amp; infrastructure</h4><ul>{T.plan.map((x) => <li key={x}>{x}</li>)}</ul></div>
        </div>
        <SourceNote>Categories are project-defined from the ML forecast and the 1991–2020 climate; they are not IMD warnings. Follow official local advisories during heat waves.</SourceNote>
      </Card>

      <h2 className="section-title">Cooling strategies</h2>
      <div className="grid three">
        {STRATEGIES.map(({ icon: Icon, title, what, why, note }) => (
          <div className="strategy" key={title}>
            <span className="s-icon"><Icon size={20} /></span>
            <h3>{title}</h3>
            <p className="small"><b>What:</b> {what}</p>
            <p className="small"><b>Why it helps:</b> {why}</p>
            <p className="small muted"><b>Tip:</b> {note}</p>
          </div>
        ))}
      </div>

      <Card title="Learn more" icon={ExternalLink}>
        <ul className="linklist">
          <li><a href="https://www.epa.gov/heatislands" target="_blank" rel="noreferrer">US EPA - Heat Island Effect &amp; mitigation strategies <ExternalLink size={11} /></a></li>
          <li><a href="https://www.ipcc.ch/report/ar6/wg2/" target="_blank" rel="noreferrer">IPCC AR6 WGII - Cities, settlements and key infrastructure <ExternalLink size={11} /></a></li>
          <li><a href="https://ndma.gov.in/" target="_blank" rel="noreferrer">NDMA India - heat-wave guidelines and action plans <ExternalLink size={11} /></a></li>
        </ul>
        <p className="muted small">Effect sizes depend strongly on local conditions; this page therefore gives qualitative guidance rather than promised temperature drops. The Prototype Lab can demonstrate the roof-colour effect on a small physical model.</p>
      </Card>
    </>
  );
}
