import { Link, Route, Routes, useParams } from "react-router-dom";

import { CandidatePage } from "./pages/CandidatePage";
import { HealthPage } from "./pages/HealthPage";
import { HomePage } from "./pages/HomePage";

import { InternalSession } from "./components/InternalSession";
import { ResultLinkPage } from "./pages/ResultLinkPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { ProductMetricsPage } from "./pages/ProductMetricsPage";
import { CandidateResultPage } from "./pages/CandidateResultPage";

function ResultRoute() {
  const { candidateId } = useParams();
  return <InternalSession>{(token) => <CandidateResultPage token={token} candidateId={candidateId!} />}</InternalSession>;
}

function MetricsRoute() {
  const { vacancyId } = useParams();
  return <InternalSession>{(token) => <ProductMetricsPage token={token} vacancyId={vacancyId} />}</InternalSession>;
}

export default function App() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 720, margin: "0 auto", padding: 24 }}>
      <nav style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        <Link to="/">Главная</Link>
        <Link to="/health">Статус системы</Link>
        <Link to="/staff/metrics">Метрики</Link>
        <Link to="/staff/review">Ревью</Link>
      </nav>
      <Routes>
        <Route path="/staff/result-link" element={<InternalSession>{(token) => <ResultLinkPage token={token} />}</InternalSession>} />
        <Route path="/staff/review" element={<InternalSession>{(token) => <ReviewQueuePage token={token} />}</InternalSession>} />
        <Route path="/staff/metrics" element={<MetricsRoute />} />
        <Route path="/staff/vacancies/:vacancyId/metrics" element={<MetricsRoute />} />
        <Route path="/staff/candidates/:candidateId" element={<ResultRoute />} />
        <Route path="/interview/*" element={<CandidatePage />} />
        <Route path="/" element={<HomePage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </div>
  );
}
