import { Link, Route, Routes } from "react-router-dom";

import { CandidatePage } from "./pages/CandidatePage";
import { HealthPage } from "./pages/HealthPage";
import { HomePage } from "./pages/HomePage";

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 720, margin: "0 auto", padding: 24 }}>
      <nav style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        <Link to="/">Главная</Link>
        <Link to="/health">Статус системы</Link>
      </nav>
      <Routes>
        <Route path="/interview/*" element={<CandidatePage />} />
        <Route path="/" element={<HomePage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </div>
  );
}
