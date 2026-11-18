import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, ComposedChart } from "recharts";
import { Cpu, Lightbulb, Thermometer, Wifi } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { Card, ErrorBox, Loading, PageHeader, RefreshBar, StatCard } from "../components/ui";
import { axisProps, anim, COLORS, gridProps, tooltipProps } from "../utils/chart";
import { fmtTime, num, signed } from "../utils/format";

export default function PrototypeLab() {
  const { data, error, loading, updatedAt, refresh } = useApi("/sensor/latest", { limit: 300 }, { interval: 15000 });
  const rows = (data?.readings || []).map((r) => ({ ...r, t: new Date(r.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) }));
  const L = data?.latest;
  const ageMin = L ? (Date.now() - new Date(L.timestamp).getTime()) / 60000 : null;
  const online = ageMin !== null && ageMin < 5;

  return (
    <>
      <PageHeader title="Prototype Lab" subtitle="Real readings from the ESP32 + DS18B20 roof model. If no hardware is connected, nothing is shown - values are never simulated.">
        <RefreshBar updatedAt={updatedAt} onRefresh={refresh} loading={loading} note="Auto-refresh 15 s ·" />
      </PageHeader>
      {error && !data && <ErrorBox error={error} onRetry={refresh} />}
      {loading && !data && !error && <Loading />}

      {data && !data.available && (
        <Card title="No hardware readings yet" icon={Cpu}>
          <p className="small">No ESP32 has reported to this server. When your prototype is online its readings appear here automatically.</p>
          <ol className="steps small">
            <li>Build the model: two miniature buildings (dark roof vs reflective / green roof), one DS18B20 sensor on each roof, one ESP32, one low-voltage lamp.</li>
            <li>Set <code>DEVICE_TOKEN</code> on the backend and the same token in the ESP32 sketch (<code>hardware/esp32/</code>).</li>
            <li>The ESP32 sends a JSON reading to <code>POST /api/sensor/reading</code> every few seconds. See <code>docs/PROTOTYPE.md</code> for wiring, payload and safety.</li>
          </ol>
        </Card>
      )}

      {L && (
        <>
          <div className="grid stats">
            <StatCard label="Dark (conventional) roof" icon={Thermometer} accent="red" value={num(L.dark_roof_c, 2)} unit="°C" sub="DS18B20 #1" />
            <StatCard label="Reflective / green roof" icon={Thermometer} accent="teal" value={num(L.reflective_roof_c, 2)} unit="°C" sub="DS18B20 #2" />
            <StatCard label="Temperature difference" icon={Thermometer} accent="amber" value={signed(L.difference_c, 2)} unit="°C" sub="dark − reflective" />
            <StatCard label="Device" icon={Wifi} accent={online ? "green" : "red"} value={<span className="small-val">{online ? "Online" : "Offline"}</span>} sub={`${L.device_id} · last reading ${fmtTime(L.timestamp)}`} />
            {L.ambient_c != null && <StatCard label="Ambient" icon={Thermometer} accent="blue" value={num(L.ambient_c, 2)} unit="°C" />}
            {L.light_on != null && <StatCard label="Lamp" icon={Lightbulb} accent="amber" value={<span className="small-val">{L.light_on ? "On" : "Off"}</span>} />}
          </div>

          <div className="grid two">
            <Card title="Roof temperatures over time" subtitle={`${rows.length} readings stored on the server`} icon={Thermometer}>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={rows}>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="t" {...axisProps} minTickGap={40} /><YAxis {...axisProps} unit="°" width={44} domain={["dataMin - 1", "dataMax + 1"]} />
                  <Tooltip {...tooltipProps} /><Legend />
                  <Line type="monotone" dataKey="dark_roof_c" name="Dark roof °C" stroke={COLORS.red} dot={false} strokeWidth={2} {...anim} />
                  <Line type="monotone" dataKey="reflective_roof_c" name="Reflective roof °C" stroke={COLORS.teal} dot={false} strokeWidth={2} {...anim} />
                  {rows.some((r) => r.ambient_c != null) && <Line type="monotone" dataKey="ambient_c" name="Ambient °C" stroke={COLORS.muted} dot={false} strokeDasharray="4 3" {...anim} />}
                </LineChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Temperature difference (dark − reflective)" icon={Thermometer}>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={rows}>
                  <defs><linearGradient id="gd" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS.amber} stopOpacity={0.5} /><stop offset="100%" stopColor={COLORS.amber} stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid {...gridProps} /><XAxis dataKey="t" {...axisProps} minTickGap={40} /><YAxis {...axisProps} unit="°" width={44} />
                  <Tooltip {...tooltipProps} />
                  <Area type="monotone" dataKey="difference_c" name="ΔT °C" stroke={COLORS.amber} fill="url(#gd)" strokeWidth={2} {...anim} />
                </ComposedChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card title="Latest observations" icon={Cpu}>
            <div className="table-wrap"><table className="data">
              <thead><tr><th>Time</th><th>Dark roof</th><th>Reflective roof</th><th>ΔT</th><th>Ambient</th><th>Lamp</th><th>Device</th></tr></thead>
              <tbody>{[...(data.readings)].reverse().slice(0, 15).map((r) => (
                <tr key={r.timestamp + r.device_id}><td>{fmtTime(r.timestamp)}</td><td>{num(r.dark_roof_c, 2)}°C</td><td>{num(r.reflective_roof_c, 2)}°C</td><td>{signed(r.difference_c, 2)}°C</td><td>{r.ambient_c != null ? `${num(r.ambient_c, 2)}°C` : "–"}</td><td>{r.light_on == null ? "–" : r.light_on ? "on" : "off"}</td><td>{r.device_id}</td></tr>
              ))}</tbody>
            </table></div>
          </Card>
        </>
      )}
    </>
  );
}
