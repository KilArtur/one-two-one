import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Vacancy, deleteVacancy, listVacancies } from "../api/client";
import { Breadcrumbs, EmptyState, PageHead, StatusPill } from "../layouts/Shell";

export function VacanciesPage({ token }: { token: string }) {
  const [vacancies, setVacancies] = useState<Vacancy[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState("");

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

  async function remove(id: string) {
    if (!window.confirm("Удалить вакансию и всех её кандидатов?")) return;
    setBusyId(id);
    setNotice("");
    try {
      await deleteVacancy(token, id);
      setVacancies((rows) => (rows ?? []).filter((row) => row.id !== id));
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Не удалось удалить вакансию.");
    } finally {
      setBusyId("");
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
      {notice && <p role="alert">{notice}</p>}

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
                    <Link className="title-cell" to={`/staff/vacancies/${vacancy.id}`}>
                      {vacancy.title}
                    </Link>
                    <div className="cell-sub">
                      {vacancy.topics.filter((t) => t.importance === "mandatory").length} обязательных ·{" "}
                      {vacancy.topics.filter((t) => t.skill_type === "hard").length} hard
                    </div>
                  </td>
                  <td>{vacancy.grade}</td>
                  <td>
                    <StatusPill tone={vacancy.status === "active" ? "success" : "blue"}>
                      {vacancy.status}
                    </StatusPill>
                  </td>
                  <td>{vacancy.topics.length}</td>
                  <td>v{vacancy.version}</td>
                  <td className="table-actions">
                    <div className="table-actions-inner">
                      <Link className="table-action" to={`/staff/vacancies/${vacancy.id}`}>
                        Топики
                      </Link>
                      <Link className="table-action" to={`/staff/candidates?vacancy_id=${vacancy.id}`}>
                        Кандидаты
                      </Link>
                      <Link className="table-action" to={`/staff/vacancies/${vacancy.id}/questions`}>
                        Вопросы
                      </Link>
                      <Link className="table-action" to={`/staff/vacancies/${vacancy.id}/metrics`}>
                        Метрики
                      </Link>
                      <button
                        type="button"
                        className="table-action table-action-danger"
                        disabled={busyId === vacancy.id}
                        onClick={() => void remove(vacancy.id)}
                      >
                        Удалить
                      </button>
                    </div>
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
