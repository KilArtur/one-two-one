import { useEffect, useState } from "react";

import { CandidateOverview, listCandidates } from "../api/client";

const STATUS_LABELS: Record<string, string> = {
  not_started: "Не начато",
  recorded: "Записано",
  transcribing: "Транскрибация",
  analyzing: "Анализ",
  ready: "Готово",
  error: "Ошибка",
};

export function CandidateListPage({ token, vacancyId }: { token: string; vacancyId: string }) {
  const [candidates, setCandidates] = useState<CandidateOverview[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    listCandidates(token, vacancyId, filter || undefined, controller.signal)
      .then(setCandidates)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, vacancyId, filter]);

  if (error) return <main><p role="alert">{error}</p></main>;
  if (!candidates) return <p role="status">Загружаем кандидатов…</p>;

  return (
    <main>
      <h1>Кандидаты</h1>
      <label>
        Фильтр по статусу:{" "}
        <select value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="">Все</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
      {candidates.length === 0 ? (
        <p>Кандидатов нет.</p>
      ) : (
        <ul>
          {candidates.map((candidate) => (
            <li
              key={candidate.candidate_id}
              data-testid="candidate-row"
              data-error={candidate.processing_status === "error" ? "true" : undefined}
              style={{
                border: "1px solid",
                borderColor: candidate.processing_status === "error" ? "#b91c1c" : "#ccc",
                padding: 8,
                margin: "8px 0",
              }}
            >
              <p>
                Статус: {STATUS_LABELS[candidate.processing_status] ?? candidate.processing_status}
                {candidate.processing_status === "error" && (
                  <strong role="alert"> · требует внимания</strong>
                )}
              </p>
              <p>
                Покрытие: ✅ {candidate.confirmed_count} · ❓ {candidate.needs_check_count} · ❌{" "}
                {candidate.not_confirmed_count}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
