import { type ReactNode } from "react";
import { Link, Navigate, Route, Routes, useParams } from "react-router-dom";

import { InternalSession } from "./components/InternalSession";
import { HealthPage } from "./pages/HealthPage";
import { OverviewPage } from "./pages/OverviewPage";
import { VacanciesPage } from "./pages/VacanciesPage";
import { VacancyCreatePage } from "./pages/VacancyCreatePage";
import { StaffCandidatesPage } from "./pages/StaffCandidatesPage";
import { CandidateResultPage } from "./pages/CandidateResultPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { ProductMetricsPage } from "./pages/ProductMetricsPage";
import { ResultLinkPage } from "./pages/ResultLinkPage";
import { CandidatePage } from "./pages/CandidatePage";

function ResultRoute() {
  const { candidateId } = useParams();
  return (
    <InternalSession>
      {(token) => <CandidateResultPage token={token} candidateId={candidateId!} />}
    </InternalSession>
  );
}

function MetricsRoute() {
  const { vacancyId } = useParams();
  return (
    <InternalSession>
      {(token) => <ProductMetricsPage token={token} vacancyId={vacancyId} />}
    </InternalSession>
  );
}

function Staff({ children }: { children: (token: string) => ReactNode }) {
  return <InternalSession>{children}</InternalSession>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/staff/overview" replace />} />
      <Route path="/health" element={<HealthPage />} />
      <Route path="/interview/*" element={<CandidatePage />} />
      <Route path="/staff/result-link" element={<Staff>{(token) => <ResultLinkPage token={token} />}</Staff>} />
      <Route path="/staff/overview" element={<Staff>{(token) => <OverviewPage token={token} />}</Staff>} />
      <Route path="/staff/vacancies" element={<Staff>{(token) => <VacanciesPage token={token} />}</Staff>} />
      <Route path="/staff/vacancies/new" element={<Staff>{(token) => <VacancyCreatePage token={token} />}</Staff>} />
      <Route path="/staff/candidates" element={<Staff>{(token) => <StaffCandidatesPage token={token} />}</Staff>} />
      <Route path="/staff/candidates/:candidateId" element={<ResultRoute />} />
      <Route path="/staff/review" element={<Staff>{(token) => <ReviewQueuePage token={token} />}</Staff>} />
      <Route path="/staff/metrics" element={<MetricsRoute />} />
      <Route path="/staff/vacancies/:vacancyId/metrics" element={<MetricsRoute />} />
      <Route
        path="*"
        element={
          <main className="error-page">
            <div className="error-box">
              <p className="eyebrow">404</p>
              <h1>Страница не найдена</h1>
              <Link className="btn primary" to="/staff/overview">
                На обзор
              </Link>
            </div>
          </main>
        }
      />
    </Routes>
  );
}
