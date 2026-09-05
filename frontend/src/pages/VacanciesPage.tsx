import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Vacancy, generateCoreQuestions, listVacancies } from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";

export function VacanciesPage({ token }: { token: string }) {
  const [vacancies, setVacancies] = useState<Vacancy[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [generating, setGenerating] = useState<string | null>(null);
  const [questions, setQuestions] = useState<{id: string; text: string}[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    listVacancies(token, controller.signal)
      .then(setVacancies)
      .catch((reason) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Ошибка загрузки.");
        }
      });
    return () => controller.abort();
  }, [token]);

  async function generate(id: string) {
    if (generating) return;
    setGenerating(id);
    setNotice("");
    setQuestions([]);
    try {
      const questions = await generateCoreQuestions(token, id);
      setQuestions(questions);
      setNotice(`Сгенерировано вопросов: ${questions.length}`);
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Ошибка генерации.");
    } finally {
      setGenerating(null);
    }
  }

  return (
    <main>
      <Breadcrumbs items={[{ label: "Команда", to: "/staff/overview" }, { label: "Вакансии" }]} />
      <PageHead
        eyebrow="Матрица требований"
        title="Вакансии"
        actions={
          <Link className="btn primary" to="/staff/vacancies/new">
            Создать вакансию
          </Link>
        }
      />

      {error && <p role="alert">{error}</p>}
      {notice && <p className="activity-note">{notice}</p>}
      {questions.length > 0 && <section className="panel"><h2>Вопросы интервью</h2>
        <ol>{questions.map((question) => <li key={question.id}>{question.text}</li>)}</ol>
      </section>}

      {vacancies === null ? (
        <p role="status">Загружаем вакансии…</p>
      ) : vacancies.length === 0 ? (
        <EmptyState title="Пока пусто" text="Создайте вакансию хотя бы с одним топиком." />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Грейд</th>
                <th>Статус</th>
                <th>Топики</th>
                <th>Версия</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {vacancies.map((vacancy) => (
                <tr key={vacancy.id}>
                  <td>
                    <div className="title-cell">{vacancy.title}</div>
                    <div className="cell-sub">{vacancy.id}</div>
                  </td>
                  <td>{vacancy.grade}</td>
                  <td>
                    <StatusPill tone={vacancy.status === "active" ? "success" : "blue"}>
                      {vacancy.status}
                    </StatusPill>
                  </td>
                  <td>{vacancy.topics.length}</td>
                  <td>v{vacancy.version}</td>
                  <td className="inline">
                    <Link className="btn small ghost" to={`/staff/candidates?vacancy_id=${vacancy.id}`}>
                      Кандидаты
                    </Link>
                    <button type="button" className="btn small" disabled={generating !== null} onClick={() => void generate(vacancy.id)}>
                      {generating === vacancy.id ? "Генерируем вопросы…" : "Core-вопросы"}
                    </button>
                    <Link className="btn small ghost" to={`/staff/vacancies/${vacancy.id}/metrics`}>
                      Метрики
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
