import { useEffect, useState } from "react";

import { getResultCard, ResultCard } from "../api/client";

const STATUS_LABEL: Record<string, string> = {
  confirmed: "✅ подтверждено",
  needs_check: "❓ требует проверки",
  not_confirmed: "❌ не подтверждено",
  out_of_scope: "вне зоны интервью",
};

const RECOMMENDATION_LABEL: Record<string, string> = {
  fit: "Подходит",
  additional_check: "Требуется дополнительная проверка",
  not_fit: "Не подходит",
};

const REASON_LABEL: Record<string, string> = {
  stop_factor: "сработал стоп-фактор",
  mandatory_not_confirmed: "есть обязательный топик со статусом «не подтверждено»",
  mandatory_needs_check: "есть обязательный топик со статусом «требует проверки»",
  all_mandatory_confirmed: "все обязательные топики подтверждены",
};

const AUTHOR_LABEL: Record<string, string> = {
  system: "система",
  technical_specialist: "техспециалист",
  hiring_manager: "нанимающий менеджер",
  recruiter: "рекрутер",
};

export function CandidateResultPage({
  token,
  candidateId,
}: {
  token: string;
  candidateId: string;
}) {
  const [card, setCard] = useState<ResultCard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getResultCard(token, candidateId, controller.signal)
      .then(setCard)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, candidateId]);

  if (error) return <main><p role="alert">{error}</p></main>;
  if (!card) return <p role="status">Загружаем карточку…</p>;

  return (
    <main>
      <h1>Карточка результата</h1>

      {/* Принцип 1: матрица топиков — первым экраном */}
      <section aria-label="Матрица топиков">
        <h2>Матрица требований (подтверждено в интервью)</h2>
        <table>
          <thead>
            <tr>
              <th>Топик</th>
              <th>Тип</th>
              <th>Важность</th>
              <th>Статус</th>
              <th>Автор</th>
            </tr>
          </thead>
          <tbody>
            {card.topics.map((row) => (
              <tr key={row.topic_id} data-testid="topic-row">
                <td>{row.topic_title}</td>
                <td>{row.skill_type === "hard" ? "hard" : "soft"}</td>
                <td>{row.importance === "mandatory" ? "обязательный" : "желательный"}</td>
                <td>{STATUS_LABEL[row.current_status] ?? row.current_status}</td>
                <td>{AUTHOR_LABEL[row.author] ?? row.author}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          Покрытие: ✅ {card.confirmed_count} · ❓ {card.needs_check_count} · ❌{" "}
          {card.not_confirmed_count}
          {card.mandatory_coverage !== null && (
            <> · обязательные: {Math.round(card.mandatory_coverage * 100)}%</>
          )}
        </p>
      </section>

      <section aria-label="Рекомендация">
        <h2>Итоговая рекомендация</h2>
        <p>
          <strong>{RECOMMENDATION_LABEL[card.recommendation] ?? card.recommendation}</strong>
        </p>
        <p>Правило Р5: {REASON_LABEL[card.recommendation_reason] ?? card.recommendation_reason}.</p>
      </section>

      {/* Принцип 3: слои резюме и интервью разведены */}
      <section aria-label="Заявлено в резюме">
        <h2>Заявлено в резюме</h2>
        <p>{card.resume_text ?? "Резюме не приложено."}</p>
      </section>
    </main>
  );
}
