import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  Vacancy,
  VacancyQuestion,
  getVacancy,
  listVacancyQuestions,
} from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";

const SKILL_LABEL = { hard: "hard · техспециалист", soft: "soft · нанимающий менеджер" } as const;
const IMPORTANCE_LABEL = { mandatory: "обязательный", desired: "желательный" } as const;
const TYPE_LABEL = { core: "Ядро", personal: "Персональный", follow_up: "Уточнение" } as const;

export function VacancyDetailPage({ token, vacancyId }: { token: string; vacancyId: string }) {
  const [vacancy, setVacancy] = useState<Vacancy | null>(null);
  const [questions, setQuestions] = useState<VacancyQuestion[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setError("");
    Promise.all([
      getVacancy(token, vacancyId, controller.signal),
      listVacancyQuestions(token, vacancyId, controller.signal),
    ])
      .then(([nextVacancy, nextQuestions]) => {
        setVacancy(nextVacancy);
        setQuestions(nextQuestions);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token, vacancyId]);

  const byTopic = useMemo(() => {
    const map = new Map<string, VacancyQuestion[]>();
    for (const question of questions ?? []) {
      const rows = map.get(question.topic_id) ?? [];
      rows.push(question);
      map.set(question.topic_id, rows);
    }
    return map;
  }, [questions]);

  if (error) {
    return (
      <main>
        <p role="alert">{error}</p>
      </main>
    );
  }

  if (!vacancy || questions === null) {
    return (
      <main>
        <p role="status">Загружаем вакансию…</p>
      </main>
    );
  }

  const topics = [...vacancy.topics].sort((a, b) => a.order - b.order);

  return (
    <main>
      <Breadcrumbs
        items={[
          { label: "Команда", to: "/staff/overview" },
          { label: "Вакансии", to: "/staff/vacancies" },
          { label: vacancy.title },
        ]}
      />
      <PageHead
        eyebrow={`${vacancy.grade} · ${vacancy.status} · v${vacancy.version}`}
        title={vacancy.title}
        actions={
          <div className="inline">
            <Link className="btn ghost" to={`/staff/candidates?vacancy_id=${vacancy.id}`}>
              Кандидаты
            </Link>
            <Link className="btn ghost" to={`/staff/vacancies/${vacancy.id}/questions`}>
              Ревью вопросов
            </Link>
            <Link className="btn ghost" to={`/staff/vacancies/${vacancy.id}/metrics`}>
              Метрики
            </Link>
          </div>
        }
      />

      {vacancy.tasks && (
        <section className="band" aria-label="Задачи вакансии">
          <p className="eyebrow">Задачи</p>
          <p style={{ whiteSpace: "pre-wrap", margin: "10px 0 0" }}>{vacancy.tasks}</p>
        </section>
      )}

      <section className="section">
        <div className="section-head">
          <h2>Топики и вопросы</h2>
          <span className="section-note">{topics.length} топиков</span>
        </div>
        {topics.length === 0 ? (
          <EmptyState title="Топиков нет" text="Добавьте требования при создании или правке вакансии." />
        ) : (
          <div className="vacancy-topic-list">
            {topics.map((topic) => {
              const topicQuestions = byTopic.get(topic.id) ?? [];
              return (
                <article key={topic.id} className="vacancy-topic" aria-label={`Топик ${topic.title}`}>
                  <div className="vacancy-topic-head">
                    <div>
                      <div className="title-cell">{topic.title}</div>
                      {topic.requirement_description && (
                        <p className="cell-sub">{topic.requirement_description}</p>
                      )}
                      {topic.depth_expectations && (
                        <p className="cell-sub">Глубина: {topic.depth_expectations}</p>
                      )}
                    </div>
                    <div className="inline">
                      <StatusPill tone={topic.skill_type === "hard" ? "blue" : "success"}>
                        {SKILL_LABEL[topic.skill_type]}
                      </StatusPill>
                      <StatusPill tone={topic.importance === "mandatory" ? "warning" : "blue"}>
                        {IMPORTANCE_LABEL[topic.importance]}
                      </StatusPill>
                    </div>
                  </div>
                  {topicQuestions.length === 0 ? (
                    <p className="meta" style={{ marginTop: 14 }}>
                      Вопросов пока нет — сгенерируйте ядро на экране ревью.
                    </p>
                  ) : (
                    <ul className="vacancy-topic-questions">
                      {topicQuestions.map((question) => (
                        <li key={question.id}>
                          <div className="vacancy-q-meta">
                            {TYPE_LABEL[question.type as keyof typeof TYPE_LABEL] ?? question.type}
                            {" · "}
                            {question.pattern}
                            {" · "}
                            {question.reviewed_by_expert ? "подтверждён" : "черновик"}
                          </div>
                          <div>{question.text}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
