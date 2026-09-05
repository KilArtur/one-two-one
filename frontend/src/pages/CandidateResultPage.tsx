import { ResultAccessPanel } from "../components/ResultAccessPanel";
import { ResultLinkContext } from "../components/ResultLinkContext";
import { useContext, useEffect, useState } from "react";

import { getResultCard, ResultCard } from "../api/client";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { EvidencePanel } from "../components/EvidencePanel";
import { Breadcrumbs, StatusPill } from "../layouts/Shell";
import {
  AUTHOR_LABEL,
  REASON_LABEL,
  RECOMMENDATION_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  coverageText,
} from "../lib/labels";

export function CandidateResultPage({
  token,
  candidateId,
  shared = false,
}: {
  token: string;
  candidateId: string;
  shared?: boolean;
}) {
  const resultLink = useContext(ResultLinkContext);
  const [access, setAccess] = useState(false);
  const [card, setCard] = useState<ResultCard | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [topic, setTopic] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getResultCard(token, candidateId, controller.signal, resultLink)
      .then(setCard)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, candidateId, resultLink]);

  if (error) {
    return (
      <main>
        <p role="alert">{error}</p>
      </main>
    );
  }
  if (!card) return <p role="status">Загружаем карточку…</p>;

  return (
    <main>
      {!shared && (
        <Breadcrumbs
          items={[
            { label: "Кандидаты", to: "/staff/candidates" },
            { label: "Результат" },
          ]}
        />
      )}

      <div className="result-hero">
        <p className="eyebrow" style={{ color: "#9d99ff" }}>
          Карточка результата
        </p>
        <h1>{RECOMMENDATION_LABEL[card.recommendation] ?? card.recommendation}</h1>
        <p>
          Правило Р5: {REASON_LABEL[card.recommendation_reason] ?? card.recommendation_reason}.
          Покрытие требований — тройка статусов, без числовой оценки.
        </p>
      </div>

      <div className="metric-strip" aria-label="Покрытие">
        <div className="metric recommendation">
          <span className="label">Рекомендация</span>
          <span className="value">{RECOMMENDATION_LABEL[card.recommendation] ?? card.recommendation}</span>
          <span className="detail">{REASON_LABEL[card.recommendation_reason] ?? card.recommendation_reason}</span>
        </div>
        <div className="metric">
          <span className="label">Подтверждено</span>
          <span className="value">{card.confirmed_count}</span>
          <span className="detail">{coverageText(card.confirmed_count, card.needs_check_count, card.not_confirmed_count)}</span>
        </div>
        <div className="metric">
          <span className="label">К проверке</span>
          <span className="value">{card.needs_check_count}</span>
          <span className="detail">needs_check</span>
        </div>
        <div className="metric">
          <span className="label">Обязательные</span>
          <span className="value">
            {card.mandatory_coverage === null ? "—" : `${Math.round(card.mandatory_coverage * 100)}%`}
          </span>
          <span className="detail">
            желательные:{" "}
            {card.desired_coverage === null ? "—" : `${Math.round(card.desired_coverage * 100)}%`}
          </span>
        </div>
      </div>

      <section className="section" aria-label="Матрица топиков">
        <div className="section-head">
          <h2>Матрица требований (подтверждено в интервью)</h2>
        </div>
        <div className="table-wrap">
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
                  <td className="title-cell">{row.topic_title}</td>
                  <td>{row.skill_type === "hard" ? "hard" : "soft"}</td>
                  <td>{row.importance === "mandatory" ? "обязательный" : "желательный"}</td>
                  <td>
                    {row.has_evidence ? (
                      <button type="button" className="btn small ghost" onClick={() => setTopic(row.topic_id)}>
                        {STATUS_LABEL[row.current_status] ?? row.current_status} — цитата и видео
                      </button>
                    ) : (
                      <StatusPill tone={STATUS_TONE[row.current_status]}>
                        {STATUS_LABEL[row.current_status] ?? row.current_status}
                      </StatusPill>
                    )}
                  </td>
                  <td>{AUTHOR_LABEL[row.author] ?? row.author}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="meta" style={{ marginTop: 12 }}>
          Покрытие: ✅ {card.confirmed_count} · ❓ {card.needs_check_count} · ❌ {card.not_confirmed_count}
          {card.mandatory_coverage !== null && (
            <> · обязательные: {Math.round(card.mandatory_coverage * 100)}%</>
          )}
        </p>
      </section>

      <section className="section" aria-label="Рекомендация">
        <div className="section-head">
          <h2>Итоговая рекомендация</h2>
        </div>
        <div className="feedback-box">
          <p>
            <strong>{RECOMMENDATION_LABEL[card.recommendation] ?? card.recommendation}</strong>
          </p>
          <p>Правило Р5: {REASON_LABEL[card.recommendation_reason] ?? card.recommendation_reason}.</p>
        </div>
      </section>

      {topic && <EvidencePanel key={topic} token={token} candidateId={candidateId} topicId={topic} />}

      <button
        type="button"
        className="btn ghost"
        aria-expanded={showTranscript}
        onClick={() => setShowTranscript((v) => !v)}
      >
        {showTranscript ? "Скрыть транскрипт" : "Открыть полный транскрипт"}
      </button>
      {showTranscript && <TranscriptPanel token={token} candidateId={candidateId} />}

      {!shared && (
        <>
          <button type="button" className="btn ghost" style={{ marginLeft: 8 }} onClick={() => setAccess((v) => !v)}>
            Ссылки и журнал просмотров
          </button>
          {access && <ResultAccessPanel token={token} candidateId={candidateId} />}
        </>
      )}

      {card.resume_text && (
        <section className="section" aria-label="Заявлено в резюме">
          <div className="section-head">
            <h2>Заявлено в резюме</h2>
          </div>
          <div className="panel">
            <p>{card.resume_text}</p>
          </div>
        </section>
      )}
    </main>
  );
}
