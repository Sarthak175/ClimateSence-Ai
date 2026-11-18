import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import LiveMonitoring from "./pages/LiveMonitoring";
import Predictions from "./pages/Predictions";
import ManualInput from "./pages/ManualInput";
import ModelLab from "./pages/ModelLab";
import Explainability from "./pages/Explainability";
import ClimateEvidence from "./pages/ClimateEvidence";
import UrbanCooling from "./pages/UrbanCooling";
import PrototypeLab from "./pages/PrototypeLab";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="live" element={<LiveMonitoring />} />
        <Route path="predictions" element={<Predictions />} />
        <Route path="manual" element={<ManualInput />} />
        <Route path="model-lab" element={<ModelLab />} />
        <Route path="explainability" element={<Explainability />} />
        <Route path="climate" element={<ClimateEvidence />} />
        <Route path="urban-cooling" element={<UrbanCooling />} />
        <Route path="prototype" element={<PrototypeLab />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
