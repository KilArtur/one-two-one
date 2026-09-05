import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ReviewItem, Vacancy, getReviewQueue, listVacancies } from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";

export function OverviewPage({ token }: { token: string }) {
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      listVacancies(token, controller.signal),
      getReviewQueue(token, controller.signal).catch(() => [] as ReviewItem[]),
    ])
      .then(([vacancyRows, reviewRows]) => {
        setVacancies(vacancyRows);
        setQueue(reviewRows);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Не удалось загрузить обзор.");
        }
      });
    return () => controller.abort();
  }, [token]);

  return (
    <main>
      <Breadcrumbs items={[{ label: "Команда" }, { label: "Обзор" }]} />
      <PageHead
        title="Обзор"
        actions={
          <Link className="btn primary" to="/staff/vacancies/new">
            Создать вакансию
          </Link>
        }
      />

      {error && <p role="alert">{error}</p>}

      <section className="section">
        <div className="section-head">
          <h2>Вакансии</h2>
          <span className="section-note">{vacancies.length} в системе</span>
        </div>
        {vacancies.length === 0 ? (
          <EmptyState title="Вакансий пока нет" text="Создайте первую матрицу требований — достаточно одного топика." />
        ) : (
          <div className="attention-list">
            {vacancies.slice(0, 6).map((vacancy) => (
              <div key={vacancy.id} className="attention-row">
                <div>
                  <p className="vacancy-kicker">{vacancy.status} · v{vacancy.version}</p>
                  <h3>{vacancy.title}</h3>
                  <p className="meta">{vacancy.topics.length} топиков · {vacancy.grade}</p>
                </div>
                <div className="attention-stats">
                  <span>
                    <b>{vacancy.topics.filter((t) => t.importance === "mandatory").length}</b>
                    обязательных
                  </span>
                  <span>
                    <b>{vacancy.topics.filter((t) => t.skill_type === "hard").length}</b>
                    hard
                  </span>
                </div>
                <Link className="btn ghost" to={`/staff/candidates?vacancy_id=${vacancy.id}`}>
                  Кандидаты
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Очередь ревью</h2>
          <Link className="btn small ghost" to="/staff/review">
            Открыть полностью
          </Link>
        </div>
        {queue.length === 0 ? (
          <EmptyState title="Спорных топиков нет" text="Когда появятся needs_check — они окажутся здесь." />
        ) : (
          <div className="attention-list">
            {queue.slice(0, 5).map((item) => (
              <div key={item.assessment_id} className="attention-row">
                <div>
                  <p className="vacancy-kicker">{item.skill_type} · {item.confidence}</p>
                  <h3>{item.topic_title}</h3>
                  <p className="meta">{item.reasoning_summary ?? "Требует экспертной проверки"}</p>
                </div>
                <StatusPill tone="warning">Требует проверки</StatusPill>
                <Link className="btn ghost" to="/staff/review">
                  В ревью
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
