import { Link, Route, Routes, useParams } from "react-router-dom";

import { CandidatePage } from "./pages/CandidatePage";
import { HealthPage } from "./pages/HealthPage";
import { HomePage } from "./pages/HomePage";

import { InternalSession } from "./components/InternalSession";
import { CandidateResultPage } from "./pages/CandidateResultPage";

function ResultRoute() {
  const { candidateId } = useParams();
  return <InternalSession>{(token) => <CandidateResultPage token={token} candidateId={candidateId!} />}</InternalSession>;
}

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 720, margin: "0 auto", padding: 24 }}>
      <nav style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        <Link to="/">Главная</Link>
        <Link to="/health">Статус системы</Link>
      </nav>
      <Routes>
        <Route path="/staff/candidates/:candidateId" element={<ResultRoute />} />
        <Route path="/interview/*" element={<CandidatePage />} />
        <Route path="/" element={<HomePage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </div>
  );
}
